"""Tests for service endpoints."""

from fastapi.testclient import TestClient

from app import __version__


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["database"] == "ok"
    assert body["moex"] == "unknown"
    assert body["last_quote_refresh_at"] is None


def test_request_id_is_returned(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "test-request-id"})

    assert response.headers["X-Request-ID"] == "test-request-id"


def test_unknown_route_uses_error_format(client: TestClient) -> None:
    response = client.get("/api/unknown")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.headers["X-Request-ID"]
