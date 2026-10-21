"""Position API tests (plan §8.5)."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, OperationType, PriceType
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.portfolio import Portfolio
from app.db.models.quote import Quote
from app.services import operation_service, portfolio_service

POSITION_FIELDS = {
    "asset",
    "quantity",
    "avg_price",
    "avg_price_percent",
    "current_price",
    "current_price_type",
    "current_face_value",
    "market_value",
    "invested",
    "share",
    "price_date",
    "price_source",
    "is_stale",
}


def _portfolio(session: Session) -> Portfolio:
    return portfolio_service.ensure_default_portfolio(session)


def _add_asset(
    session: Session,
    *,
    secid: str,
    asset_type: AssetType = AssetType.STOCK,
    face_value_kopecks: int | None = None,
) -> Asset:
    asset = Asset(
        secid=secid,
        name=f"{secid} name",
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


def _buy(
    session: Session,
    asset: Asset,
    *,
    quantity: int,
    price: Decimal,
    trade_date: date,
    price_type: PriceType = PriceType.RUB,
) -> None:
    operation_service.create_operation(
        session,
        asset_id=asset.id,
        type=OperationType.BUY,
        trade_date=trade_date,
        quantity=quantity,
        price=price,
        price_type=price_type,
        note=None,
    )


def _quote(session: Session, asset: Asset, *, price_micro: int, price_type: PriceType) -> None:
    session.add(
        Quote(
            asset_id=asset.id,
            quote_date=today_local(),
            price_micro=price_micro,
            price_type=price_type,
            source=DataSource.MOEX,
        )
    )
    session.commit()


def _build_portfolio(session: Session) -> tuple[Asset, Asset]:
    _portfolio(session)
    stock = _add_asset(session, secid="SBER")
    _buy(session, stock, quantity=10, price=Decimal("100"), trade_date=date(2026, 1, 10))
    _buy(session, stock, quantity=10, price=Decimal("120"), trade_date=date(2026, 1, 11))
    _quote(session, stock, price_micro=310_500_000, price_type=PriceType.RUB)

    bond = _add_asset(
        session, secid="SU26238RMFS4", asset_type=AssetType.BOND, face_value_kopecks=100_000
    )
    _buy(
        session,
        bond,
        quantity=15,
        price=Decimal("95.123"),
        trade_date=date(2026, 2, 1),
        price_type=PriceType.PERCENT,
    )
    _quote(session, bond, price_micro=98_500_000, price_type=PriceType.PERCENT)
    return stock, bond


def test_positions_return_contract_fields(client: TestClient, db_session: Session) -> None:
    _build_portfolio(db_session)

    response = client.get("/api/positions")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total_market_value", "total_invested"}
    assert [item["asset"]["secid"] for item in body["items"]] == ["SBER", "SU26238RMFS4"]
    assert all(set(item) == POSITION_FIELDS for item in body["items"])
    assert body["total_market_value"] == "20985.00"
    assert body["total_invested"] == "16468.45"


def test_stock_position_strings_and_share(client: TestClient, db_session: Session) -> None:
    _build_portfolio(db_session)

    item = client.get("/api/positions").json()["items"][0]

    assert item["asset"] == {
        "id": item["asset"]["id"],
        "secid": "SBER",
        "name": "SBER name",
        "type": "STOCK",
    }
    assert item["quantity"] == 20
    assert item["avg_price"] == "110.000000"
    assert item["avg_price_percent"] is None
    assert item["current_price"] == "310.500000"
    assert item["current_price_type"] == "RUB"
    assert item["current_face_value"] is None
    assert item["market_value"] == "6210.00"
    assert item["invested"] == "2200.00"
    assert item["share"] == "0.2959"
    assert item["price_date"] == today_local().isoformat()
    assert item["price_source"] == "MOEX"
    assert item["is_stale"] is False


def test_bond_position_uses_percent_of_face(client: TestClient, db_session: Session) -> None:
    _build_portfolio(db_session)

    bond = client.get("/api/positions").json()["items"][1]

    assert bond["quantity"] == 15
    assert bond["avg_price"] == "951.230000"
    assert bond["avg_price_percent"] == "95.123000"
    assert bond["current_price"] == "98.500000"
    assert bond["current_price_type"] == "PERCENT"
    assert bond["current_face_value"] == "1000.00"
    assert bond["market_value"] == "14775.00"
    assert bond["invested"] == "14268.45"
    assert bond["share"] == "0.7041"


def test_without_quote_positions_fall_back_to_cost(client: TestClient, db_session: Session) -> None:
    _portfolio(db_session)
    asset = _add_asset(db_session, secid="SBER")
    _buy(db_session, asset, quantity=10, price=Decimal("100"), trade_date=date(2026, 1, 10))

    body = client.get("/api/positions").json()

    item = body["items"][0]
    assert item["current_price"] == "100.000000"
    assert item["current_price_type"] == "RUB"
    assert item["market_value"] == "1000.00"
    assert item["invested"] == "1000.00"
    assert item["share"] == "1.0000"
    assert item["price_date"] is None
    assert item["price_source"] == "COST"
    assert item["is_stale"] is True
    assert body["total_market_value"] == "1000.00"
    assert body["total_invested"] == "1000.00"


def test_closed_positions_are_not_listed(client: TestClient, db_session: Session) -> None:
    _portfolio(db_session)
    asset = _add_asset(db_session, secid="SBER")
    _buy(db_session, asset, quantity=10, price=Decimal("100"), trade_date=date(2026, 1, 10))
    operation_service.create_operation(
        db_session,
        asset_id=asset.id,
        type=OperationType.SELL,
        trade_date=date(2026, 1, 20),
        quantity=10,
        price=Decimal("150"),
        price_type=PriceType.RUB,
        note=None,
    )

    body = client.get("/api/positions").json()

    assert body["items"] == []
    assert body["total_market_value"] == "0.00"
    assert body["total_invested"] == "0.00"


def test_future_quote_is_not_used(client: TestClient, db_session: Session) -> None:
    _portfolio(db_session)
    asset = _add_asset(db_session, secid="SBER")
    _buy(db_session, asset, quantity=1, price=Decimal("100"), trade_date=date(2026, 1, 10))
    db_session.add(
        Quote(
            asset_id=asset.id,
            quote_date=today_local().replace(year=today_local().year + 1),
            price_micro=200_000_000,
            price_type=PriceType.RUB,
            source=DataSource.MOEX,
        )
    )
    db_session.commit()

    item = client.get("/api/positions").json()["items"][0]

    assert item["price_source"] == "COST"
    assert item["market_value"] == "100.00"
