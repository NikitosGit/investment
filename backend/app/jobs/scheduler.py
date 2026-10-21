"""APScheduler setup for the daily quote refresh (plan §10)."""

import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.core.config import Settings
from app.core.time import local_now
from app.jobs.refresh import run_daily_refresh

logger = logging.getLogger(__name__)

DAILY_JOB_ID = "daily_quote_refresh"
STARTUP_JOB_ID = "startup_quote_refresh"


def create_scheduler(
    settings: Settings,
    *,
    startup_delay_seconds: int = 10,
) -> BackgroundScheduler | None:
    """Build a scheduler when automatic refresh is enabled.

    The scheduler is not started here; the lifespan owns that.
    """

    if not settings.quote_refresh_enabled:
        return None

    scheduler = BackgroundScheduler(timezone=settings.timezone)
    scheduler.add_job(
        run_daily_refresh,
        CronTrigger(
            hour=settings.quote_refresh_hour,
            minute=settings.quote_refresh_minute,
            timezone=settings.timezone,
        ),
        id=DAILY_JOB_ID,
        name="Daily quote refresh",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_refresh,
        DateTrigger(run_date=local_now() + timedelta(seconds=startup_delay_seconds)),
        id=STARTUP_JOB_ID,
        name="Startup quote refresh",
        replace_existing=True,
    )
    return scheduler


def start_scheduler(settings: Settings) -> BackgroundScheduler | None:
    """Create and start the scheduler (or return ``None`` when disabled)."""

    scheduler = create_scheduler(settings)
    if scheduler is not None:
        scheduler.start()
        logger.info("Quote refresh scheduler started (timezone=%s)", settings.timezone)
    return scheduler


def shutdown_scheduler(scheduler: BackgroundScheduler | None) -> None:
    """Stop the scheduler without waiting for running jobs."""

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("Quote refresh scheduler stopped")
