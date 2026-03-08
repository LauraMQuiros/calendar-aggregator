"""Website add, validate, delete operations."""

import logging
from urllib.parse import urlparse

from scraper import fetch, ScraperError

logger = logging.getLogger(__name__)


def validate_url(url: str) -> bool:
    """Check URL format is valid."""
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme in ("http", "https") and parsed.netloc)
    except Exception:
        return False


def test_connectivity(url: str, timeout: int = 10) -> tuple[bool, str | None]:
    """
    Test that the URL is reachable.

    Returns:
        (success: bool, error_message: str | None)
    """
    if not validate_url(url):
        return False, "Invalid URL format"
    try:
        fetch(url, timeout=timeout)
        return True, None
    except ScraperError as e:
        return False, str(e)


def add_website(
    url: str,
    folder_id: int | None,
    user_id: int | None,
    name: str | None = None,
    extraction_interval_minutes: int = 60,
    session=None,
) -> tuple[dict, str | None]:
    """
    Add a website to the monitoring list.

    Args:
        url: Website URL.
        folder_id: Optional folder ID.
        user_id: Optional user ID.
        name: Optional display name.
        extraction_interval_minutes: How often to scrape.
        session: SQLAlchemy session (required for DB persistence).

    Returns:
        (website_dict, error_message)
        On success: (website_dict, None)
        On failure: ({}, "error message")
    """
    ok, err = test_connectivity(url)
    if not ok:
        return {}, err or "Connectivity test failed"

    if session is None:
        return {"url": url, "name": name or url, "folder_id": folder_id, "user_id": user_id}, None

    from models import Website, WebsiteStatus

    existing = session.query(Website).filter(Website.url == url).first()
    if existing:
        return {}, "Website already in monitoring list"

    website = Website(
        url=url,
        name=name or url,
        folder_id=folder_id,
        user_id=user_id,
        status=WebsiteStatus.ACTIVE.value,
        extraction_interval_minutes=extraction_interval_minutes,
    )
    session.add(website)
    session.commit()
    session.refresh(website)
    return {
        "id": website.id,
        "url": website.url,
        "name": website.name,
        "folder_id": website.folder_id,
        "user_id": website.user_id,
        "status": website.status,
        "extraction_interval_minutes": website.extraction_interval_minutes,
    }, None


def delete_website(website_id: int, session=None) -> tuple[bool, str | None]:
    """
    Remove a website from the monitoring list.

    Returns:
        (success, error_message)
    """
    if session is None:
        return False, "Database not configured"

    from models import Website

    website = session.query(Website).filter(Website.id == website_id).first()
    if not website:
        return False, "Website not found"
    session.delete(website)
    session.commit()
    return True, None
