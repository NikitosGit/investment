"""Exact decimal helpers for money and prices.

Money is stored as integer kopecks and prices as integer millionths of a ruble.
Conversion always rounds half up and never uses binary floats.
"""

from decimal import ROUND_HALF_UP, Decimal

type Number = Decimal | int | str

_ONE = Decimal(1)
_KOPECKS_PER_RUBLE = Decimal(100)
_MICRO_PER_RUBLE = Decimal(1_000_000)


def to_decimal(value: Number) -> Decimal:
    """Convert a value to :class:`Decimal` via its string form."""

    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def rubles_to_kopecks(value: Number) -> int:
    """Convert rubles to whole kopecks, rounding half up."""

    return int((to_decimal(value) * _KOPECKS_PER_RUBLE).quantize(_ONE, rounding=ROUND_HALF_UP))


def rubles_to_micro(value: Number) -> int:
    """Convert rubles to millionths of a ruble, rounding half up."""

    return int((to_decimal(value) * _MICRO_PER_RUBLE).quantize(_ONE, rounding=ROUND_HALF_UP))


def kopecks_to_rubles(kopecks: int) -> Decimal:
    """Convert whole kopecks to rubles with two decimal places."""

    return (Decimal(kopecks) / _KOPECKS_PER_RUBLE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def micro_to_rubles(micro: int) -> Decimal:
    """Convert millionths of a ruble to rubles with six decimal places."""

    return (Decimal(micro) / _MICRO_PER_RUBLE).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def format_money(kopecks: int) -> str:
    """Format kopecks as a fixed two-decimal string (e.g. ``"1234.56"``)."""

    return f"{kopecks_to_rubles(kopecks):.2f}"


def format_price(micro: int) -> str:
    """Format millionths as a fixed six-decimal string (e.g. ``"110.000000"``)."""

    return f"{micro_to_rubles(micro):.6f}"
