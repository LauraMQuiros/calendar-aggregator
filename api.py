"""REST API layer."""

import logging
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from cache import InMemoryContentCache
from database import SessionLocal
from database import get_db, init_db
from models import Event, ExtractionLog, Folder, Website, WebsiteStatus
from pipeline import run_pipeline
from website_manager import add_website as wm_add_website, delete_website as wm_delete_website, test_connectivity

logger = logging.getLogger(__name__)

app = FastAPI(title="Calendar Aggregator API", version="1.0.0")

# In-memory cache for content change detection (use DB-backed cache in production)
content_cache = InMemoryContentCache()


def get_db_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# --- Pydantic schemas ---


class WebsiteCreate(BaseModel):
    url: str
    folder_id: int | None = None
    user_id: int | None = None
    name: str | None = None
    extraction_interval_minutes: int = 60


class WebsiteResponse(BaseModel):
    id: int
    url: str
    name: str | None
    folder_id: int | None
    user_id: int | None
    status: str
    extraction_interval_minutes: int
    last_checked: datetime | None

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    id: int
    title: str
    date: str | None
    start_time: str | None
    end_time: str | None
    location: str | None
    description: str | None
    source_url: str
    original_language: str | None

    class Config:
        from_attributes = True


class FolderCreate(BaseModel):
    name: str
    parent_id: int | None = None
    user_id: int | None = None


# --- DB dependency for FastAPI ---


# --- Endpoints ---


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", include_in_schema=False)
def root():
    """Redirect to API docs."""
    return RedirectResponse(url="/docs", status_code=302)


@app.post("/websites", response_model=dict)
def create_website(data: WebsiteCreate, db: Session = Depends(get_db_session)):
    """Add a website to the monitoring list."""
    result, err = wm_add_website(
        url=data.url,
        folder_id=data.folder_id,
        user_id=data.user_id,
        name=data.name,
        extraction_interval_minutes=data.extraction_interval_minutes,
        session=db,
    )
    if err:
        raise HTTPException(status_code=400, detail=err)
    # Re-fetch from DB for response
    website = db.query(Website).filter(Website.url == data.url).first()
    return {
        "id": website.id,
        "url": website.url,
        "name": website.name,
        "folder_id": website.folder_id,
        "user_id": website.user_id,
        "status": website.status,
        "extraction_interval_minutes": website.extraction_interval_minutes,
    }


@app.get("/websites", response_model=list[dict])
def list_websites(
    folder_id: int | None = None,
    user_id: int | None = None,
    db: Session = Depends(get_db_session),
):
    """List monitored websites, optionally filtered."""
    q = db.query(Website)
    if folder_id is not None:
        q = q.filter(Website.folder_id == folder_id)
    if user_id is not None:
        q = q.filter(Website.user_id == user_id)
    sites = q.all()
    return [
        {"id": w.id, "url": w.url, "name": w.name, "folder_id": w.folder_id, "user_id": w.user_id, "status": w.status}
        for w in sites
    ]


@app.delete("/websites/{website_id}")
def remove_website(website_id: int, db: Session = Depends(get_db_session)):
    """Remove a website from monitoring."""
    success, err = wm_delete_website(website_id, session=db)
    if not success:
        raise HTTPException(status_code=404, detail=err)
    return {"ok": True}


@app.get("/events", response_model=list[dict])
def list_events(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    website_id: int | None = None,
    db: Session = Depends(get_db_session),
):
    """List events, optionally filtered by month/year or website."""
    q = db.query(Event)
    if website_id is not None:
        q = q.filter(Event.website_id == website_id)
    events = q.all()
    result = []
    for e in events:
        if month and year and e.date:
            try:
                parts = e.date.split("-")
                if len(parts) >= 2:
                    ey, em = int(parts[0]), int(parts[1])
                    if ey != year or em != month:
                        continue
            except (ValueError, IndexError):
                pass
        result.append({
            "id": e.id,
            "title": e.title,
            "date": e.date,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "location": e.location,
            "description": e.description,
            "source_url": e.source_url,
            "original_language": e.original_language,
        })
    return result


@app.get("/calendar")
def get_calendar(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db_session),
):
    """Get events for a specific month (calendar view)."""
    events = db.query(Event).all()
    filtered = []
    for e in events:
        if not e.date:
            continue
        try:
            parts = e.date.split("-")
            if len(parts) >= 2:
                ey, em = int(parts[0]), int(parts[1])
                if ey == year and em == month:
                    filtered.append({
                        "id": e.id,
                        "title": e.title,
                        "date": e.date,
                        "start_time": e.start_time,
                        "end_time": e.end_time,
                        "location": e.location,
                        "description": e.description,
                        "source_url": e.source_url,
                    })
        except (ValueError, IndexError):
            pass
    return {"month": month, "year": year, "events": filtered}


@app.post("/websites/{website_id}/extract")
def trigger_extraction(website_id: int, db: Session = Depends(get_db_session)):
    """Manually trigger extraction for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    log = ExtractionLog(website_id=website_id)
    db.add(log)
    db.commit()

    def get_existing():
        with get_db() as sess:
            return [{"title": x.title, "date": x.date, "location": x.location} for x in sess.query(Event).all()]

    def save_events(evts: list[dict]):
        with get_db() as sess:
            for ev in evts:
                e = Event(
                    title=ev["title"],
                    date=ev.get("date"),
                    start_time=ev.get("time"),
                    location=ev.get("location"),
                    description=ev.get("description"),
                    source_url=ev.get("source_url", website.url),
                    website_id=website_id,
                )
                sess.add(e)
            sess.commit()

    result = run_pipeline(
        website.url,
        content_cache=content_cache,
        get_existing_events=get_existing,
        save_events=save_events,
    )
    log.completed_at = datetime.utcnow()
    log.events_extracted = result.get("events_extracted", 0)
    log.success = result.get("success", False)
    log.error_message = result.get("error")
    db.commit()

    if result.get("error") and not result.get("success"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/websites/{website_id}/validate")
def validate_website(website_id: int, db: Session = Depends(get_db_session)):
    """Test connectivity for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    ok, err = test_connectivity(website.url)
    return {"reachable": ok, "error": err}


@app.get("/folders", response_model=list[dict])
def list_folders(db: Session = Depends(get_db_session)):
    """List folders."""
    folders = db.query(Folder).all()
    return [{"id": f.id, "name": f.name, "parent_id": f.parent_id, "user_id": f.user_id} for f in folders]


@app.post("/folders", response_model=dict)
def create_folder(data: FolderCreate, db: Session = Depends(get_db_session)):
    """Create a folder."""
    folder = Folder(name=data.name, parent_id=data.parent_id, user_id=data.user_id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id, "user_id": folder.user_id}


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}
