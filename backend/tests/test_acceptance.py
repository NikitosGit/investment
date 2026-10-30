"""Demo-driven subset of the plan §14 functional acceptance checklist.

Most scenarios start from the demo seed, so the suite exercises the same data
the frontend receives during handoff without any network access. One simple
bond case is built directly to check the 1000 @ 95% contract independently of
the demo data.
"""

import io
import json
import sqlite3
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, OperationType, PriceType
from app.core.time import today_local
from app.db.models.asset import Asset
from app.scripts.seed_demo import seed_demo


def _asset_id(session: Session, secid: str) -> int:
    asset = session.scalar(select(Asset).where(Asset.secid == secid))
    assert asset is not None
    return asset.id


def _items_by_secid(body: dict) -> dict[str, dict]:
    return {item["asset"]["secid"]: item for item in body["items"]}


def test_health_is_ok_after_seed(client: TestClient, db_session: Session) -> None:
    seed_demo(db_session)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["moex"] == "unknown"
    assert body["version"] == "0.1.0"


def test_positions_match_the_demo_trade_history(client: TestClient, db_session: Session) -> None:
    seed_demo(db_session)

    response = client.get("/api/positions")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total_market_value", "total_invested"}
    positions = _items_by_secid(body)
    assert set(positions) == {"SBER", "SU26238RMFS4"}

    stock = positions["SBER"]
    assert stock["quantity"] == 15
    assert stock["avg_price"] == "110.000000"
    assert stock["avg_price_percent"] is None
    assert stock["current_price"] == "302.000000"
    assert stock["market_value"] == "4530.00"
    assert stock["invested"] == "1650.00"
    assert stock["price_source"] == "MANUAL"

    bond = positions["SU26238RMFS4"]
    assert bond["quantity"] == 15
    assert bond["avg_price"] == "951.230000"
    assert bond["avg_price_percent"] == "95.123000"
    assert bond["current_price"] == "97.600000"
    assert bond["current_face_value"] == "800.00"
    assert bond["market_value"] == "11712.00"
    assert bond["invested"] == "14268.45"

    assert body["total_market_value"] == "16242.00"
    assert body["total_invested"] == "15918.45"


def test_dashboard_income_and_snapshots(client: TestClient, db_session: Session) -> None:
    seed_demo(db_session)

    dashboard = client.get("/api/dashboard", params={"period": "1Y"})
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["period"] == "1Y"
    assert body["as_of"] == today_local().isoformat()
    assert body["totals"] == {
        "market_value": "16242.00",
        "invested": "15918.45",
        "dividends_paid": "200.00",
        "coupons_paid": "525.00",
        "income_paid_total": "725.00",
        "expected_coupons": "1575.00",
        "positions_count": 2,
        "assets_count": 2,
    }
    assert len(body["positions"]) == 2
    assert body["series"]
    assert all(isinstance(point["market_value"], str) for point in body["series"])
    assert len(body["upcoming_coupons"]) == 3
    assert all(item["quantity"] == 15 for item in body["upcoming_coupons"])
    assert all(item["amount_total"] == "525.00" for item in body["upcoming_coupons"])

    paid = client.get("/api/income", params={"status": "PAID"}).json()
    assert len(paid["items"]) == 2
    assert all(item["status"] == "PAID" for item in paid["items"])
    assert paid["totals"] == {
        "dividends_paid": "200.00",
        "coupons_paid": "525.00",
        "expected_coupons": "1575.00",
    }

    snapshots = client.get("/api/snapshots").json()
    assert snapshots["period"] == "1Y"
    today_item = next(
        item for item in snapshots["items"] if item["date"] == today_local().isoformat()
    )
    assert today_item["market_value"] == "16242.00"
    assert today_item["invested"] == "15918.45"
    assert today_item["income_paid"] == "725.00"


def test_backup_and_exports_are_valid(client: TestClient, db_session: Session) -> None:
    seed_demo(db_session)

    backup = client.post("/api/backup")

    assert backup.status_code == 200
    body = backup.json()
    path = Path(body["path"])
    assert path.is_file()
    assert body["size_bytes"] == path.stat().st_size
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM asset").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM operation").fetchone()[0] == 4

    json_export = client.get("/api/export", params={"format": "json"})
    assert json_export.status_code == 200
    assert json_export.headers["content-type"].startswith("application/json")
    payload = json.loads(json_export.content)
    assert payload["portfolio"]["id"] == 1
    assert len(payload["assets"]) == 2
    assert len(payload["operations"]) == 4
    assert len(payload["income"]) == 5
    assert len(payload["quotes"]) == 54
    assert len(payload["amortizations"]) == 1
    assert len(payload["snapshots"]) == 1

    csv_export = client.get("/api/export", params={"format": "csv"})
    assert csv_export.status_code == 200
    assert csv_export.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(csv_export.content)) as archive:
        assert set(archive.namelist()) == {"positions.csv", "operations.csv", "income.csv"}
        position_rows = archive.read("positions.csv").decode("utf-8-sig").splitlines()
        assert len(position_rows) == 3


def test_oversell_returns_the_stable_error_contract(
    client: TestClient, db_session: Session
) -> None:
    seed_demo(db_session)
    stock_id = _asset_id(db_session, "SBER")

    response = client.post(
        "/api/operations",
        json={
            "asset_id": stock_id,
            "type": OperationType.SELL.value,
            "trade_date": today_local().isoformat(),
            "quantity": 100,
            "price": "150.00",
            "price_type": PriceType.RUB.value,
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "INSUFFICIENT_QUANTITY"
    assert body["error"]["details"]["available"] == 15
    assert body["error"]["details"]["requested"] == 100
    assert "Нельзя продать 100" in body["error"]["message"]


def test_bond_1000_at_95_percent(client: TestClient, db_session: Session) -> None:
    bond = Asset(
        secid="TESTBOND",
        name="Тестовая облигация",
        type=AssetType.BOND,
        engine="stock",
        market="bonds",
        board="TQCB",
        currency="RUB",
        initial_face_value_kopecks=100_000,
        lot_size=1,
    )
    db_session.add(bond)
    db_session.commit()

    response = client.post(
        "/api/operations",
        json={
            "asset_id": bond.id,
            "type": OperationType.BUY.value,
            "trade_date": today_local().isoformat(),
            "quantity": 10,
            "price": "95",
            "price_type": PriceType.PERCENT.value,
        },
    )

    assert response.status_code == 201
    position = _items_by_secid(client.get("/api/positions").json())["TESTBOND"]
    assert position["quantity"] == 10
    assert position["avg_price"] == "950.000000"
    assert position["avg_price_percent"] == "95.000000"
    assert position["current_face_value"] == "1000.00"
