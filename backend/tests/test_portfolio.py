"""Portfolio API tests."""

from fastapi.testclient import TestClient

from app.db.models.portfolio import DEFAULT_PORTFOLIO_NAME


def test_reading_portfolio_creates_default(client: TestClient) -> None:
    response = client.get("/api/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == DEFAULT_PORTFOLIO_NAME
    assert body["base_currency"] == "RUB"
    assert body["id"] > 0
    assert body["created_at"].endswith(("Z", "+00:00"))


def test_reading_portfolio_is_idempotent(client: TestClient) -> None:
    first = client.get("/api/portfolio").json()
    second = client.get("/api/portfolio").json()

    assert first["id"] == second["id"]


def test_renaming_portfolio_persists(client: TestClient) -> None:
    response = client.patch("/api/portfolio", json={"name": "Основной"})

    assert response.status_code == 200
    assert response.json()["name"] == "Основной"
    assert client.get("/api/portfolio").json()["name"] == "Основной"


def test_empty_name_is_rejected(client: TestClient) -> None:
    response = client.patch("/api/portfolio", json={"name": "   "})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["errors"]
