"""Bond amortization schedule model."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
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
from app.db.enums import DataSource


class BondAmortization(Base):
    """A partial or full face-value repayment event."""

    __tablename__ = "bond_amortization"
    __table_args__ = (
        UniqueConstraint("external_id"),
        CheckConstraint("amount_per_unit_kopecks > 0", name="amount_positive"),
        Index("ix_bond_amortization_asset_date", "asset_id", "amortization_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    amortization_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_per_unit_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[DataSource] = mapped_column(db_enum(DataSource), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
