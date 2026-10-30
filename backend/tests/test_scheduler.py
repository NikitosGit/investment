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


class _FailingCloseClient(_FakeClient):
    """A client whose shutdown fails."""

    def close(self) -> None:
        raise RuntimeError("close boom")


class _FakeSession:
    """Minimal session for the disabled-refresh path."""

    def __init__(self, stored_setting: str | None = None) -> None:
        self.stored_setting = stored_setting

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def scalar(self, _: object) -> str | None:
        return self.stored_setting


class _RecordingSession:
    """Fake session that records transaction control calls."""

    instances: ClassVar[list["_RecordingSession"]] = []

    def __init__(self, stored_setting: str | None = None) -> None:
        self.stored_setting = stored_setting
        self.commits = 0
        self.rollbacks = 0
        _RecordingSession.instances.append(self)

    def __enter__(self) -> "_RecordingSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def scalar(self, _: object) -> str | None:
        return self.stored_setting

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _patch_job(
    monkeypatch: pytest.MonkeyPatch,
    refresh_all: Any,
    session_factory: Any = _FakeSession,
    *,
    stored_enabled: str | None = None,
    env_enabled: bool = True,
    client_class: Any = _FakeClient,
) -> None:
    _FakeClient.instances.clear()
    _RecordingSession.instances.clear()
    monkeypatch.setattr(
        refresh_job,
        "get_settings",
        lambda: _settings(quote_refresh_enabled=env_enabled),
    )
    monkeypatch.setattr(refresh_job, "MoexClient", client_class)
    monkeypatch.setattr(refresh_job, "SessionLocal", lambda: session_factory(stored_enabled))
    monkeypatch.setattr(refresh_job.quote_service, "refresh_all", refresh_all)


def _refresh_result() -> RefreshResult:
    return RefreshResult(
        updated=1,
        failed=0,
        last_refresh_at=utc_now_naive(),
        errors=[],
    )


def test_daily_refresh_closes_client_and_skips_running_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_calls: list[Any] = []

    def _busy(*_: Any) -> Any:
        raise AppError(
            ErrorCode.REFRESH_IN_PROGRESS,
            "Обновление котировок уже выполняется",
            status_code=409,
        )

    _patch_job(monkeypatch, _busy)
    monkeypatch.setattr(
        refresh_job.snapshot_service,
        "compute_and_store",
        lambda session: snapshot_calls.append(session),
    )

    refresh_job.run_daily_refresh()

    assert len(_FakeClient.instances) == 1
    assert _FakeClient.instances[0].closed
    assert snapshot_calls == []


def test_daily_refresh_computes_a_snapshot_after_a_successful_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_calls: list[Any] = []
    _patch_job(monkeypatch, lambda *_: _refresh_result(), _RecordingSession)
    monkeypatch.setattr(
        refresh_job.snapshot_service,
        "compute_and_store",
        lambda session: snapshot_calls.append(session),
    )

    refresh_job.run_daily_refresh()

    session = _RecordingSession.instances[0]
    assert snapshot_calls == [session]
    assert session.commits == 1
    assert session.rollbacks == 0
    assert _FakeClient.instances[0].closed


def test_daily_refresh_swallows_snapshot_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(_: Any) -> None:
        raise RuntimeError("snapshot boom")

    logged: list[str] = []

    def _capture(message: str, *args: Any) -> None:
        logged.append(message)

    _patch_job(monkeypatch, lambda *_: _refresh_result(), _RecordingSession)
    monkeypatch.setattr(refresh_job.snapshot_service, "compute_and_store", _fail)
    monkeypatch.setattr(refresh_job.logger, "exception", _capture)

    refresh_job.run_daily_refresh()

    session = _RecordingSession.instances[0]
    assert session.commits == 0
    assert session.rollbacks == 1
    assert "Daily snapshot failed" in logged
    assert _FakeClient.instances[0].closed


def test_daily_refresh_swallows_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_calls: list[Any] = []

    def _boom(*_: Any) -> Any:
        raise RuntimeError("boom")

    _patch_job(monkeypatch, _boom)
    monkeypatch.setattr(
        refresh_job.snapshot_service,
        "compute_and_store",
        lambda session: snapshot_calls.append(session),
    )

    refresh_job.run_daily_refresh()

    assert snapshot_calls == []
    assert _FakeClient.instances[0].closed


def test_daily_refresh_logs_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    result = RefreshResult(
        updated=1,
        failed=1,
        last_refresh_at=utc_now_naive(),
        errors=[RefreshError(asset_id=1, secid="GAZP", error="MOEX недоступен")],
    )
    _patch_job(monkeypatch, lambda *_: result, _RecordingSession)
    monkeypatch.setattr(refresh_job.snapshot_service, "compute_and_store", lambda _: None)

    refresh_job.run_daily_refresh()

    assert _FakeClient.instances[0].closed
    assert _RecordingSession.instances[0].commits == 1


def test_daily_refresh_skips_when_disabled_in_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    snapshot_calls: list[Any] = []

    def _refresh(*_: Any) -> Any:
        calls.append(True)
        return _refresh_result()

    _patch_job(
        monkeypatch,
        _refresh,
        _RecordingSession,
        stored_enabled="false",
        env_enabled=True,
    )
    monkeypatch.setattr(
        refresh_job.snapshot_service,
        "compute_and_store",
        lambda session: snapshot_calls.append(session),
    )
    logged: list[str] = []
    monkeypatch.setattr(refresh_job.logger, "info", lambda message, *args: logged.append(message))

    refresh_job.run_daily_refresh()

    assert calls == []
    assert _FakeClient.instances == []
    assert snapshot_calls == []
    assert any("disabled" in message for message in logged)


def test_daily_refresh_skips_when_master_switch_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    _patch_job(
        monkeypatch,
        lambda *_: calls.append(True) or _refresh_result(),
        _RecordingSession,
        stored_enabled="true",
        env_enabled=False,
    )

    refresh_job.run_daily_refresh()

    assert calls == []
    assert _FakeClient.instances == []


def test_daily_refresh_runs_when_enabled_in_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    _patch_job(
        monkeypatch,
        lambda *_: calls.append(True) or _refresh_result(),
        _RecordingSession,
        stored_enabled="true",
        env_enabled=True,
    )
    monkeypatch.setattr(refresh_job.snapshot_service, "compute_and_store", lambda _: None)

    refresh_job.run_daily_refresh()

    assert calls == [True]
    assert len(_FakeClient.instances) == 1
    assert _FakeClient.instances[0].closed
    assert _RecordingSession.instances[0].commits == 1


def test_daily_refresh_uses_env_default_when_setting_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []
    _patch_job(
        monkeypatch,
        lambda *_: calls.append(True) or _refresh_result(),
        _FakeSession,
        stored_enabled=None,
        env_enabled=False,
    )

    refresh_job.run_daily_refresh()

    assert calls == []
    assert _FakeClient.instances == []


def test_daily_refresh_falls_back_to_enabled_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    _patch_job(
        monkeypatch,
        lambda *_: calls.append(True) or _refresh_result(),
        _FakeSession,
        stored_enabled=None,
        env_enabled=True,
    )
    monkeypatch.setattr(refresh_job.snapshot_service, "compute_and_store", lambda _: None)
    monkeypatch.setattr(_FakeSession, "commit", lambda _: None, raising=False)

    refresh_job.run_daily_refresh()

    assert calls == [True]
    assert len(_FakeClient.instances) == 1


def test_daily_refresh_propagates_other_app_errors_to_the_outer_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(*_: Any) -> Any:
        raise AppError(ErrorCode.BAD_REQUEST, "bad request", status_code=400)

    logged: list[str] = []
    _patch_job(monkeypatch, _fail, _RecordingSession)
    monkeypatch.setattr(
        refresh_job.logger,
        "exception",
        lambda message, *args: logged.append(message),
    )

    refresh_job.run_daily_refresh()

    assert "Daily quote refresh failed" in logged
    assert _FakeClient.instances[0].closed


def test_daily_refresh_swallows_client_close_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []
    _patch_job(
        monkeypatch,
        lambda *_: _refresh_result(),
        _RecordingSession,
        client_class=_FailingCloseClient,
    )
    monkeypatch.setattr(refresh_job.snapshot_service, "compute_and_store", lambda _: None)
    monkeypatch.setattr(
        refresh_job.logger,
        "exception",
        lambda message, *args: logged.append(message),
    )

    refresh_job.run_daily_refresh()

    assert "Failed to close the quote refresh MOEX client" in logged
