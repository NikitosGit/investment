"""Income service tests: expected coupons, manual incomes, views and totals."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, IncomeKind, IncomeStatus
from app.core.errors import AppError, ErrorCode
from app.db.models.income import Income
from app.services import income_service

from income_helpers import (  # isort: skip
    TODAY,
    buy,
    make_asset,
    make_expected,
    make_paid,
)


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(income_service, "today_local", lambda: TODAY)


def test_expected_amount_is_zero_without_per_unit(db_session: Session) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset, per_unit_micro=None, external_id=None)

    assert income_service.expected_amount(coupon, 10) == 0


def test_expected_amount_rounds_half_up(db_session: Session) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset, per_unit_micro=33_333_333)

    assert income_service.expected_amount(coupon, 3) == 10_000
    assert income_service.expected_amount(coupon, 0) == 0


def test_create_manual_dividend_defaults_to_current_quantity(db_session: Session) -> None:
    asset = make_asset(db_session)
    buy(db_session, asset, quantity=10)
    buy(db_session, asset, quantity=5, trade_date=date(2026, 2, 1))

    income = income_service.create_manual(
        db_session,
        asset_id=asset.id,
        kind=IncomeKind.DIVIDEND,
        amount_total=Decimal("200.00"),
        pay_date=date(2026, 7, 15),
        note="Выплата за 2025 год",
    )

    assert income.status is IncomeStatus.PAID
    assert income.source is DataSource.MANUAL
    assert income.currency == "RUB"
    assert income.external_id is None
    assert income.quantity == 15
    assert income.amount_total_kopecks == 20_000
    # 200 / 15 rounds to six decimals and is not fed back into the total.
    assert income.amount_per_unit_micro == 13_333_333
    assert income.note == "Выплата за 2025 год"


def test_create_manual_coupon_derives_per_unit(db_session: Session) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND, secid="SU26238RMFS4")
    buy(db_session, asset, quantity=15)

    income = income_service.create_manual(
        db_session,
        asset_id=asset.id,
        kind=IncomeKind.COUPON,
        amount_total=Decimal("525.00"),
        pay_date=date(2026, 12, 1),
    )

    assert income.quantity == 15
    assert income.amount_total_kopecks == 52_500
    assert income.amount_per_unit_micro == 35_000_000


def test_create_manual_ignores_conflicting_per_unit(db_session: Session) -> None:
    asset = make_asset(db_session)
    buy(db_session, asset, quantity=3)

    income = income_service.create_manual(
        db_session,
        asset_id=asset.id,
        kind=IncomeKind.DIVIDEND,
        amount_total=Decimal("100.00"),
        amount_per_unit=Decimal("30.00"),
        quantity=3,
        pay_date=date(2026, 7, 15),
    )

    # The total is authoritative: 100 / 3, not the supplied 30.
    assert income.amount_total_kopecks == 10_000
    assert income.amount_per_unit_micro == 33_333_333


def test_create_manual_without_position_stores_zero_quantity(db_session: Session) -> None:
    asset = make_asset(db_session)

    income = income_service.create_manual(
        db_session,
        asset_id=asset.id,
        kind=IncomeKind.DIVIDEND,
        amount_total=Decimal("50.00"),
        amount_per_unit=Decimal("30.00"),
        quantity=0,
        pay_date=date(2026, 7, 15),
    )

    assert income.quantity == 0
    assert income.amount_total_kopecks == 5_000
    assert income.amount_per_unit_micro is None


def test_create_manual_rejects_unknown_asset(db_session: Session) -> None:
    with pytest.raises(AppError) as error:
        income_service.create_manual(
            db_session,
            asset_id=999,
            kind=IncomeKind.DIVIDEND,
            amount_total=Decimal("10.00"),
            pay_date=date(2026, 7, 15),
        )

    assert error.value.code == ErrorCode.ASSET_NOT_FOUND
    assert error.value.status_code == 404


def test_create_manual_rejects_non_positive_total(db_session: Session) -> None:
    asset = make_asset(db_session)

    with pytest.raises(AppError) as error:
        income_service.create_manual(
            db_session,
            asset_id=asset.id,
            kind=IncomeKind.DIVIDEND,
            amount_total=Decimal("0"),
            pay_date=date(2026, 7, 15),
        )

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400


def test_views_flag_overdue_expected_only(db_session: Session, fixed_today: None) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    overdue = make_expected(
        db_session,
        asset,
        pay_date=date(2026, 6, 1),
        external_id="moex:coupon:TEST:2026-06-01",
    )
    paid = make_paid(db_session, asset, pay_date=date(2026, 5, 1))

    views = income_service.build_views(db_session, [overdue, paid])

    assert views[0].is_overdue is True
    assert views[1].is_overdue is False


def test_views_use_current_quantity_for_expected_and_stored_for_paid(
    db_session: Session, fixed_today: None
) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset)
    paid = make_paid(db_session, asset, quantity=20, total_kopecks=20_000)
    buy(db_session, asset, quantity=2)

    coupon_view, paid_view = income_service.build_views(db_session, [coupon, paid])

    assert coupon_view.asset_secid == "SBER"
    assert coupon_view.quantity == 2
    assert coupon_view.amount_total_kopecks == 7_080
    assert paid_view.quantity == 20
    assert paid_view.amount_total_kopecks == 20_000


def test_views_of_expected_without_position_are_zero(
    db_session: Session, fixed_today: None
) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset)

    (view,) = income_service.build_views(db_session, [coupon])

    assert view.quantity == 0
    assert view.amount_total_kopecks == 0


def test_build_views_of_empty_sequence(db_session: Session) -> None:
    assert income_service.build_views(db_session, []) == []


def test_totals_sums_paid_and_expected(db_session: Session, fixed_today: None) -> None:
    first = make_asset(db_session, secid="SBER")
    second = make_asset(db_session, asset_type=AssetType.BOND, secid="SU26238RMFS4")
    buy(db_session, first, quantity=15)
    buy(db_session, second, quantity=10)
    make_paid(db_session, first, quantity=15, total_kopecks=20_000)
    make_paid(
        db_session,
        first,
        quantity=15,
        total_kopecks=10_000,
        kind=IncomeKind.COUPON,
        per_unit_micro=None,
    )
    # Overdue EXPECTED coupon: totals are not limited to future pay dates.
    make_expected(
        db_session, first, pay_date=date(2026, 6, 1), external_id="moex:coupon:1:2026-06-01"
    )
    make_expected(
        db_session, first, pay_date=date(2026, 7, 1), external_id="moex:coupon:1:2026-07-01"
    )
    make_expected(
        db_session,
        second,
        pay_date=date(2026, 8, 1),
        per_unit_micro=36_000_000,
        external_id="moex:coupon:2:2026-08-01",
    )

    totals = income_service.totals(db_session)

    assert totals.dividends_paid_kopecks == 20_000
    assert totals.coupons_paid_kopecks == 10_000
    # Two coupons of the first asset (15 bonds * 35.40) plus one of the second.
    assert totals.expected_coupons_kopecks == 53_100 + 53_100 + 36_000


def test_list_filters_and_orders(db_session: Session) -> None:
    first = make_asset(db_session, secid="SBER")
    second = make_asset(db_session, asset_type=AssetType.BOND, secid="SU26238RMFS4")
    make_paid(db_session, first, pay_date=date(2026, 7, 15))
    make_paid(db_session, second, kind=IncomeKind.COUPON, pay_date=date(2026, 3, 1))
    make_expected(db_session, second, pay_date=date(2026, 9, 1))

    assert [item.pay_date for item in income_service.list_incomes(db_session)] == [
        date(2026, 3, 1),
        date(2026, 7, 15),
        date(2026, 9, 1),
    ]
    paid = income_service.list_incomes(db_session, status=IncomeStatus.PAID)
    assert len(paid) == 2
    coupons = income_service.list_incomes(db_session, kind=IncomeKind.COUPON)
    assert len(coupons) == 2
    by_asset = income_service.list_incomes(db_session, asset_id=first.id)
    assert [item.asset_id for item in by_asset] == [first.id]
    in_range = income_service.list_incomes(
        db_session, from_date=date(2026, 3, 1), to_date=date(2026, 7, 15)
    )
    assert [item.pay_date for item in in_range] == [date(2026, 3, 1), date(2026, 7, 15)]


def test_list_income_views_returns_computed_amounts(db_session: Session, fixed_today: None) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    buy(db_session, asset, quantity=15)
    make_expected(db_session, asset, pay_date=date(2026, 7, 1))

    (view,) = income_service.list_income_views(db_session)

    assert view.asset_secid == "SBER"
    assert view.quantity == 15
    assert view.amount_total_kopecks == 53_100
    assert view.is_overdue is False


def test_get_income_returns_404(db_session: Session) -> None:
    with pytest.raises(AppError) as error:
        income_service.get_income(db_session, 42)

    assert error.value.code == ErrorCode.NOT_FOUND
    assert error.value.message == "Доход 42 не найден"


def test_delete_income(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset)

    income_service.delete_income(db_session, income.id)

    assert db_session.scalars(select(Income)).all() == []
    with pytest.raises(AppError) as error:
        income_service.delete_income(db_session, income.id)
    assert error.value.code == ErrorCode.NOT_FOUND
