"""Test fixtures for the backend suite."""

import json
import os
import shutil
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="investment-tracker-tests-"))
os.environ.setdefault("APP_ENV", "test")
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_DATA_DIR / 'test.db').as_posix()}"
os.environ["DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["BACKUP_DIR"] = str(_TEST_DATA_DIR / "backups")

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    """Remove the temporary data directory once the suite is done."""

    engine.dispose()
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_database() -> Generator[None, None, None]:
    """Recreate the schema before every test for isolation."""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def load_fixture() -> Callable[..., Any]:
    """Return a loader for JSON fixtures under ``tests/fixtures``."""

    def _load(*parts: str) -> Any:
        return json.loads(FIXTURES_DIR.joinpath(*parts).read_text(encoding="utf-8"))

    return _load
