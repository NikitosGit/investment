"""Settings API tests: defaults, partial updates and validation (plan §8.9)."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from app.services import settings_service


@pytest.fixture
def env_enabled(client: TestClient) -> Generator[None, None, None]:
    """Simulate a deployment whose master switch allows automatic refresh."""

    del client
    app.dependency_overrides[get_settings] = lambda: Settings(
        quote_refresh_enabled=True, cors_origins=[]
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_settings_defaults(client: TestClient) -> None:
    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {
        "quote_refresh_enabled": get_settings().quote_refresh_enabled,
        "dashboard_period": "1Y",
    }


def test_settings_default_to_enabled_when_the_master_switch_is_on(
    client: TestClient, env_enabled: None
) -> None:
    del env_enabled

    assert client.get("/api/settings").json()["quote_refresh_enabled"] is True


def test_settings_patch_both_keys(
    client: TestClient, db_session: Session, env_enabled: None
) -> None:
    del env_enabled

    response = client.patch(
        "/api/settings",
        json={"quote_refresh_enabled": True, "dashboard_period": "3M"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "quote_refresh_enabled": True,
        "dashboard_period": "3M",
    }
    assert client.get("/api/settings").json() == {
        "quote_refresh_enabled": True,
        "dashboard_period": "3M",
    }
    assert settings_service.get_value(db_session, settings_service.QUOTE_REFRESH_ENABLED) == "true"
    assert settings_service.get_value(db_session, settings_service.DASHBOARD_PERIOD) == "3M"


def test_settings_patch_one_key_keeps_the_other(client: TestClient) -> None:
    client.patch("/api/settings", json={"dashboard_period": "ALL"})

    response = client.patch("/api/settings", json={"quote_refresh_enabled": False})

    assert response.status_code == 200
    assert response.json() == {
        "quote_refresh_enabled": False,
        "dashboard_period": "ALL",
    }


def test_settings_patch_is_persisted_between_requests(client: TestClient) -> None:
    client.patch("/api/settings", json={"quote_refresh_enabled": False})

    assert client.get("/api/settings").json()["quote_refresh_enabled"] is False
    assert client.get("/api/dashboard").json()["period"] == "1Y"


def test_settings_env_master_switch_wins_over_a_stored_true(
    client: TestClient, db_session: Session
) -> None:
    settings_service.set_quote_refresh_enabled(db_session, True)
    assert get_settings().quote_refresh_enabled is False

    assert client.get("/api/settings").json()["quote_refresh_enabled"] is False

    response = client.patch(
        "/api/settings",
        json={"quote_refresh_enabled": True, "dashboard_period": "3M"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert "развёртывания" in response.json()["error"]["message"]
    assert settings_service.get_value(db_session, settings_service.QUOTE_REFRESH_ENABLED) == "true"
    assert settings_service.get_value(db_session, settings_service.DASHBOARD_PERIOD) is None


def test_settings_env_false_still_allows_disabling(client: TestClient, db_session: Session) -> None:
    response = client.patch("/api/settings", json={"quote_refresh_enabled": False})

    assert response.status_code == 200
    assert response.json()["quote_refresh_enabled"] is False
    assert settings_service.get_value(db_session, settings_service.QUOTE_REFRESH_ENABLED) == "false"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"quote_refresh_enabled": None},
        {"dashboard_period": None},
        {"quote_refresh_enabled": True, "dashboard_period": None},
    ],
)
def test_settings_empty_or_null_payloads_are_422(client: TestClient, payload: dict) -> None:
    response = client.patch("/api/settings", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_settings_unknown_key_is_422(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"unknown": True})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_settings_invalid_period_is_422(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"dashboard_period": "2Y"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_settings_invalid_boolean_is_422(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"quote_refresh_enabled": "maybe"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_openapi_documents_the_settings_endpoints(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/settings"]["get"]["summary"] == "Получить настройки"
    assert schema["paths"]["/api/settings"]["patch"]["summary"] == "Изменить настройки"
