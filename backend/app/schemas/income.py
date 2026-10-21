"""Income API schemas.

Money crosses the API boundary as fixed two-decimal strings. Expected coupons
return computed quantity and amount; paid rows return the stored values.
"""

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import DataSource, IncomeKind, IncomeStatus
from app.core.money import format_money, micro_to_kopecks
from app.schemas.common import ApiModel
from app.services.income_service import IncomeTotals, IncomeView


class IncomeItem(ApiModel):
    """A dividend or coupon as returned by the API."""

    id: int
    asset_id: int
    asset_secid: str
    kind: IncomeKind
    status: IncomeStatus
    amount_per_unit: str | None
    quantity: int | None
    amount_total: str | None
    currency: str
    record_date: date | None
    pay_date: date
    source: DataSource
    note: str | None
    is_overdue: bool

    @classmethod
    def from_view(cls, view: IncomeView) -> Self:
        income = view.income
        per_unit = (
            format_money(micro_to_kopecks(income.amount_per_unit_micro))
            if income.amount_per_unit_micro is not None
            else None
        )
        total = (
            format_money(view.amount_total_kopecks)
            if view.amount_total_kopecks is not None
            else None
        )
        return cls(
            id=income.id,
            asset_id=income.asset_id,
            asset_secid=view.asset_secid,
            kind=income.kind,
            status=income.status,
            amount_per_unit=per_unit,
            quantity=view.quantity,
            amount_total=total,
            currency=income.currency,
            record_date=income.record_date,
            pay_date=income.pay_date,
            source=income.source,
            note=income.note,
            is_overdue=view.is_overdue,
        )


class IncomeTotalsOut(ApiModel):
    """Portfolio income totals."""

    dividends_paid: str
    coupons_paid: str
    expected_coupons: str

    @classmethod
    def from_totals(cls, totals: IncomeTotals) -> Self:
        return cls(
            dividends_paid=format_money(totals.dividends_paid_kopecks),
            coupons_paid=format_money(totals.coupons_paid_kopecks),
            expected_coupons=format_money(totals.expected_coupons_kopecks),
        )


class IncomeListResponse(ApiModel):
    """A list of incomes with portfolio totals."""

    items: list[IncomeItem]
    totals: IncomeTotalsOut


class IncomeCreateIn(BaseModel):
    """Request body for adding an actual dividend or coupon."""

    model_config = ConfigDict(extra="forbid")

    asset_id: int
    kind: IncomeKind
    amount_total: Decimal = Field(gt=0, decimal_places=2)
    pay_date: date
    quantity: int | None = Field(default=None, ge=0)
    amount_per_unit: Decimal | None = Field(default=None, gt=0, decimal_places=6)
    record_date: date | None = None
    note: str | None = Field(default=None, max_length=500)


class IncomeUpdateIn(BaseModel):
    """Request body for a partial income update."""

    model_config = ConfigDict(extra="forbid")

    amount_total: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    amount_per_unit: Decimal | None = Field(default=None, gt=0, decimal_places=6)
    quantity: int | None = Field(default=None, ge=0)
    record_date: date | None = None
    pay_date: date | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Нужно передать хотя бы одно поле")
        for field in self.model_fields_set - {"note", "record_date"}:
            if getattr(self, field) is None:
                raise ValueError(f"Поле {field} не может быть null")
        return self


class MarkPaidIn(BaseModel):
    """Request body for confirming an expected coupon."""

    model_config = ConfigDict(extra="forbid")

    amount_total: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    pay_date: date | None = None
