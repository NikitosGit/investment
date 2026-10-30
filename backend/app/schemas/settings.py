"""Settings API schemas (plan §8.9)."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.common import ApiModel
from app.schemas.dashboard import DashboardPeriod


class SettingsResponse(ApiModel):
    """Effective application settings."""

    quote_refresh_enabled: bool
    dashboard_period: DashboardPeriod


class SettingsUpdate(BaseModel):
    """Request body for a partial settings update."""

    model_config = ConfigDict(extra="forbid")

    quote_refresh_enabled: bool | None = None
    dashboard_period: DashboardPeriod | None = None

    @model_validator(mode="after")
    def _require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Нужно передать хотя бы одно поле")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"Поле {field} не может быть null")
        return self
