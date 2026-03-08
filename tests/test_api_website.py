"""Test Calendar Aggregator API: add website, validate, extract, list events."""

import os
import time

# Use test DB so tests don't touch the dev database (must be set before any app import)
# File-based so all connections share the same DB
os.environ["DATABASE_URL"] = "sqlite:///./test_calendar_aggregator.db"

import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.database import init_db

# Create tables on the same engine the app uses (TestClient doesn't run startup before first request)
init_db()

HANDS2OCEAN_URL = "https://www.hands2ocean.com/"
TOTAL_STEPS = 5
PROGRESS_WIDTH = 30


def _progress_bar(step: int, total: int, label: str = "") -> str:
    filled = int(PROGRESS_WIDTH * step / total) if total else 0
    bar = "█" * filled + "░" * (PROGRESS_WIDTH - filled)
    pct = 100 * step / total if total else 0
    return f"  [{bar}] {pct:5.0f}%  {label}"


def _elapsed(start: float) -> float:
    return time.perf_counter() - start


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_api_website_flow(client: TestClient):
    """
    Flow: POST website -> GET websites -> GET validate -> POST extract -> GET events.
    Extract may return 500 if no LLM is configured (OLLAMA_MODEL, etc.).
    If the website is already in the list (e.g. from a previous run), use it instead of failing.
    """
    print("\n" + "=" * 60 + "\n  API website flow: hands2ocean.com\n" + "=" * 60 + "\n", flush=True)
    t0_total = time.perf_counter()

    # 1. POST /websites — add Hands2Ocean (or get existing)
    print(_progress_bar(1, TOTAL_STEPS, "POST /websites"), flush=True)
    add_resp = client.post(
        "/websites",
        json={"url": HANDS2OCEAN_URL, "extraction_interval_minutes": 60},
    )
    if add_resp.status_code == 400 and "already in monitoring list" in (add_resp.json().get("detail") or ""):
        print("  ℹ  Website already in list, fetching existing id ...", flush=True)
        list_resp = client.get("/websites")
        assert list_resp.status_code == 200
        websites = list_resp.json()
        match = next((w for w in websites if w["url"] == HANDS2OCEAN_URL), None)
        assert match is not None, "Website should exist but was not found in list"
        website_id = match["id"]
        print(f"  ✓ Using existing website_id={website_id}\n", flush=True)
    else:
        assert add_resp.status_code == 200, add_resp.text
        data = add_resp.json()
        assert "id" in data
        assert data["url"] == HANDS2OCEAN_URL
        website_id = data["id"]
        print(f"  ✓ Created website_id={website_id}\n", flush=True)

    # 2. GET /websites — list websites
    print(_progress_bar(2, TOTAL_STEPS, "GET /websites"), flush=True)
    list_resp = client.get("/websites")
    assert list_resp.status_code == 200
    websites = list_resp.json()
    assert isinstance(websites, list)
    ids = [w["id"] for w in websites]
    assert website_id in ids
    match = next(w for w in websites if w["id"] == website_id)
    assert match["url"] == HANDS2OCEAN_URL
    print(f"  ✓ Listed {len(websites)} website(s)\n", flush=True)

    # 3. GET /websites/{website_id}/validate
    print(_progress_bar(3, TOTAL_STEPS, f"GET /websites/{website_id}/validate"), flush=True)
    validate_resp = client.get(f"/websites/{website_id}/validate")
    assert validate_resp.status_code == 200
    validate_data = validate_resp.json()
    assert "reachable" in validate_data
    assert "error" in validate_data
    assert isinstance(validate_data["reachable"], bool)
    reachable = validate_data["reachable"]
    err = validate_data.get("error") or ""
    err_suffix = f"  error={err[:50]}..." if len(err) > 50 else (f"  {err}" if err else "")
    print(f"  ✓ reachable={reachable}{err_suffix}\n", flush=True)

    # 4. POST /websites/{website_id}/extract
    print(_progress_bar(4, TOTAL_STEPS, f"POST /websites/{website_id}/extract"), flush=True)
    t0_extract = time.perf_counter()
    extract_resp = client.post(f"/websites/{website_id}/extract")
    elapsed_extract = _elapsed(t0_extract)
    if extract_resp.status_code == 500:
        detail = (extract_resp.json().get("detail") or "") or extract_resp.text
        if "Configure a model" in str(detail) or "Ollama" in str(detail):
            print(f"  ⊘ Skipped (no LLM configured) in {elapsed_extract:.2f}s\n", flush=True)
            pytest.skip(
                "Extraction requires OLLAMA_MODEL, USE_TRANSFORMERS, OPENAI_API_KEY, or ANTHROPIC_API_KEY"
            )
        pytest.fail(f"Extract failed: {detail}")
    assert extract_resp.status_code == 200, extract_resp.text
    extract_data = extract_resp.json()
    assert "events_extracted" in extract_data
    assert "success" in extract_data
    n = extract_data.get("events_extracted", 0)
    success = extract_data.get("success", False)
    print(f"  ✓ extracted={n} success={success} in {elapsed_extract:.2f}s\n", flush=True)

    # 5. GET /events (optionally filtered by website_id)
    print(_progress_bar(TOTAL_STEPS, TOTAL_STEPS, "GET /events"), flush=True)
    events_resp = client.get("/events", params={"website_id": website_id})
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert isinstance(events, list)
    for e in events:
        assert "title" in e
        assert "date" in e
    print(f"  ✓ {len(events)} event(s) for website_id={website_id}\n", flush=True)

    total_elapsed = _elapsed(t0_total)
    print(_progress_bar(TOTAL_STEPS, TOTAL_STEPS, "Done"), flush=True)
    print(f"  ✓ test_api_website_flow passed in {total_elapsed:.2f}s\n", flush=True)
