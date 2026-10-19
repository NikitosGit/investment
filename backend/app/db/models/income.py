"""Income model for dividends and coupons."""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base, db_enum
from app.db.enums import DataSource, IncomeKind, IncomeStatus


class Income(Base):
    """An expected or paid dividend/coupon."""

    __tablename__ = "income"
    __table_args__ = (
        UniqueConstraint("external_id"),
        Index("ix_income_asset_status_pay_date", "asset_id", "status", "pay_date"),
        Index("ix_income_portfolio_kind_status", "portfolio_id", "kind", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    kind: Mapped[IncomeKind] = mapped_column(db_enum(IncomeKind), nullable=False)
    status: Mapped[IncomeStatus] = mapped_column(db_enum(IncomeStatus), nullable=False)
    amount_per_unit_micro: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int | None] = mapped_column(Integer)
    amount_total_kopecks: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    record_date: Mapped[date | None] = mapped_column(Date)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[DataSource] = mapped_column(db_enum(DataSource), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )
