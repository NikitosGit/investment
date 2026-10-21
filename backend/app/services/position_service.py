"""Position reconstruction and valuation.

Positions are never stored: they are replayed from the operation history on
every request (plan §6.1). This module is read-only and never writes to the
database.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, OperationType, PriceType
from app.core.errors import AppError, ErrorCode
from app.core.money import bond_market_value_kopecks, quantity_cost_kopecks
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.operation import Operation
from app.services import asset_service, bondization_service, quote_service

_ONE = Decimal(1)
_AVG_DIVISOR = Decimal(100)
_SHARE_PLACES = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class PositionState:
    """Quantity and cost basis of one asset after replaying its operations."""

    asset_id: int
    quantity: int
    cost_kopecks: int
    avg_price_micro: int


@dataclass(frozen=True, slots=True)
class PositionView:
    """A position enriched with its current price and valuation."""

    asset: Asset
    state: PositionState
    current_price_micro: int
    current_price_type: PriceType
    current_face_value_kopecks: int | None
    market_value_kopecks: int
    invested_kopecks: int
    share: Decimal
    price_date: date | None
    price_source: str
    is_stale: bool


def calculate_position(asset_id: int, operations: Sequence[Operation]) -> PositionState:
    """Replay ``operations`` and return the resulting position state.

    Operations are sorted defensively by ``(trade_date, id)`` so a caller can
    pass either an ordered query result or freshly created rows. Selling more
    than is available at that point of the history raises
    ``INSUFFICIENT_QUANTITY``.
    """

    ordered = sorted(operations, key=lambda operation: (operation.trade_date, operation.id or 0))
    quantity = 0
    cost_kopecks = 0

    for operation in ordered:
        if operation.type is OperationType.BUY:
            quantity += operation.quantity
            cost_kopecks += quantity_cost_kopecks(operation.quantity, operation.price_micro)
            continue

        _ensure_can_sell(asset_id, operation, available=quantity)
        if operation.quantity == quantity:
            # Full close: the whole cost basis is released exactly.
            cost_kopecks = 0
        else:
            cost_kopecks -= _sale_cost_kopecks(cost_kopecks, operation.quantity, quantity)
        quantity -= operation.quantity
        if quantity == 0:
            cost_kopecks = 0

    return PositionState(
        asset_id=asset_id,
        quantity=quantity,
        cost_kopecks=cost_kopecks,
        avg_price_micro=_average_price_micro(cost_kopecks, quantity),
    )


def load_operations(session: Session, asset_id: int) -> list[Operation]:
    """Return all operations of an asset ordered by ``trade_date`` and ``id``."""

    statement = (
        select(Operation)
        .where(Operation.asset_id == asset_id)
        .order_by(Operation.trade_date, Operation.id)
    )
    return list(session.scalars(statement))


def validate_operation_sequence(session: Session, asset_id: int) -> PositionState:
    """Replay the stored history of an asset and raise if it is inconsistent."""

    return calculate_position(asset_id, load_operations(session, asset_id))


def get_position(session: Session, asset_id: int) -> PositionView:
    """Return the position of one asset, including fully closed positions.

    The share is computed against the market value of all open positions, so
    an asset card shows the same fraction as the positions list.
    """

    asset = asset_service.get_asset(session, asset_id)
    today = today_local()
    state = calculate_position(asset_id, load_operations(session, asset_id))
    view = _build_view(session, asset, state, today)
    if state.quantity <= 0:
        return replace(view, share=Decimal(0))

    total_market_value = sum(other.market_value_kopecks for other in _open_views(session, today))
    return replace(view, share=_share(view.market_value_kopecks, total_market_value))


def get_positions(session: Session) -> list[PositionView]:
    """Return all open positions with shares based on the portfolio total."""

    views = _open_views(session, today_local())
    total_market_value = sum(view.market_value_kopecks for view in views)
    return [
        replace(view, share=_share(view.market_value_kopecks, total_market_value)) for view in views
    ]


def _open_views(session: Session, today: date) -> list[PositionView]:
    """Build valuations for every asset whose replayed quantity is positive."""

    asset_ids = session.scalars(
        select(Operation.asset_id).distinct().order_by(Operation.asset_id)
    ).all()

    views: list[PositionView] = []
    for asset_id in asset_ids:
        asset = session.get(Asset, asset_id)
        if asset is None:
            continue
        state = calculate_position(asset_id, load_operations(session, asset_id))
        if state.quantity <= 0:
            continue
        views.append(_build_view(session, asset, state, today))
    return views


def _ensure_can_sell(asset_id: int, operation: Operation, *, available: int) -> None:
    if operation.quantity <= available:
        return
    raise AppError(
        ErrorCode.INSUFFICIENT_QUANTITY,
        f"Нельзя продать {operation.quantity}: доступно {available}",
        status_code=409,
        details={
            "asset_id": asset_id,
            "available": available,
            "requested": operation.quantity,
            "operation_id": operation.id,
            "trade_date": operation.trade_date.isoformat(),
        },
    )


def _sale_cost_kopecks(cost_kopecks: int, sell_quantity: int, quantity: int) -> int:
    """Release the average share of the cost basis with half-up rounding."""

    value = Decimal(cost_kopecks) * Decimal(sell_quantity) / Decimal(quantity)
    return int(value.quantize(_ONE, rounding=ROUND_HALF_UP))


def _average_price_micro(cost_kopecks: int, quantity: int) -> int:
    if quantity <= 0:
        return 0
    value = Decimal(cost_kopecks) * Decimal(1_000_000) / (_AVG_DIVISOR * Decimal(quantity))
    return int(value.quantize(_ONE, rounding=ROUND_HALF_UP))


def _share(market_value_kopecks: int, total_kopecks: int) -> Decimal:
    if total_kopecks <= 0:
        return Decimal(0)
    return (Decimal(market_value_kopecks) / Decimal(total_kopecks)).quantize(
        _SHARE_PLACES, rounding=ROUND_HALF_UP
    )


def _build_view(session: Session, asset: Asset, state: PositionState, today: date) -> PositionView:
    """Attach price and valuation information to a position state (plan §6.4)."""

    is_bond = asset.type is AssetType.BOND
    current_face_value = (
        bondization_service.current_face_value_kopecks(session, asset, today) if is_bond else None
    )
    quote = quote_service.get_last_quote(session, asset.id, on_date=today)

    if quote is not None:
        if is_bond and quote.price_type is PriceType.RUB:
            # Manual ruble quote for a bond: the price is already per unit.
            market_value = quantity_cost_kopecks(state.quantity, quote.price_micro)
            price_type = PriceType.RUB
        elif is_bond:
            # The quoted percent refers to the face value on the quote date.
            valuation_face = bondization_service.current_face_value_kopecks(
                session, asset, quote.quote_date
            )
            market_value = bond_market_value_kopecks(
                state.quantity, valuation_face or 0, quote.price_micro
            )
            price_type = PriceType.PERCENT
        else:
            market_value = quantity_cost_kopecks(state.quantity, quote.price_micro)
            price_type = PriceType.RUB
        return PositionView(
            asset=asset,
            state=state,
            current_price_micro=quote.price_micro,
            current_price_type=price_type,
            current_face_value_kopecks=current_face_value,
            market_value_kopecks=market_value,
            invested_kopecks=state.cost_kopecks,
            share=Decimal(0),
            price_date=quote.quote_date,
            price_source=quote.source.value,
            is_stale=quote.quote_date < today,
        )

    # No quote at all: fall back to the average cost from the plan §6.4.
    return PositionView(
        asset=asset,
        state=state,
        current_price_micro=state.avg_price_micro,
        current_price_type=PriceType.RUB,
        current_face_value_kopecks=current_face_value,
        market_value_kopecks=state.cost_kopecks,
        invested_kopecks=state.cost_kopecks,
        share=Decimal(0),
        price_date=None,
        price_source="COST",
        is_stale=True,
    )
