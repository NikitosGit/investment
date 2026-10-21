"""Income API tests: listing, formats, creation and updates."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, IncomeKind, IncomeStatus
from app.db.models.income import Income
from app.services import income_service

from income_api_helpers import api_asset, api_buy, api_income, api_payload  # isort: skip

TODAY = date(2026, 1, 1)


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(income_service, "today_local", lambda: TODAY)


def test_list_returns_contract_and_totals(
    client: TestClient, db_session: Session, fixed_today: None
) -> None:
    stock = api_asset(db_session)
    bond = api_asset(db_session, asset_type=AssetType.BOND, secid="SU26238RMFS4")
    api_buy(db_session, stock)
    api_buy(db_session, bond, quantity=15)
    api_income(db_session, stock)
    api_income(
        db_session,
        bond,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.EXPECTED,
        quantity=None,
        total_kopecks=None,
        per_unit_micro=35_400_000,
        pay_date=date(2026, 12, 1),
    )

    response = client.get("/api/income")

    assert response.status_code == 200
    body = response.json()
    assert [item["kind"] for item in body["items"]] == ["DIVIDEND", "COUPON"]
    item = body["items"][0]
    assert item == {
        "id": item["id"],
        "asset_id": stock.id,
        "asset_secid": "SBER",
        "kind": "DIVIDEND",
        "status": "PAID",
        "amount_per_unit": "10.00",
        "quantity": 20,
        "amount_total": "200.00",
        "currency": "RUB",
        "record_date": None,
        "pay_date": "2026-07-15",
        "source": "MANUAL",
        "note": None,
        "is_overdue": False,
    }
    coupon = body["items"][1]
    assert coupon["quantity"] == 15
    assert coupon["amount_total"] == "531.00"
    assert coupon["amount_per_unit"] == "35.40"
    assert coupon["source"] == "MANUAL"

    assert body["totals"] == {
        "dividends_paid": "200.00",
        "coupons_paid": "0.00",
        "expected_coupons": "531.00",
    }


def test_list_filters(client: TestClient, db_session: Session) -> None:
    stock = api_asset(db_session)
    bond = api_asset(db_session, asset_type=AssetType.BOND, secid="SU26238RMFS4")
    api_buy(db_session, stock)
    api_buy(db_session, bond, quantity=15)
    first = api_income(db_session, stock, pay_date=date(2026, 7, 15))
    second = api_income(
        db_session,
        bond,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.EXPECTED,
        quantity=None,
        total_kopecks=None,
        per_unit_micro=35_400_000,
        pay_date=date(2026, 9, 1),
    )

    paid_body = client.get("/api/income", params={"status": "PAID"}).json()
    assert [item["id"] for item in paid_body["items"]] == [first.id]
    # Totals stay portfolio-wide even when the list is filtered.
    assert paid_body["totals"] == {
        "dividends_paid": "200.00",
        "coupons_paid": "0.00",
        "expected_coupons": "531.00",
    }

    by_kind = client.get("/api/income", params={"kind": "COUPON"}).json()["items"]
    assert [item["id"] for item in by_kind] == [second.id]

    by_asset = client.get("/api/income", params={"asset_id": bond.id}).json()["items"]
    assert [item["id"] for item in by_asset] == [second.id]

    in_range = client.get("/api/income", params={"from": "2026-07-15", "to": "2026-08-31"}).json()[
        "items"
    ]
    assert [item["id"] for item in in_range] == [first.id]


def test_create_dividend(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)
    api_buy(db_session, asset)

    response = client.post("/api/income", json=api_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["asset_id"] == asset.id
    assert body["asset_secid"] == "SBER"
    assert body["kind"] == "DIVIDEND"
    assert body["status"] == "PAID"
    assert body["amount_per_unit"] == "10.00"
    assert body["amount_total"] == "200.00"
    assert body["quantity"] == 20
    assert body["source"] == "MANUAL"
    assert body["note"] == "Выплата за 2025 год"
    assert body["is_overdue"] is False

    db_session.rollback()
    stored = db_session.scalars(select(Income)).one()
    assert stored.amount_total_kopecks == 20_000
    assert stored.external_id is None
    assert stored.currency == "RUB"


def test_create_manual_coupon(client: TestClient, db_session: Session) -> None:
    bond = api_asset(db_session, asset_type=AssetType.BOND, secid="SU26238RMFS4")
    api_buy(db_session, bond, quantity=15)

    response = client.post(
        "/api/income",
        json=api_payload(
            asset_id=bond.id,
            kind="COUPON",
            quantity=15,
            amount_total="525.00",
            amount_per_unit=None,
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "COUPON"
    assert body["amount_total"] == "525.00"
    assert body["amount_per_unit"] == "35.00"


def test_create_with_zero_quantity_is_accepted(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)

    response = client.post(
        "/api/income",
        json=api_payload(asset_id=asset.id, quantity=0, amount_per_unit=None),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 0
    assert body["amount_total"] == "200.00"
    assert body["amount_per_unit"] is None


def test_patch_paid_values(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)
    income = api_income(db_session, asset)

    response = client.patch(
        f"/api/income/{income.id}",
        json={"amount_total": "250.00", "pay_date": "2026-07-20", "note": "Уточнено"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["amount_total"] == "250.00"
    assert body["amount_per_unit"] == "12.50"
    assert body["pay_date"] == "2026-07-20"
    assert body["note"] == "Уточнено"


def test_patch_paid_quantity_zero_preserves_total(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)
    income = api_income(db_session, asset)

    response = client.patch(f"/api/income/{income.id}", json={"quantity": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["quantity"] == 0
    assert body["amount_total"] == "200.00"
    assert body["amount_per_unit"] is None


def test_patch_can_clear_record_date_and_note(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)
    income = api_income(db_session, asset)
    income.record_date = date(2026, 6, 1)
    income.note = "Черновик"
    db_session.commit()

    response = client.patch(f"/api/income/{income.id}", json={"record_date": None, "note": None})

    assert response.status_code == 200
    body = response.json()
    assert body["record_date"] is None
    assert body["note"] is None
    assert body["amount_total"] == "200.00"


def test_patch_expected_rejects_computed_fields(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session, asset_type=AssetType.BOND)
    coupon = api_income(
        db_session,
        asset,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.EXPECTED,
        quantity=None,
        total_kopecks=None,
        per_unit_micro=35_400_000,
    )

    response = client.patch(f"/api/income/{coupon.id}", json={"quantity": 10})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_patch_expected_rejects_per_unit_for_moex(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session, asset_type=AssetType.BOND)
    coupon = api_income(
        db_session,
        asset,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.EXPECTED,
        quantity=None,
        total_kopecks=None,
        per_unit_micro=35_400_000,
    )
    coupon.source = DataSource.MOEX
    db_session.commit()

    response = client.patch(f"/api/income/{coupon.id}", json={"amount_per_unit": "36.00"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_delete_income(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)
    income = api_income(db_session, asset)

    response = client.delete(f"/api/income/{income.id}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/income").json()["items"] == []


def test_unknown_asset_returns_404(client: TestClient) -> None:
    response = client.post("/api/income", json=api_payload(asset_id=999))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ASSET_NOT_FOUND"


def test_unknown_income_returns_404(client: TestClient) -> None:
    patch = client.patch("/api/income/999", json={"note": "x"})
    mark_paid = client.post("/api/income/999/mark-paid", json={})
    delete = client.delete("/api/income/999")

    assert patch.status_code == 404
    assert mark_paid.status_code == 404
    assert delete.status_code == 404
    for response in (patch, mark_paid, delete):
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_openapi_exposes_income_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert {"get", "post"} <= set(paths["/api/income"])
    assert {"patch", "delete"} <= set(paths["/api/income/{income_id}"])
    assert "post" in paths["/api/income/{income_id}/mark-paid"]
