"""Dashboard API tests: contract, periods and validation (plan §8.7)."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.time import today_local
from app.services import settings_service

from dashboard_helpers import (  # isort: skip
    add_income,
    add_operation,
    add_quote,
    build_dashboard_portfolio,
    days_ago,
    days_ahead,
    make_asset,
)

RESPONSE_FIELDS = {
    "as_of",
    "currency",
    "period",
    "totals",
    "series",
    "positions",
    "upcoming_coupons",
    "is_partial",
}
TOTALS_FIELDS = {
    "market_value",
    "invested",
    "dividends_paid",
    "coupons_paid",
    "income_paid_total",
    "expected_coupons",
    "positions_count",
    "assets_count",
}
SERIES_FIELDS = {"date", "market_value", "invested", "is_partial"}
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
INCOME_FIELDS = {
    "id",
    "asset_id",
    "asset_secid",
    "kind",
    "status",
    "amount_per_unit",
    "quantity",
    "amount_total",
    "currency",
    "record_date",
    "pay_date",
    "source",
    "note",
    "is_overdue",
}


def _build_portfolio(session: Session) -> None:
    _, bond = build_dashboard_portfolio(session)
    add_income(session, bond, pay_date=days_ahead(10), per_unit_micro=35_000_000)
    add_income(session, bond, pay_date=days_ago(2), per_unit_micro=10_000_000)


def test_dashboard_default_period_and_contract(client: TestClient, db_session: Session) -> None:
    _build_portfolio(db_session)

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert body["period"] == "1Y"
    assert body["as_of"] == today_local().isoformat()
    assert body["currency"] == "RUB"
    assert isinstance(body["is_partial"], bool)
    assert body["is_partial"] is True

    assert set(body["totals"]) == TOTALS_FIELDS
    assert body["totals"] == {
        "market_value": "15875.00",
        "invested": "15268.45",
        "dividends_paid": "200.00",
        "coupons_paid": "525.00",
        "income_paid_total": "725.00",
        "expected_coupons": "675.00",
        "positions_count": 2,
        "assets_count": 2,
    }

    assert all(set(point) == SERIES_FIELDS for point in body["series"])
    assert all(isinstance(point["is_partial"], bool) for point in body["series"])
    assert body["series"][0]["date"] == days_ago(60).isoformat()
    assert body["series"][-1]["date"] == today_local().isoformat()

    assert [item["asset"]["secid"] for item in body["positions"]] == [
        "SBER",
        "SU26238RMFS4",
    ]
    assert all(set(item) == POSITION_FIELDS for item in body["positions"])

    assert len(body["upcoming_coupons"]) == 1
    coupon = body["upcoming_coupons"][0]
    assert set(coupon) == INCOME_FIELDS
    assert coupon["asset_secid"] == "SU26238RMFS4"
    assert coupon["status"] == "EXPECTED"
    assert coupon["quantity"] == 15
    assert coupon["amount_total"] == "525.00"
    assert coupon["pay_date"] == days_ahead(10).isoformat()
    assert coupon["is_overdue"] is False


def test_dashboard_explicit_periods(client: TestClient, db_session: Session) -> None:
    _build_portfolio(db_session)

    expected = {
        "1M": (days_ago(30), 31),
        "3M": (days_ago(60), 61),
        "1Y": (days_ago(60), 61),
        "ALL": (days_ago(60), 61),
    }
    for period, (first_date, length) in expected.items():
        body = client.get("/api/dashboard", params={"period": period}).json()

        assert body["period"] == period
        assert len(body["series"]) == length
        assert body["series"][0]["date"] == first_date.isoformat()
        assert body["series"][-1]["date"] == today_local().isoformat()


def test_dashboard_invalid_period_is_422(client: TestClient) -> None:
    response = client.get("/api/dashboard", params={"period": "2Y"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["errors"][0]["field"] == "query.period"


def test_dashboard_uses_the_stored_period(client: TestClient, db_session: Session) -> None:
    _build_portfolio(db_session)
    settings_service.set_dashboard_period(db_session, "3M")

    body = client.get("/api/dashboard").json()

    assert body["period"] == "3M"
    assert body["series"][0]["date"] == days_ago(60).isoformat()


def test_dashboard_explicit_period_overrides_the_stored_one(
    client: TestClient, db_session: Session
) -> None:
    _build_portfolio(db_session)
    settings_service.set_dashboard_period(db_session, "1M")

    body = client.get("/api/dashboard", params={"period": "ALL"}).json()

    assert body["period"] == "ALL"


def test_dashboard_invalid_stored_period_falls_back_to_one_year(
    client: TestClient, db_session: Session
) -> None:
    _build_portfolio(db_session)
    settings_service.set_value(db_session, settings_service.DASHBOARD_PERIOD, "2Y")

    body = client.get("/api/dashboard").json()

    assert body["period"] == "1Y"


def test_dashboard_on_an_empty_portfolio(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()

    assert body["totals"]["market_value"] == "0.00"
    assert body["totals"]["assets_count"] == 0
    assert body["series"] == []
    assert body["positions"] == []
    assert body["upcoming_coupons"] == []
    assert body["is_partial"] is False


def test_dashboard_is_not_partial_when_every_point_has_a_quote(
    client: TestClient, db_session: Session
) -> None:
    stock = make_asset(db_session)
    add_operation(
        db_session,
        stock,
        trade_date=days_ago(2),
        quantity=2,
        price_micro=100_000_000,
    )
    add_quote(db_session, stock, quote_date=days_ago(2), price_micro=100_000_000)

    body = client.get("/api/dashboard").json()

    assert len(body["series"]) == 3
    assert all(point["is_partial"] is False for point in body["series"])
    assert body["is_partial"] is False


def test_dashboard_money_strings_are_fixed_two_decimals(
    client: TestClient, db_session: Session
) -> None:
    _build_portfolio(db_session)

    body = client.get("/api/dashboard").json()

    for value in body["totals"].values():
        if isinstance(value, str):
            assert value.count(".") == 1
            assert len(value.split(".")[1]) == 2
    for point in body["series"]:
        assert len(point["market_value"].split(".")[1]) == 2
        assert len(point["invested"].split(".")[1]) == 2
    assert body["series"][-1]["market_value"] == "15875.00"
    assert body["series"][-1]["invested"] == "15268.45"


def test_dashboard_period_uses_inclusive_days(client: TestClient, db_session: Session) -> None:
    _build_portfolio(db_session)

    body = client.get("/api/dashboard", params={"period": "1M"}).json()

    dates = [point["date"] for point in body["series"]]
    first = today_local() - timedelta(days=30)
    assert dates[0] == first.isoformat()
    assert len(dates) == 31
    assert len(set(dates)) == len(dates)


def test_openapi_documents_the_dashboard_endpoint(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    path = schema["paths"]["/api/dashboard"]["get"]
    assert path["summary"] == "Дашборд портфеля"
    period = next(parameter for parameter in path["parameters"] if parameter["name"] == "period")
    assert period["required"] is False
    variants = period["schema"].get("anyOf", [period["schema"]])
    enum_values = next(variant["enum"] for variant in variants if "enum" in variant)
    assert set(enum_values) == {"1M", "3M", "1Y", "ALL"}
