"""Quote API schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import DataSource, PriceType
from app.core.money import format_price
from app.core.time import to_local
from app.db.models.quote import Quote
from app.schemas.common import ApiModel, UtcDatetime
from app.services.quote_service import RefreshResult


class QuoteItem(ApiModel):
    """One cached daily price."""

    id: int
    asset_id: int
    quote_date: date
    price: str
    price_type: PriceType
    source: DataSource
    fetched_at: UtcDatetime

    @classmethod
    def from_quote(cls, quote: Quote) -> Self:
        return cls(
            id=quote.id,
            asset_id=quote.asset_id,
            quote_date=quote.quote_date,
            price=format_price(quote.price_micro),
            price_type=quote.price_type,
            source=quote.source,
            fetched_at=quote.fetched_at,
        )


class QuoteHistoryResponse(ApiModel):
    """Price history of one asset."""

    asset_id: int
    period: str
    items: list[QuoteItem]


class QuoteRefreshErrorOut(ApiModel):
    """One asset that failed during a batch refresh."""

    asset_id: int
    secid: str
    error: str


class QuoteRefreshResponse(ApiModel):
    """Summary of a batch quote refresh.

    ``last_refresh_at`` is presented in the configured local timezone; the
    stored setting remains naive UTC.
    """

    updated: int
    failed: int
    last_refresh_at: datetime
    errors: list[QuoteRefreshErrorOut]

    @classmethod
    def from_result(cls, result: RefreshResult) -> Self:
        return cls(
            updated=result.updated,
            failed=result.failed,
            last_refresh_at=to_local(result.last_refresh_at),
            errors=[
                QuoteRefreshErrorOut(asset_id=item.asset_id, secid=item.secid, error=item.error)
                for item in result.errors
            ],
        )


class ManualQuoteIn(BaseModel):
    """Request body for a user-provided price."""

    model_config = ConfigDict(extra="forbid")

    asset_id: int
    quote_date: date
    price: Decimal = Field(gt=0, decimal_places=6)
    price_type: PriceType
