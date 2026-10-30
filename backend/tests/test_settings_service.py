"""SettingsService persistence tests."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.services import settings_service


def test_get_value_returns_none_without_table() -> None:
    engine = create_engine("sqlite://")

    with Session(engine) as session:
        assert settings_service.get_value(session, "missing") is None


def test_set_value_inserts_and_updates(db_session: Session) -> None:
    assert settings_service.get_value(db_session, "dashboard_period") is None

    settings_service.set_value(db_session, "dashboard_period", "1Y")
    assert settings_service.get_value(db_session, "dashboard_period") == "1Y"

    settings_service.set_value(db_session, "dashboard_period", "3M")
    assert settings_service.get_value(db_session, "dashboard_period") == "3M"


def test_last_refresh_round_trip(db_session: Session) -> None:
    at = datetime(2026, 10, 19, 16, 5, tzinfo=UTC)

    settings_service.set_last_quote_refresh(db_session, at, "partial")

    assert settings_service.get_last_quote_refresh_at(db_session) == datetime(2026, 10, 19, 16, 5)
    assert (
        settings_service.get_value(db_session, settings_service.LAST_QUOTE_REFRESH_STATUS)
        == "partial"
    )


def test_invalid_timestamp_is_ignored(db_session: Session) -> None:
    settings_service.set_value(db_session, settings_service.LAST_QUOTE_REFRESH_AT, "not-a-date")

    assert settings_service.get_last_quote_refresh_at(db_session) is None


def test_quote_refresh_enabled_defaults_and_round_trip(db_session: Session) -> None:
    assert settings_service.get_quote_refresh_enabled(db_session, default=True) is True
    assert settings_service.get_quote_refresh_enabled(db_session, default=False) is False

    settings_service.set_quote_refresh_enabled(db_session, False)
    assert settings_service.get_quote_refresh_enabled(db_session, default=True) is False
    assert settings_service.get_value(db_session, settings_service.QUOTE_REFRESH_ENABLED) == "false"

    settings_service.set_quote_refresh_enabled(db_session, True)
    assert settings_service.get_quote_refresh_enabled(db_session, default=False) is True
    assert settings_service.get_value(db_session, settings_service.QUOTE_REFRESH_ENABLED) == "true"


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("On", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        (" off ", False),
    ],
)
def test_quote_refresh_enabled_parses_aliases(
    db_session: Session, stored: str, expected: bool
) -> None:
    settings_service.set_value(db_session, settings_service.QUOTE_REFRESH_ENABLED, stored)

    assert settings_service.get_quote_refresh_enabled(db_session, default=not expected) is expected


def test_quote_refresh_enabled_invalid_value_uses_default(db_session: Session) -> None:
    settings_service.set_value(db_session, settings_service.QUOTE_REFRESH_ENABLED, "maybe")

    assert settings_service.get_quote_refresh_enabled(db_session, default=True) is True
    assert settings_service.get_quote_refresh_enabled(db_session, default=False) is False


def test_dashboard_period_defaults_and_validation(db_session: Session) -> None:
    assert settings_service.get_dashboard_period(db_session) == "1Y"

    for period in settings_service.DASHBOARD_PERIODS:
        settings_service.set_dashboard_period(db_session, period)
        assert settings_service.get_dashboard_period(db_session) == period

    settings_service.set_value(db_session, settings_service.DASHBOARD_PERIOD, "2Y")
    assert settings_service.get_dashboard_period(db_session) == "1Y"
    assert settings_service.get_dashboard_period(db_session, default="3M") == "3M"


def test_set_dashboard_period_rejects_unsupported_value(db_session: Session) -> None:
    with pytest.raises(AppError) as error:
        settings_service.set_dashboard_period(db_session, "6M")

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert settings_service.get_dashboard_period(db_session) == "1Y"


def test_all_values_returns_stored_settings(db_session: Session) -> None:
    assert settings_service.all_values(db_session) == {}

    settings_service.set_value(db_session, "zeta", "1")
    settings_service.set_value(db_session, "alpha", "2")
    settings_service.set_quote_refresh_enabled(db_session, True, commit=False)
    db_session.commit()

    assert settings_service.all_values(db_session) == {
        "alpha": "2",
        "quote_refresh_enabled": "true",
        "zeta": "1",
    }


def test_all_values_propagates_database_errors() -> None:
    engine = create_engine("sqlite://")

    with Session(engine) as session, pytest.raises(SQLAlchemyError):
        settings_service.all_values(session)


def test_effective_quote_refresh_requires_the_env_master_switch(db_session: Session) -> None:
    assert settings_service.effective_quote_refresh_enabled(db_session, env_enabled=True) is True

    settings_service.set_quote_refresh_enabled(db_session, True)
    assert settings_service.effective_quote_refresh_enabled(db_session, env_enabled=False) is False
    assert settings_service.effective_quote_refresh_enabled(db_session, env_enabled=True) is True

    settings_service.set_quote_refresh_enabled(db_session, False)
    assert settings_service.effective_quote_refresh_enabled(db_session, env_enabled=True) is False
