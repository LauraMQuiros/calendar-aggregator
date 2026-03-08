"""Test event extraction from https://www.hands2ocean.com/"""

import json
import os
import time
from unittest.mock import patch

import pytest

from scraper import fetch, ScraperError
from cleaner import clean
from pipeline import run_pipeline

HANDS2OCEAN_URL = "https://www.hands2ocean.com/"
TOTAL_STEPS = 5

# Progress bar width and helpers
PROGRESS_WIDTH = 30


def _progress_bar(step: int, total: int, label: str = "") -> str:
    filled = int(PROGRESS_WIDTH * step / total) if total else 0
    bar = "█" * filled + "░" * (PROGRESS_WIDTH - filled)
    pct = 100 * step / total if total else 0
    return f"  [{bar}] {pct:5.0f}%  {label}"


def _timed(label: str):
    """Context manager that prints elapsed time."""
    start = time.perf_counter()
    print(f"  ⏱  {label} ...", flush=True)
    return start


def _elapsed(start: float) -> float:
    return time.perf_counter() - start


@pytest.fixture(scope="module")
def hands2ocean_html():
    """Cache fetched HTML for the whole test run (avoids re-downloading every test)."""
    print("\n" + _progress_bar(0, TOTAL_STEPS, "Fetching page") + "\n", flush=True)
    t0 = time.perf_counter()
    html = fetch(HANDS2OCEAN_URL)
    print(f"  ✓ Fetched in {time.perf_counter() - t0:.2f}s ({len(html):,} chars)\n", flush=True)
    return html


class TestScraper:
    """Test fetching the Hands2Ocean page."""

    def test_fetch_returns_html(self, hands2ocean_html):
        print(_progress_bar(1, TOTAL_STEPS, "TestScraper: fetch"), flush=True)
        t0 = _timed("Checking HTML structure")
        html = hands2ocean_html
        assert isinstance(html, str)
        assert len(html) > 1000
        assert "Hands2Ocean" in html or "hands2ocean" in html.lower()
        assert "evenemang" in html.lower() or "event" in html.lower()
        print(f"  ✓ Done in {_elapsed(t0):.2f}s\n", flush=True)


@pytest.fixture(scope="module")
def cleaned_text(hands2ocean_html):
    """Clean HTML once for the whole test run (avoids re-cleaning in every test)."""
    t0 = time.perf_counter()
    text = clean(hands2ocean_html)
    print(f"  ✓ Cleaned in {time.perf_counter() - t0:.2f}s ({len(text):,} chars)\n", flush=True)
    return text


class TestCleaner:
    """Test cleaning Hands2Ocean HTML."""

    def test_clean_produces_plain_text(self, cleaned_text):
        print(_progress_bar(2, TOTAL_STEPS, "TestCleaner: plain text"), flush=True)
        assert isinstance(cleaned_text, str)
        assert len(cleaned_text) > 200
        assert "dyk" in cleaned_text.lower() or "volontär" in cleaned_text.lower() or "mars" in cleaned_text.lower()
        print("  ✓ Assertions passed\n", flush=True)

    def test_cleaned_text_includes_kommande_evenemang(self, cleaned_text):
        """Verify the upcoming events section is preserved in cleaned text."""
        print(_progress_bar(2, TOTAL_STEPS, "TestCleaner: Kommande evenemang"), flush=True)
        assert "Kommande evenemang" in cleaned_text
        print("  ✓ Done\n", flush=True)


class TestFullPipeline:
    """End-to-end: scrape, clean, extract events from Hands2Ocean."""

    @pytest.mark.skipif(
        not os.environ.get("OLLAMA_MODEL")
        and not os.environ.get("USE_TRANSFORMERS")
        and not os.environ.get("OPENAI_API_KEY")
        and not os.environ.get("ANTHROPIC_API_KEY"),
        reason="Set OLLAMA_MODEL, USE_TRANSFORMERS, OPENAI_API_KEY, or ANTHROPIC_API_KEY to run extraction",
    )
    def test_pipeline_extracts_events(self, hands2ocean_html):
        """Full pipeline (scraper → cleaner → extractor → dedup); uses cached HTML to avoid re-fetch."""
        extracted_events: list = []
        print(_progress_bar(3, TOTAL_STEPS, "Full pipeline: starting"), flush=True)

        def capture_and_print(events):
            extracted_events.extend(events)
            print("\n" + "=" * 60 + "\nExtracted events from hands2ocean.com:\n" + "=" * 60, flush=True)
            if not events:
                print("  (no new events saved — all duplicates or none extracted)\n", flush=True)
                return
            for i, ev in enumerate(events, 1):
                print(f"\n--- Event {i} ---", flush=True)
                print(json.dumps(ev, indent=2, ensure_ascii=False), flush=True)
            print("=" * 60 + f"\nTotal: {len(events)} events\n", flush=True)

        def mock_fetch(url, **kwargs):
            if url == HANDS2OCEAN_URL:
                return hands2ocean_html
            return fetch(url, **kwargs)

        print("  ⏱  Running pipeline (fetch → clean → extract → dedup) ...", flush=True)
        t0 = time.perf_counter()
        with patch("pipeline.fetch", side_effect=mock_fetch):
            result = run_pipeline(
                HANDS2OCEAN_URL,
                content_cache=None,
                get_existing_events=lambda: [],
                save_events=capture_and_print,
            )
        elapsed = time.perf_counter() - t0

        # Always print pipeline summary so failures are visible (not silent)
        n_extracted = result.get("events_extracted", 0)
        n_saved = result.get("events_saved", 0)
        n_dupes = result.get("events_duplicates", 0)
        skipped = result.get("skipped_cached", False)
        err = result.get("error") or ""
        print(f"  ✓ Pipeline finished in {elapsed:.2f}s  [extracted={n_extracted}, saved={n_saved}, duplicates={n_dupes}, skipped_cached={skipped}]", flush=True)
        if err:
            print(f"  ⚠ error: {err}", flush=True)
        if n_extracted > 0 and n_saved == 0:
            print("  ℹ All extracted events were duplicates (none new to save).", flush=True)
        if skipped and n_extracted == 0:
            print("  ℹ Pipeline skipped LLM (cached content unchanged).", flush=True)
        print(_progress_bar(4, TOTAL_STEPS, f"Pipeline done ({elapsed:.1f}s)"), flush=True)

        _unreachable = ("connection", "refused", "connect", "timed out", "timeout")
        if not result["success"] and any(w in err.lower() for w in _unreachable):
            pytest.skip(f"Ollama/LLM not reachable or timed out ({err}). Run: ollama serve && ollama pull llama3.2")

        assert result["success"] is True, (
            f"Pipeline reported success=False. error={result.get('error')!r} "
            f"extracted={n_extracted} saved={n_saved} skipped_cached={skipped}"
        )
        assert n_extracted >= 1, (
            f"Expected at least one extracted event. extracted={n_extracted} saved={n_saved} "
            f"skipped_cached={skipped} error={result.get('error')!r}"
        )
        print(_progress_bar(TOTAL_STEPS, TOTAL_STEPS, "All assertions passed"), flush=True)
        print(f"  ✓ test_pipeline_extracts_events passed in {elapsed:.2f}s\n", flush=True)


def test_hands2ocean_smoke(cleaned_text):
    """Smoke test: scraper + cleaner work without LLM (no API key needed)."""
    print(_progress_bar(TOTAL_STEPS, TOTAL_STEPS, "Smoke test"), flush=True)
    assert len(cleaned_text) > 100
    assert "Hands2Ocean" in cleaned_text or "hands2ocean" in cleaned_text.lower()
    print("  ✓ Smoke test passed\n", flush=True)