"""Cleans raw HTML to plain text suitable for LLM extraction."""

import logging

import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def clean(html: str, full_page: bool = True) -> str:
    """
    Extract plain text from HTML for LLM event extraction.

    Args:
        html: Raw HTML string.
        full_page: If True (default), extract the entire page including event lists,
            buttons, and all sections. If False, use article-focused extraction.

    Returns:
        Cleaned plain text.
    """
    if not html or not html.strip():
        return ""

    if full_page:
        # Maximize recall: get all text including event lists, buttons, and every section
        return _extract_full_page(html)
    return _extract_article(html)


def _extract_full_page(html: str) -> str:
    """
    Extract the entire page - all text, buttons, event lists, regardless of layout.
    Removes only scripts/styles; preserves nav, footer, and all content blocks.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove only non-content: scripts, styles, SVGs (icons)
    for tag in soup.find_all(["script", "style", "noscript", "svg"]):
        tag.decompose()

    body = soup.find("body") or soup
    text = body.get_text(separator="\n", strip=True)

    # Collapse excessive blank lines, keep structure
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _extract_article(html: str) -> str:
    """Article-focused extraction (for non-event pages)."""
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        favor_recall=True,
    )
    if not text or len(text.strip()) < 50:
        text = _extract_with_bs4(html)
    return (text or "").strip()


def _extract_with_bs4(html: str) -> str:
    """Fallback: extract main content using BeautifulSoup."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()
    main = soup.find(["main", "article"]) or soup.find(
        "div", class_=lambda c: c and ("content" in str(c).lower() or "main" in str(c).lower())
    )
    if main:
        return main.get_text(separator="\n", strip=True)
    body = soup.find("body")
    if body:
        return body.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)
