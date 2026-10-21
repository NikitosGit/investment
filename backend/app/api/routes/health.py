"""Health and service endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import AppSettings, DbSession
from app.core.time import to_local
from app.schemas.common import HealthResponse
from app.services import settings_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["service"])

_REFRESH_HEALTH = {
    settings_service.REFRESH_STATUS_OK: "ok",
    settings_service.REFRESH_STATUS_PARTIAL: "ok",
    settings_service.REFRESH_STATUS_FAILED: "error",
}


def _check_database(session: DbSession) -> bool:
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False


def _last_quote_refresh_at(session: DbSession) -> datetime | None:
    """Read the last refresh timestamp and present it in the local timezone."""

    value = settings_service.get_last_quote_refresh_at(session)
    return to_local(value) if value is not None else None


def _quote_refresh_health(session: DbSession) -> str:
    """Map the last refresh status onto the public health vocabulary."""

    status = settings_service.get_value(session, settings_service.LAST_QUOTE_REFRESH_STATUS)
    if status is None:
        return "unknown"
    return _REFRESH_HEALTH.get(status, "unknown")


@router.get("/health", response_model=HealthResponse, summary="Состояние приложения")
def health(session: DbSession, settings: AppSettings) -> HealthResponse:
    """Return application, database and quote-refresh status."""

    database_ok = _check_database(session)
    last_refresh = _last_quote_refresh_at(session) if database_ok else None
    moex_status = _quote_refresh_health(session) if database_ok else "unknown"
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        version=settings.app_version,
        database="ok" if database_ok else "error",
        moex=moex_status,
        last_quote_refresh_at=last_refresh,
    )
