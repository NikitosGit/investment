"""Bond price normalization API tests (percent/RUB and amortization)."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization


def _add_bond(
    session: Session, *, secid: str = "SU26238RMFS4", face_value_kopecks: int | None = 100_000
) -> Asset:
    bond = Asset(
        secid=secid,
        name=secid,
        type=AssetType.BOND,
        engine="stock",
        market="bonds",
        board="TQCB",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=face_value_kopecks,
    )
    session.add(bond)
    session.commit()
    return bond


def _post(client: TestClient, **overrides: object):
    payload: dict[str, object] = {
        "asset_id": 1,
        "type": "BUY",
        "trade_date": "2026-01-10",
        "quantity": 10,
        "price": "100.00",
        "price_type": "RUB",
        "note": None,
    }
    payload.update(overrides)
    return client.post("/api/operations", json=payload)


def _create(client: TestClient, **overrides: object) -> dict:
    response = _post(client, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


def test_bond_percent_operation_is_normalized(client: TestClient, db_session: Session) -> None:
    bond = _add_bond(db_session)

    body = _create(
        client,
        asset_id=bond.id,
        trade_date="2026-02-01",
        quantity=15,
        price="95.123",
        price_type="PERCENT",
    )

    assert body["input_price"] == "95.123000"
    assert body["input_price_type"] == "PERCENT"
    assert body["price_rub"] == "951.230000"


def test_patch_trade_date_recomputes_percent_against_new_face(
    client: TestClient, db_session: Session
) -> None:
    bond = _add_bond(db_session)
    body = _create(
        client,
        asset_id=bond.id,
        trade_date="2026-02-01",
        quantity=1,
        price="95.123",
        price_type="PERCENT",
    )
    db_session.add(
        BondAmortization(
            asset_id=bond.id,
            amortization_date=date(2026, 3, 1),
            amount_per_unit_kopecks=20_000,
            source=DataSource.MOEX,
        )
    )
    db_session.commit()

    response = client.patch(f"/api/operations/{body['id']}", json={"trade_date": "2026-03-05"})

    assert response.status_code == 200
    updated = response.json()
    assert updated["trade_date"] == "2026-03-05"
    assert updated["input_price"] == "95.123000"
    assert updated["price_rub"] == "760.984000"


def test_patch_price_type_preserves_ruble_price(client: TestClient, db_session: Session) -> None:
    bond = _add_bond(db_session)
    body = _create(
        client,
        asset_id=bond.id,
        trade_date="2026-02-01",
        quantity=1,
        price="951.23",
        price_type="RUB",
    )

    to_percent = client.patch(f"/api/operations/{body['id']}", json={"price_type": "PERCENT"})
    assert to_percent.status_code == 200
    assert to_percent.json()["input_price"] == "95.123000"
    assert to_percent.json()["price_rub"] == "951.230000"

    to_rub = client.patch(f"/api/operations/{body['id']}", json={"price_type": "RUB"})
    assert to_rub.status_code == 200
    assert to_rub.json()["input_price"] == "951.230000"
    assert to_rub.json()["price_rub"] == "951.230000"


def test_patch_price_type_keeps_normalized_price_exactly(
    client: TestClient, db_session: Session
) -> None:
    bond = _add_bond(db_session)
    body = _create(
        client,
        asset_id=bond.id,
        trade_date="2026-02-01",
        quantity=1,
        price="951.234567",
        price_type="RUB",
    )

    response = client.patch(f"/api/operations/{body['id']}", json={"price_type": "PERCENT"})

    assert response.status_code == 200
    assert response.json()["price_rub"] == "951.234567"
    assert response.json()["input_price"] == "95.123457"
    assert response.json()["input_price_type"] == "PERCENT"


def test_patch_date_and_type_together_renormalizes(client: TestClient, db_session: Session) -> None:
    bond = _add_bond(db_session)
    rub_body = _create(
        client,
        asset_id=bond.id,
        trade_date="2026-02-01",
        quantity=1,
        price="951.23",
        price_type="RUB",
    )
    percent_body = _create(
        client,
        asset_id=bond.id,
        trade_date="2026-02-02",
        quantity=1,
        price="95.123",
        price_type="PERCENT",
    )

    to_percent = client.patch(
        f"/api/operations/{rub_body['id']}",
        json={"trade_date": "2026-02-05", "price_type": "PERCENT"},
    )
    assert to_percent.status_code == 200
    assert to_percent.json()["price_rub"] == "951.230000"
    assert to_percent.json()["input_price"] == "95.123000"
    assert to_percent.json()["input_price_type"] == "PERCENT"

    to_rub = client.patch(
        f"/api/operations/{percent_body['id']}",
        json={"trade_date": "2026-02-05", "price_type": "RUB"},
    )
    assert to_rub.status_code == 200
    assert to_rub.json()["price_rub"] == "951.230000"
    assert to_rub.json()["input_price"] == "951.230000"
    assert to_rub.json()["input_price_type"] == "RUB"


def test_patch_price_type_to_percent_rounding_to_zero_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    bond = _add_bond(db_session)
    body = _create(
        client,
        asset_id=bond.id,
        trade_date="2026-02-01",
        quantity=1,
        price="0.000001",
        price_type="RUB",
    )

    response = client.patch(f"/api/operations/{body['id']}", json={"price_type": "PERCENT"})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "BAD_REQUEST"
    assert error["message"] == "Цена в процентах от номинала должна быть больше нуля"
    stored = client.get("/api/operations").json()["items"][0]
    assert stored["input_price_type"] == "RUB"
    assert stored["input_price"] == "0.000001"


def test_bond_percent_price_rounding_to_zero_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    bond = _add_bond(db_session, secid="TINY", face_value_kopecks=1)

    response = _post(client, asset_id=bond.id, quantity=1, price="0.000001", price_type="PERCENT")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_fully_amortized_bond_is_rejected(client: TestClient, db_session: Session) -> None:
    bond = _add_bond(db_session)
    db_session.add(
        BondAmortization(
            asset_id=bond.id,
            amortization_date=date(2026, 1, 1),
            amount_per_unit_kopecks=100_000,
            source=DataSource.MOEX,
        )
    )
    db_session.commit()

    response = _post(client, asset_id=bond.id, trade_date="2026-02-01", quantity=1, price="900")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_bond_without_face_value_is_rejected(client: TestClient, db_session: Session) -> None:
    bond = _add_bond(db_session, secid="NOFACE", face_value_kopecks=None)

    response = _post(client, asset_id=bond.id, trade_date="2026-02-01", quantity=1, price="900")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
