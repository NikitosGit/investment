"""Application settings key/value model."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class AppSetting(Base):
    """A single application setting."""

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )
