"""Internal data structures returned by the MOEX provider.

These types are deliberately independent of the database and API layers.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.core.enums import AssetType, PriceType


@dataclass(frozen=True, slots=True)
class SecuritySearchResult:
    """One security found by a MOEX search."""

    secid: str
    name: str
    short_name: str | None
    isin: str | None
    type: AssetType
    board: str
    currency: str = "RUB"


@dataclass(frozen=True, slots=True)
class SecurityInfo:
    """Detailed metadata for a single security."""

    secid: str
    name: str
    short_name: str | None
    isin: str | None
    type: AssetType
    board: str
    currency: str
    lot_size: int
    face_value_kopecks: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CurrentQuote:
    """A single latest price."""

    quote_date: date
    price_micro: int
    price_type: PriceType


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    """One historical daily price."""

    quote_date: date
    price_micro: int
    price_type: PriceType


@dataclass(frozen=True, slots=True)
class CouponInfo:
    """A scheduled coupon payment."""

    pay_date: date
    record_date: date | None
    amount_per_unit_micro: int


@dataclass(frozen=True, slots=True)
class AmortizationInfo:
    """A scheduled face-value repayment."""

    amortization_date: date
    amount_per_unit_kopecks: int


@dataclass(frozen=True, slots=True)
class Bondization:
    """Coupon and amortization schedules of a bond."""

    coupons: list[CouponInfo] = field(default_factory=list)
    amortizations: list[AmortizationInfo] = field(default_factory=list)
