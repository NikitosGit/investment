"""Database engine, session factory and SQLite pragmas."""

import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

_is_sqlite = _settings.database_url.startswith("sqlite")
if _is_sqlite:
    _database_path = make_url(_settings.database_url).database
    if _database_path and _database_path != ":memory:":
        Path(_database_path).parent.mkdir(parents=True, exist_ok=True)

engine: Engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it afterwards."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
