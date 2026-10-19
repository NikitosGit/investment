"""Domain enumerations shared by the database, provider and API layers.

All enums inherit :class:`enum.StrEnum`, so their values are plain strings and
are stored verbatim in the database.
"""

from enum import StrEnum


class AssetType(StrEnum):
    """Supported security types."""

    STOCK = "STOCK"
    BOND = "BOND"


class OperationType(StrEnum):
    """Portfolio operations."""

    BUY = "BUY"
    SELL = "SELL"


class PriceType(StrEnum):
    """How a price is expressed."""

    RUB = "RUB"
    PERCENT = "PERCENT"


class IncomeKind(StrEnum):
    """Income kinds."""

    DIVIDEND = "DIVIDEND"
    COUPON = "COUPON"


class IncomeStatus(StrEnum):
    """Income lifecycle states."""

    EXPECTED = "EXPECTED"
    PAID = "PAID"


class DataSource(StrEnum):
    """Where a record came from."""

    MOEX = "MOEX"
    MANUAL = "MANUAL"
