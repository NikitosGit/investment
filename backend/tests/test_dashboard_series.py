"""Dashboard series tests: replay, valuation, partial points and periods."""

import ast
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AssetType, OperationType, PriceType
from app.core.time import today_local
from app.services import dashboard_service, snapshot_service

from dashboard_helpers import (  # isort: skip
    add_amortization,
    add_operation,
    add_quote,
    days_ago,
    make_asset,
)


def _by_date(
    points: list[dashboard_service.SeriesPoint],
) -> dict[date, dashboard_service.SeriesPoint]:
    return {point.date: point for point in points}


def test_series_tracks_quantity_sells_and_carries_the_last_quote(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=10, price_micro=100_000_000)
    add_operation(
        db_session,
        stock,
        trade_date=days_ago(3),
        quantity=4,
        price_micro=150_000_000,
        type=OperationType.SELL,
    )
    add_quote(db_session, stock, quote_date=days_ago(5), price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(2), price_micro=120_000_000)

    points = dashboard_service.compute_series(db_session, "1M")
    by_date = _by_date(points)

    assert points[0].date == days_ago(5)
    assert points[-1].date == today_local()
    assert len(points) == 6
    assert (by_date[days_ago(5)].market_value_kopecks, by_date[days_ago(5)].invested_kopecks) == (
        100_000,
        100_000,
    )
    # The quote of day -5 is carried forward until the next one.
    assert by_date[days_ago(4)].market_value_kopecks == 100_000
    assert (by_date[days_ago(3)].market_value_kopecks, by_date[days_ago(3)].invested_kopecks) == (
        60_000,
        60_000,
    )
    assert (by_date[days_ago(2)].market_value_kopecks, by_date[days_ago(2)].invested_kopecks) == (
        72_000,
        60_000,
    )
    assert by_date[today_local()].market_value_kopecks == 72_000
    assert not any(point.is_partial for point in points)


def test_series_uses_cost_and_marks_partial_before_the_first_quote(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=10, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(2), price_micro=120_000_000)

    by_date = _by_date(dashboard_service.compute_series(db_session, "1M"))

    for offset in (5, 4, 3):
        point = by_date[days_ago(offset)]
        assert point.market_value_kopecks == 100_000
        assert point.invested_kopecks == 100_000
        assert point.is_partial

    for offset in (2, 1, 0):
        point = by_date[days_ago(offset)]
        assert point.market_value_kopecks == 120_000
        assert point.is_partial is False


def test_series_without_any_quote_uses_cost_for_every_point(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(2), quantity=2, price_micro=50_000_000)

    points = dashboard_service.compute_series(db_session, "1M")

    assert [point.market_value_kopecks for point in points] == [10_000, 10_000, 10_000]
    assert [point.invested_kopecks for point in points] == [10_000, 10_000, 10_000]
    assert all(point.is_partial for point in points)


def test_series_values_bond_percent_quotes_at_face_on_the_quote_date(
    db_session: Session,
) -> None:
    bond = make_asset(db_session, secid="SU26238RMFS4", asset_type=AssetType.BOND)
    add_operation(
        db_session,
        bond,
        trade_date=days_ago(5),
        quantity=2,
        price_micro=950_000_000,
    )
    add_amortization(
        db_session,
        bond,
        amortization_date=days_ago(3),
        amount_per_unit_kopecks=20_000,
    )
    add_quote(db_session, bond, quote_date=days_ago(5), price_micro=95_000_000)
    add_quote(db_session, bond, quote_date=days_ago(2), price_micro=98_000_000)

    by_date = _by_date(dashboard_service.compute_series(db_session, "1M"))

    # The quote from day -5 predates the amortization, so its face value is
    # still 1000 RUB even after the amortization date.
    assert by_date[days_ago(5)].market_value_kopecks == 190_000
    assert by_date[days_ago(4)].market_value_kopecks == 190_000
    assert by_date[days_ago(3)].market_value_kopecks == 190_000
    # A quote after the amortization uses the reduced 800 RUB face value.
    assert by_date[days_ago(2)].market_value_kopecks == 156_800
    assert by_date[today_local()].market_value_kopecks == 156_800
    assert by_date[today_local()].invested_kopecks == 190_000


def test_series_honours_a_manual_bond_ruble_quote(db_session: Session) -> None:
    bond = make_asset(db_session, secid="SU26238RMFS4", asset_type=AssetType.BOND)
    add_operation(
        db_session,
        bond,
        trade_date=days_ago(4),
        quantity=2,
        price_micro=900_000_000,
    )
    add_quote(
        db_session,
        bond,
        quote_date=days_ago(2),
        price_micro=1_000_000_000,
        price_type=PriceType.RUB,
    )

    by_date = _by_date(dashboard_service.compute_series(db_session, "1M"))

    assert (by_date[days_ago(4)].market_value_kopecks, by_date[days_ago(4)].is_partial) == (
        180_000,
        True,
    )
    assert (by_date[days_ago(3)].market_value_kopecks, by_date[days_ago(3)].is_partial) == (
        180_000,
        True,
    )
    assert (by_date[days_ago(2)].market_value_kopecks, by_date[days_ago(2)].is_partial) == (
        200_000,
        False,
    )
    assert by_date[today_local()].market_value_kopecks == 200_000


def test_fully_closed_position_contributes_zero(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=10, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(5), price_micro=100_000_000)
    add_operation(
        db_session,
        stock,
        trade_date=days_ago(2),
        quantity=10,
        price_micro=150_000_000,
        type=OperationType.SELL,
    )

    by_date = _by_date(dashboard_service.compute_series(db_session, "1M"))

    assert by_date[days_ago(3)].market_value_kopecks == 100_000
    assert by_date[days_ago(2)].market_value_kopecks == 0
    assert by_date[days_ago(2)].invested_kopecks == 0
    assert by_date[today_local()].market_value_kopecks == 0
    assert by_date[today_local()].invested_kopecks == 0


@pytest.mark.parametrize(
    ("period", "first_offset", "expected_length"),
    [
        ("1M", 30, 31),
        ("3M", 90, 91),
        ("1Y", 365, 366),
        ("ALL", 400, 401),
    ],
)
def test_period_boundaries(
    db_session: Session,
    period: str,
    first_offset: int,
    expected_length: int,
) -> None:
    stock = make_asset(db_session)
    add_operation(
        db_session,
        stock,
        trade_date=days_ago(400),
        quantity=1,
        price_micro=100_000_000,
    )
    add_quote(db_session, stock, quote_date=days_ago(400), price_micro=100_000_000)

    points = dashboard_service.compute_series(db_session, period)

    assert len(points) == expected_length
    assert points[0].date == days_ago(first_offset)
    assert points[-1].date == today_local()


def test_period_never_starts_before_the_first_operation(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(10), quantity=1, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(10), price_micro=100_000_000)

    points = dashboard_service.compute_series(db_session, "1M")

    assert len(points) == 11
    assert points[0].date == days_ago(10)


def test_empty_and_future_only_portfolios_produce_no_series(db_session: Session) -> None:
    for period in ("1M", "3M", "1Y", "ALL"):
        assert dashboard_service.compute_series(db_session, period) == []

    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(-5), quantity=1, price_micro=100_000_000)

    for period in ("1M", "3M", "1Y", "ALL"):
        assert dashboard_service.compute_series(db_session, period) == []


def test_series_rounding_uses_exact_integers(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(
        db_session,
        stock,
        trade_date=days_ago(1),
        quantity=3,
        price_micro=33_333_333,
    )
    add_quote(db_session, stock, quote_date=days_ago(1), price_micro=33_333_333)
    add_operation(
        db_session,
        stock,
        trade_date=today_local(),
        quantity=1,
        price_micro=40_000_000,
        type=OperationType.SELL,
    )

    by_date = _by_date(dashboard_service.compute_series(db_session, "1M"))

    # 3 * 33.333333 = 99.999999 RUB, rounded half up to 100.00.
    assert by_date[days_ago(1)].market_value_kopecks == 10_000
    assert by_date[days_ago(1)].invested_kopecks == 10_000
    # Proportional release: 10000 / 3 = 3333.33 kopecks -> 3333.
    assert by_date[today_local()].invested_kopecks == 6_667
    # 2 * 33.333333 = 66.666666 RUB -> 6666.67 kopecks -> 6667.
    assert by_date[today_local()].market_value_kopecks == 6_667
    for point in by_date.values():
        assert type(point.market_value_kopecks) is int
        assert type(point.invested_kopecks) is int


def test_value_on_date_matches_the_series(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(4), quantity=10, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(2), price_micro=120_000_000)

    assert dashboard_service.value_on_date(db_session, days_ago(3)) == (100_000, 100_000, True)
    assert dashboard_service.value_on_date(db_session, days_ago(2)) == (120_000, 100_000, False)
    assert dashboard_service.value_on_date(db_session, days_ago(10)) == (0, 0, False)


def _float_literals(module_path: str) -> list[ast.Constant]:
    tree = ast.parse(Path(module_path).read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    ]


def test_new_services_contain_no_float_literals() -> None:
    """Guard against accidental float arithmetic in the new services."""

    for module in (dashboard_service, snapshot_service):
        assert _float_literals(module.__file__) == []
