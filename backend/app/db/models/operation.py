"""Operation model."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OperationType, PriceType
from app.core.time import utc_now_naive
from app.db.base import Base, db_enum


class Operation(Base):
    """A buy or sell operation for an asset."""

    __tablename__ = "operation"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("price_micro > 0", name="price_positive"),
        Index("ix_operation_portfolio_asset_date", "portfolio_id", "asset_id", "trade_date", "id"),
        Index("ix_operation_asset_date", "asset_id", "trade_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    type: Mapped[OperationType] = mapped_column(db_enum(OperationType), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_micro: Mapped[int] = mapped_column(Integer, nullable=False)
    input_price_micro: Mapped[int] = mapped_column(Integer, nullable=False)
    input_price_type: Mapped[PriceType] = mapped_column(db_enum(PriceType), nullable=False)
    face_value_kopecks: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )
