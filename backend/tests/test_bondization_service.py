"""Bondization service tests: schedules, face value and idempotency."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, IncomeStatus
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.providers.moex.schemas import AmortizationInfo, Bondization, CouponInfo
from app.services import bondization_service, portfolio_service

TODAY = date(2026, 1, 1)


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> date:
    """Pin the service date source so coupon filtering is deterministic."""

    monkeypatch.setattr(bondization_service, "today_local", lambda: TODAY)
    return TODAY


@pytest.fixture
def portfolio_id(db_session: Session) -> int:
    """Create the single portfolio and return its id."""

    return portfolio_service.ensure_default_portfolio(db_session).id


def _create_asset(
    session: Session,
    *,
    asset_type: AssetType = AssetType.BOND,
    face_value_kopecks: int | None = 100_000,
    secid: str = "TESTBOND",
) -> Asset:
    asset = Asset(
        secid=secid,
        name="Тестовая бумага",
        type=asset_type,
        engine="stock",
        market="bonds" if asset_type is AssetType.BOND else "shares",
        board="TQCB" if asset_type is AssetType.BOND else "TQBR",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=face_value_kopecks,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_current_face_value_accounts_for_amortization(
    db_session: Session, fixed_today: date, portfolio_id: int
) -> None:
    asset = _create_asset(db_session)
    schedule = Bondization(
        amortizations=[
            AmortizationInfo(amortization_date=date(2026, 3, 1), amount_per_unit_kopecks=20_000)
        ]
    )

    bondization_service.sync_bondization(db_session, asset, schedule, portfolio_id=portfolio_id)
    db_session.commit()

    assert (
        bondization_service.current_face_value_kopecks(db_session, asset, date(2026, 2, 1))
        == 100_000
    )
    assert (
        bondization_service.current_face_value_kopecks(db_session, asset, date(2026, 3, 1))
        == 80_000
    )


def test_current_face_value_is_clamped_at_zero(
    db_session: Session, fixed_today: date, portfolio_id: int
) -> None:
    asset = _create_asset(db_session, face_value_kopecks=100_000)
    schedule = Bondization(
        amortizations=[
            AmortizationInfo(amortization_date=date(2026, 3, 1), amount_per_unit_kopecks=120_000)
        ]
    )

    bondization_service.sync_bondization(db_session, asset, schedule, portfolio_id=portfolio_id)
    db_session.commit()

    assert bondization_service.current_face_value_kopecks(db_session, asset, date(2026, 3, 1)) == 0


def test_current_face_value_is_none_for_stock(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_type=AssetType.STOCK, face_value_kopecks=None)

    assert (
        bondization_service.current_face_value_kopecks(db_session, asset, date(2026, 1, 1)) is None
    )


def test_pure_face_value_helpers_return_none_for_stock(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_type=AssetType.STOCK, face_value_kopecks=None)

    assert bondization_service.face_value_from_amortized(asset, 20_000) is None
    assert bondization_service.face_value_on(asset, [], date(2026, 1, 1)) is None


def test_face_value_on_includes_amortization_on_the_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    amortization = BondAmortization(
        asset_id=asset.id,
        amortization_date=date(2026, 3, 1),
        amount_per_unit_kopecks=20_000,
        source=DataSource.MANUAL,
    )

    assert bondization_service.face_value_on(asset, [amortization], date(2026, 2, 28)) == 100_000
    assert bondization_service.face_value_on(asset, [amortization], date(2026, 3, 1)) == 80_000


def test_sync_is_idempotent(db_session: Session, fixed_today: date, portfolio_id: int) -> None:
    asset = _create_asset(db_session)
    schedule = Bondization(
        coupons=[CouponInfo(date(2026, 6, 1), date(2026, 5, 25), 35_400_000)],
        amortizations=[AmortizationInfo(date(2030, 1, 1), 20_000)],
    )

    bondization_service.sync_bondization(db_session, asset, schedule, portfolio_id=portfolio_id)
    db_session.commit()
    bondization_service.sync_bondization(db_session, asset, schedule, portfolio_id=portfolio_id)
    db_session.commit()

    assert _count(db_session, Income) == 1
    assert _count(db_session, BondAmortization) == 1


def test_past_coupons_are_skipped(
    db_session: Session, fixed_today: date, portfolio_id: int
) -> None:
    asset = _create_asset(db_session)
    schedule = Bondization(
        coupons=[
            CouponInfo(date(2025, 12, 1), None, 35_400_000),
            CouponInfo(date(2026, 1, 1), None, 35_400_000),
        ]
    )

    bondization_service.sync_bondization(db_session, asset, schedule, portfolio_id=portfolio_id)
    db_session.commit()

    pay_dates = list(db_session.scalars(select(Income.pay_date).order_by(Income.pay_date)))
    assert pay_dates == [date(2026, 1, 1)]


def test_expected_coupon_is_updated(
    db_session: Session, fixed_today: date, portfolio_id: int
) -> None:
    asset = _create_asset(db_session)
    bondization_service.sync_bondization(
        db_session,
        asset,
        Bondization(coupons=[CouponInfo(date(2026, 6, 1), None, 35_400_000)]),
        portfolio_id=portfolio_id,
    )
    db_session.commit()

    bondization_service.sync_bondization(
        db_session,
        asset,
        Bondization(coupons=[CouponInfo(date(2026, 6, 1), None, 40_000_000)]),
        portfolio_id=portfolio_id,
    )
    db_session.commit()

    coupon = db_session.scalars(select(Income)).one()
    assert coupon.amount_per_unit_micro == 40_000_000
    assert coupon.status is IncomeStatus.EXPECTED
    assert coupon.source is DataSource.MOEX


def test_paid_coupon_is_not_overwritten(
    db_session: Session, fixed_today: date, portfolio_id: int
) -> None:
    asset = _create_asset(db_session)
    bondization_service.sync_bondization(
        db_session,
        asset,
        Bondization(coupons=[CouponInfo(date(2026, 6, 1), None, 35_400_000)]),
        portfolio_id=portfolio_id,
    )
    db_session.commit()

    coupon = db_session.scalars(select(Income)).one()
    coupon.status = IncomeStatus.PAID
    coupon.amount_per_unit_micro = 1
    db_session.commit()

    bondization_service.sync_bondization(
        db_session,
        asset,
        Bondization(coupons=[CouponInfo(date(2026, 6, 1), None, 99_000_000)]),
        portfolio_id=portfolio_id,
    )
    db_session.commit()
    db_session.refresh(coupon)

    assert coupon.status is IncomeStatus.PAID
    assert coupon.amount_per_unit_micro == 1


def test_external_ids_follow_moex_convention(
    db_session: Session, fixed_today: date, portfolio_id: int
) -> None:
    asset = _create_asset(db_session, secid="SU26238RMFS4")
    bondization_service.sync_bondization(
        db_session,
        asset,
        Bondization(
            coupons=[CouponInfo(date(2026, 6, 1), None, 35_400_000)],
            amortizations=[AmortizationInfo(date(2030, 1, 1), 20_000)],
        ),
        portfolio_id=portfolio_id,
    )
    db_session.commit()

    assert (
        db_session.scalars(select(Income.external_id)).one()
        == "moex:coupon:SU26238RMFS4:2026-06-01"
    )
    assert (
        db_session.scalars(select(BondAmortization.external_id)).one()
        == "moex:amortization:SU26238RMFS4:2030-01-01"
    )


def test_list_amortizations_is_ordered_by_date(
    db_session: Session, fixed_today: date, portfolio_id: int
) -> None:
    asset = _create_asset(db_session)
    bondization_service.sync_bondization(
        db_session,
        asset,
        Bondization(
            amortizations=[
                AmortizationInfo(date(2031, 1, 1), 30_000),
                AmortizationInfo(date(2030, 1, 1), 20_000),
            ]
        ),
        portfolio_id=portfolio_id,
    )
    db_session.commit()

    dates = [
        item.amortization_date
        for item in bondization_service.list_amortizations(db_session, asset.id)
    ]
    assert dates == [date(2030, 1, 1), date(2031, 1, 1)]
