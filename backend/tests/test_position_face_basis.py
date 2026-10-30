"""Face-basis regressions for the average bond purchase percentage."""

from datetime import date
from decimal import Decimal

from app.core.enums import AssetType, OperationType, PriceType
from app.db.models.asset import Asset
from app.db.models.operation import Operation
from app.schemas.position import PositionItem
from app.services import position_service
from app.services.position_service import PositionState, PositionView

FACE_1000 = 100_000
FACE_800 = 80_000
PRICE_95_1000 = 950_000_000
PRICE_95_800 = 760_000_000


def _op(
    operation_type: OperationType,
    trade_date: date,
    quantity: int,
    price_micro: int,
    *,
    face_value_kopecks: int | None,
) -> Operation:
    """Build an unsaved operation with the frozen face value of its trade date."""

    return Operation(
        id=0,
        portfolio_id=1,
        asset_id=1,
        type=operation_type,
        trade_date=trade_date,
        quantity=quantity,
        price_micro=price_micro,
        input_price_micro=price_micro,
        input_price_type=(PriceType.PERCENT if face_value_kopecks is not None else PriceType.RUB),
        face_value_kopecks=face_value_kopecks,
    )


def _buy(
    trade_date: date,
    quantity: int,
    price_micro: int,
    *,
    face_value_kopecks: int | None,
) -> Operation:
    return _op(
        OperationType.BUY,
        trade_date,
        quantity,
        price_micro,
        face_value_kopecks=face_value_kopecks,
    )


def _sell(trade_date: date, quantity: int, price_micro: int = 900_000_000) -> Operation:
    return _op(
        OperationType.SELL,
        trade_date,
        quantity,
        price_micro,
        face_value_kopecks=None,
    )


def _item(
    state: PositionState,
    *,
    asset_type: AssetType = AssetType.BOND,
    current_face_value_kopecks: int | None = FACE_800,
) -> PositionItem:
    """Wrap a replayed state into the API view without touching the database."""

    is_bond = asset_type is AssetType.BOND
    asset = Asset(
        id=1,
        secid="SU26238RMFS4" if is_bond else "SBER",
        name="Демо",
        type=asset_type,
        engine="stock",
        market="bonds" if is_bond else "shares",
        board="TQCB" if is_bond else "TQBR",
        currency="RUB",
        initial_face_value_kopecks=FACE_1000 if is_bond else None,
        lot_size=1,
    )
    view = PositionView(
        asset=asset,
        state=state,
        current_price_micro=state.avg_price_micro,
        current_price_type=PriceType.PERCENT if is_bond else PriceType.RUB,
        current_face_value_kopecks=current_face_value_kopecks if is_bond else None,
        market_value_kopecks=state.cost_kopecks,
        invested_kopecks=state.cost_kopecks,
        share=Decimal(0),
        price_date=None,
        price_source="COST",
        is_stale=True,
    )
    return PositionItem.from_view(view)


def test_buys_spanning_amortization_use_a_weighted_face_basis() -> None:
    state = position_service.calculate_position(
        1,
        [
            _buy(date(2026, 1, 10), 10, PRICE_95_1000, face_value_kopecks=FACE_1000),
            _buy(date(2026, 3, 1), 10, PRICE_95_800, face_value_kopecks=FACE_800),
        ],
    )

    assert state.quantity == 20
    assert state.cost_kopecks == 1_710_000
    assert state.avg_price_micro == 855_000_000
    assert state.avg_face_value_kopecks == 90_000

    item = _item(state, current_face_value_kopecks=FACE_800)
    assert item.avg_price == "855.000000"
    assert item.avg_price_percent == "95.000000"


def test_selling_the_later_lot_keeps_the_weighted_percent() -> None:
    state = position_service.calculate_position(
        1,
        [
            _buy(date(2026, 1, 10), 10, PRICE_95_1000, face_value_kopecks=FACE_1000),
            _buy(date(2026, 3, 1), 10, PRICE_95_800, face_value_kopecks=FACE_800),
            _sell(date(2026, 4, 1), 10),
        ],
    )

    assert state.quantity == 10
    assert state.cost_kopecks == 855_000
    assert state.avg_price_micro == 855_000_000
    assert state.avg_face_value_kopecks == 90_000
    assert _item(state).avg_price_percent == "95.000000"


def test_full_close_resets_the_face_basis_before_a_rebuy() -> None:
    state = position_service.calculate_position(
        1,
        [
            _buy(date(2026, 1, 10), 10, PRICE_95_1000, face_value_kopecks=FACE_1000),
            _sell(date(2026, 2, 1), 10),
            _buy(date(2026, 3, 1), 10, PRICE_95_800, face_value_kopecks=FACE_800),
        ],
    )

    assert state.quantity == 10
    assert state.cost_kopecks == 760_000
    assert state.avg_price_micro == 760_000_000
    assert state.avg_face_value_kopecks == FACE_800
    assert _item(state).avg_price_percent == "95.000000"


def test_fully_amortized_bond_keeps_the_historical_purchase_percent() -> None:
    state = position_service.calculate_position(
        1,
        [
            _buy(
                date(2026, 1, 10),
                10,
                951_230_000,
                face_value_kopecks=FACE_1000,
            )
        ],
    )

    item = _item(state, current_face_value_kopecks=0)

    assert state.avg_face_value_kopecks == FACE_1000
    assert item.avg_price_percent == "95.123000"
    assert item.current_face_value == "0.00"


def test_bond_without_amortization_is_unchanged() -> None:
    state = position_service.calculate_position(
        1,
        [
            _buy(
                date(2026, 1, 10),
                15,
                951_230_000,
                face_value_kopecks=FACE_1000,
            )
        ],
    )

    item = _item(state, current_face_value_kopecks=FACE_1000)

    assert item.avg_price == "951.230000"
    assert item.avg_price_percent == "95.123000"
    assert item.current_face_value == "1000.00"


def test_stock_has_no_average_percent() -> None:
    state = position_service.calculate_position(
        1,
        [_buy(date(2026, 1, 10), 10, 100_000_000, face_value_kopecks=None)],
    )

    item = _item(state, asset_type=AssetType.STOCK, current_face_value_kopecks=None)

    assert item.avg_price == "100.000000"
    assert item.avg_price_percent is None


def test_legacy_operation_without_frozen_face_falls_back_to_current_face() -> None:
    state = position_service.calculate_position(
        1,
        [_buy(date(2026, 1, 10), 10, PRICE_95_1000, face_value_kopecks=None)],
    )

    assert state.avg_face_value_kopecks == 0
    assert _item(state, current_face_value_kopecks=FACE_1000).avg_price_percent == "95.000000"
    assert _item(state, current_face_value_kopecks=None).avg_price_percent is None


def test_face_basis_release_rounds_half_up() -> None:
    state = position_service.calculate_position(
        1,
        [
            _buy(date(2026, 1, 10), 1, 950_000_000, face_value_kopecks=FACE_1000),
            _buy(date(2026, 1, 11), 2, 760_000_000, face_value_kopecks=FACE_800),
            _sell(date(2026, 2, 1), 1),
        ],
    )

    # 260_000 * 1 / 3 = 86_666.67 kopecks released -> 173_333 left for 2 units.
    assert state.quantity == 2
    assert state.avg_face_value_kopecks == 86_667
