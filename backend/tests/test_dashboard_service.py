"""Dashboard service tests: totals, upcoming coupons and aggregate rules."""

from typing import get_args

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, OperationType
from app.core.errors import AppError, ErrorCode
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.portfolio import Portfolio
from app.schemas.dashboard import DashboardPeriod
from app.services import dashboard_service, portfolio_service

from dashboard_helpers import (  # isort: skip
    add_income,
    add_operation,
    build_dashboard_portfolio,
    days_ago,
    days_ahead,
    make_asset,
)


def _add_scenario_extras(session: Session, bond: Asset) -> None:
    """Add the closed bond, empty asset and expected coupons of this scenario."""

    # A fully closed bond still owns a coupon; its quantity is zero.
    closed = make_asset(session, secid="CLOSED", asset_type=AssetType.BOND)
    add_operation(session, closed, trade_date=days_ago(40), quantity=5, price_micro=100_000_000)
    add_operation(
        session,
        closed,
        trade_date=days_ago(30),
        quantity=5,
        price_micro=100_000_000,
        type=OperationType.SELL,
    )

    # An asset without operations still counts in assets_count.
    make_asset(session, secid="EMPTY")

    add_income(session, bond, pay_date=days_ahead(10), per_unit_micro=35_000_000)
    add_income(session, bond, pay_date=days_ahead(10), per_unit_micro=10_000_000)
    add_income(session, bond, pay_date=days_ahead(20), per_unit_micro=4_000_000)
    add_income(session, bond, pay_date=days_ago(5), per_unit_micro=20_000_000)
    add_income(session, closed, pay_date=days_ahead(5), per_unit_micro=100_000_000)


def _build_portfolio(session: Session) -> None:
    _, bond = build_dashboard_portfolio(session)
    _add_scenario_extras(session, bond)


def test_dashboard_totals_and_counts(db_session: Session) -> None:
    _build_portfolio(db_session)

    data = dashboard_service.get_dashboard(db_session)

    totals = data.totals
    assert totals.market_value_kopecks == 1_587_500
    assert totals.invested_kopecks == 1_526_845
    assert totals.dividends_paid_kopecks == 20_000
    assert totals.coupons_paid_kopecks == 52_500
    assert totals.income_paid_total_kopecks == 72_500
    # Overdue coupons stay expected and count; the closed bond contributes 0.
    assert totals.expected_coupons_kopecks == 103_500
    assert totals.positions_count == 2
    assert totals.assets_count == 4
    assert data.as_of == today_local()
    assert data.currency == "RUB"
    assert data.period == "1Y"
    assert [view.asset.secid for view in data.positions] == ["SBER", "SU26238RMFS4"]


def test_upcoming_coupons_filter_sort_and_zero_quantity(db_session: Session) -> None:
    _build_portfolio(db_session)

    data = dashboard_service.get_dashboard(db_session)

    views = data.upcoming_coupons
    assert [view.asset_secid for view in views] == [
        "SU26238RMFS4",
        "SU26238RMFS4",
        "SU26238RMFS4",
    ]
    assert [view.amount_total_kopecks for view in views] == [52_500, 15_000, 6_000]
    assert all(view.quantity == 15 for view in views)
    assert all(not view.is_overdue for view in views)
    # The closed bond's coupon is excluded because the current quantity is zero.
    assert all(view.asset_secid != "CLOSED" for view in views)


def test_upcoming_coupons_are_ordered_by_pay_date_then_id(db_session: Session) -> None:
    portfolio = portfolio_service.ensure_default_portfolio(db_session)
    bond = make_asset(db_session, secid="SU26238RMFS4", asset_type=AssetType.BOND)
    add_operation(db_session, bond, trade_date=days_ago(10), quantity=1, price_micro=100_000_000)
    later = add_income(db_session, bond, pay_date=days_ahead(20), per_unit_micro=10_000_000)
    first = add_income(db_session, bond, pay_date=days_ahead(10), per_unit_micro=10_000_000)
    second = add_income(db_session, bond, pay_date=days_ahead(10), per_unit_micro=10_000_000)

    views = dashboard_service.get_dashboard(db_session).upcoming_coupons

    assert [view.income.id for view in views] == [first.id, second.id, later.id]
    assert portfolio.id == views[0].income.portfolio_id


def test_currency_comes_from_the_portfolio(db_session: Session) -> None:
    portfolio = portfolio_service.ensure_default_portfolio(db_session)
    portfolio.base_currency = "USD"
    db_session.commit()

    assert dashboard_service.get_dashboard(db_session).currency == "USD"


def test_dashboard_does_not_create_a_portfolio(db_session: Session) -> None:
    assert db_session.scalar(select(func.count()).select_from(Portfolio)) == 0

    data = dashboard_service.get_dashboard(db_session)

    assert data.currency == "RUB"
    assert data.totals.market_value_kopecks == 0
    assert data.totals.assets_count == 0
    assert data.series == []
    assert data.positions == []
    assert data.upcoming_coupons == []
    assert db_session.scalar(select(func.count()).select_from(Portfolio)) == 0


def test_invalid_period_is_a_bad_request(db_session: Session) -> None:
    with pytest.raises(AppError) as exc_info:
        dashboard_service.get_dashboard(db_session, "2Y")

    error = exc_info.value
    assert error.code == ErrorCode.BAD_REQUEST
    assert error.status_code == 400
    assert error.details == {"period": "2Y", "supported": ["1M", "3M", "1Y", "ALL"]}

    with pytest.raises(AppError):
        dashboard_service.compute_series(db_session, "6M")


def test_coupon_pay_date_today_is_upcoming_and_not_overdue(db_session: Session) -> None:
    _, bond = build_dashboard_portfolio(db_session)
    today_coupon = add_income(
        db_session,
        bond,
        pay_date=today_local(),
        per_unit_micro=10_000_000,
    )
    overdue_coupon = add_income(
        db_session,
        bond,
        pay_date=days_ago(1),
        per_unit_micro=20_000_000,
    )

    data = dashboard_service.get_dashboard(db_session)

    assert [view.income.id for view in data.upcoming_coupons] == [today_coupon.id]
    today_view = data.upcoming_coupons[0]
    assert today_view.quantity == 15
    assert today_view.amount_total_kopecks == 15_000
    assert today_view.is_overdue is False
    # The coupon of yesterday is hidden from the upcoming list but still
    # expected to be paid, so it remains in the total.
    assert overdue_coupon.id not in {view.income.id for view in data.upcoming_coupons}
    assert data.totals.expected_coupons_kopecks == 15_000 + 30_000


def test_dashboard_period_mapping_matches_the_api_literal() -> None:
    assert list(dashboard_service.DASHBOARD_PERIOD_DAYS) == list(get_args(DashboardPeriod))
