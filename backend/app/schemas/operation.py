"""Operation API schemas."""

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.core.enums import OperationType, PriceType
from app.core.money import format_price
from app.db.models.operation import Operation
from app.schemas.common import ApiModel


class OperationCreateIn(BaseModel):
    """Request body for creating an operation."""

    asset_id: int
    type: OperationType
    trade_date: date
    quantity: int = Field(gt=0)
    price: Decimal = Field(gt=0, decimal_places=6)
    price_type: PriceType
    note: str | None = Field(default=None, max_length=500)


class OperationUpdateIn(BaseModel):
    """Request body for a partial operation update."""

    type: OperationType | None = None
    trade_date: date | None = None
    quantity: int | None = Field(default=None, gt=0)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=6)
    price_type: PriceType | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Нужно передать хотя бы одно поле")
        for field in self.model_fields_set - {"note"}:
            if getattr(self, field) is None:
                raise ValueError(f"Поле {field} не может быть null")
        return self


class OperationResponse(ApiModel):
    """An operation as returned by the API."""

    id: int
    asset_id: int
    type: OperationType
    trade_date: date
    quantity: int
    input_price: str
    input_price_type: PriceType
    price_rub: str
    note: str | None

    @classmethod
    def from_operation(cls, operation: Operation) -> Self:
        return cls(
            id=operation.id,
            asset_id=operation.asset_id,
            type=operation.type,
            trade_date=operation.trade_date,
            quantity=operation.quantity,
            input_price=format_price(operation.input_price_micro),
            input_price_type=operation.input_price_type,
            price_rub=format_price(operation.price_micro),
            note=operation.note,
        )


class OperationListResponse(ApiModel):
    """A list of operations."""

    items: list[OperationResponse]
