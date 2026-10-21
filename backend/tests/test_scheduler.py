"""Scheduler and daily job wiring tests."""

from datetime import UTC, datetime
from typing import Any, ClassVar

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now_naive
from app.jobs import refresh as refresh_job
from app.jobs import scheduler as scheduler_module
from app.jobs.scheduler import (
    DAILY_JOB_ID,
    STARTUP_JOB_ID,
    create_scheduler,
    shutdown_scheduler,
    start_scheduler,
)
from app.services.quote_service import RefreshError, RefreshResult


def _settings(**overrides: Any) -> Settings:
    options: dict[str, Any] = {
        "quote_refresh_enabled": True,
        "quote_refresh_hour": 20,
        "quote_refresh_minute": 7,
        "timezone": "Europe/Moscow",
        "cors_origins": [],
    }
    options.update(overrides)
    return Settings(**options)


def test_scheduler_disabled_returns_none() -> None:
    settings = _settings(quote_refresh_enabled=False)

    assert create_scheduler(settings) is None
    assert start_scheduler(settings) is None
    shutdown_scheduler(None)


def test_scheduler_has_daily_and_startup_jobs() -> None:
    scheduler = create_scheduler(_settings(), startup_delay_seconds=15)

    assert scheduler is not None
    assert not scheduler.running
    assert str(scheduler.timezone) == "Europe/Moscow"
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {DAILY_JOB_ID, STARTUP_JOB_ID}

    daily = jobs[DAILY_JOB_ID]
    assert str(daily.trigger) == "cron[hour='20', minute='7']"
    assert str(daily.trigger.timezone) == "Europe/Moscow"

    startup = jobs[STARTUP_JOB_ID]
    assert isinstance(startup.trigger, DateTrigger)
    assert startup.trigger.run_date > datetime.now(UTC)


def test_start_and_shutdown_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    # A started scheduler would fire the real startup job; keep it inert.
    monkeypatch.setattr(scheduler_module, "run_daily_refresh", lambda: None)

    scheduler = start_scheduler(_settings(quote_refresh_hour=3, quote_refresh_minute=0))

    assert isinstance(scheduler, BackgroundScheduler)
    assert scheduler.running
    shutdown_scheduler(scheduler)
    assert not scheduler.running


class _FakeClient:
    """Records construction and closes instead of touching the network."""

    instances: ClassVar[list["_FakeClient"]] = []

    def __init__(self) -> None:
        self.closed = False
        _FakeClient.instances.append(self)

    @classmethod
    def from_settings(cls, settings: Settings) -> "_FakeClient":
        return cls()

    def close(self) -> None:
        self.closed = True


class _FakeSession:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *args: object) -> None:
        return None


def _patch_job(monkeypatch: pytest.MonkeyPatch, refresh_all: Any) -> None:
    _FakeClient.instances.clear()
    monkeypatch.setattr(refresh_job, "MoexClient", _FakeClient)
    monkeypatch.setattr(refresh_job, "SessionLocal", _FakeSession)
    monkeypatch.setattr(refresh_job.quote_service, "refresh_all", refresh_all)


def test_daily_refresh_closes_client_and_skips_running_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _busy(*_: Any) -> Any:
        raise AppError(
            ErrorCode.REFRESH_IN_PROGRESS,
            "Обновление котировок уже выполняется",
            status_code=409,
        )

    _patch_job(monkeypatch, _busy)

    refresh_job.run_daily_refresh()

    assert len(_FakeClient.instances) == 1
    assert _FakeClient.instances[0].closed


def test_daily_refresh_swallows_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_: Any) -> Any:
        raise RuntimeError("boom")

    _patch_job(monkeypatch, _boom)

    refresh_job.run_daily_refresh()

    assert _FakeClient.instances[0].closed


def test_daily_refresh_logs_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    result = RefreshResult(
        updated=1,
        failed=1,
        last_refresh_at=utc_now_naive(),
        errors=[RefreshError(asset_id=1, secid="GAZP", error="MOEX недоступен")],
    )
    _patch_job(monkeypatch, lambda *_: result)

    refresh_job.run_daily_refresh()

    assert _FakeClient.instances[0].closed
