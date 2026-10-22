"""Dividends and coupons: expected schedules, actual payments and totals.

Monetary inputs of the write functions are expressed in **rubles** as
:class:`~decimal.Decimal` (an ``int`` is treated as whole rubles); the service
converts them to integer kopecks and millionths before touching the database.
Expected coupons are never stored with their computed total: it is derived on
read from the current replayed quantity (plan §6.5). Only actual payments
(``PAID``) persist ``quantity`` and ``amount_total_kopecks`` (plan §6.6).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import DataSource, IncomeKind, IncomeStatus
from app.core.errors import AppError, ErrorCode
from app.core.money import quantity_cost_kopecks, unit_price_from_total_micro
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.income import Income
from app.providers.moex.client import MoexClient
from app.services import (
    asset_service,
    bondization_service,
    portfolio_service,
    position_service,
)
from app.services.income_rules import (
    UPDATE_FIELDS,
    MoneyInput,
    apply_expected_changes,
    apply_paid_changes,
    ensure_quantity,
    positive_kopecks,
    positive_micro,
)


@dataclass(frozen=True, slots=True)
class IncomeView:
    """An income record enriched with its asset and computed amounts."""

    income: Income
    asset_secid: str
    quantity: int | None
    amount_total_kopecks: int | None
    is_overdue: bool


@dataclass(frozen=True, slots=True)
class IncomeTotals:
    """Portfolio income totals in kopecks."""

    dividends_paid_kopecks: int
    coupons_paid_kopecks: int
    expected_coupons_kopecks: int


def list_incomes(
    session: Session,
    *,
    status: IncomeStatus | None = None,
    kind: IncomeKind | None = None,
    asset_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Income]:
    """Return incomes ordered by pay date, filtering pay dates inclusively."""

    statement = select(Income)
    if status is not None:
        statement = statement.where(Income.status == status)
    if kind is not None:
        statement = statement.where(Income.kind == kind)
    if asset_id is not None:
        statement = statement.where(Income.asset_id == asset_id)
    if from_date is not None:
        statement = statement.where(Income.pay_date >= from_date)
    if to_date is not None:
        statement = statement.where(Income.pay_date <= to_date)
    statement = statement.order_by(Income.pay_date, Income.id)
    return list(session.scalars(statement))


def get_income(session: Session, income_id: int) -> Income:
    """Return an income record or raise a 404 domain error."""

    income = session.get(Income, income_id)
    if income is None:
        raise AppError(
            ErrorCode.NOT_FOUND,
            f"Доход {income_id} не найден",
            status_code=404,
            details={"income_id": income_id},
        )
    return income


def build_views(session: Session, incomes: Sequence[Income]) -> list[IncomeView]:
    """Attach secids and computed amounts to income records.

    Asset secids are loaded in one query and the current quantity of every
    asset is replayed at most once. For ``EXPECTED`` rows the quantity and the
    total are computed from the current position; for ``PAID`` rows the stored
    values are authoritative.
    """

    if not incomes:
        return []

    asset_ids = {income.asset_id for income in incomes}
    secids = dict(
        session.execute(select(Asset.id, Asset.secid).where(Asset.id.in_(asset_ids))).all()
    )
    today = today_local()
    quantities: dict[int, int] = {}

    views: list[IncomeView] = []
    for income in incomes:
        if income.status is IncomeStatus.PAID:
            views.append(
                IncomeView(
                    income=income,
                    asset_secid=secids[income.asset_id],
                    quantity=income.quantity,
                    amount_total_kopecks=income.amount_total_kopecks,
                    is_overdue=False,
                )
            )
            continue

        quantity = quantities.get(income.asset_id)
        if quantity is None:
            quantity = current_quantity(session, income.asset_id)
            quantities[income.asset_id] = quantity
        views.append(
            IncomeView(
                income=income,
                asset_secid=secids[income.asset_id],
                quantity=quantity,
                amount_total_kopecks=expected_amount(income, quantity),
                is_overdue=income.pay_date < today,
            )
        )
    return views


def list_income_views(
    session: Session,
    *,
    status: IncomeStatus | None = None,
    kind: IncomeKind | None = None,
    asset_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[IncomeView]:
    """Return filtered incomes together with their computed view data."""

    incomes = list_incomes(
        session,
        status=status,
        kind=kind,
        asset_id=asset_id,
        from_date=from_date,
        to_date=to_date,
    )
    return build_views(session, incomes)


def create_manual(
    session: Session,
    *,
    asset_id: int,
    kind: IncomeKind,
    amount_total: MoneyInput,
    pay_date: date,
    quantity: int | None = None,
    amount_per_unit: MoneyInput | None = None,
    record_date: date | None = None,
    note: str | None = None,
) -> Income:
    """Create an actual (``PAID``) dividend or coupon entered by the user.

    A missing quantity defaults to the current replayed quantity (``0`` is
    allowed and stored as is). The total is authoritative: the per-unit value
    is always derived from the total when the quantity is positive, and stored
    as ``None`` at zero quantity. A supplied per-unit value is validated for
    the request contract but does not change the stored amount.
    """

    asset = asset_service.get_asset(session, asset_id)
    total_kopecks = positive_kopecks(amount_total, "amount_total")

    if quantity is None:
        quantity = current_quantity(session, asset.id)
    ensure_quantity(quantity)
    if amount_per_unit is not None:
        # The total is authoritative: validate the supplied value, then derive
        # the stored per-unit value from the total (plan §6.6).
        positive_micro(amount_per_unit, "amount_per_unit")
    per_unit_micro = unit_price_from_total_micro(total_kopecks, quantity)

    portfolio = portfolio_service.ensure_default_portfolio(session, commit=False)
    income = Income(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        kind=kind,
        status=IncomeStatus.PAID,
        amount_per_unit_micro=per_unit_micro,
        quantity=quantity,
        amount_total_kopecks=total_kopecks,
        currency="RUB",
        record_date=record_date,
        pay_date=pay_date,
        source=DataSource.MANUAL,
        external_id=None,
        note=note,
    )
    session.add(income)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(income)
    return income


def update_income(session: Session, income_id: int, changes: dict) -> Income:
    """Apply the provided fields to an income record.

    Expected coupons only accept display fields: their amounts are derived from
    the position and their pay date is the key of the MOEX schedule (and of the
    ``external_id`` used for idempotent synchronization). Paid rows keep the
    monetary invariants: a non-negative quantity and a non-null total.
    """

    income = get_income(session, income_id)
    unknown = set(changes) - UPDATE_FIELDS
    if unknown:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Нельзя изменить поля: {', '.join(sorted(unknown))}",
            status_code=400,
            details={"fields": sorted(unknown)},
        )

    try:
        if income.status is IncomeStatus.EXPECTED:
            apply_expected_changes(income, changes)
        else:
            apply_paid_changes(income, changes)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(income)
    return income


def mark_paid(
    session: Session,
    income_id: int,
    *,
    amount_total: MoneyInput | None = None,
    pay_date: date | None = None,
) -> Income:
    """Confirm an expected coupon as paid, computing amounts when omitted."""

    income = get_income(session, income_id)
    if income.status is IncomeStatus.PAID:
        raise AppError(
            ErrorCode.INCOME_ALREADY_PAID,
            f"Доход {income_id} уже выплачен",
            status_code=409,
            details={"income_id": income_id},
        )

    quantity = current_quantity(session, income.asset_id)
    if amount_total is not None:
        total_kopecks = positive_kopecks(amount_total, "amount_total")
        per_unit_micro = unit_price_from_total_micro(total_kopecks, quantity)
    elif income.amount_per_unit_micro is None:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Не указана сумма дохода",
            status_code=400,
            details={"income_id": income_id},
        )
    else:
        total_kopecks = expected_amount(income, quantity)
        per_unit_micro = income.amount_per_unit_micro

    income.quantity = quantity
    income.amount_total_kopecks = total_kopecks
    income.amount_per_unit_micro = per_unit_micro
    income.pay_date = pay_date or income.pay_date
    income.status = IncomeStatus.PAID
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(income)
    return income


def delete_income(session: Session, income_id: int) -> None:
    """Delete an income record."""

    income = get_income(session, income_id)
    try:
        session.delete(income)
        session.commit()
    except Exception:
        session.rollback()
        raise


def expected_amount(income: Income, current_quantity: int) -> int:
    """Return the expected amount in kopecks for ``current_quantity`` units."""

    if income.amount_per_unit_micro is None:
        return 0
    return quantity_cost_kopecks(current_quantity, income.amount_per_unit_micro)


def current_quantity(session: Session, asset_id: int) -> int:
    """Replay the operation history of an asset as of today and return quantity.

    Future-dated operations are excluded: a scheduled trade must not change
    the quantity used for expected coupons before it happens.
    """

    operations = position_service.load_operations(session, asset_id, on_date=today_local())
    return position_service.calculate_position(asset_id, operations).quantity


def totals(session: Session, portfolio_id: int = 1) -> IncomeTotals:
    """Return paid and expected income totals of a portfolio.

    The expected total sums every ``EXPECTED`` coupon at the current quantity,
    including overdue ones, because they are still expected to be paid. An
    asset with a zero position contributes zero.
    """

    dividends_paid = _paid_sum(session, portfolio_id, IncomeKind.DIVIDEND)
    coupons_paid = _paid_sum(session, portfolio_id, IncomeKind.COUPON)
    expected_coupons = _expected_sum(session, portfolio_id)
    return IncomeTotals(
        dividends_paid_kopecks=dividends_paid,
        coupons_paid_kopecks=coupons_paid,
        expected_coupons_kopecks=expected_coupons,
    )


def _paid_sum(session: Session, portfolio_id: int, kind: IncomeKind) -> int:
    sum_kopecks = session.scalar(
        select(func.coalesce(func.sum(Income.amount_total_kopecks), 0)).where(
            Income.portfolio_id == portfolio_id,
            Income.kind == kind,
            Income.status == IncomeStatus.PAID,
        )
    )
    return int(sum_kopecks or 0)


def _expected_sum(session: Session, portfolio_id: int) -> int:
    coupons = session.scalars(
        select(Income).where(
            Income.portfolio_id == portfolio_id,
            Income.kind == IncomeKind.COUPON,
            Income.status == IncomeStatus.EXPECTED,
        )
    )
    quantities: dict[int, int] = {}
    total = 0
    for coupon in coupons:
        if coupon.asset_id not in quantities:
            quantities[coupon.asset_id] = current_quantity(session, coupon.asset_id)
        total += expected_amount(coupon, quantities[coupon.asset_id])
    return total


def sync_coupons(session: Session, client: MoexClient, asset: Asset) -> int:
    """Synchronize the coupon schedule of a bond and return upcoming coupons.

    The caller owns the transaction: this function never commits or rolls back,
    so a failure and the surrounding unit of work stay under the caller's
    control. The returned count covers the bond's ``EXPECTED`` coupons with a
    pay date on or after today, i.e. the rows the schedule maintains.
    """

    bondization = client.get_bondization(asset.secid)
    portfolio = portfolio_service.ensure_default_portfolio(session, commit=False)
    bondization_service.sync_bondization(session, asset, bondization, portfolio_id=portfolio.id)

    upcoming = session.scalar(
        select(func.count())
        .select_from(Income)
        .where(
            Income.asset_id == asset.id,
            Income.kind == IncomeKind.COUPON,
            Income.status == IncomeStatus.EXPECTED,
            Income.pay_date >= today_local(),
        )
    )
    return int(upcoming or 0)
