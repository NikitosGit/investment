"""Position API schemas (plan §8.5)."""

from collections.abc import Sequence
from datetime import date
from typing import Self

from app.core.enums import AssetType, PriceType
from app.core.money import format_money, format_price, format_ratio, price_micro_to_percent_micro
from app.db.models.asset import Asset
from app.schemas.common import ApiModel
from app.services.position_service import PositionView


class PositionAsset(ApiModel):
    """A short asset description embedded into a position."""

    id: int
    secid: str
    name: str
    type: AssetType

    @classmethod
    def from_asset(cls, asset: Asset) -> Self:
        return cls(id=asset.id, secid=asset.secid, name=asset.name, type=asset.type)


class PositionItem(ApiModel):
    """One open position with current pricing."""

    asset: PositionAsset
    quantity: int
    avg_price: str
    avg_price_percent: str | None
    current_price: str
    current_price_type: PriceType
    current_face_value: str | None
    market_value: str
    invested: str
    share: str
    price_date: date | None
    price_source: str
    is_stale: bool

    @classmethod
    def from_view(cls, view: PositionView) -> Self:
        face_value = view.current_face_value_kopecks
        avg_price_percent = None
        avg_face_value = view.state.avg_face_value_kopecks or face_value
        if view.asset.type is AssetType.BOND and avg_face_value:
            percent_micro = price_micro_to_percent_micro(view.state.avg_price_micro, avg_face_value)
            avg_price_percent = format_price(percent_micro) if percent_micro is not None else None

        return cls(
            asset=PositionAsset.from_asset(view.asset),
            quantity=view.state.quantity,
            avg_price=format_price(view.state.avg_price_micro),
            avg_price_percent=avg_price_percent,
            current_price=format_price(view.current_price_micro),
            current_price_type=view.current_price_type,
            current_face_value=format_money(face_value) if face_value is not None else None,
            market_value=format_money(view.market_value_kopecks),
            invested=format_money(view.invested_kopecks),
            share=format_ratio(view.share),
            price_date=view.price_date,
            price_source=view.price_source,
            is_stale=view.is_stale,
        )


class PositionListResponse(ApiModel):
    """All open positions plus portfolio totals."""

    items: list[PositionItem]
    total_market_value: str
    total_invested: str

    @classmethod
    def from_views(cls, views: Sequence[PositionView]) -> Self:
        return cls(
            items=[PositionItem.from_view(view) for view in views],
            total_market_value=format_money(sum(view.market_value_kopecks for view in views)),
            total_invested=format_money(sum(view.invested_kopecks for view in views)),
        )
