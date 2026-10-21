"""Coupon synchronization tests backed by respx; no real network access."""

from collections.abc import Callable, Iterator
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, IncomeKind, IncomeStatus
from app.core.errors import AppError, ErrorCode
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.providers.moex.client import MoexClient
from app.providers.moex.schemas import Bondization, CouponInfo
from app.services import bondization_service, income_service, portfolio_service

BASE_URL = "https://iss.moex.com/iss"
TODAY = date(2026, 1, 1)
SECID = "SU26238RMFS4"


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bondization_service, "today_local", lambda: TODAY)
    monkeypatch.setattr(income_service, "today_local", lambda: TODAY)


@pytest.fixture
def moex_client() -> Iterator[MoexClient]:
    with MoexClient(BASE_URL, retries=0, min_request_interval=0) as client:
        yield client


def _asset(session: Session) -> Asset:
    asset = Asset(
        secid=SECID,
        name="ОФЗ 26238",
        type=AssetType.BOND,
        engine="stock",
        market="bonds",
        board="TQCB",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=100_000,
    )
    session.add(asset)
    session.commit()
    return asset


def _payload(coupons: list[list[Any]]) -> dict[str, Any]:
    return {
        "coupons": {
            "columns": ["coupondate", "value", "value_rub", "valueprc", "recorddate"],
            "data": coupons,
        },
        "amortizations": {
            "columns": ["amortizationdate", "value", "value_rub", "valueprc"],
            "data": [],
        },
    }


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


@respx.mock
def test_sync_creates_only_upcoming_expected_coupons(
    db_session: Session,
    moex_client: MoexClient,
    fixed_today: None,
    load_fixture: Callable[..., Any],
) -> None:
    asset = _asset(db_session)
    respx.get(f"{BASE_URL}/securities/{SECID}/bondization.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "bondization_ofz_schedule.json"))
    )

    upcoming = income_service.sync_coupons(db_session, moex_client, asset)
    db_session.commit()

    assert upcoming == 2
    coupons = db_session.scalars(select(Income).order_by(Income.pay_date)).all()
    assert [coupon.pay_date for coupon in coupons] == [date(2026, 6, 1), date(2026, 12, 1)]
    assert all(coupon.status is IncomeStatus.EXPECTED for coupon in coupons)
    assert all(coupon.kind is IncomeKind.COUPON for coupon in coupons)
    assert all(coupon.source is DataSource.MOEX for coupon in coupons)
    assert all(coupon.portfolio_id == 1 for coupon in coupons)
    assert [coupon.amount_per_unit_micro for coupon in coupons] == [35_400_000, 36_000_000]
    assert coupons[0].external_id == f"moex:coupon:{SECID}:2026-06-01"


@respx.mock
def test_sync_is_idempotent(
    db_session: Session,
    moex_client: MoexClient,
    fixed_today: None,
    load_fixture: Callable[..., Any],
) -> None:
    asset = _asset(db_session)
    payload = load_fixture("moex", "bondization_ofz_schedule.json")
    respx.get(f"{BASE_URL}/securities/{SECID}/bondization.json").mock(
        side_effect=[httpx.Response(200, json=payload), httpx.Response(200, json=payload)]
    )

    first = income_service.sync_coupons(db_session, moex_client, asset)
    db_session.commit()
    second = income_service.sync_coupons(db_session, moex_client, asset)
    db_session.commit()

    assert (first, second) == (2, 2)
    assert _count(db_session, Income) == 2
    assert _count(db_session, BondAmortization) == 2


@respx.mock
def test_sync_does_not_overwrite_paid_coupon(
    db_session: Session, moex_client: MoexClient, fixed_today: None
) -> None:
    asset = _asset(db_session)
    portfolio = portfolio_service.ensure_default_portfolio(db_session)
    bondization_service.sync_bondization(
        db_session,
        asset,
        Bondization(
            coupons=[
                CouponInfo(date(2026, 6, 1), date(2026, 5, 25), 35_400_000),
                CouponInfo(date(2026, 12, 1), date(2026, 11, 24), 35_400_000),
            ]
        ),
        portfolio_id=portfolio.id,
    )
    db_session.commit()
    coupon = db_session.scalars(select(Income).where(Income.pay_date == date(2026, 6, 1))).one()
    income_service.mark_paid(db_session, coupon.id)
    assert coupon.status is IncomeStatus.PAID
    assert coupon.amount_total_kopecks == 0

    respx.get(f"{BASE_URL}/securities/{SECID}/bondization.json").mock(
        return_value=httpx.Response(
            200,
            json=_payload(
                [
                    ["2026-06-01", "99.0", "99.00", "9.90", "2026-05-25"],
                    ["2026-12-01", "40.0", "40.00", "4.00", "2026-11-24"],
                ]
            ),
        )
    )

    upcoming = income_service.sync_coupons(db_session, moex_client, asset)
    db_session.commit()

    assert upcoming == 1
    db_session.refresh(coupon)
    assert coupon.status is IncomeStatus.PAID
    assert coupon.amount_per_unit_micro == 35_400_000
    expected = db_session.scalars(select(Income).where(Income.pay_date == date(2026, 12, 1))).one()
    assert expected.status is IncomeStatus.EXPECTED
    assert expected.amount_per_unit_micro == 40_000_000


@respx.mock
def test_sync_skips_past_coupons(
    db_session: Session, moex_client: MoexClient, fixed_today: None
) -> None:
    asset = _asset(db_session)
    respx.get(f"{BASE_URL}/securities/{SECID}/bondization.json").mock(
        return_value=httpx.Response(
            200,
            json=_payload([["2025-12-01", "35.4", "35.40", "3.54", "2025-11-24"]]),
        )
    )

    upcoming = income_service.sync_coupons(db_session, moex_client, asset)
    db_session.commit()

    assert upcoming == 0
    assert _count(db_session, Income) == 0


def test_sync_includes_coupon_due_today_and_skips_yesterday(
    db_session: Session, fixed_today: None
) -> None:
    asset = _asset(db_session)
    portfolio = portfolio_service.ensure_default_portfolio(db_session)

    bondization_service.sync_bondization(
        db_session,
        asset,
        Bondization(
            coupons=[
                CouponInfo(TODAY - timedelta(days=1), None, 10_000_000),
                CouponInfo(TODAY, None, 20_000_000),
            ]
        ),
        portfolio_id=portfolio.id,
    )
    db_session.commit()

    coupons = db_session.scalars(select(Income).order_by(Income.pay_date)).all()
    assert [coupon.pay_date for coupon in coupons] == [TODAY]
    assert coupons[0].amount_per_unit_micro == 20_000_000
    assert coupons[0].status is IncomeStatus.EXPECTED


@respx.mock
def test_sync_failure_leaves_transaction_to_caller(
    db_session: Session, moex_client: MoexClient, fixed_today: None
) -> None:
    asset = _asset(db_session)
    respx.get(f"{BASE_URL}/securities/{SECID}/bondization.json").mock(
        return_value=httpx.Response(500)
    )

    with pytest.raises(AppError) as error:
        income_service.sync_coupons(db_session, moex_client, asset)

    assert error.value.code == ErrorCode.MOEX_UNAVAILABLE
    assert error.value.status_code == 502
    # sync_coupons never rolls back; the caller owns the transaction.
    db_session.rollback()
    assert _count(db_session, Income) == 0
