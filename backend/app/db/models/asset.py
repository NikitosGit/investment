"""Asset model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AssetType
from app.core.time import utc_now_naive
from app.db.base import Base, db_enum


class Asset(Base):
    """A tradable security tracked by the portfolio."""

    __tablename__ = "asset"
    __table_args__ = (
        UniqueConstraint("secid", "board"),
        Index("ix_asset_secid", "secid"),
        Index("ix_asset_type", "type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    secid: Mapped[str] = mapped_column(String(32), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    type: Mapped[AssetType] = mapped_column(db_enum(AssetType), nullable=False)
    engine: Mapped[str] = mapped_column(String(10), nullable=False, default="stock")
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    board: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    initial_face_value_kopecks: Mapped[int | None] = mapped_column(Integer)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )
