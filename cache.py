"""Content hash cache for change detection."""

import hashlib
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class InMemoryContentCache:
    """In-memory content hash cache."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def has_changed(self, url: str, content: str) -> bool:
        """
        Check if content has changed since last time.

        Args:
            url: Page URL.
            content: Current page content (HTML or plain text).

        Returns:
            True if content changed or URL not seen before; False if unchanged.
        """
        new_hash = _hash_content(content)
        old_hash = self._cache.get(url)
        self._cache[url] = new_hash
        return old_hash is None or old_hash != new_hash


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def has_content_changed(
    url: str,
    content: str,
    get_stored_hash: Callable[[str], str | None],
    set_stored_hash: Callable[[str, str], None],
) -> bool:
    """
    Generic change detection using provided storage callbacks.

    Args:
        url: Page URL.
        content: Current page content.
        get_stored_hash: Callable that returns stored hash for URL, or None.
        set_stored_hash: Callable to store (url, hash).

    Returns:
        True if content changed or never seen; False if unchanged.
    """
    new_hash = _hash_content(content)
    old_hash = get_stored_hash(url)
    set_stored_hash(url, new_hash)
    return old_hash is None or old_hash != new_hash
