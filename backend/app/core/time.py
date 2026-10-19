"""Application-wide date and time helpers.

All timestamps persisted to the database are naive UTC values. Presentation
layer timestamps are converted to the configured local timezone.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def local_timezone() -> ZoneInfo:
    """Return the configured presentation timezone."""

    return ZoneInfo(get_settings().timezone)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(UTC)


def utc_now_naive() -> datetime:
    """Return the current UTC datetime without tzinfo, suitable for storage."""

    return utc_now().replace(tzinfo=None)


def local_now() -> datetime:
    """Return the current timezone-aware local datetime."""

    return datetime.now(local_timezone())


def today_local() -> date:
    """Return today's date in the configured timezone."""

    return local_now().date()


def to_local(value: datetime) -> datetime:
    """Convert a datetime to the configured timezone.

    Naive datetimes are treated as UTC.
    """

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(local_timezone())
