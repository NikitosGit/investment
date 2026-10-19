"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app import __version__


class Settings(BaseSettings):
    """Runtime settings for the backend.

    Values are read from the process environment and, when present, from the
    ``.env`` file in the current working directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "test", "prod"] = "local"
    app_version: str = __version__

    database_url: str = "sqlite:///./data/investments.db"
    data_dir: Path = Path("./data")
    backup_dir: Path = Path("./data/backups")

    moex_base_url: str = "https://iss.moex.com/iss"
    moex_timeout_seconds: float = Field(default=10.0, gt=0)
    moex_retries: int = Field(default=3, ge=1, le=10)
    moex_user_agent: str = "investment-tracker/0.1"

    quote_refresh_enabled: bool = True
    quote_refresh_hour: int = Field(default=19, ge=0, le=23)
    quote_refresh_minute: int = Field(default=5, ge=0, le=59)
    timezone: str = "Europe/Moscow"

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:4200", "http://127.0.0.1:4200"]
    )
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
