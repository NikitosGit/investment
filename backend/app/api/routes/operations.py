"""Operation endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DbSession
from app.schemas.operation import (
    OperationCreateIn,
    OperationListResponse,
    OperationResponse,
    OperationUpdateIn,
)
from app.services import operation_service

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=OperationListResponse, summary="Список операций")
def list_operations(
    session: DbSession,
    asset_id: Annotated[int | None, Query()] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> OperationListResponse:
    """Return operations filtered by asset and inclusive trade-date range."""

    operations = operation_service.list_operations(
        session, asset_id=asset_id, from_date=from_date, to_date=to_date
    )
    return OperationListResponse(
        items=[OperationResponse.from_operation(operation) for operation in operations]
    )


@router.post(
    "",
    response_model=OperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать операцию",
)
def create_operation(payload: OperationCreateIn, session: DbSession) -> OperationResponse:
    """Create a buy or sell operation and validate the asset history."""

    operation = operation_service.create_operation(
        session,
        asset_id=payload.asset_id,
        type=payload.type,
        trade_date=payload.trade_date,
        quantity=payload.quantity,
        price=payload.price,
        price_type=payload.price_type,
        note=payload.note,
    )
    return OperationResponse.from_operation(operation)


@router.patch("/{operation_id}", response_model=OperationResponse, summary="Изменить операцию")
def update_operation(
    operation_id: int, payload: OperationUpdateIn, session: DbSession
) -> OperationResponse:
    """Update provided operation fields and revalidate the asset history."""

    operation = operation_service.update_operation(
        session, operation_id, payload.model_dump(exclude_unset=True)
    )
    return OperationResponse.from_operation(operation)


@router.delete(
    "/{operation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить операцию",
)
def delete_operation(operation_id: int, session: DbSession) -> Response:
    """Delete an operation if the remaining history stays valid."""

    operation_service.delete_operation(session, operation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
