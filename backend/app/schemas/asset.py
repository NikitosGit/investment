"""Asset API schemas.

Money and prices cross the API boundary as fixed-precision strings; the
constructors keep the route handlers free of formatting logic.
"""

from collections.abc import Sequence
from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints

from app.core.enums import AssetType, DataSource
from app.core.money import format_money
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.providers.moex.schemas import SecuritySearchResult
from app.schemas.common import ApiModel

Secid = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
Board = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]


class AssetSearchItem(ApiModel):
    """One security found by a MOEX search."""

    secid: str
    isin: str | None
    name: str
    short_name: str | None
    type: AssetType
    board: str
    currency: str

    @classmethod
    def from_result(cls, result: SecuritySearchResult) -> Self:
        return cls(
            secid=result.secid,
            isin=result.isin,
            name=result.name,
            short_name=result.short_name,
            type=result.type,
            board=result.board,
            currency=result.currency,
        )


class AssetListItem(ApiModel):
    """A tracked asset as shown in lists."""

    id: int
    secid: str
    isin: str | None
    name: str
    short_name: str | None
    type: AssetType
    board: str
    currency: str
    lot_size: int
    is_active: bool

    @classmethod
    def from_asset(cls, asset: Asset) -> Self:
        return cls(
            id=asset.id,
            secid=asset.secid,
            isin=asset.isin,
            name=asset.name,
            short_name=asset.short_name,
            type=asset.type,
            board=asset.board,
            currency=asset.currency,
            lot_size=asset.lot_size,
            is_active=asset.is_active,
        )


class AmortizationItem(ApiModel):
    """One amortization payment in the schedule."""

    id: int
    amortization_date: date
    amount_per_unit: str
    source: DataSource

    @classmethod
    def from_model(cls, amortization: BondAmortization) -> Self:
        return cls(
            id=amortization.id,
            amortization_date=amortization.amortization_date,
            amount_per_unit=format_money(amortization.amount_per_unit_kopecks),
            source=amortization.source,
        )


class AssetDetail(ApiModel):
    """Full asset card."""

    id: int
    secid: str
    isin: str | None
    name: str
    short_name: str | None
    type: AssetType
    board: str
    currency: str
    initial_face_value: str | None
    current_face_value: str | None
    lot_size: int
    is_active: bool
    amortizations: list[AmortizationItem] = Field(default_factory=list)

    @classmethod
    def from_asset(
        cls,
        asset: Asset,
        *,
        current_face_value_kopecks: int | None = None,
        amortizations: Sequence[BondAmortization] = (),
    ) -> Self:
        initial = asset.initial_face_value_kopecks
        return cls(
            id=asset.id,
            secid=asset.secid,
            isin=asset.isin,
            name=asset.name,
            short_name=asset.short_name,
            type=asset.type,
            board=asset.board,
            currency=asset.currency,
            initial_face_value=format_money(initial) if initial is not None else None,
            current_face_value=(
                format_money(current_face_value_kopecks)
                if current_face_value_kopecks is not None
                else None
            ),
            lot_size=asset.lot_size,
            is_active=asset.is_active,
            amortizations=[AmortizationItem.from_model(item) for item in amortizations],
        )


class AssetCreateIn(BaseModel):
    """Request body for adding a security from MOEX."""

    secid: Secid
    board: Board


class AssetListResponse(ApiModel):
    """List of tracked assets."""

    items: list[AssetListItem]


class AssetSearchResponse(ApiModel):
    """List of securities found in MOEX."""

    items: list[AssetSearchItem]
