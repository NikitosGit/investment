"""Stored portfolio snapshot endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.dashboard import DashboardPeriod
from app.schemas.snapshot import SnapshotItem, SnapshotListResponse
from app.services import snapshot_service

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("", response_model=SnapshotListResponse, summary="История снимков портфеля")
def list_snapshots(
    session: DbSession,
    period: Annotated[DashboardPeriod, Query(alias="period")] = "1Y",
) -> SnapshotListResponse:
    """Return stored daily snapshots for a period, oldest first."""

    snapshots = snapshot_service.get_snapshots(session, period)
    return SnapshotListResponse(
        period=period,
        items=[SnapshotItem.from_snapshot(snapshot) for snapshot in snapshots],
    )
