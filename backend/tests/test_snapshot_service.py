"""Snapshot service tests: valuation, cumulative income and upserts."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import IncomeKind, IncomeStatus
from app.core.errors import AppError, ErrorCode
from app.core.time import today_local
from app.db.models.portfolio import Portfolio
from app.db.models.snapshot import PortfolioSnapshot
from app.db.session import SessionLocal
from app.services import portfolio_service, snapshot_service

from dashboard_helpers import (  # isort: skip
    add_income,
    add_operation,
    add_quote,
    days_ago,
    days_ahead,
    make_asset,
)


def test_compute_for_date_uses_market_data_and_cumulative_income(
    db_session: Session,
) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(10), quantity=10, price_micro=100_000_000)
    add_quote(db_session, stock, quote_date=days_ago(5), price_micro=110_000_000)
    add_income(
        db_session,
        stock,
        kind=IncomeKind.DIVIDEND,
        status=IncomeStatus.PAID,
        pay_date=days_ago(20),
        quantity=10,
        amount_total_kopecks=20_000,
    )
    add_income(
        db_session,
        stock,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.PAID,
        pay_date=days_ago(4),
        quantity=10,
        amount_total_kopecks=52_500,
    )
    add_income(
        db_session,
        stock,
        kind=IncomeKind.DIVIDEND,
        status=IncomeStatus.PAID,
        pay_date=today_local(),
        quantity=10,
        amount_total_kopecks=5_000,
    )
    add_income(
        db_session,
        stock,
        kind=IncomeKind.DIVIDEND,
        status=IncomeStatus.PAID,
        pay_date=days_ahead(1),
        quantity=10,
        amount_total_kopecks=7_000,
    )

    before_quote = snapshot_service.compute_for_date(db_session, days_ago(7))
    assert before_quote.market_value_kopecks == 100_000
    assert before_quote.invested_kopecks == 100_000
    assert before_quote.income_paid_kopecks == 20_000

    mid = snapshot_service.compute_for_date(db_session, days_ago(3))
    assert mid.market_value_kopecks == 110_000
    assert mid.invested_kopecks == 100_000
    assert mid.income_paid_kopecks == 72_500

    latest = snapshot_service.compute_for_date(db_session, today_local())
    assert latest.market_value_kopecks == 110_000
    assert latest.income_paid_kopecks == 77_500


def test_compute_for_date_on_an_empty_portfolio(db_session: Session) -> None:
    values = snapshot_service.compute_for_date(db_session, today_local())

    assert values.market_value_kopecks == 0
    assert values.invested_kopecks == 0
    assert values.income_paid_kopecks == 0
    assert db_session.scalar(select(func.count()).select_from(Portfolio)) == 0


def test_upsert_snapshot_inserts_and_preserves_created_at(db_session: Session) -> None:
    snapshot = snapshot_service.upsert_snapshot(
        db_session,
        days_ago(1),
        market_value_kopecks=100_000,
        invested_kopecks=80_000,
        income_paid_kopecks=5_000,
    )
    db_session.commit()
    snapshot_id = snapshot.id
    created_at = snapshot.created_at
    assert created_at is not None

    updated = snapshot_service.upsert_snapshot(
        db_session,
        days_ago(1),
        market_value_kopecks=110_000,
        invested_kopecks=90_000,
        income_paid_kopecks=6_000,
    )
    db_session.commit()
    db_session.expire_all()

    stored = db_session.scalars(select(PortfolioSnapshot)).one()
    assert updated.id == snapshot_id == stored.id
    assert stored.market_value_kopecks == 110_000
    assert stored.invested_kopecks == 90_000
    assert stored.income_paid_kopecks == 6_000
    assert stored.created_at == created_at
    assert db_session.scalar(select(func.count()).select_from(PortfolioSnapshot)) == 1


def test_upsert_snapshot_never_commits(db_session: Session) -> None:
    snapshot_service.upsert_snapshot(
        db_session,
        days_ago(1),
        market_value_kopecks=1,
        invested_kopecks=2,
        income_paid_kopecks=3,
    )
    db_session.rollback()

    with SessionLocal() as other:
        assert other.scalar(select(func.count()).select_from(PortfolioSnapshot)) == 0
        assert other.scalar(select(func.count()).select_from(Portfolio)) == 0


def test_compute_and_store_defaults_to_today(db_session: Session) -> None:
    snapshot = snapshot_service.compute_and_store(db_session)
    db_session.commit()

    assert snapshot.snapshot_date == today_local()
    assert snapshot.market_value_kopecks == 0
    assert snapshot.invested_kopecks == 0
    assert snapshot.income_paid_kopecks == 0
    assert snapshot.portfolio_id == portfolio_service.ensure_default_portfolio(db_session).id


def test_compute_and_store_explicit_date_and_idempotency(db_session: Session) -> None:
    stock = make_asset(db_session)
    add_operation(db_session, stock, trade_date=days_ago(5), quantity=2, price_micro=50_000_000)
    add_quote(db_session, stock, quote_date=days_ago(2), price_micro=60_000_000)

    first = snapshot_service.compute_and_store(db_session, days_ago(2))
    db_session.commit()
    second = snapshot_service.compute_and_store(db_session, days_ago(2))
    db_session.commit()

    assert first.id == second.id
    assert second.market_value_kopecks == 12_000
    assert second.invested_kopecks == 10_000
    assert db_session.scalar(select(func.count()).select_from(PortfolioSnapshot)) == 1


def test_get_snapshots_filters_by_period_oldest_first(db_session: Session) -> None:
    for offset, value in ((40, 1), (20, 2), (5, 3)):
        snapshot_service.upsert_snapshot(
            db_session,
            days_ago(offset),
            market_value_kopecks=value,
            invested_kopecks=value,
            income_paid_kopecks=value,
        )
    db_session.commit()

    one_month = snapshot_service.get_snapshots(db_session, "1M")
    assert [item.snapshot_date for item in one_month] == [days_ago(20), days_ago(5)]

    for period in ("3M", "1Y", "ALL"):
        dates = [item.snapshot_date for item in snapshot_service.get_snapshots(db_session, period)]
        assert dates == [days_ago(40), days_ago(20), days_ago(5)]


def test_snapshot_exactly_at_the_month_boundary_is_included(db_session: Session) -> None:
    snapshot_service.upsert_snapshot(
        db_session,
        days_ago(30),
        market_value_kopecks=1,
        invested_kopecks=1,
        income_paid_kopecks=1,
    )
    db_session.commit()

    assert [item.snapshot_date for item in snapshot_service.get_snapshots(db_session, "1M")] == [
        days_ago(30)
    ]


def test_get_snapshots_excludes_future_dated_rows(db_session: Session) -> None:
    for snapshot_date in (today_local(), days_ahead(1)):
        snapshot_service.upsert_snapshot(
            db_session,
            snapshot_date,
            market_value_kopecks=1,
            invested_kopecks=1,
            income_paid_kopecks=1,
        )
    db_session.commit()

    assert [item.snapshot_date for item in snapshot_service.get_snapshots(db_session, "ALL")] == [
        today_local()
    ]


def test_get_snapshots_without_portfolio_is_empty(db_session: Session) -> None:
    assert snapshot_service.get_snapshots(db_session) == []


def test_get_snapshots_rejects_an_invalid_period(db_session: Session) -> None:
    with pytest.raises(AppError) as exc_info:
        snapshot_service.get_snapshots(db_session, "2Y")

    error = exc_info.value
    assert error.code == ErrorCode.BAD_REQUEST
    assert error.status_code == 400
    assert error.details == {"period": "2Y", "supported": ["1M", "3M", "1Y", "ALL"]}


def test_snapshot_values_are_present_on_an_empty_portfolio_date(
    db_session: Session,
) -> None:
    snapshot = snapshot_service.upsert_snapshot(
        db_session,
        date(2020, 1, 1),
        market_value_kopecks=0,
        invested_kopecks=0,
        income_paid_kopecks=0,
    )
    db_session.commit()

    assert snapshot.id is not None
    assert snapshot.market_value_kopecks == 0
