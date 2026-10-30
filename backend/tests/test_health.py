"""Tests for service endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import __version__
from app.core.time import to_local, utc_now_naive
from app.services import settings_service


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["database"] == "ok"
    assert body["moex"] == "unknown"
    assert body["last_quote_refresh_at"] is None


@pytest.mark.parametrize(
    ("refresh_status", "expected"),
    [("ok", "ok"), ("partial", "ok"), ("failed", "error")],
)
def test_health_reports_last_refresh_status(
    client: TestClient,
    db_session: Session,
    refresh_status: str,
    expected: str,
) -> None:
    refreshed_at = utc_now_naive()
    settings_service.set_last_quote_refresh(db_session, refreshed_at, refresh_status)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["moex"] == expected
    assert body["last_quote_refresh_at"] == to_local(refreshed_at).isoformat()


def test_request_id_is_returned(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "test-request-id"})

    assert response.headers["X-Request-ID"] == "test-request-id"


def test_cors_exposes_the_export_filename_header(client: TestClient) -> None:
    response = client.get("/api/export", headers={"Origin": "http://localhost:4200"})

    assert response.status_code == 200
    assert "Content-Disposition" in response.headers
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "content-disposition" in exposed
    assert "x-request-id" in exposed


def test_unknown_route_uses_error_format(client: TestClient) -> None:
    response = client.get("/api/unknown")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.headers["X-Request-ID"]
