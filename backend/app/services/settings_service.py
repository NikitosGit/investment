"""Persistent key/value application settings.

Only user-changeable values and the quote refresh bookkeeping live here. The
settings API builds on the same helpers. Missing or malformed stored values
always fall back to a caller-provided default, so a corrupted row can never
break startup or a scheduled job.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.periods import DASHBOARD_PERIODS, DEFAULT_DASHBOARD_PERIOD
from app.db.models.setting import AppSetting

LAST_QUOTE_REFRESH_AT = "last_quote_refresh_at"
LAST_QUOTE_REFRESH_STATUS = "last_quote_refresh_status"

QUOTE_REFRESH_ENABLED = "quote_refresh_enabled"
DASHBOARD_PERIOD = "dashboard_period"

REFRESH_STATUS_OK = "ok"
REFRESH_STATUS_PARTIAL = "partial"
REFRESH_STATUS_FAILED = "failed"

_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
_FALSE_VALUES = frozenset({"false", "0", "no", "off"})


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


def all_values(session: Session) -> dict[str, str]:
    """Return every stored setting as a ``key -> value`` mapping.

    Database errors propagate: an export must not silently look like a
    database without settings. Only :func:`get_value` stays tolerant, so
    startup can survive a database that has not been migrated yet.
    """

    settings = session.scalars(select(AppSetting).order_by(AppSetting.key)).all()
    return {setting.key: setting.value for setting in settings}


def get_quote_refresh_enabled(session: Session, *, default: bool) -> bool:
    """Return the stored automatic-refresh flag, or ``default`` when unset.

    Both conventional boolean spellings (``true/false``) and the common
    ``1/0``, ``yes/no``, ``on/off`` aliases are accepted case-insensitively.
    An unrecognized value is treated as absent.
    """

    raw = get_value(session, QUOTE_REFRESH_ENABLED)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def effective_quote_refresh_enabled(session: Session, *, env_enabled: bool) -> bool:
    """Combine the deployment master switch with the stored preference.

    ``QUOTE_REFRESH_ENABLED`` is authoritative: when it is false, automatic
    refreshes are off regardless of what the database says. When it is true,
    the stored preference decides and defaults to enabled.
    """

    return env_enabled and get_quote_refresh_enabled(session, default=True)


def set_quote_refresh_enabled(session: Session, value: bool, *, commit: bool = True) -> None:
    """Store the automatic-refresh flag as ``"true"`` or ``"false"``."""

    set_value(session, QUOTE_REFRESH_ENABLED, "true" if value else "false", commit=commit)


def get_dashboard_period(session: Session, *, default: str = DEFAULT_DASHBOARD_PERIOD) -> str:
    """Return the stored dashboard period or ``default`` when unset/invalid."""

    stored = get_value(session, DASHBOARD_PERIOD)
    if stored in DASHBOARD_PERIODS:
        return stored
    return default


def set_dashboard_period(session: Session, value: str, *, commit: bool = True) -> None:
    """Store the default dashboard period, rejecting unsupported values."""

    if value not in DASHBOARD_PERIODS:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Неподдерживаемый период: {value}",
            status_code=400,
            details={"value": value},
        )
    set_value(session, DASHBOARD_PERIOD, value, commit=commit)


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
