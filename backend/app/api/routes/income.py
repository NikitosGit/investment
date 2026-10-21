"""Income endpoints: dividends, coupons and confirmation of expected coupons."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import DbSession
from app.core.enums import IncomeKind, IncomeStatus
from app.db.models.income import Income
from app.schemas.income import (
    IncomeCreateIn,
    IncomeItem,
    IncomeListResponse,
    IncomeTotalsOut,
    IncomeUpdateIn,
    MarkPaidIn,
)
from app.services import income_service

router = APIRouter(prefix="/income", tags=["income"])


def _to_item(session: Session, income: Income) -> IncomeItem:
    """Build the API item for one income record."""

    return IncomeItem.from_view(income_service.build_views(session, [income])[0])


@router.get("", response_model=IncomeListResponse, summary="Список доходов")
def list_incomes(
    session: DbSession,
    income_status: Annotated[IncomeStatus | None, Query(alias="status")] = None,
    kind: Annotated[IncomeKind | None, Query()] = None,
    asset_id: Annotated[int | None, Query()] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> IncomeListResponse:
    """Return incomes filtered by status, kind, asset and inclusive pay dates."""

    views = income_service.list_income_views(
        session,
        status=income_status,
        kind=kind,
        asset_id=asset_id,
        from_date=from_date,
        to_date=to_date,
    )
    return IncomeListResponse(
        items=[IncomeItem.from_view(view) for view in views],
        totals=IncomeTotalsOut.from_totals(income_service.totals(session)),
    )


@router.post(
    "",
    response_model=IncomeItem,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить фактический доход",
)
def create_income(payload: IncomeCreateIn, session: DbSession) -> IncomeItem:
    """Create an actual dividend or coupon entered by the user."""

    income = income_service.create_manual(
        session,
        asset_id=payload.asset_id,
        kind=payload.kind,
        amount_total=payload.amount_total,
        pay_date=payload.pay_date,
        quantity=payload.quantity,
        amount_per_unit=payload.amount_per_unit,
        record_date=payload.record_date,
        note=payload.note,
    )
    return _to_item(session, income)


@router.patch("/{income_id}", response_model=IncomeItem, summary="Изменить доход")
def update_income(income_id: int, payload: IncomeUpdateIn, session: DbSession) -> IncomeItem:
    """Update provided income fields."""

    income = income_service.update_income(
        session, income_id, payload.model_dump(exclude_unset=True)
    )
    return _to_item(session, income)


@router.post(
    "/{income_id}/mark-paid",
    response_model=IncomeItem,
    summary="Подтвердить ожидаемый купон",
)
def mark_income_paid(income_id: int, payload: MarkPaidIn, session: DbSession) -> IncomeItem:
    """Confirm an expected coupon as paid."""

    income = income_service.mark_paid(
        session, income_id, amount_total=payload.amount_total, pay_date=payload.pay_date
    )
    return _to_item(session, income)


@router.delete(
    "/{income_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить доход",
)
def delete_income(income_id: int, session: DbSession) -> Response:
    """Delete an income record."""

    income_service.delete_income(session, income_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
