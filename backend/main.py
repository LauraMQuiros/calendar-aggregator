"""Calendar Aggregator - main entry point."""

import logging
import uvicorn

from .api import app, content_cache
from .database import get_db, init_db
from .models import Event, Website
from .pipeline import run_pipeline
from .scheduler import create_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_websites_for_scheduler():
    with get_db() as db:
        sites = db.query(Website).filter(Website.status == "active").all()
        return [{"id": w.id, "url": w.url, "extraction_interval_minutes": w.extraction_interval_minutes} for w in sites]


def run_extraction_job(website_id: int, url: str):
    from datetime import datetime

    from .models import ExtractionLog

    def get_existing():
        with get_db() as sess:
            return [{"title": x.title, "date": x.date, "location": x.location} for x in sess.query(Event).all()]

    def save_events(evts):
        with get_db() as sess:
            for ev in evts:
                e = Event(
                    title=ev["title"],
                    date=ev.get("date"),
                    start_time=ev.get("time"),
                    location=ev.get("location"),
                    description=ev.get("description"),
                    source_url=ev.get("source_url", url),
                    website_id=website_id,
                )
                sess.add(e)
            sess.commit()

    result = run_pipeline(
        url,
        content_cache=content_cache,
        get_existing_events=get_existing,
        save_events=save_events,
    )

    with get_db() as db:
        log = ExtractionLog(
            website_id=website_id,
            completed_at=datetime.utcnow(),
            events_extracted=result.get("events_extracted", 0),
            success=result.get("success", False),
            error_message=result.get("error"),
        )
        db.add(log)
        website = db.query(Website).filter(Website.id == website_id).first()
        if website:
            website.last_checked = datetime.utcnow()
    logger.info("Extraction for %s: %s", url, result)


def run():
    init_db()
    scheduler = create_scheduler(get_websites_for_scheduler, run_extraction_job)
    scheduler.start()
    logger.info("Scheduler started")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
