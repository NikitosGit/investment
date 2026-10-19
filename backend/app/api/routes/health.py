"""Health and service endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import AppSettings, DbSession
from app.core.time import to_local
from app.schemas.common import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["service"])


def _check_database(session: DbSession) -> bool:
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False


def _last_quote_refresh_at(session: DbSession) -> datetime | None:
    """Read the last refresh timestamp when the settings table exists."""

    try:
        row = session.execute(
            text("SELECT value FROM app_setting WHERE key = 'last_quote_refresh_at'")
        ).first()
    except SQLAlchemyError:
        return None
    if not row or not row[0]:
        return None
    try:
        return to_local(datetime.fromisoformat(str(row[0])))
    except ValueError:
        return None


@router.get("/health", response_model=HealthResponse, summary="Состояние приложения")
def health(session: DbSession, settings: AppSettings) -> HealthResponse:
    """Return application, database and quote-refresh status."""

    database_ok = _check_database(session)
    last_refresh = _last_quote_refresh_at(session) if database_ok else None
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        version=settings.app_version,
        database="ok" if database_ok else "error",
        moex="unknown",
        last_quote_refresh_at=last_refresh,
    )
