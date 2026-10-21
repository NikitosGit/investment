"""Position endpoints."""

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.position import PositionListResponse
from app.services import position_service

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=PositionListResponse, summary="Позиции портфеля")
def list_positions(session: DbSession) -> PositionListResponse:
    """Return open positions with current prices, valuations and shares."""

    return PositionListResponse.from_views(position_service.get_positions(session))
