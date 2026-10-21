"""SettingsService persistence tests."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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
