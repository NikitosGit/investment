"""Daily portfolio snapshot model."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class PortfolioSnapshot(Base):
    """Cached portfolio valuation for a single day."""

    __tablename__ = "portfolio_snapshot"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date"),
        Index("ix_portfolio_snapshot_portfolio_date", "portfolio_id", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    market_value_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    invested_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    income_paid_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
