"""Dashboard endpoint."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.dashboard import DashboardPeriod, DashboardResponse
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse, summary="Дашборд портфеля")
def get_dashboard(
    session: DbSession,
    period: Annotated[DashboardPeriod, Query(alias="period")] = "1Y",
) -> DashboardResponse:
    """Return totals, open positions, the value chart and upcoming coupons."""

    return DashboardResponse.from_data(dashboard_service.get_dashboard(session, period))
