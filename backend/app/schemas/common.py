"""Shared API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Base model for API responses."""

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(ApiModel):
    """Service health information."""

    status: Literal["ok", "degraded"] = "ok"
    version: str
    database: Literal["ok", "error"]
    moex: Literal["ok", "error", "unknown"]
    last_quote_refresh_at: datetime | None = None
