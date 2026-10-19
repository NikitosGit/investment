"""Portfolio endpoints."""

from fastapi import APIRouter

from app.api.deps import DbSession
from app.db.models.portfolio import Portfolio
from app.schemas.portfolio import PortfolioResponse, PortfolioUpdate
from app.services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioResponse, summary="Получить портфель")
def read_portfolio(session: DbSession) -> Portfolio:
    """Return the single portfolio, creating it on first access."""

    return portfolio_service.ensure_default_portfolio(session)


@router.patch("", response_model=PortfolioResponse, summary="Переименовать портфель")
def update_portfolio(payload: PortfolioUpdate, session: DbSession) -> Portfolio:
    """Rename the single portfolio."""

    return portfolio_service.rename_portfolio(session, payload.name)
