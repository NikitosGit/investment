"""Exact decimal helpers for money and prices.

Money is stored as integer kopecks and prices as integer millionths of a ruble.
Conversion always rounds half up and never uses binary floats.
"""

from decimal import ROUND_HALF_UP, Decimal

type Number = Decimal | int | str

_ONE = Decimal(1)
_KOPECKS_PER_RUBLE = Decimal(100)
_MICRO_PER_RUBLE = Decimal(1_000_000)
_MICRO_PER_KOPECK = Decimal(10_000)
# face_kopecks * percent_micro / 10_000 == face_rub * percent / 100 * 1_000_000.
_PERCENT_PRICE_DIVISOR = Decimal(100 * 100)
_BOND_VALUE_DIVISOR = Decimal(100_000_000)
_RATIO_PLACES = Decimal("0.0001")


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


def micro_to_kopecks(micro: int) -> int:
    """Convert millionths of a ruble to whole kopecks, rounding half up."""

    return int((Decimal(micro) / _MICRO_PER_KOPECK).quantize(_ONE, rounding=ROUND_HALF_UP))


def unit_price_from_total_micro(total_kopecks: int, quantity: int) -> int | None:
    """Return the per-unit price in millionths derived from a total.

    ``unit = total_rub / quantity``, i.e. ``total_kopecks * 10_000 / quantity``
    (one kopeck is 10 000 millionths of a ruble), rounded half up.
    Returns ``None`` for a non-positive quantity because the price is
    undefined in that case.
    """

    if quantity <= 0:
        return None
    value = Decimal(total_kopecks) * _MICRO_PER_KOPECK / Decimal(quantity)
    return int(value.quantize(_ONE, rounding=ROUND_HALF_UP))


def format_money(kopecks: int) -> str:
    """Format kopecks as a fixed two-decimal string (e.g. ``"1234.56"``)."""

    return f"{kopecks_to_rubles(kopecks):.2f}"


def format_price(micro: int) -> str:
    """Format millionths as a fixed six-decimal string (e.g. ``"110.000000"``)."""

    return f"{micro_to_rubles(micro):.6f}"


def percent_price_to_micro(face_value_kopecks: int, percent_micro: int) -> int:
    """Convert a percentage of the face value into millionths of a ruble.

    ``face_value_kopecks`` is the face value in kopecks and ``percent_micro``
    is the price in percent with six implied decimals (``95.123%`` →
    ``95_123_000``). Returns ``0`` for a non-positive face value.

    Formula: ``face_rub * percent / 100 * 1_000_000``, which equals
    ``face_value_kopecks * percent_micro / 10_000``.
    """

    if face_value_kopecks <= 0:
        return 0
    value = Decimal(face_value_kopecks) * Decimal(percent_micro) / _PERCENT_PRICE_DIVISOR
    return int(value.quantize(_ONE, rounding=ROUND_HALF_UP))


def price_micro_to_percent_micro(price_micro: int, face_value_kopecks: int) -> int | None:
    """Convert a ruble price into percent of the face value.

    Returns ``None`` when the face value is not positive, because the
    percentage is undefined in that case.
    """

    if face_value_kopecks <= 0:
        return None
    value = (
        Decimal(price_micro) * _MICRO_PER_RUBLE / (_KOPECKS_PER_RUBLE * Decimal(face_value_kopecks))
    )
    return int(value.quantize(_ONE, rounding=ROUND_HALF_UP))


def quantity_cost_kopecks(quantity: int, price_micro: int) -> int:
    """Return ``quantity * price`` in kopecks, rounding half up."""

    value = Decimal(quantity) * Decimal(price_micro) / _MICRO_PER_KOPECK
    return int(value.quantize(_ONE, rounding=ROUND_HALF_UP))


def bond_market_value_kopecks(quantity: int, face_value_kopecks: int, percent_micro: int) -> int:
    """Return the market value of a bond position in kopecks.

    ``value = quantity * face_rub * percent / 100``, i.e.
    ``quantity * face_kopecks * percent_micro / 100_000_000``.
    """

    value = (
        Decimal(quantity) * Decimal(face_value_kopecks) * Decimal(percent_micro)
    ) / _BOND_VALUE_DIVISOR
    return int(value.quantize(_ONE, rounding=ROUND_HALF_UP))


def format_ratio(value: Decimal) -> str:
    """Format a ratio with four decimals (e.g. ``"0.1532"``)."""

    return f"{value.quantize(_RATIO_PLACES, rounding=ROUND_HALF_UP):.4f}"
