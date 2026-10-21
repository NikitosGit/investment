"""Income API tests for confirming expected coupons."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, IncomeKind, IncomeStatus
from app.db.models.income import Income
from app.providers.moex.schemas import Bondization, CouponInfo
from app.services import bondization_service, income_service, portfolio_service

from income_api_helpers import api_asset, api_buy, api_income  # isort: skip

TODAY = date(2026, 1, 1)


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bondization_service, "today_local", lambda: TODAY)
    monkeypatch.setattr(income_service, "today_local", lambda: TODAY)


def test_mark_paid_and_second_attempt_conflicts(
    client: TestClient, db_session: Session, fixed_today: None
) -> None:
    bond = api_asset(db_session, asset_type=AssetType.BOND, secid="SU26238RMFS4")
    api_buy(db_session, bond, quantity=15)
    portfolio = portfolio_service.ensure_default_portfolio(db_session)
    bondization_service.sync_bondization(
        db_session,
        bond,
        Bondization(coupons=[CouponInfo(date(2026, 12, 1), date(2026, 11, 24), 35_400_000)]),
        portfolio_id=portfolio.id,
    )
    db_session.commit()
    coupon = db_session.scalars(select(Income)).one()

    response = client.post(f"/api/income/{coupon.id}/mark-paid", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PAID"
    assert body["quantity"] == 15
    assert body["amount_total"] == "531.00"
    assert body["pay_date"] == "2026-12-01"

    again = client.post(f"/api/income/{coupon.id}/mark-paid", json={})

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INCOME_ALREADY_PAID"


def test_mark_paid_with_explicit_amount(client: TestClient, db_session: Session) -> None:
    bond = api_asset(db_session, asset_type=AssetType.BOND)
    api_buy(db_session, bond, quantity=15)
    coupon = api_income(
        db_session,
        bond,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.EXPECTED,
        quantity=None,
        total_kopecks=None,
        per_unit_micro=None,
    )

    response = client.post(
        f"/api/income/{coupon.id}/mark-paid",
        json={"amount_total": "500.00", "pay_date": "2026-12-15"},
    )

    assert response.status_code == 200
    assert response.json()["amount_total"] == "500.00"
    # 500.00 RUB over 15 units, derived from the authoritative total.
    assert response.json()["amount_per_unit"] == "33.33"
    assert response.json()["pay_date"] == "2026-12-15"


def test_mark_paid_without_amount_returns_400(client: TestClient, db_session: Session) -> None:
    bond = api_asset(db_session, asset_type=AssetType.BOND)
    coupon = api_income(
        db_session,
        bond,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.EXPECTED,
        quantity=None,
        total_kopecks=None,
        per_unit_micro=None,
    )

    response = client.post(f"/api/income/{coupon.id}/mark-paid", json={})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Не указана сумма дохода"
