"""Tests that Alembic migrations build a complete schema on a clean database."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "app_setting",
    "asset",
    "bond_amortization",
    "income",
    "operation",
    "portfolio",
    "portfolio_snapshot",
    "quote",
}


def _config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "app" / "db" / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_upgrade_creates_all_tables(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'clean.db').as_posix()}"
    command.upgrade(_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert tables >= EXPECTED_TABLES


def test_downgrade_removes_application_tables(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'clean.db').as_posix()}"
    config = _config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert not EXPECTED_TABLES & tables
