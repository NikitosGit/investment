"""Income API validation tests: payload constraints and unknown fields."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import AssetType, IncomeKind, IncomeStatus

from income_api_helpers import api_asset, api_income, api_payload  # isort: skip


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"amount_total": "0"},
        {"amount_total": "-5"},
        {"amount_total": None},
        {"quantity": -1},
        {"quantity": None},
        {"pay_date": None},
    ],
)
def test_patch_validation(client: TestClient, db_session: Session, payload: dict) -> None:
    asset = api_asset(db_session)
    income = api_income(db_session, asset)

    response = client.patch(f"/api/income/{income.id}", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("payload", [{"status": "PAID"}, {"asset_id": 1}])
def test_patch_rejects_unknown_fields(
    client: TestClient, db_session: Session, payload: dict
) -> None:
    asset = api_asset(db_session)
    income = api_income(db_session, asset)

    response = client.patch(f"/api/income/{income.id}", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_mark_paid_rejects_unknown_fields(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session, asset_type=AssetType.BOND)
    coupon = api_income(
        db_session,
        asset,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.EXPECTED,
        quantity=None,
        total_kopecks=None,
        per_unit_micro=None,
    )

    response = client.post(
        f"/api/income/{coupon.id}/mark-paid", json={"title": "x", "amount_total": "100.00"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_rejects_unknown_fields(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)

    response = client.post("/api/income", json=api_payload(asset_id=asset.id, status="PAID"))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_rejects_negative_quantity(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)

    response = client.post("/api/income", json=api_payload(asset_id=asset.id, quantity=-1))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_validation(client: TestClient, db_session: Session) -> None:
    asset = api_asset(db_session)

    response = client.post(
        "/api/income",
        json={
            "asset_id": asset.id,
            "kind": "COUPON",
            "amount_total": "0",
            "pay_date": "2026-07-15",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
