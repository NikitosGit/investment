"""Asset API tests backed by respx; no real network access."""

from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    AssetType,
    DataSource,
    IncomeKind,
    IncomeStatus,
    OperationType,
    PriceType,
)
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.services import asset_service, bondization_service, portfolio_service

BASE_URL = "https://iss.moex.com/iss"
FIXED_TODAY = date(2026, 1, 1)


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the coupon-date boundary so schedules are deterministic."""

    monkeypatch.setattr(bondization_service, "today_local", lambda: FIXED_TODAY)


@respx.mock
def test_search_returns_supported_items(
    client: TestClient, load_fixture: Callable[..., Any]
) -> None:
    respx.get(f"{BASE_URL}/securities.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "search_sber.json"))
    )

    response = client.get("/api/assets/search", params={"q": "SBER"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["secid"] for item in items] == ["SBER", "SBERP", "SU26238RMFS4"]
    assert items[0]["board"] == "TQBR"
    assert items[0]["type"] == "STOCK"
    assert items[2]["type"] == "BOND"


def test_search_requires_query(client: TestClient) -> None:
    response = client.get("/api/assets/search")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@respx.mock
def test_create_stock_persists_and_lists(
    client: TestClient, db_session: Session, load_fixture: Callable[..., Any]
) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_sber.json"))
    )

    response = client.post("/api/assets", json={"secid": "SBER", "board": "TQBR"})

    assert response.status_code == 201
    body = response.json()
    assert body["secid"] == "SBER"
    assert body["type"] == "STOCK"
    assert body["board"] == "TQBR"
    assert body["currency"] == "RUB"
    assert body["isin"] == "RU0009029540"
    assert body["lot_size"] == 10
    assert body["initial_face_value"] is None
    assert body["current_face_value"] is None
    assert body["amortizations"] == []

    listed = client.get("/api/assets").json()["items"]
    assert [item["id"] for item in listed] == [body["id"]]

    db_session.rollback()
    stored = db_session.scalars(select(Asset)).one()
    assert stored.secid == "SBER"
    assert stored.market == "shares"
    assert stored.engine == "stock"

    detail = client.get(f"/api/assets/{body['id']}").json()
    assert detail["name"] == "Сбербанк России ПАО ао"


@respx.mock
def test_duplicate_asset_conflicts_without_moex_call(
    client: TestClient, load_fixture: Callable[..., Any]
) -> None:
    route = respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_sber.json"))
    )
    payload = {"secid": "SBER", "board": "TQBR"}
    assert client.post("/api/assets", json=payload).status_code == 201

    response = client.post("/api/assets", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ASSET_ALREADY_EXISTS"
    assert len(route.calls) == 1


@respx.mock
def test_unsupported_board_is_rejected(client: TestClient) -> None:
    response = client.post("/api/assets", json={"secid": "GAZP", "board": "TQTF"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


@respx.mock
def test_create_bond_with_schedule(
    client: TestClient, db_session: Session, fixed_today: None, load_fixture: Callable[..., Any]
) -> None:
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_ofz.json"))
    )
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4/bondization.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "bondization_ofz_schedule.json"))
    )

    response = client.post("/api/assets", json={"secid": "SU26238RMFS4", "board": "TQCB"})

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "BOND"
    assert body["initial_face_value"] == "1000.00"
    assert body["current_face_value"] == "1000.00"
    assert body["lot_size"] == 1
    assert [item["amortization_date"] for item in body["amortizations"]] == [
        "2030-01-01",
        "2031-01-01",
    ]
    assert [item["amount_per_unit"] for item in body["amortizations"]] == ["200.00", "300.00"]
    assert body["amortizations"][0]["source"] == "MOEX"

    db_session.rollback()
    coupons = db_session.scalars(select(Income).order_by(Income.pay_date)).all()
    assert [coupon.pay_date for coupon in coupons] == [date(2026, 6, 1), date(2026, 12, 1)]
    assert all(coupon.kind is IncomeKind.COUPON for coupon in coupons)
    assert all(coupon.status is IncomeStatus.EXPECTED for coupon in coupons)
    assert all(coupon.source.value == "MOEX" for coupon in coupons)


@respx.mock
def test_refresh_updates_name_and_lot(client: TestClient, load_fixture: Callable[..., Any]) -> None:
    route = respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        side_effect=[
            httpx.Response(200, json=load_fixture("moex", "security_sber.json")),
            httpx.Response(200, json=load_fixture("moex", "security_sber_updated.json")),
        ]
    )
    asset_id = client.post("/api/assets", json={"secid": "SBER", "board": "TQBR"}).json()["id"]

    response = client.post(f"/api/assets/{asset_id}/refresh")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Сбербанк России ПАО ао (обновлено)"
    assert body["lot_size"] == 1
    assert len(route.calls) == 2


@respx.mock
def test_delete_unused_asset(client: TestClient, load_fixture: Callable[..., Any]) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_sber.json"))
    )
    asset_id = client.post("/api/assets", json={"secid": "SBER", "board": "TQBR"}).json()["id"]

    response = client.delete(f"/api/assets/{asset_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/assets/{asset_id}").status_code == 404


@respx.mock
def test_delete_asset_with_operation_is_rejected(
    client: TestClient, db_session: Session, load_fixture: Callable[..., Any]
) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_sber.json"))
    )
    asset_id = client.post("/api/assets", json={"secid": "SBER", "board": "TQBR"}).json()["id"]

    db_session.rollback()
    portfolio = portfolio_service.ensure_default_portfolio(db_session)

    db_session.add(
        Operation(
            portfolio_id=portfolio.id,
            asset_id=asset_id,
            type=OperationType.BUY,
            trade_date=date(2026, 1, 10),
            quantity=1,
            price_micro=100_000_000,
            input_price_micro=100_000_000,
            input_price_type=PriceType.RUB,
        )
    )
    db_session.commit()

    response = client.delete(f"/api/assets/{asset_id}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ASSET_IN_USE"


def test_missing_asset_returns_404(client: TestClient) -> None:
    response = client.get("/api/assets/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ASSET_NOT_FOUND"


@respx.mock
def test_refresh_bond_syncs_schedule(
    client: TestClient, db_session: Session, fixed_today: None, load_fixture: Callable[..., Any]
) -> None:
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_ofz.json"))
    )
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4/bondization.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "bondization_ofz_schedule.json"))
    )
    asset_id = client.post("/api/assets", json={"secid": "SU26238RMFS4", "board": "TQCB"}).json()[
        "id"
    ]

    response = client.post(f"/api/assets/{asset_id}/refresh")

    assert response.status_code == 200
    assert len(response.json()["amortizations"]) == 2

    db_session.rollback()
    amortizations = db_session.scalar(select(func.count()).select_from(BondAmortization))
    coupons = db_session.scalar(select(func.count()).select_from(Income))
    assert amortizations == 2
    assert coupons == 2


def test_list_assets_filters_by_type(db_session: Session) -> None:
    db_session.add_all(
        [
            Asset(
                secid="SBER",
                name="Сбербанк",
                type=AssetType.STOCK,
                engine="stock",
                market="shares",
                board="TQBR",
                currency="RUB",
                lot_size=10,
            ),
            Asset(
                secid="SU26238RMFS4",
                name="ОФЗ 26238",
                type=AssetType.BOND,
                engine="stock",
                market="bonds",
                board="TQCB",
                currency="RUB",
                lot_size=1,
                initial_face_value_kopecks=100_000,
            ),
        ]
    )
    db_session.commit()

    assert [asset.secid for asset in asset_service.list_assets(db_session)] == [
        "SBER",
        "SU26238RMFS4",
    ]
    bonds = asset_service.list_assets(db_session, asset_type=AssetType.BOND)
    assert [asset.secid for asset in bonds] == ["SU26238RMFS4"]


def _security_payload(
    *,
    secid: str,
    board: str,
    security_type: str,
    face_value: float | None,
) -> dict[str, Any]:
    """Build a minimal MOEX ``securities`` payload for edge cases."""

    return {
        "securities": {
            "columns": [
                "SECID",
                "BOARDID",
                "SECNAME",
                "SHORTNAME",
                "ISIN",
                "TYPE",
                "LOTSIZE",
                "FACEVALUE",
                "FACEUNIT",
            ],
            "data": [
                [
                    secid,
                    board,
                    "Тестовая бумага",
                    "Тест",
                    "RU0000000001",
                    security_type,
                    1,
                    face_value,
                    "SUR",
                ]
            ],
        }
    }


@respx.mock
def test_create_bond_rolls_back_on_bondization_failure(
    client: TestClient, load_fixture: Callable[..., Any]
) -> None:
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_ofz.json"))
    )
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4/bondization.json").mock(
        return_value=httpx.Response(500)
    )

    response = client.post("/api/assets", json={"secid": "SU26238RMFS4", "board": "TQCB"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MOEX_UNAVAILABLE"
    assert client.get("/api/assets").json()["items"] == []


@respx.mock
def test_delete_new_bond_succeeds(
    client: TestClient, db_session: Session, fixed_today: None, load_fixture: Callable[..., Any]
) -> None:
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_ofz.json"))
    )
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4/bondization.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "bondization_ofz_schedule.json"))
    )
    asset_id = client.post("/api/assets", json={"secid": "SU26238RMFS4", "board": "TQCB"}).json()[
        "id"
    ]

    response = client.delete(f"/api/assets/{asset_id}")

    assert response.status_code == 204
    assert client.get(f"/api/assets/{asset_id}").status_code == 404

    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(Income)) == 0
    assert db_session.scalar(select(func.count()).select_from(BondAmortization)) == 0


@respx.mock
def test_duplicate_is_case_insensitive(
    client: TestClient, load_fixture: Callable[..., Any]
) -> None:
    route = respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_sber.json"))
    )
    assert client.post("/api/assets", json={"secid": "SBER", "board": "TQBR"}).status_code == 201

    response = client.post("/api/assets", json={"secid": "sber", "board": "TQBR"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ASSET_ALREADY_EXISTS"
    assert len(route.calls) == 1


@respx.mock
def test_board_type_mismatch_is_rejected(client: TestClient) -> None:
    respx.get(f"{BASE_URL}/securities/BADTYPE.json").mock(
        return_value=httpx.Response(
            200,
            json=_security_payload(
                secid="BADTYPE",
                board="TQCB",
                security_type="common_share",
                face_value=1000.0,
            ),
        )
    )

    response = client.post("/api/assets", json={"secid": "BADTYPE", "board": "TQCB"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert client.get("/api/assets").json()["items"] == []


@respx.mock
def test_bond_without_face_value_is_rejected(client: TestClient) -> None:
    respx.get(f"{BASE_URL}/securities/NOFACE.json").mock(
        return_value=httpx.Response(
            200,
            json=_security_payload(
                secid="NOFACE",
                board="TQCB",
                security_type="ofz_bond",
                face_value=None,
            ),
        )
    )

    response = client.post("/api/assets", json={"secid": "NOFACE", "board": "TQCB"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MOEX_PARSE_ERROR"
    assert client.get("/api/assets").json()["items"] == []


@respx.mock
def test_delete_asset_with_paid_income_is_rejected(
    client: TestClient, db_session: Session, load_fixture: Callable[..., Any]
) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_sber.json"))
    )
    asset_id = client.post("/api/assets", json={"secid": "SBER", "board": "TQBR"}).json()["id"]

    db_session.rollback()
    portfolio = portfolio_service.ensure_default_portfolio(db_session)
    db_session.add(
        Income(
            portfolio_id=portfolio.id,
            asset_id=asset_id,
            kind=IncomeKind.DIVIDEND,
            status=IncomeStatus.PAID,
            amount_total_kopecks=20_000,
            currency="RUB",
            pay_date=date(2026, 7, 15),
            source=DataSource.MANUAL,
        )
    )
    db_session.commit()

    response = client.delete(f"/api/assets/{asset_id}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ASSET_IN_USE"


@respx.mock
def test_refresh_bond_rolls_back_on_bondization_failure(
    client: TestClient, load_fixture: Callable[..., Any]
) -> None:
    def _bondization(request: httpx.Request) -> httpx.Response:
        """Serve the initial schedule once, then fail every retry."""

        if not bondization_calls:
            bondization_calls.append(request.url)
            return httpx.Response(200, json=load_fixture("moex", "bondization_ofz_schedule.json"))
        return httpx.Response(500)

    bondization_calls: list[httpx.URL] = []
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4.json").mock(
        side_effect=[
            httpx.Response(200, json=load_fixture("moex", "security_ofz.json")),
            httpx.Response(
                200,
                json=_security_payload(
                    secid="SU26238RMFS4",
                    board="TQCB",
                    security_type="ofz_bond",
                    face_value=1000.0,
                ),
            ),
        ]
    )
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4/bondization.json").mock(side_effect=_bondization)
    asset_id = client.post("/api/assets", json={"secid": "SU26238RMFS4", "board": "TQCB"}).json()[
        "id"
    ]

    response = client.post(f"/api/assets/{asset_id}/refresh")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MOEX_UNAVAILABLE"

    detail = client.get(f"/api/assets/{asset_id}").json()
    assert detail["name"] == "ОФЗ 26238"
    assert detail["initial_face_value"] == "1000.00"


def test_openapi_exposes_asset_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert {"get", "post"} <= set(paths["/api/assets"])
    assert "get" in paths["/api/assets/search"]
    assert {"get", "delete"} <= set(paths["/api/assets/{asset_id}"])
    assert "post" in paths["/api/assets/{asset_id}/refresh"]
