"""Recurring extraction jobs using APScheduler."""

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def create_scheduler(
    get_websites: Callable[[], list[dict]],
    run_extraction: Callable[[int, str], None],
) -> BackgroundScheduler:
    """
    Create a scheduler that runs extraction for each website on its interval.

    Args:
        get_websites: Returns list of {id, url, extraction_interval_minutes}.
        run_extraction: Called with (website_id, url) for each job.

    Returns:
        Configured BackgroundScheduler (not started).
    """
    scheduler = BackgroundScheduler()

    def job_for_website(website_id: int, url: str):
        try:
            run_extraction(website_id, url)
        except Exception as e:
            logger.exception("Extraction job failed for %s: %s", url, e)

    def refresh_jobs():
        websites = get_websites()
        for w in websites:
            wid = w.get("id")
            url = w.get("url")
            interval = w.get("extraction_interval_minutes", 60)
            if not wid or not url:
                continue
            job_id = f"website_{wid}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
            scheduler.add_job(
                job_for_website,
                trigger=IntervalTrigger(minutes=interval),
                args=[wid, url],
                id=job_id,
                replace_existing=True,
            )
        logger.info("Scheduled %d extraction jobs", len(websites))

    # Run refresh on start
    refresh_jobs()
    # Refresh job list every 5 minutes
    scheduler.add_job(refresh_jobs, trigger=IntervalTrigger(minutes=5), id="refresh_jobs")
    return scheduler
