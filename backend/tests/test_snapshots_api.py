"""Snapshot API tests: contract, period filter and validation."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.time import today_local
from app.services import snapshot_service

from dashboard_helpers import days_ago  # isort: skip

ITEM_FIELDS = {"date", "market_value", "invested", "income_paid"}


def _store(session: Session, offset: int, value: int) -> None:
    snapshot_service.upsert_snapshot(
        session,
        days_ago(offset),
        market_value_kopecks=value,
        invested_kopecks=value + 1,
        income_paid_kopecks=value + 2,
    )


def test_snapshots_response_contract(client: TestClient, db_session: Session) -> None:
    _store(db_session, 20, 100_000)
    _store(db_session, 5, 110_000)
    db_session.commit()

    response = client.get("/api/snapshots")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"period", "items"}
    assert body["period"] == "1Y"
    assert all(set(item) == ITEM_FIELDS for item in body["items"])
    assert [item["date"] for item in body["items"]] == [
        days_ago(20).isoformat(),
        days_ago(5).isoformat(),
    ]
    assert body["items"][0] == {
        "date": days_ago(20).isoformat(),
        "market_value": "1000.00",
        "invested": "1000.01",
        "income_paid": "1000.02",
    }


def test_snapshots_period_filter(client: TestClient, db_session: Session) -> None:
    _store(db_session, 40, 1)
    _store(db_session, 20, 2)
    _store(db_session, 5, 3)
    db_session.commit()

    one_month = client.get("/api/snapshots", params={"period": "1M"}).json()
    assert one_month["period"] == "1M"
    assert len(one_month["items"]) == 2

    for period in ("3M", "1Y", "ALL"):
        body = client.get("/api/snapshots", params={"period": period}).json()
        assert body["period"] == period
        assert len(body["items"]) == 3


def test_snapshots_empty(client: TestClient) -> None:
    body = client.get("/api/snapshots").json()

    assert body == {"period": "1Y", "items": []}


def test_snapshots_invalid_period_is_422(client: TestClient) -> None:
    response = client.get("/api/snapshots", params={"period": "6M"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]["errors"][0]["field"] == "query.period"


def test_snapshots_are_oldest_first(client: TestClient, db_session: Session) -> None:
    _store(db_session, 3, 30)
    _store(db_session, 10, 10)
    _store(db_session, 1, 20)
    db_session.commit()

    dates = [item["date"] for item in client.get("/api/snapshots").json()["items"]]

    assert dates == [
        days_ago(10).isoformat(),
        days_ago(3).isoformat(),
        days_ago(1).isoformat(),
    ]
    assert today_local().isoformat() not in dates


def test_openapi_documents_the_snapshots_endpoint(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    path = schema["paths"]["/api/snapshots"]["get"]
    assert path["summary"] == "История снимков портфеля"
    period = next(parameter for parameter in path["parameters"] if parameter["name"] == "period")
    assert set(period["schema"]["enum"]) == {"1M", "3M", "1Y", "ALL"}
