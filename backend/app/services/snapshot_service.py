"""Daily portfolio snapshots (plan §5.7/§6.8).

A snapshot is a cached valuation for one day. Market value and invested cost
are computed by the same replay as the dashboard chart; paid income is summed
cumulatively by pay date. The service never commits: the caller owns the
transaction.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.enums import IncomeStatus
from app.core.time import today_local, utc_now_naive
from app.db.models.income import Income
from app.db.models.snapshot import PortfolioSnapshot
from app.services import dashboard_service, portfolio_service


@dataclass(frozen=True, slots=True)
class SnapshotValues:
    """The three values stored for one day."""

    market_value_kopecks: int
    invested_kopecks: int
    income_paid_kopecks: int


def compute_for_date(session: Session, snapshot_date: date) -> SnapshotValues:
    """Compute the snapshot values for a date without storing them."""

    market_value, invested, _ = dashboard_service.value_on_date(session, snapshot_date)
    portfolio = portfolio_service.get_portfolio(session)
    income_paid = 0
    if portfolio is not None:
        income_paid = int(
            session.scalar(
                select(func.coalesce(func.sum(Income.amount_total_kopecks), 0)).where(
                    Income.portfolio_id == portfolio.id,
                    Income.status == IncomeStatus.PAID,
                    Income.pay_date <= snapshot_date,
                )
            )
            or 0
        )
    return SnapshotValues(
        market_value_kopecks=market_value,
        invested_kopecks=invested,
        income_paid_kopecks=income_paid,
    )


def upsert_snapshot(
    session: Session,
    snapshot_date: date,
    *,
    market_value_kopecks: int,
    invested_kopecks: int,
    income_paid_kopecks: int,
) -> PortfolioSnapshot:
    """Insert or update the single snapshot of ``(portfolio, date)``.

    The original ``created_at`` is preserved on update. Only ``flush`` is
    called; the caller decides when to commit.
    """

    portfolio = portfolio_service.ensure_default_portfolio(session, commit=False)
    statement = (
        sqlite_insert(PortfolioSnapshot)
        .values(
            portfolio_id=portfolio.id,
            snapshot_date=snapshot_date,
            market_value_kopecks=market_value_kopecks,
            invested_kopecks=invested_kopecks,
            income_paid_kopecks=income_paid_kopecks,
            created_at=utc_now_naive(),
        )
        .on_conflict_do_update(
            index_elements=["portfolio_id", "snapshot_date"],
            set_={
                "market_value_kopecks": market_value_kopecks,
                "invested_kopecks": invested_kopecks,
                "income_paid_kopecks": income_paid_kopecks,
            },
        )
    )
    session.execute(statement)
    session.flush()

    return session.scalars(
        select(PortfolioSnapshot)
        .where(
            PortfolioSnapshot.portfolio_id == portfolio.id,
            PortfolioSnapshot.snapshot_date == snapshot_date,
        )
        .execution_options(populate_existing=True)
    ).one()


def compute_and_store(
    session: Session,
    snapshot_date: date | None = None,
) -> PortfolioSnapshot:
    """Compute and upsert a snapshot; defaults to today in the local timezone."""

    target_date = snapshot_date or today_local()
    values = compute_for_date(session, target_date)
    return upsert_snapshot(
        session,
        target_date,
        market_value_kopecks=values.market_value_kopecks,
        invested_kopecks=values.invested_kopecks,
        income_paid_kopecks=values.income_paid_kopecks,
    )


def get_snapshots(session: Session, period: str = "1Y") -> list[PortfolioSnapshot]:
    """Return stored snapshots for a period, oldest first."""

    start = dashboard_service.period_start(period)
    portfolio = portfolio_service.get_portfolio(session)
    if portfolio is None:
        return []

    statement = select(PortfolioSnapshot).where(
        PortfolioSnapshot.portfolio_id == portfolio.id,
        PortfolioSnapshot.snapshot_date <= today_local(),
    )
    if start is not None:
        statement = statement.where(PortfolioSnapshot.snapshot_date >= start)
    statement = statement.order_by(
        PortfolioSnapshot.snapshot_date,
        PortfolioSnapshot.id,
    )
    return list(session.scalars(statement))
