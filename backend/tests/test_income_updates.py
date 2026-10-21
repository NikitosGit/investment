"""Income service tests: paid/expected updates and coupon confirmation."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, IncomeStatus
from app.core.errors import AppError, ErrorCode
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


def test_update_paid_total_derives_per_unit(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10, total_kopecks=100_000)

    updated = income_service.update_income(
        db_session, income.id, {"amount_total": Decimal("500.00")}
    )

    assert updated.amount_total_kopecks == 50_000
    assert updated.amount_per_unit_micro == 50_000_000


def test_update_paid_per_unit_derives_total(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10)

    updated = income_service.update_income(
        db_session, income.id, {"amount_per_unit": Decimal("42.50")}
    )

    assert updated.amount_per_unit_micro == 42_500_000
    assert updated.amount_total_kopecks == 42_500


def test_update_paid_quantity_preserves_recorded_total(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10, total_kopecks=10_000)

    updated = income_service.update_income(db_session, income.id, {"quantity": 7})

    assert updated.quantity == 7
    assert updated.amount_total_kopecks == 10_000
    # 100.00 RUB / 7 units.
    assert updated.amount_per_unit_micro == 14_285_714


def test_update_paid_zero_quantity_preserves_total_and_clears_per_unit(
    db_session: Session,
) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10, total_kopecks=100_000)

    updated = income_service.update_income(db_session, income.id, {"quantity": 0})

    assert updated.quantity == 0
    assert updated.amount_total_kopecks == 100_000
    assert updated.amount_per_unit_micro is None


def test_update_paid_total_with_zero_quantity_clears_per_unit(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(
        db_session, asset, quantity=0, total_kopecks=50_000, per_unit_micro=50_000_000
    )

    updated = income_service.update_income(
        db_session, income.id, {"amount_total": Decimal("300.00")}
    )

    assert updated.quantity == 0
    assert updated.amount_total_kopecks == 30_000
    assert updated.amount_per_unit_micro is None


def test_update_paid_quantity_rederives_per_unit_from_stored_total(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10, total_kopecks=10_000, per_unit_micro=None)

    updated = income_service.update_income(db_session, income.id, {"quantity": 5})

    assert updated.quantity == 5
    assert updated.amount_total_kopecks == 10_000
    # 100.00 RUB / 5 units.
    assert updated.amount_per_unit_micro == 20_000_000


def test_update_paid_without_per_unit_zero_quantity_preserves_total(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10, total_kopecks=10_000, per_unit_micro=None)

    updated = income_service.update_income(db_session, income.id, {"quantity": 0})

    assert updated.amount_total_kopecks == 10_000
    assert updated.amount_per_unit_micro is None


def test_update_paid_total_wins_over_per_unit(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10)

    updated = income_service.update_income(
        db_session,
        income.id,
        {"amount_total": Decimal("500.00"), "amount_per_unit": Decimal("99.00")},
    )

    assert updated.amount_total_kopecks == 50_000
    assert updated.amount_per_unit_micro == 50_000_000


def test_update_paid_quantity_and_total_normalizes_per_unit(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10)

    updated = income_service.update_income(
        db_session,
        income.id,
        {"quantity": 4, "amount_total": Decimal("200.00")},
    )

    assert updated.quantity == 4
    assert updated.amount_total_kopecks == 20_000
    assert updated.amount_per_unit_micro == 50_000_000


def test_update_paid_quantity_and_per_unit_derives_total(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset, quantity=10, total_kopecks=10_000)

    updated = income_service.update_income(
        db_session,
        income.id,
        {"quantity": 4, "amount_per_unit": Decimal("25.00")},
    )

    assert updated.quantity == 4
    assert updated.amount_per_unit_micro == 25_000_000
    assert updated.amount_total_kopecks == 10_000


def test_update_paid_record_date_and_note(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset)

    updated = income_service.update_income(
        db_session, income.id, {"record_date": date(2026, 4, 25), "note": None}
    )

    assert updated.record_date == date(2026, 4, 25)
    assert updated.note is None
    assert updated.amount_total_kopecks == 10_000


@pytest.mark.parametrize(
    "changes",
    [{"amount_per_unit": Decimal("0")}, {"quantity": -1}],
)
def test_update_paid_rejects_invalid_values(db_session: Session, changes: dict) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset)

    with pytest.raises(AppError) as error:
        income_service.update_income(db_session, income.id, changes)

    assert error.value.code == ErrorCode.BAD_REQUEST


def test_update_paid_requires_stored_invariants(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset)
    income.quantity = None
    db_session.commit()

    with pytest.raises(AppError) as error:
        income_service.update_income(db_session, income.id, {"note": "x"})

    assert error.value.code == ErrorCode.BAD_REQUEST


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 5},
        {"amount_total": Decimal("10.00")},
        {"pay_date": date(2026, 8, 1)},
    ],
)
def test_update_expected_rejects_computed_fields(db_session: Session, changes: dict) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset, pay_date=date(2026, 7, 1))

    with pytest.raises(AppError) as error:
        income_service.update_income(db_session, coupon.id, changes)

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    db_session.refresh(coupon)
    assert coupon.pay_date == date(2026, 7, 1)
    assert coupon.status is IncomeStatus.EXPECTED


def test_update_expected_rejects_per_unit_for_moex(db_session: Session) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset)
    original = coupon.amount_per_unit_micro

    with pytest.raises(AppError) as error:
        income_service.update_income(db_session, coupon.id, {"amount_per_unit": Decimal("36.00")})

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    db_session.refresh(coupon)
    assert coupon.amount_per_unit_micro == original
    assert coupon.status is IncomeStatus.EXPECTED


def test_update_expected_allows_record_date_and_note(db_session: Session) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset)
    original = coupon.amount_per_unit_micro

    updated = income_service.update_income(
        db_session,
        coupon.id,
        {"record_date": date(2026, 6, 20), "note": "Уточнено"},
    )

    assert updated.amount_per_unit_micro == original
    assert updated.record_date == date(2026, 6, 20)
    assert updated.note == "Уточнено"
    assert updated.status is IncomeStatus.EXPECTED


def test_update_expected_allows_per_unit_for_manual(db_session: Session) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset, external_id=None)
    assert coupon.source is DataSource.MANUAL

    updated = income_service.update_income(
        db_session, coupon.id, {"amount_per_unit": Decimal("36.00")}
    )

    assert updated.amount_per_unit_micro == 36_000_000


def test_update_rejects_unknown_fields(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset)

    with pytest.raises(AppError) as error:
        income_service.update_income(db_session, income.id, {"asset_id": 2})

    assert error.value.code == ErrorCode.BAD_REQUEST


def test_update_unknown_income_returns_404(db_session: Session) -> None:
    with pytest.raises(AppError) as error:
        income_service.update_income(db_session, 999, {"note": "x"})

    assert error.value.code == ErrorCode.NOT_FOUND


def test_mark_paid_computes_from_expected(db_session: Session, fixed_today: None) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND, secid="SU26238RMFS4")
    buy(db_session, asset, quantity=15)
    coupon = make_expected(db_session, asset)

    paid = income_service.mark_paid(db_session, coupon.id)

    assert paid.status is IncomeStatus.PAID
    assert paid.quantity == 15
    assert paid.amount_total_kopecks == 53_100
    assert paid.pay_date == date(2026, 7, 1)
    assert paid.source is DataSource.MOEX
    assert paid.external_id == "moex:coupon:TEST:2026-07-01"


def test_mark_paid_accepts_explicit_amount_and_date(db_session: Session, fixed_today: None) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    buy(db_session, asset, quantity=10)
    coupon = make_expected(db_session, asset)

    paid = income_service.mark_paid(
        db_session,
        coupon.id,
        amount_total=Decimal("500.00"),
        pay_date=date(2026, 7, 20),
    )

    assert paid.amount_total_kopecks == 50_000
    assert paid.amount_per_unit_micro == 50_000_000
    assert paid.pay_date == date(2026, 7, 20)


def test_mark_paid_explicit_total_with_zero_quantity_clears_per_unit(
    db_session: Session, fixed_today: None
) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset)

    paid = income_service.mark_paid(db_session, coupon.id, amount_total=Decimal("500.00"))

    assert paid.quantity == 0
    assert paid.amount_total_kopecks == 50_000
    assert paid.amount_per_unit_micro is None


def test_mark_paid_twice_returns_409(db_session: Session) -> None:
    asset = make_asset(db_session)
    income = make_paid(db_session, asset)

    with pytest.raises(AppError) as error:
        income_service.mark_paid(db_session, income.id)

    assert error.value.code == ErrorCode.INCOME_ALREADY_PAID
    assert error.value.status_code == 409


def test_mark_paid_without_amount_data_returns_400(db_session: Session) -> None:
    asset = make_asset(db_session, asset_type=AssetType.BOND)
    coupon = make_expected(db_session, asset, per_unit_micro=None, external_id=None)

    with pytest.raises(AppError) as error:
        income_service.mark_paid(db_session, coupon.id)

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.message == "Не указана сумма дохода"
