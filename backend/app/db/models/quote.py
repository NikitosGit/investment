"""Quote model for cached market prices."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DataSource, PriceType
from app.core.time import utc_now_naive
from app.db.base import Base, db_enum


class Quote(Base):
    """One cached price for an asset on a given date."""

    __tablename__ = "quote"
    __table_args__ = (
        UniqueConstraint("asset_id", "quote_date"),
        CheckConstraint("price_micro > 0", name="price_positive"),
        Index("ix_quote_asset_date", "asset_id", "quote_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    quote_date: Mapped[date] = mapped_column(Date, nullable=False)
    price_micro: Mapped[int] = mapped_column(Integer, nullable=False)
    price_type: Mapped[PriceType] = mapped_column(db_enum(PriceType), nullable=False)
    source: Mapped[DataSource] = mapped_column(db_enum(DataSource), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
