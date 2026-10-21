"""Validation and monetary invariants of income write operations.

Monetary values are expressed in rubles as :class:`~decimal.Decimal` (an
``int`` is treated as whole rubles) and converted to integer kopecks or
millionths here, so the service functions stay focused on the workflow.
"""

from decimal import Decimal

from app.core.enums import DataSource
from app.core.errors import AppError, ErrorCode
from app.core.money import (
    quantity_cost_kopecks,
    rubles_to_kopecks,
    rubles_to_micro,
    unit_price_from_total_micro,
)
from app.db.models.income import Income

UPDATE_FIELDS = frozenset(
    {"amount_total", "amount_per_unit", "quantity", "record_date", "pay_date", "note"}
)
EXPECTED_UPDATE_FIELDS = frozenset({"amount_per_unit", "record_date", "note"})

MoneyInput = Decimal | int


def positive_kopecks(value: MoneyInput, field: str) -> int:
    """Convert rubles to kopecks, rejecting non-positive amounts."""

    kopecks = rubles_to_kopecks(value)
    if kopecks <= 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Сумма дохода должна быть больше нуля",
            status_code=400,
            details={field: str(value)},
        )
    return kopecks


def positive_micro(value: MoneyInput, field: str) -> int:
    """Convert rubles to millionths, rejecting non-positive amounts."""

    micro = rubles_to_micro(value)
    if micro <= 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Сумма на единицу должна быть больше нуля",
            status_code=400,
            details={field: str(value)},
        )
    return micro


def ensure_quantity(quantity: int) -> None:
    """Reject negative quantities (zero is valid for paid incomes)."""

    if quantity < 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Количество не может быть отрицательным",
            status_code=400,
            details={"quantity": quantity},
        )


def apply_expected_changes(income: Income, changes: dict) -> None:
    """Apply display fields to an expected coupon.

    Amounts of an expected coupon are derived from the position and its pay
    date is the key of the MOEX schedule (and of the ``external_id`` used for
    idempotent synchronization), so both are immutable here. A per-unit value
    of a MOEX coupon is also immutable: the next synchronization overwrites it
    from the provider schedule.
    """

    rejected = sorted(set(changes) - EXPECTED_UPDATE_FIELDS)
    if rejected:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Ожидаемый купон рассчитывается автоматически, а его дата выплаты — "
            "ключ расписания MOEX и не может быть изменена",
            status_code=400,
            details={"income_id": income.id, "fields": rejected},
        )

    if "amount_per_unit" in changes:
        if income.source is DataSource.MOEX:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                "Сумма ожидаемого купона MOEX задается расписанием и будет "
                "перезаписана при синхронизации",
                status_code=400,
                details={"income_id": income.id, "field": "amount_per_unit"},
            )
        income.amount_per_unit_micro = positive_micro(changes["amount_per_unit"], "amount_per_unit")
    if "record_date" in changes:
        income.record_date = changes["record_date"]
    if "note" in changes:
        income.note = changes["note"]


def apply_paid_changes(income: Income, changes: dict) -> None:
    """Apply changes to a paid income, keeping the recorded total authoritative.

    * total provided -> the total wins and the per-unit value is derived from
      it (``None`` for a zero quantity);
    * only per-unit provided -> the total is derived from it (``0`` for a zero
      quantity);
    * only quantity provided -> the recorded total is preserved and the
      per-unit value is re-derived from it (``None`` for a zero quantity).
    """

    total_given = "amount_total" in changes
    per_unit_given = "amount_per_unit" in changes
    quantity_given = "quantity" in changes

    if quantity_given:
        ensure_quantity(changes["quantity"])
        income.quantity = changes["quantity"]
    if per_unit_given:
        income.amount_per_unit_micro = positive_micro(changes["amount_per_unit"], "amount_per_unit")
    if "record_date" in changes:
        income.record_date = changes["record_date"]
    if "pay_date" in changes:
        income.pay_date = changes["pay_date"]
    if "note" in changes:
        income.note = changes["note"]

    quantity = income.quantity or 0
    if total_given:
        total_kopecks = positive_kopecks(changes["amount_total"], "amount_total")
        income.amount_total_kopecks = total_kopecks
        income.amount_per_unit_micro = unit_price_from_total_micro(total_kopecks, quantity)
    elif per_unit_given:
        income.amount_total_kopecks = quantity_cost_kopecks(
            quantity, income.amount_per_unit_micro or 0
        )
    elif quantity_given:
        total_kopecks = income.amount_total_kopecks
        if quantity > 0 and total_kopecks is not None:
            income.amount_per_unit_micro = unit_price_from_total_micro(total_kopecks, quantity)
        elif quantity == 0:
            income.amount_per_unit_micro = None

    if income.quantity is None or income.amount_total_kopecks is None:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "У выплаченного дохода должны быть заполнены количество и сумма",
            status_code=400,
            details={"income_id": income.id},
        )
