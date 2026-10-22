"""Dashboard API schemas (plan §8.7)."""

from datetime import date
from typing import Literal, Self

from app.core.money import format_money
from app.schemas.common import ApiModel
from app.schemas.income import IncomeItem
from app.schemas.position import PositionItem
from app.services.dashboard_service import DashboardData, DashboardTotals, SeriesPoint

DashboardPeriod = Literal["1M", "3M", "1Y", "ALL"]
"""Periods accepted by the dashboard and snapshot history endpoints."""


class DashboardTotalsOut(ApiModel):
    """Portfolio totals shown above the chart."""

    market_value: str
    invested: str
    dividends_paid: str
    coupons_paid: str
    income_paid_total: str
    expected_coupons: str
    positions_count: int
    assets_count: int

    @classmethod
    def from_totals(cls, totals: DashboardTotals) -> Self:
        return cls(
            market_value=format_money(totals.market_value_kopecks),
            invested=format_money(totals.invested_kopecks),
            dividends_paid=format_money(totals.dividends_paid_kopecks),
            coupons_paid=format_money(totals.coupons_paid_kopecks),
            income_paid_total=format_money(totals.income_paid_total_kopecks),
            expected_coupons=format_money(totals.expected_coupons_kopecks),
            positions_count=totals.positions_count,
            assets_count=totals.assets_count,
        )


class DashboardSeriesPointOut(ApiModel):
    """One point of the portfolio value chart."""

    date: date
    market_value: str
    invested: str
    is_partial: bool

    @classmethod
    def from_point(cls, point: SeriesPoint) -> Self:
        return cls(
            date=point.date,
            market_value=format_money(point.market_value_kopecks),
            invested=format_money(point.invested_kopecks),
            is_partial=point.is_partial,
        )


class DashboardResponse(ApiModel):
    """Dashboard totals, positions, chart and upcoming coupons.

    The top-level ``is_partial`` is true when at least one chart point falls
    back to the cost basis, i.e. a part of the series is estimated.
    """

    as_of: date
    currency: str
    period: str
    totals: DashboardTotalsOut
    series: list[DashboardSeriesPointOut]
    positions: list[PositionItem]
    upcoming_coupons: list[IncomeItem]
    is_partial: bool

    @classmethod
    def from_data(cls, data: DashboardData) -> Self:
        return cls(
            as_of=data.as_of,
            currency=data.currency,
            period=data.period,
            totals=DashboardTotalsOut.from_totals(data.totals),
            series=[DashboardSeriesPointOut.from_point(point) for point in data.series],
            positions=[PositionItem.from_view(view) for view in data.positions],
            upcoming_coupons=[IncomeItem.from_view(view) for view in data.upcoming_coupons],
            is_partial=any(point.is_partial for point in data.series),
        )
