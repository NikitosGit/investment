"""Operation API tests (offline, temporary SQLite)."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, OperationType, PriceType
from app.db.models.asset import Asset
from app.db.models.operation import Operation
from app.services import portfolio_service

BUY_100 = 100_000_000


def _add_asset(
    session: Session,
    *,
    secid: str = "SBER",
    asset_type: AssetType = AssetType.STOCK,
    face_value_kopecks: int | None = None,
) -> Asset:
    asset = Asset(
        secid=secid,
        name=secid,
        type=asset_type,
        engine="stock",
        market="shares" if asset_type is AssetType.STOCK else "bonds",
        board="TQBR" if asset_type is AssetType.STOCK else "TQCB",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=face_value_kopecks,
    )
    session.add(asset)
    session.commit()
    return asset


def _store_operation(
    session: Session,
    asset: Asset,
    *,
    operation_type: OperationType = OperationType.BUY,
    trade_date: date = date(2026, 1, 10),
    quantity: int = 10,
    price_micro: int = BUY_100,
) -> Operation:
    portfolio = portfolio_service.ensure_default_portfolio(session)
    operation = Operation(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        type=operation_type,
        trade_date=trade_date,
        quantity=quantity,
        price_micro=price_micro,
        input_price_micro=price_micro,
        input_price_type=PriceType.RUB,
    )
    session.add(operation)
    session.commit()
    return operation


def _post(client: TestClient, **overrides: object):
    payload: dict[str, object] = {
        "asset_id": 1,
        "type": "BUY",
        "trade_date": "2026-01-10",
        "quantity": 10,
        "price": "100.00",
        "price_type": "RUB",
        "note": "Первая покупка",
    }
    payload.update(overrides)
    return client.post("/api/operations", json=payload)


def _create(client: TestClient, **overrides: object) -> dict:
    response = _post(client, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


def _sell(client: TestClient, asset_id: int, *, quantity: int = 5) -> dict:
    return _create(
        client,
        asset_id=asset_id,
        type="SELL",
        trade_date="2026-01-12",
        quantity=quantity,
        price="150",
        note=None,
    )


def test_create_buy_persists_and_echoes_prices(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)

    body = _create(client, asset_id=asset.id)

    assert body["asset_id"] == asset.id
    assert body["type"] == "BUY"
    assert body["trade_date"] == "2026-01-10"
    assert body["quantity"] == 10
    assert body["input_price"] == "100.000000"
    assert body["input_price_type"] == "RUB"
    assert body["price_rub"] == "100.000000"
    assert body["note"] == "Первая покупка"

    db_session.rollback()
    stored = db_session.scalars(select(Operation)).one()
    assert stored.price_micro == 100_000_000
    assert stored.face_value_kopecks is None


def test_create_sell_after_buy(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)
    _create(client, asset_id=asset.id)

    response = _post(
        client, asset_id=asset.id, type="SELL", trade_date="2026-01-12", quantity=5, price="150"
    )

    assert response.status_code == 201
    assert response.json()["type"] == "SELL"
    assert response.json()["price_rub"] == "150.000000"


def test_list_operations_filters_by_asset_and_dates(
    client: TestClient, db_session: Session
) -> None:
    first = _add_asset(db_session, secid="SBER")
    second = _add_asset(db_session, secid="GAZP")
    _store_operation(db_session, first, trade_date=date(2026, 1, 10))
    _store_operation(db_session, first, trade_date=date(2026, 2, 5), quantity=3)
    _store_operation(db_session, second, trade_date=date(2026, 1, 20), quantity=7)

    all_items = client.get("/api/operations").json()["items"]
    assert [(item["asset_id"], item["trade_date"]) for item in all_items] == [
        (first.id, "2026-01-10"),
        (second.id, "2026-01-20"),
        (first.id, "2026-02-05"),
    ]

    filtered = client.get(
        "/api/operations",
        params={"asset_id": first.id, "from": "2026-02-01", "to": "2026-02-05"},
    ).json()["items"]
    assert [item["quantity"] for item in filtered] == [3]


def test_insufficient_sell_returns_409(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)
    _create(client, asset_id=asset.id)

    response = _post(
        client, asset_id=asset.id, type="SELL", trade_date="2026-01-12", quantity=20, price="150"
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INSUFFICIENT_QUANTITY"
    assert error["message"] == "Нельзя продать 20: доступно 10"
    assert error["details"]["asset_id"] == asset.id
    assert error["details"]["available"] == 10
    assert error["details"]["requested"] == 20


def test_patch_quantity_and_price_recalculates(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)
    body = _create(client, asset_id=asset.id)

    response = client.patch(
        f"/api/operations/{body['id']}", json={"quantity": 4, "price": "120.50"}
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["quantity"] == 4
    assert updated["input_price"] == "120.500000"
    assert updated["price_rub"] == "120.500000"

    db_session.rollback()
    stored = db_session.get(Operation, body["id"])
    assert stored is not None
    assert stored.quantity == 4
    assert stored.price_micro == 120_500_000


def test_patch_creating_invalid_history_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    asset = _add_asset(db_session)
    _create(client, asset_id=asset.id)
    sell = _sell(client, asset.id)

    response = client.patch(f"/api/operations/{sell['id']}", json={"quantity": 11})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_QUANTITY"
    operations = client.get("/api/operations").json()["items"]
    assert [item["quantity"] for item in operations] == [10, 5]


def test_patch_note_only(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)
    body = _create(client, asset_id=asset.id)

    response = client.patch(f"/api/operations/{body['id']}", json={"note": None})

    assert response.status_code == 200
    assert response.json()["note"] is None
    assert response.json()["price_rub"] == "100.000000"


def test_delete_operation_that_breaks_later_sell_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    asset = _add_asset(db_session)
    buy = _create(client, asset_id=asset.id)
    _sell(client, asset.id)

    response = client.delete(f"/api/operations/{buy['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_QUANTITY"
    assert len(client.get("/api/operations").json()["items"]) == 2


def test_delete_operation_succeeds(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)
    body = _create(client, asset_id=asset.id)

    response = client.delete(f"/api/operations/{body['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/operations").json()["items"] == []


def test_unknown_asset_returns_404(client: TestClient) -> None:
    response = _post(client, asset_id=999, quantity=1)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ASSET_NOT_FOUND"


def test_unknown_operation_returns_404(client: TestClient) -> None:
    patch = client.patch("/api/operations/999", json={"quantity": 1})
    delete = client.delete("/api/operations/999")

    assert patch.status_code == 404
    assert patch.json()["error"]["code"] == "NOT_FOUND"
    assert delete.status_code == 404
    assert delete.json()["error"]["code"] == "NOT_FOUND"


def test_stock_percent_price_is_rejected(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)

    response = _post(client, asset_id=asset.id, quantity=1, price="95", price_type="PERCENT")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_patch_date_and_type(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)
    body = _create(client, asset_id=asset.id)
    sell = _sell(client, asset.id)

    moved = client.patch(f"/api/operations/{body['id']}", json={"trade_date": "2026-01-05"})
    assert moved.status_code == 200
    assert moved.json()["price_rub"] == "100.000000"

    retyped = client.patch(f"/api/operations/{sell['id']}", json={"type": "BUY"})
    assert retyped.status_code == 200
    assert retyped.json()["type"] == "BUY"


def test_patch_sell_date_before_buy_is_rejected(client: TestClient, db_session: Session) -> None:
    asset = _add_asset(db_session)
    _create(client, asset_id=asset.id)
    sell = _sell(client, asset.id)

    response = client.patch(f"/api/operations/{sell['id']}", json={"trade_date": "2026-01-05"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_QUANTITY"
    items = client.get("/api/operations").json()["items"]
    assert [(item["type"], item["trade_date"]) for item in items] == [
        ("BUY", "2026-01-10"),
        ("SELL", "2026-01-12"),
    ]


def test_patch_buy_to_sell_without_stock_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    asset = _add_asset(db_session)
    buy = _create(client, asset_id=asset.id)

    response = client.patch(f"/api/operations/{buy['id']}", json={"type": "SELL"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_QUANTITY"
    item = client.get("/api/operations").json()["items"][0]
    assert item["type"] == "BUY"


def test_patch_stock_price_type_percent_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    asset = _add_asset(db_session)
    body = _create(client, asset_id=asset.id)

    response = client.patch(f"/api/operations/{body['id']}", json={"price_type": "PERCENT"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert response.json()["error"]["message"] == (
        "Для акций цена указывается в рублях, а не в процентах"
    )


def test_validation_rejects_fractional_price_precision(client: TestClient) -> None:
    response = _post(client, quantity=1, price="100.1234567")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_openapi_exposes_operations_and_positions(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert {"get", "post"} <= set(paths["/api/operations"])
    assert {"patch", "delete"} <= set(paths["/api/operations/{operation_id}"])
    assert "get" in paths["/api/positions"]
