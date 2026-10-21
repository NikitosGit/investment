"""Asset API edge cases: MOEX failures, type mismatches and deletion rules."""

from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import DataSource, IncomeKind, IncomeStatus
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.services import bondization_service, portfolio_service

from asset_helpers import BASE_URL, security_payload, stub_quotes  # isort: skip

FIXED_TODAY = date(2026, 1, 1)


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the coupon-date boundary so schedules are deterministic."""

    monkeypatch.setattr(bondization_service, "today_local", lambda: FIXED_TODAY)


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
    stub_quotes(
        load_fixture,
        secid="SU26238RMFS4",
        market="bonds",
        board="TQCB",
        marketdata="marketdata_ofz.json",
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
    stub_quotes(load_fixture)
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
            json=security_payload(
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
            json=security_payload(
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
    stub_quotes(load_fixture)
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
                json=security_payload(
                    secid="SU26238RMFS4",
                    board="TQCB",
                    security_type="ofz_bond",
                    face_value=1000.0,
                ),
            ),
        ]
    )
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4/bondization.json").mock(side_effect=_bondization)
    stub_quotes(
        load_fixture,
        secid="SU26238RMFS4",
        market="bonds",
        board="TQCB",
        marketdata="marketdata_ofz.json",
    )
    asset_id = client.post("/api/assets", json={"secid": "SU26238RMFS4", "board": "TQCB"}).json()[
        "id"
    ]

    response = client.post(f"/api/assets/{asset_id}/refresh")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MOEX_UNAVAILABLE"

    detail = client.get(f"/api/assets/{asset_id}").json()
    assert detail["name"] == "ОФЗ 26238"
    assert detail["initial_face_value"] == "1000.00"
