"""Shared API schemas."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer


class ApiModel(BaseModel):
    """Base model for API responses."""

    model_config = ConfigDict(from_attributes=True)


def _as_utc(value: datetime) -> datetime:
    """Interpret naive datetimes as UTC and normalize to UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDatetime = Annotated[
    datetime,
    PlainSerializer(_as_utc, return_type=datetime, when_used="json"),
]
"""A datetime stored as naive UTC, serialized as timezone-aware ISO 8601."""


class HealthResponse(ApiModel):
    """Service health information."""

    status: Literal["ok", "degraded"] = "ok"
    version: str
    database: Literal["ok", "error"]
    moex: Literal["ok", "error", "unknown"]
    last_quote_refresh_at: datetime | None = None
