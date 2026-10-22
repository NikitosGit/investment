"""Snapshot API schemas: stored daily valuations for diagnostics."""

from datetime import date
from typing import Self

from app.core.money import format_money
from app.db.models.snapshot import PortfolioSnapshot
from app.schemas.common import ApiModel


class SnapshotItem(ApiModel):
    """One stored daily snapshot."""

    date: date
    market_value: str
    invested: str
    income_paid: str

    @classmethod
    def from_snapshot(cls, snapshot: PortfolioSnapshot) -> Self:
        return cls(
            date=snapshot.snapshot_date,
            market_value=format_money(snapshot.market_value_kopecks),
            invested=format_money(snapshot.invested_kopecks),
            income_paid=format_money(snapshot.income_paid_kopecks),
        )


class SnapshotListResponse(ApiModel):
    """Stored snapshots of a period, oldest first."""

    period: str
    items: list[SnapshotItem]
