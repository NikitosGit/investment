"""Daily quote refresh job.

The job owns its MOEX client and database session because it runs outside the
request lifecycle. It never raises: scheduler errors must not kill the worker.
"""

import logging

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.session import SessionLocal
from app.providers.moex.client import MoexClient
from app.services import quote_service

logger = logging.getLogger(__name__)


def run_daily_refresh() -> None:
    """Refresh all quotes and record the outcome. Never raises."""

    client: MoexClient | None = None
    try:
        settings = get_settings()
        client = MoexClient.from_settings(settings)
        with SessionLocal() as session:
            try:
                result = quote_service.refresh_all(session, client)
            except AppError as exc:
                if str(exc.code) == ErrorCode.REFRESH_IN_PROGRESS:
                    logger.warning("Quote refresh skipped: %s", exc.message)
                    return
                raise
            logger.info(
                "Quote refresh finished: updated=%s failed=%s at=%s",
                result.updated,
                result.failed,
                result.last_refresh_at.isoformat(),
            )
            for error in result.errors:
                logger.warning("Quote refresh error for %s: %s", error.secid, error.error)
    except Exception:
        logger.exception("Daily quote refresh failed")
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.exception("Failed to close the quote refresh MOEX client")
