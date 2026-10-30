"""Tests for the demo seed script (plan §15)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.db.models.quote import Quote
from app.db.models.setting import AppSetting
from app.db.models.snapshot import PortfolioSnapshot
from app.scripts import seed_demo as seed_module
from app.scripts.seed_demo import (
    DEMO_SEED_ANCHOR_KEY,
    DEMO_SEED_VERSION_KEY,
    seed_demo,
)
from app.services import settings_service


def _table_counts(session: Session) -> dict[str, int]:
    return {
        "assets": int(session.scalar(select(func.count()).select_from(Asset)) or 0),
        "operations": int(session.scalar(select(func.count()).select_from(Operation)) or 0),
        "quotes": int(session.scalar(select(func.count()).select_from(Quote)) or 0),
        "income": int(session.scalar(select(func.count()).select_from(Income)) or 0),
        "amortizations": int(
            session.scalar(select(func.count()).select_from(BondAmortization)) or 0
        ),
        "snapshots": int(session.scalar(select(func.count()).select_from(PortfolioSnapshot)) or 0),
    }


def _position(client: TestClient, secid: str) -> dict:
    items = client.get("/api/positions").json()["items"]
    return next(item for item in items if item["asset"]["secid"] == secid)


def test_seed_creates_the_demo_portfolio(client: TestClient, db_session: Session) -> None:
    summary = seed_demo(db_session)

    assert summary.already_seeded is False
    assert summary.assets_created == 2
    assert summary.operations_created == 4
    assert summary.quotes_created == 54
    assert summary.income_created == 5
    assert summary.amortizations_created == 1
    assert summary.snapshot_created is True

    assert _table_counts(db_session) == {
        "assets": 2,
        "operations": 4,
        "quotes": 54,
        "income": 5,
        "amortizations": 1,
        "snapshots": 1,
    }

    snapshot = db_session.scalar(
        select(PortfolioSnapshot).where(PortfolioSnapshot.snapshot_date == today_local())
    )
    assert snapshot is not None

    dashboard = client.get("/api/dashboard", params={"period": "1Y"}).json()
    assert len(dashboard["positions"]) == 2
    assert dashboard["series"]
    assert len(dashboard["upcoming_coupons"]) == 3
    assert dashboard["totals"]["expected_coupons"] == "1575.00"
    assert dashboard["totals"]["dividends_paid"] == "200.00"
    assert dashboard["totals"]["coupons_paid"] == "525.00"


def test_seed_is_idempotent(client: TestClient, db_session: Session) -> None:
    first = seed_demo(db_session)
    counts_before = _table_counts(db_session)

    second = seed_demo(db_session)

    assert first.already_seeded is False
    assert second.already_seeded is True
    assert second.assets_created == 0
    assert second.operations_created == 0
    assert second.quotes_created == 0
    assert second.income_created == 0
    assert second.amortizations_created == 0
    assert second.snapshot_created is False
    assert _table_counts(db_session) == counts_before


def test_seed_positions_keep_purchase_percent_after_amortization(
    client: TestClient, db_session: Session
) -> None:
    seed_demo(db_session)

    stock = _position(client, "SBER")
    assert stock["quantity"] == 15
    assert stock["avg_price"] == "110.000000"
    assert stock["avg_price_percent"] is None

    bond = _position(client, "SU26238RMFS4")
    assert bond["quantity"] == 15
    assert bond["avg_price"] == "951.230000"
    assert bond["avg_price_percent"] == "95.123000"
    assert bond["current_face_value"] == "800.00"


def test_seed_repairs_deleted_demo_rows_without_shifting_dates(
    client: TestClient, db_session: Session
) -> None:
    seed_demo(db_session)
    anchor = db_session.get(AppSetting, DEMO_SEED_ANCHOR_KEY).value

    stock = db_session.scalar(select(Asset).where(Asset.secid == "SBER"))
    sell = db_session.scalar(
        select(Operation).where(
            Operation.asset_id == stock.id,
            Operation.type == "SELL",
        )
    )
    quote = db_session.scalar(select(Quote).where(Quote.asset_id == stock.id))
    expected = db_session.scalar(
        select(Income).where(Income.status == "EXPECTED").order_by(Income.pay_date)
    )
    marker = db_session.get(AppSetting, DEMO_SEED_VERSION_KEY)
    db_session.delete(sell)
    db_session.delete(quote)
    db_session.delete(expected)
    db_session.delete(marker)
    db_session.commit()

    summary = seed_demo(db_session)

    assert summary.already_seeded is False
    assert summary.assets_created == 0
    assert summary.operations_created == 1
    assert summary.quotes_created == 1
    assert summary.income_created == 1
    assert summary.amortizations_created == 0
    assert summary.snapshot_created is False
    assert db_session.get(AppSetting, DEMO_SEED_ANCHOR_KEY).value == anchor
    assert _table_counts(db_session)["operations"] == 4
    assert _table_counts(db_session)["quotes"] == 54
    assert _table_counts(db_session)["income"] == 5


def test_seed_rolls_back_everything_when_a_late_step_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_: object, **__: object) -> None:
        raise RuntimeError("snapshot failed")

    with monkeypatch.context() as patcher:
        patcher.setattr(seed_module.snapshot_service, "compute_and_store", _boom)
        with pytest.raises(RuntimeError, match="snapshot failed"):
            seed_demo(db_session)

    assert _table_counts(db_session) == {
        "assets": 0,
        "operations": 0,
        "quotes": 0,
        "income": 0,
        "amortizations": 0,
        "snapshots": 0,
    }
    assert db_session.scalar(select(func.count()).select_from(AppSetting)) == 0

    # The rolled-back session is reusable and a retry succeeds normally.
    summary = seed_demo(db_session)
    assert summary.assets_created == 2
    assert _table_counts(db_session)["operations"] == 4


def test_seed_falls_back_to_today_when_the_stored_anchor_is_invalid(
    db_session: Session,
) -> None:
    settings_service.set_value(db_session, DEMO_SEED_ANCHOR_KEY, "not-a-date")

    seed_demo(db_session, today=date(2026, 5, 15))

    assert db_session.get(AppSetting, DEMO_SEED_ANCHOR_KEY).value == "2026-05-15"
    assert db_session.get(AppSetting, DEMO_SEED_VERSION_KEY).value == "1"


def test_seed_cli_reports_success_and_idempotence(capsys: pytest.CaptureFixture[str]) -> None:
    assert seed_module.main() == 0
    first_output = capsys.readouterr().out
    assert "Демо-данные загружены" in first_output
    assert "котировок: 54" in first_output

    assert seed_module.main() == 0
    second_output = capsys.readouterr().out
    assert "уже загружены" in second_output


@pytest.mark.parametrize("error", [SQLAlchemyError("db"), RuntimeError("boom")])
def test_seed_cli_reports_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    def _raise(*_: object, **__: object) -> None:
        raise error

    monkeypatch.setattr(seed_module, "seed_demo", _raise)

    assert seed_module.main() == 1
    error_output = capsys.readouterr().err
    assert "Не удалось загрузить демо-данные" in error_output
    assert "alembic upgrade head" in error_output


def test_seed_stores_an_iso_anchor(db_session: Session) -> None:
    seed_demo(db_session, today=date(2026, 5, 15))

    assert db_session.get(AppSetting, DEMO_SEED_ANCHOR_KEY).value == "2026-05-15"
    assert db_session.get(AppSetting, DEMO_SEED_VERSION_KEY).value == "1"
