"""Orchestrates scraper → cleaner → cache → extractor → deduplicator."""

import logging
from datetime import datetime
from typing import Any, Callable

from cache import InMemoryContentCache
from cleaner import clean
from deduplicator import deduplicate
from extractor import extract_events
from scraper import ScraperError, fetch

logger = logging.getLogger(__name__)


def run_pipeline(
    url: str,
    content_cache: InMemoryContentCache | None = None,
    get_existing_events: Callable[[], list[dict[str, Any]]] | None = None,
    save_events: Callable[[list[dict[str, Any]]], None] | None = None,
) -> dict[str, Any]:
    """
    Run full extraction pipeline for a URL.

    Args:
        url: Website URL.
        content_cache: Optional cache for change detection. If None, always extracts.
        get_existing_events: Callable returning existing events for deduplication.
        save_events: Callable to persist new events.

    Returns:
        {
            "success": bool,
            "events_extracted": int,
            "events_saved": int,
            "events_duplicates": int,
            "skipped_cached": bool,
            "error": str | None,
        }
    """
    cache = content_cache or InMemoryContentCache()
    result: dict[str, Any] = {
        "success": False,
        "events_extracted": 0,
        "events_saved": 0,
        "events_duplicates": 0,
        "skipped_cached": False,
        "error": None,
    }

    try:
        raw_html = fetch(url)
    except ScraperError as e:
        result["error"] = str(e)
        return result

    if not cache.has_changed(url, raw_html):
        result["success"] = True
        result["skipped_cached"] = True
        return result

    plain_text = clean(raw_html)
    if not plain_text or len(plain_text) < 50:
        result["success"] = True
        result["skipped_cached"] = False
        return result

    try:
        extracted = extract_events(plain_text, source_url=url)
    except Exception as e:
        result["error"] = str(e)
        return result

    result["events_extracted"] = len(extracted)

    existing = (get_existing_events or (lambda: []))()
    unique, duplicates = deduplicate(extracted, existing)
    result["events_duplicates"] = len(duplicates)

    if save_events and unique:
        save_events(unique)
    result["events_saved"] = len(unique)
    result["success"] = True
    return result
