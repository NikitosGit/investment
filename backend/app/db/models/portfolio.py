"""Portfolio model."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base

DEFAULT_PORTFOLIO_NAME = "Мой портфель"


class Portfolio(Base):
    """The single investment portfolio.

    The ``id = 1`` check enforces the single-portfolio invariant at the
    database level, so concurrent bootstrap attempts cannot create a second row.
    """

    __tablename__ = "portfolio"
    __table_args__ = (CheckConstraint("id = 1", name="single_portfolio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default=DEFAULT_PORTFOLIO_NAME)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
