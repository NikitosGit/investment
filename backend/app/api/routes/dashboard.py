"""Dashboard endpoint."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.dashboard import DashboardPeriod, DashboardResponse
from app.services import dashboard_service, settings_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse, summary="Дашборд портфеля")
def get_dashboard(
    session: DbSession,
    period: Annotated[DashboardPeriod | None, Query(alias="period")] = None,
) -> DashboardResponse:
    """Return totals, open positions, the value chart and upcoming coupons.

    Without an explicit ``period`` the stored dashboard setting is used; it
    falls back to ``1Y`` when none is stored. An explicit query parameter
    always wins over the stored preference.
    """

    resolved_period = period or settings_service.get_dashboard_period(session)
    return DashboardResponse.from_data(dashboard_service.get_dashboard(session, resolved_period))
