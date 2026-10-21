"""Quote API contract tests (offline)."""

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes import quotes as quotes_routes
from app.core.enums import AssetType, DataSource, PriceType
from app.core.time import to_local, today_local, utc_now_naive
from app.db.models.asset import Asset
from app.db.models.quote import Quote
from app.services.quote_service import RefreshError, RefreshResult


def _asset(session: Session, *, asset_type: AssetType = AssetType.STOCK) -> Asset:
    asset = Asset(
        secid="SBER" if asset_type is AssetType.STOCK else "SU26238RMFS4",
        name="Тестовая бумага",
        type=asset_type,
        engine="stock",
        market="shares" if asset_type is AssetType.STOCK else "bonds",
        board="TQBR" if asset_type is AssetType.STOCK else "TQCB",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=100_000 if asset_type is AssetType.BOND else None,
    )
    session.add(asset)
    session.commit()
    return asset


def test_history_contract_has_prices_and_ascending_order(
    client: TestClient, db_session: Session
) -> None:
    asset = _asset(db_session)
    today = today_local()
    db_session.add_all(
        [
            # Inserted in reverse order to prove the service sorts by date.
            _quote(asset.id, today - timedelta(days=1), 310_500_000),
            _quote(asset.id, today - timedelta(days=2), 305_000_000),
        ]
    )
    db_session.commit()

    response = client.get(f"/api/quotes/{asset.id}/history", params={"period": "1M"})

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset.id
    assert body["period"] == "1M"
    assert [item["price"] for item in body["items"]] == ["305.000000", "310.500000"]
    assert [item["quote_date"] for item in body["items"]] == [
        (today - timedelta(days=2)).isoformat(),
        (today - timedelta(days=1)).isoformat(),
    ]
    assert body["items"][0]["price_type"] == "RUB"
    assert body["items"][0]["source"] == "MOEX"
    assert body["items"][0]["fetched_at"].endswith(("Z", "+00:00"))


def test_history_missing_asset_and_invalid_period(client: TestClient, db_session: Session) -> None:
    missing = client.get("/api/quotes/999/history")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ASSET_NOT_FOUND"

    asset = _asset(db_session)
    invalid = client.get(f"/api/quotes/{asset.id}/history", params={"period": "2Y"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_refresh_response_maps_result_and_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = RefreshResult(
        updated=2,
        failed=1,
        last_refresh_at=utc_now_naive(),
        errors=[RefreshError(asset_id=7, secid="GAZP", error="MOEX недоступен")],
    )
    monkeypatch.setattr(quotes_routes.quote_service, "refresh_all", lambda *_: result)

    response = client.post("/api/quotes/refresh")

    assert response.status_code == 200
    body = response.json()
    assert body["updated"] == 2
    assert body["failed"] == 1
    assert body["errors"] == [{"asset_id": 7, "secid": "GAZP", "error": "MOEX недоступен"}]
    # Presented in the configured local timezone, like /api/health.
    assert datetime.fromisoformat(body["last_refresh_at"]) == to_local(result.last_refresh_at)


def test_manual_quote_created_and_validated(client: TestClient, db_session: Session) -> None:
    stock = _asset(db_session)
    bond = _asset(db_session, asset_type=AssetType.BOND)
    today = today_local()

    response = client.post(
        "/api/quotes/manual",
        json={
            "asset_id": stock.id,
            "quote_date": today.isoformat(),
            "price": "305.50",
            "price_type": "RUB",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["asset_id"] == stock.id
    assert body["price"] == "305.500000"
    assert body["price_type"] == "RUB"
    assert body["source"] == "MANUAL"

    cases = [
        (
            {
                "asset_id": stock.id,
                "quote_date": (today + timedelta(days=1)).isoformat(),
                "price": "1",
                "price_type": "RUB",
            },
            400,
            "BAD_REQUEST",
        ),
        (
            {
                "asset_id": stock.id,
                "quote_date": today.isoformat(),
                "price": "1",
                "price_type": "PERCENT",
            },
            400,
            "BAD_REQUEST",
        ),
        (
            {
                "asset_id": bond.id,
                "quote_date": today.isoformat(),
                "price": "1",
                "price_type": "RUB",
            },
            400,
            "BAD_REQUEST",
        ),
        (
            {
                "asset_id": 999,
                "quote_date": today.isoformat(),
                "price": "1",
                "price_type": "RUB",
            },
            404,
            "ASSET_NOT_FOUND",
        ),
        (
            {
                "asset_id": stock.id,
                "quote_date": today.isoformat(),
                "price": "0",
                "price_type": "RUB",
            },
            422,
            "VALIDATION_ERROR",
        ),
        (
            {
                "asset_id": stock.id,
                "quote_date": today.isoformat(),
                "price": "1",
                "price_type": "RUB",
                "extra": True,
            },
            422,
            "VALIDATION_ERROR",
        ),
    ]
    for payload, status, code in cases:
        invalid = client.post("/api/quotes/manual", json=payload)
        assert invalid.status_code == status, payload
        assert invalid.json()["error"]["code"] == code


def test_openapi_exposes_quote_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "get" in paths["/api/quotes/{asset_id}/history"]
    assert "post" in paths["/api/quotes/refresh"]
    assert "post" in paths["/api/quotes/manual"]


def _quote(asset_id: int, quote_date: date, price_micro: int) -> Quote:
    return Quote(
        asset_id=asset_id,
        quote_date=quote_date,
        price_micro=price_micro,
        price_type=PriceType.RUB,
        source=DataSource.MOEX,
        fetched_at=utc_now_naive(),
    )
