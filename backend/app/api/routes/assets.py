"""Asset endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DbSession, MoexDep
from app.schemas.asset import (
    AssetCreateIn,
    AssetDetail,
    AssetListItem,
    AssetListResponse,
    AssetSearchItem,
    AssetSearchResponse,
)
from app.services import asset_service
from app.services.asset_service import AssetCard

router = APIRouter(prefix="/assets", tags=["assets"])


def _to_detail(card: AssetCard) -> AssetDetail:
    """Convert a service card into the API response model."""

    return AssetDetail.from_asset(
        card.asset,
        current_face_value_kopecks=card.current_face_value_kopecks,
        amortizations=card.amortizations,
    )


@router.get("", response_model=AssetListResponse, summary="Локальные активы")
def list_assets(session: DbSession) -> AssetListResponse:
    """Return all tracked assets ordered by id."""

    assets = asset_service.list_assets(session)
    return AssetListResponse(items=[AssetListItem.from_asset(asset) for asset in assets])


@router.get("/search", response_model=AssetSearchResponse, summary="Поиск бумаг в MOEX")
def search_assets(
    client: MoexDep, q: Annotated[str, Query(min_length=1, max_length=64)]
) -> AssetSearchResponse:
    """Search MOEX for stocks and bonds by ticker or name."""

    results = asset_service.search_moex(client, q)
    return AssetSearchResponse(items=[AssetSearchItem.from_result(result) for result in results])


@router.post(
    "",
    response_model=AssetDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить бумагу из MOEX",
)
def create_asset(payload: AssetCreateIn, session: DbSession, client: MoexDep) -> AssetDetail:
    """Add a security from MOEX, syncing bond coupons and amortizations."""

    asset = asset_service.create_from_moex(
        session, client, secid=payload.secid, board=payload.board
    )
    return _to_detail(asset_service.get_asset_card(session, asset.id))


@router.get("/{asset_id}", response_model=AssetDetail, summary="Карточка актива")
def read_asset(asset_id: int, session: DbSession) -> AssetDetail:
    """Return the full card of a tracked asset."""

    return _to_detail(asset_service.get_asset_card(session, asset_id))


@router.post("/{asset_id}/refresh", response_model=AssetDetail, summary="Обновить данные актива")
def refresh_asset(asset_id: int, session: DbSession, client: MoexDep) -> AssetDetail:
    """Refresh asset metadata, coupons and amortizations from MOEX."""

    asset = asset_service.get_asset(session, asset_id)
    asset_service.refresh_asset(session, client, asset)
    return _to_detail(asset_service.get_asset_card(session, asset_id))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить актив")
def delete_asset(asset_id: int, session: DbSession) -> Response:
    """Delete an asset when no operations or paid incomes reference it."""

    asset_service.delete_asset(session, asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
