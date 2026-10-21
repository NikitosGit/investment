"""Quote endpoints: history, batch refresh and manual prices."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession, MoexDep
from app.schemas.quote import (
    ManualQuoteIn,
    QuoteHistoryResponse,
    QuoteItem,
    QuoteRefreshResponse,
)
from app.services import quote_service

Period = Literal["1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL"]

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get(
    "/{asset_id}/history",
    response_model=QuoteHistoryResponse,
    summary="История котировок актива",
)
def get_quote_history(
    asset_id: int,
    session: DbSession,
    period: Annotated[Period, Query(alias="period")] = "1Y",
) -> QuoteHistoryResponse:
    """Return cached prices for a period, oldest first."""

    quotes = quote_service.get_history(session, asset_id, period)
    return QuoteHistoryResponse(
        asset_id=asset_id,
        period=period,
        items=[QuoteItem.from_quote(quote) for quote in quotes],
    )


@router.post(
    "/refresh",
    response_model=QuoteRefreshResponse,
    summary="Обновить котировки всех активов",
)
def refresh_quotes(session: DbSession, client: MoexDep) -> QuoteRefreshResponse:
    """Refresh quotes and bond schedules for every active asset."""

    return QuoteRefreshResponse.from_result(quote_service.refresh_all(session, client))


@router.post(
    "/manual",
    response_model=QuoteItem,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить ручную котировку",
)
def add_manual_quote(payload: ManualQuoteIn, session: DbSession) -> QuoteItem:
    """Store a user-provided price for one date."""

    quote = quote_service.add_manual(
        session,
        asset_id=payload.asset_id,
        quote_date=payload.quote_date,
        price=payload.price,
        price_type=payload.price_type,
    )
    return QuoteItem.from_quote(quote)
