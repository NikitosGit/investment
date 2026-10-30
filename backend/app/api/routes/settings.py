"""Settings endpoints: read and update user-changeable values (plan §8.9)."""

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.api.deps import AppSettings, DbSession
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


def _build_response(session: Session, settings: Settings) -> SettingsResponse:
    """Resolve effective values over deployment defaults and the master switch."""

    return SettingsResponse(
        quote_refresh_enabled=settings_service.effective_quote_refresh_enabled(
            session, env_enabled=settings.quote_refresh_enabled
        ),
        dashboard_period=settings_service.get_dashboard_period(session),
    )


@router.get("", response_model=SettingsResponse, summary="Получить настройки")
def read_settings(session: DbSession, settings: AppSettings) -> SettingsResponse:
    """Return effective settings."""

    return _build_response(session, settings)


@router.patch("", response_model=SettingsResponse, summary="Изменить настройки")
def update_settings(
    payload: SettingsUpdate,
    session: DbSession,
    settings: AppSettings,
) -> SettingsResponse:
    """Update only the submitted keys and return the full effective settings."""

    if payload.quote_refresh_enabled is True and not settings.quote_refresh_enabled:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Автоматическое обновление котировок отключено настройками развёртывания",
            status_code=400,
        )
    if payload.quote_refresh_enabled is not None:
        settings_service.set_quote_refresh_enabled(
            session, payload.quote_refresh_enabled, commit=False
        )
    if payload.dashboard_period is not None:
        settings_service.set_dashboard_period(session, payload.dashboard_period, commit=False)
    session.commit()
    return _build_response(session, settings)
