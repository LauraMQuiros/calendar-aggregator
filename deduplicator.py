"""Fuzzy deduplication of events by title, date, and location."""

import logging
from typing import Any

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Thresholds: 0-100, higher = stricter matching
TITLE_THRESHOLD = 80
DATE_THRESHOLD = 90
LOCATION_THRESHOLD = 75
COMBINED_WEIGHT = 0.5  # All three must pass for a match


def deduplicate(
    new_events: list[dict[str, Any]],
    existing_events: list[dict[str, Any]],
    keep: str = "first",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Filter duplicates from new_events against existing_events.

    Uses fuzzy matching on title + date + location.

    Args:
        new_events: Newly extracted events.
        existing_events: Events already in the system (from DB or other sources).
        keep: "first" = keep first occurrence, "new" = prefer new.

    Returns:
        (unique_new_events, duplicate_events)
    """
    if not existing_events:
        return new_events, []

    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []

    for candidate in new_events:
        is_dup = False
        for existing in existing_events:
            if _is_duplicate(candidate, existing):
                is_dup = True
                break
        if is_dup:
            duplicates.append(candidate)
        else:
            unique.append(candidate)

    return unique, duplicates


def _normalize(s: str | None) -> str:
    if s is None:
        return ""
    return " ".join(str(s).lower().split())


def _is_duplicate(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Check if two events are likely the same."""
    title_a = _normalize(a.get("title", ""))
    title_b = _normalize(b.get("title", ""))
    date_a = _normalize(a.get("date", ""))
    date_b = _normalize(b.get("date", ""))
    loc_a = _normalize(a.get("location", ""))
    loc_b = _normalize(b.get("location", ""))

    if not title_a or not title_b:
        return False

    title_score = fuzz.ratio(title_a, title_b)
    if title_score < TITLE_THRESHOLD:
        return False

    date_score = fuzz.ratio(date_a, date_b) if (date_a and date_b) else 100
    if date_score < DATE_THRESHOLD:
        return False

    loc_score = fuzz.ratio(loc_a, loc_b) if (loc_a and loc_b) else 100
    if loc_score < LOCATION_THRESHOLD:
        return False

    return True
