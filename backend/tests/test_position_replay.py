"""Pure replay tests for position reconstruction (plan §6.1)."""

from datetime import date

import pytest

from app.core.enums import OperationType, PriceType
from app.core.errors import AppError, ErrorCode
from app.db.models.operation import Operation
from app.services import position_service

BUY_100 = 100_000_000  # 100.00 RUB per unit
BUY_120 = 120_000_000  # 120.00 RUB per unit


def _op(
    operation_type: OperationType,
    trade_date: date,
    quantity: int,
    price_micro: int = BUY_100,
    *,
    operation_id: int | None = None,
    asset_id: int = 1,
) -> Operation:
    """Build an unsaved operation for pure replay tests."""

    return Operation(
        id=operation_id,
        portfolio_id=1,
        asset_id=asset_id,
        type=operation_type,
        trade_date=trade_date,
        quantity=quantity,
        price_micro=price_micro,
        input_price_micro=price_micro,
        input_price_type=PriceType.RUB,
    )


def test_two_buys_give_weighted_average() -> None:
    state = position_service.calculate_position(
        1,
        [
            _op(OperationType.BUY, date(2026, 1, 10), 10, BUY_100),
            _op(OperationType.BUY, date(2026, 1, 11), 10, BUY_120),
        ],
    )

    assert state.quantity == 20
    assert state.cost_kopecks == 220_000
    assert state.avg_price_micro == 110_000_000


def test_sell_keeps_average_and_releases_cost() -> None:
    state = position_service.calculate_position(
        1,
        [
            _op(OperationType.SELL, date(2026, 1, 12), 5, 150_000_000),
            _op(OperationType.BUY, date(2026, 1, 10), 10, BUY_100),
            _op(OperationType.BUY, date(2026, 1, 11), 10, BUY_120),
        ],
    )

    assert state.quantity == 15
    assert state.cost_kopecks == 165_000
    assert state.avg_price_micro == 110_000_000


def test_sell_above_available_raises_with_details() -> None:
    operations = [
        _op(OperationType.BUY, date(2026, 1, 10), 10, BUY_100),
        _op(OperationType.BUY, date(2026, 1, 11), 10, BUY_120),
        _op(OperationType.SELL, date(2026, 1, 12), 25, 150_000_000, operation_id=7),
    ]

    with pytest.raises(AppError) as exc_info:
        position_service.calculate_position(1, operations)

    error = exc_info.value
    assert error.code == ErrorCode.INSUFFICIENT_QUANTITY
    assert error.status_code == 409
    assert error.message == "Нельзя продать 25: доступно 20"
    assert error.details == {
        "asset_id": 1,
        "available": 20,
        "requested": 25,
        "operation_id": 7,
        "trade_date": "2026-01-12",
    }


def test_full_sell_closes_position_to_zero() -> None:
    state = position_service.calculate_position(
        1,
        [
            _op(OperationType.BUY, date(2026, 1, 10), 10, BUY_100),
            _op(OperationType.SELL, date(2026, 1, 11), 10, 150_000_000),
        ],
    )

    assert (state.quantity, state.cost_kopecks, state.avg_price_micro) == (0, 0, 0)


def test_cost_is_rounded_to_kopecks() -> None:
    state = position_service.calculate_position(
        1, [_op(OperationType.BUY, date(2026, 1, 10), 3, 33_333_333)]
    )

    assert state.cost_kopecks == 10_000
    assert state.avg_price_micro == 33_333_333
