"""Dependency providers for API routes."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.providers.moex.client import MoexClient

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_moex(request: Request) -> MoexClient:
    """Return the MOEX client created once during application startup."""

    return request.app.state.moex


MoexDep = Annotated[MoexClient, Depends(get_moex)]
