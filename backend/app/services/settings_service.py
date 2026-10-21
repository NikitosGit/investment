"""Minimal persistent key/value settings.

Only the keys needed by the quote refresh job and health endpoint live here.
The settings API arrives in a later stage and will build on the same helpers.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.setting import AppSetting

LAST_QUOTE_REFRESH_AT = "last_quote_refresh_at"
LAST_QUOTE_REFRESH_STATUS = "last_quote_refresh_status"

REFRESH_STATUS_OK = "ok"
REFRESH_STATUS_PARTIAL = "partial"
REFRESH_STATUS_FAILED = "failed"


def get_value(session: Session, key: str) -> str | None:
    """Return a stored value, or ``None`` when the key/table is absent."""

    try:
        return session.scalar(select(AppSetting.value).where(AppSetting.key == key))
    except SQLAlchemyError:
        return None


def set_value(session: Session, key: str, value: str, *, commit: bool = True) -> None:
    """Insert or update a setting and optionally commit the transaction."""

    setting = session.get(AppSetting, key)
    if setting is None:
        session.add(AppSetting(key=key, value=value))
    else:
        setting.value = value
    session.flush()
    if commit:
        session.commit()


def get_last_quote_refresh_at(session: Session) -> datetime | None:
    """Return the last refresh timestamp as naive UTC, or ``None``."""

    raw = get_value(session, LAST_QUOTE_REFRESH_AT)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return _naive_utc(parsed)


def set_last_quote_refresh(
    session: Session,
    at: datetime,
    status: str,
    *,
    commit: bool = True,
) -> None:
    """Store the timestamp and status of the last quote refresh."""

    set_value(
        session,
        LAST_QUOTE_REFRESH_AT,
        _naive_utc(at).isoformat(),
        commit=False,
    )
    set_value(session, LAST_QUOTE_REFRESH_STATUS, status, commit=commit)


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
