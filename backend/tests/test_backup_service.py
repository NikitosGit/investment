"""Backup service and CLI tests: consistency, naming and failure handling."""

import re
import runpy
import sqlite3
import threading
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.time import local_now
from app.scripts import backup as backup_script
from app.services import backup_service

from dashboard_helpers import build_dashboard_portfolio  # isort: skip

FILENAME_PATTERN = re.compile(r"investments-\d{8}-\d{6}(?:-\d+)?\.db")


@pytest.fixture
def backup_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Point the service at an isolated backup directory."""

    backup_dir = tmp_path / "backups"
    settings = Settings(backup_dir=backup_dir, cors_origins=[])
    monkeypatch.setattr(backup_service, "get_settings", lambda: settings)
    yield backup_dir


def test_create_backup_copies_a_valid_database(db_session: Session, backup_settings: Path) -> None:
    build_dashboard_portfolio(db_session)

    result = backup_service.create_backup()

    assert result.path.exists()
    assert result.path.parent == backup_settings
    assert FILENAME_PATTERN.fullmatch(result.path.name)
    assert result.size_bytes == result.path.stat().st_size
    assert result.size_bytes > 0
    assert result.created_at.tzinfo is not None

    connection = sqlite3.connect(result.path)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"portfolio", "asset", "operation"} <= tables
        assert connection.execute("SELECT COUNT(*) FROM portfolio").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM asset").fetchone()[0] == 2
    finally:
        connection.close()


def test_create_backup_uses_a_unique_filename(db_session: Session, backup_settings: Path) -> None:
    build_dashboard_portfolio(db_session)

    first = backup_service.create_backup()
    second = backup_service.create_backup()

    assert first.path != second.path
    assert first.path.exists()
    assert second.path.exists()
    assert FILENAME_PATTERN.fullmatch(second.path.name)


def test_concurrent_backups_use_distinct_files(db_session: Session, backup_settings: Path) -> None:
    build_dashboard_portfolio(db_session)
    barrier = threading.Barrier(2)
    results: list[backup_service.BackupResult] = []
    failures: list[BaseException] = []

    def _worker() -> None:
        barrier.wait()
        try:
            results.append(backup_service.create_backup())
        except Exception as exc:
            failures.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    assert len(results) == 2
    paths = [result.path for result in results]
    assert len(set(paths)) == 2
    assert all(path.exists() and path.parent == backup_settings for path in paths)


def test_create_backup_rejects_a_non_file_database(
    backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup_service, "engine", create_engine("sqlite://"))

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert not backup_settings.exists() or not any(backup_settings.iterdir())


def test_create_backup_rejects_a_missing_database_file(
    tmp_path: Path, backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.db"
    monkeypatch.setattr(
        backup_service,
        "engine",
        create_engine(f"sqlite:///{missing.as_posix()}"),
    )

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert not missing.exists()
    assert not backup_settings.exists() or not any(backup_settings.iterdir())


def test_create_backup_rejects_a_zero_byte_database(
    tmp_path: Path, backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    monkeypatch.setattr(
        backup_service,
        "engine",
        create_engine(f"sqlite:///{empty.as_posix()}"),
    )

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert empty.exists()
    assert empty.stat().st_size == 0
    assert not backup_settings.exists() or not any(backup_settings.iterdir())


def test_create_backup_rejects_a_database_without_the_application_schema(
    tmp_path: Path, backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unmigrated = tmp_path / "unmigrated.db"
    connection = sqlite3.connect(unmigrated)
    try:
        connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()
    monkeypatch.setattr(
        backup_service,
        "engine",
        create_engine(f"sqlite:///{unmigrated.as_posix()}"),
    )

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert "схема приложения" in error.value.message
    assert not backup_settings.exists() or not any(backup_settings.iterdir())


def test_create_backup_rejects_a_file_that_is_not_sqlite(
    tmp_path: Path, backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database")
    monkeypatch.setattr(
        backup_service,
        "engine",
        create_engine(f"sqlite:///{corrupt.as_posix()}"),
    )

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert "прочитать схему" in error.value.message
    assert not backup_settings.exists() or not any(backup_settings.iterdir())


def test_create_backup_wraps_an_unreadable_database(
    db_session: Session, backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dashboard_portfolio(db_session)

    def _unreadable(*_: object, **__: object) -> sqlite3.Connection:
        raise sqlite3.OperationalError("unreadable")

    monkeypatch.setattr(backup_service.sqlite3, "connect", _unreadable)

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert error.value.message == "Файл базы данных не найден или недоступен"
    assert list(backup_settings.iterdir()) == []


def test_create_backup_cleans_up_when_reservation_fails(
    db_session: Session, backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dashboard_portfolio(db_session)

    def _fail(*_: object) -> Path:
        raise RuntimeError("reservation boom")

    monkeypatch.setattr(backup_service, "_next_available_path", _fail)

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.INTERNAL_ERROR
    assert error.value.status_code == 500
    assert list(backup_settings.iterdir()) == []


def test_create_backup_rejects_an_in_memory_database(
    backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup_service, "engine", create_engine("sqlite:///:memory:"))

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert not backup_settings.exists() or not any(backup_settings.iterdir())


def test_create_backup_rejects_a_named_in_memory_database(
    backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine("sqlite:///file::memory:?cache=shared&uri=true")
    monkeypatch.setattr(backup_service, "engine", engine)

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.BAD_REQUEST


def test_create_backup_wraps_errors_before_a_destination_exists(
    backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _broken_settings() -> Settings:
        raise RuntimeError("config boom")

    monkeypatch.setattr(backup_service, "get_settings", _broken_settings)

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.INTERNAL_ERROR
    assert error.value.status_code == 500


def test_create_backup_removes_a_partial_file_on_failure(
    db_session: Session, backup_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dashboard_portfolio(db_session)

    def _fail_after_write(source: Path, destination: Path) -> None:
        del source
        destination.write_bytes(b"partial")
        raise RuntimeError("disk full")

    monkeypatch.setattr(backup_service, "_copy_sqlite_database", _fail_after_write)

    with pytest.raises(AppError) as error:
        backup_service.create_backup()

    assert error.value.code == ErrorCode.INTERNAL_ERROR
    assert error.value.status_code == 500
    assert error.value.message == "Не удалось создать резервную копию"
    assert list(backup_settings.iterdir()) == []


def test_cli_prints_the_created_backup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    result = backup_service.BackupResult(
        path=tmp_path / "investments-20260101-000000.db",
        size_bytes=1234,
        created_at=local_now(),
    )
    monkeypatch.setattr(backup_script.backup_service, "create_backup", lambda: result)

    exit_code = backup_script.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(result.path) in captured.out
    assert "1234" in captured.out
    assert captured.err == ""


def test_cli_exits_non_zero_on_failure(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail() -> backup_service.BackupResult:
        raise AppError(
            ErrorCode.INTERNAL_ERROR,
            "Не удалось создать резервную копию",
            status_code=500,
        )

    monkeypatch.setattr(backup_script.backup_service, "create_backup", _fail)

    exit_code = backup_script.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Не удалось создать резервную копию" in captured.err
    assert captured.out == ""


def test_cli_exits_non_zero_on_unexpected_failure(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail() -> backup_service.BackupResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(backup_script.backup_service, "create_backup", _fail)

    assert backup_script.main() == 1
    assert "boom" in capsys.readouterr().err


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_module_entrypoint_exits_with_the_main_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = backup_service.BackupResult(
        path=tmp_path / "investments-20260101-000000.db",
        size_bytes=7,
        created_at=local_now(),
    )
    monkeypatch.setattr(backup_script.backup_service, "create_backup", lambda: result)

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("app.scripts.backup", run_name="__main__")

    assert exit_info.value.code == 0


def test_database_path_uses_the_configured_engine(db_session: Session) -> None:
    del db_session
    path = backup_service._database_path()

    assert path.name == "test.db"


def test_connect_read_only_rejects_a_missing_file_without_creating_it(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"

    with pytest.raises(AppError) as error:
        backup_service._connect_read_only(missing)

    assert error.value.code == ErrorCode.BAD_REQUEST
    assert error.value.status_code == 400
    assert not missing.exists()


def test_next_available_path_adds_a_counter(tmp_path: Path) -> None:
    created_at = local_now()
    stem = f"investments-{created_at.strftime('%Y%m%d-%H%M%S')}"
    (tmp_path / f"{stem}.db").write_bytes(b"")
    (tmp_path / f"{stem}-1.db").write_bytes(b"")

    path = backup_service._next_available_path(tmp_path, created_at)

    assert path.name == f"{stem}-2.db"
