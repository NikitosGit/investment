"""Single source of truth for the supported dashboard periods."""

from typing import Literal

DashboardPeriod = Literal["1M", "3M", "1Y", "ALL"]
"""Periods accepted by the dashboard and snapshot history endpoints."""

DASHBOARD_PERIODS: tuple[str, ...] = ("1M", "3M", "1Y", "ALL")
"""Every supported period, in display order."""

DEFAULT_DASHBOARD_PERIOD = "1Y"
"""Period used when the user has not stored a preference."""

DASHBOARD_PERIOD_DAYS: dict[str, int | None] = {
    "1M": 30,
    "3M": 90,
    "1Y": 365,
    "ALL": None,
}
"""Supported periods and their lookback in days (``None`` = all)."""
