"""Regressions: current positions and totals are computed as of today.

Future-dated operations are part of the history and must still pass full
sequence validation, but they must not change today's positions, dashboard
totals, expected coupon quantities or stored snapshots.
"""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AssetType, IncomeStatus, OperationType, PriceType
from app.core.time import today_local
from app.services import (
    dashboard_service,
    income_service,
    operation_service,
    position_service,
    snapshot_service,
)

from dashboard_helpers import (  # isort: skip
    add_amortization,
    add_income,
    add_operation,
    add_quote,
    build_dashboard_portfolio,
    days_ago,
    days_ahead,
    make_asset,
)


def _assert_current_totals(
    session: Session,
    *,
    quantity: int,
    market_value: int,
    invested: int,
    coupon_amount: int,
) -> None:
    """Assert positions, asset card, dashboard and snapshot agree today."""

    positions = position_service.get_positions(session)
    assert len(positions) == 1
    assert positions[0].state.quantity == quantity
    assert positions[0].market_value_kopecks == market_value
    assert positions[0].invested_kopecks == invested

    data = dashboard_service.get_dashboard(session)
    assert data.totals.market_value_kopecks == market_value
    assert data.totals.invested_kopecks == invested
    assert [view.state.quantity for view in data.positions] == [quantity]
    assert data.series[-1].market_value_kopecks == market_value
    assert data.series[-1].invested_kopecks == invested

    assert [view.quantity for view in data.upcoming_coupons] == [quantity]
    assert [view.amount_total_kopecks for view in data.upcoming_coupons] == [coupon_amount]

    snapshot = snapshot_service.compute_for_date(session, today_local())
    assert snapshot.market_value_kopecks == market_value
    assert snapshot.invested_kopecks == invested


def test_future_buy_does_not_change_today(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=10, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(1), price_micro=110_000_000)
    add_income(db_session, stock, pay_date=days_ahead(1), per_unit_micro=10_000_000)

    add_operation(
        db_session,
        stock,
        trade_date=days_ahead(1),
        quantity=10,
        price_micro=200_000_000,
    )

    card = position_service.get_position(db_session, stock.id)
    assert card.state.quantity == 10
    assert card.market_value_kopecks == 110_000
    _assert_current_totals(
        db_session,
        quantity=10,
        market_value=110_000,
        invested=100_000,
        coupon_amount=10_000,
    )


def test_future_sell_does_not_close_today(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=10, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(1), price_micro=110_000_000)
    add_income(db_session, stock, pay_date=days_ahead(1), per_unit_micro=10_000_000)

    add_operation(
        db_session,
        stock,
        trade_date=days_ahead(1),
        quantity=10,
        price_micro=150_000_000,
        type=OperationType.SELL,
    )

    card = position_service.get_position(db_session, stock.id)
    assert card.state.quantity == 10
    assert card.market_value_kopecks == 110_000
    _assert_current_totals(
        db_session,
        quantity=10,
        market_value=110_000,
        invested=100_000,
        coupon_amount=10_000,
    )


def test_today_buy_is_included_while_a_future_trade_is_not(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=10, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(1), price_micro=110_000_000)
    add_income(db_session, stock, pay_date=days_ahead(1), per_unit_micro=10_000_000)

    baseline = dashboard_service.get_dashboard(db_session)
    assert baseline.totals.market_value_kopecks == 110_000
    assert [view.quantity for view in baseline.upcoming_coupons] == [10]

    today = today_local()
    add_operation(db_session, stock, trade_date=today, quantity=5, price_micro=100_000_000)

    data = dashboard_service.get_dashboard(db_session)
    assert data.totals.market_value_kopecks == 165_000
    assert data.totals.market_value_kopecks > baseline.totals.market_value_kopecks
    _assert_current_totals(
        db_session,
        quantity=15,
        market_value=165_000,
        invested=150_000,
        coupon_amount=15_000,
    )

    add_operation(
        db_session,
        stock,
        trade_date=days_ahead(1),
        quantity=5,
        price_micro=200_000_000,
    )
    _assert_current_totals(
        db_session,
        quantity=15,
        market_value=165_000,
        invested=150_000,
        coupon_amount=15_000,
    )


def test_today_sell_is_included_while_a_future_trade_is_not(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=10, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(1), price_micro=110_000_000)
    add_income(db_session, stock, pay_date=days_ahead(1), per_unit_micro=10_000_000)

    baseline = dashboard_service.get_dashboard(db_session)
    assert baseline.totals.market_value_kopecks == 110_000

    add_operation(
        db_session,
        stock,
        trade_date=today_local(),
        quantity=4,
        price_micro=150_000_000,
        type=OperationType.SELL,
    )

    data = dashboard_service.get_dashboard(db_session)
    assert data.totals.market_value_kopecks == 66_000
    assert data.totals.market_value_kopecks < baseline.totals.market_value_kopecks
    _assert_current_totals(
        db_session,
        quantity=6,
        market_value=66_000,
        invested=60_000,
        coupon_amount=6_000,
    )

    add_operation(
        db_session,
        stock,
        trade_date=days_ahead(1),
        quantity=6,
        price_micro=150_000_000,
        type=OperationType.SELL,
    )
    _assert_current_totals(
        db_session,
        quantity=6,
        market_value=66_000,
        invested=60_000,
        coupon_amount=6_000,
    )


def test_today_quote_and_amortization_agree_across_views(db_session: Session) -> None:
    bond = make_asset(db_session, secid="SU26238RMFS4", asset_type=AssetType.BOND)
    add_operation(
        db_session,
        bond,
        trade_date=days_ago(2),
        quantity=2,
        price_micro=950_000_000,
    )
    today = today_local()
    add_amortization(
        db_session,
        bond,
        amortization_date=today,
        amount_per_unit_kopecks=20_000,
    )
    add_quote(db_session, bond, quote_date=today, price_micro=98_000_000)

    positions = position_service.get_positions(db_session)
    last = dashboard_service.compute_series(db_session, "1M")[-1]
    snapshot = snapshot_service.compute_for_date(db_session, today)

    assert len(positions) == 1
    assert positions[0].current_face_value_kopecks == 80_000
    assert positions[0].market_value_kopecks == 156_800
    assert positions[0].invested_kopecks == 190_000
    assert last.date == today
    assert last.market_value_kopecks == positions[0].market_value_kopecks
    assert last.invested_kopecks == positions[0].invested_kopecks
    assert snapshot.market_value_kopecks == positions[0].market_value_kopecks
    assert snapshot.invested_kopecks == positions[0].invested_kopecks


def test_future_only_portfolio_is_empty_today(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(
        db_session,
        stock,
        trade_date=days_ahead(5),
        quantity=10,
        price_micro=100_000_000,
    )
    add_income(db_session, stock, pay_date=days_ahead(10), per_unit_micro=10_000_000)

    data = dashboard_service.get_dashboard(db_session)

    assert data.positions == []
    assert data.series == []
    assert data.totals.market_value_kopecks == 0
    assert data.totals.invested_kopecks == 0
    assert data.totals.expected_coupons_kopecks == 0
    assert data.totals.positions_count == 0
    assert data.upcoming_coupons == []
    assert position_service.get_positions(db_session) == []

    card = position_service.get_position(db_session, stock.id)
    assert card.state.quantity == 0
    assert card.market_value_kopecks == 0

    snapshot = snapshot_service.compute_for_date(db_session, today_local())
    assert snapshot.market_value_kopecks == 0
    assert snapshot.invested_kopecks == 0


def test_validation_still_replays_future_operations(db_session: Session) -> None:
    stock = make_asset(db_session)

    buy = operation_service.create_operation(
        db_session,
        asset_id=stock.id,
        type=OperationType.BUY,
        trade_date=days_ahead(1),
        quantity=5,
        price=Decimal("100"),
        price_type=PriceType.RUB,
    )
    sell = operation_service.create_operation(
        db_session,
        asset_id=stock.id,
        type=OperationType.SELL,
        trade_date=days_ahead(2),
        quantity=5,
        price=Decimal("120"),
        price_type=PriceType.RUB,
    )

    # Creating the future sell only succeeds because validation replays the
    # future buy as well. As of today neither operation has happened.
    assert [operation.id for operation in operation_service.list_operations(db_session)] == [
        buy.id,
        sell.id,
    ]
    assert position_service.validate_operation_sequence(db_session, stock.id).quantity == 0
    assert position_service.load_operations(db_session, stock.id, on_date=today_local()) == []


def test_mark_paid_uses_today_quantity_despite_a_future_buy(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=10, price_micro=100_000_000)
    coupon = add_income(
        db_session,
        stock,
        pay_date=today_local(),
        per_unit_micro=10_000_000,
    )
    add_operation(
        db_session,
        stock,
        trade_date=days_ahead(1),
        quantity=10,
        price_micro=100_000_000,
    )

    paid = income_service.mark_paid(db_session, coupon.id)

    assert paid.status is IncomeStatus.PAID
    assert paid.quantity == 10
    assert paid.amount_per_unit_micro == 10_000_000
    assert paid.amount_total_kopecks == 10_000


def test_dashboard_totals_match_the_last_series_point_and_snapshot(
    db_session: Session,
) -> None:
    build_dashboard_portfolio(db_session)

    data = dashboard_service.get_dashboard(db_session)
    last = data.series[-1]

    assert last.date == today_local()
    assert data.totals.market_value_kopecks == last.market_value_kopecks
    assert data.totals.invested_kopecks == last.invested_kopecks

    snapshot = snapshot_service.compute_and_store(db_session)
    assert snapshot.snapshot_date == today_local()
    assert snapshot.market_value_kopecks == last.market_value_kopecks
    assert snapshot.invested_kopecks == last.invested_kopecks


def _build_valuation_case(session: Session, case: str) -> None:
    if case == "stock":
        asset = make_asset(session, secid="SBER")
        add_operation(
            session,
            asset,
            trade_date=days_ago(6),
            quantity=4,
            price_micro=100_000_000,
        )
        add_quote(session, asset, quote_date=days_ago(1), price_micro=120_000_000)
        return

    if case == "bond_rub":
        asset = make_asset(session, secid="SU26238RMFS4", asset_type=AssetType.BOND)
        add_operation(
            session,
            asset,
            trade_date=days_ago(6),
            quantity=2,
            price_micro=900_000_000,
        )
        add_quote(
            session,
            asset,
            quote_date=days_ago(1),
            price_micro=1_000_000_000,
            price_type=PriceType.RUB,
        )
        return

    asset = make_asset(session, secid="SU26238RMFS4", asset_type=AssetType.BOND)
    add_operation(
        session,
        asset,
        trade_date=days_ago(6),
        quantity=2,
        price_micro=950_000_000,
    )
    add_amortization(
        session,
        asset,
        amortization_date=days_ago(3),
        amount_per_unit_kopecks=20_000,
    )
    add_quote(session, asset, quote_date=days_ago(1), price_micro=98_000_000)


@pytest.mark.parametrize(
    ("case", "market_value", "invested"),
    [
        ("stock", 48_000, 40_000),
        ("bond_rub", 200_000, 180_000),
        ("bond_percent", 156_800, 190_000),
    ],
)
def test_today_series_matches_current_positions(
    db_session: Session,
    case: str,
    market_value: int,
    invested: int,
) -> None:
    _build_valuation_case(db_session, case)

    positions = position_service.get_positions(db_session)
    last = dashboard_service.compute_series(db_session, "1M")[-1]

    assert last.date == today_local()
    assert last.market_value_kopecks == market_value
    assert last.invested_kopecks == invested
    assert sum(view.market_value_kopecks for view in positions) == market_value
    assert sum(view.invested_kopecks for view in positions) == invested
