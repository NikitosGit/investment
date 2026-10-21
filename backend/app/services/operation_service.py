"""Operation CRUD with full-history validation.

Every write replays the operation history of the affected asset and rejects a
change that would make a sale exceed the available quantity (plan §6.2). Bond
prices entered as a percentage are normalized to rubles and the face value on
the trade date is frozen on the operation (plan §5.3).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, OperationType, PriceType
from app.core.errors import AppError, ErrorCode
from app.core.money import (
    micro_to_rubles,
    percent_price_to_micro,
    price_micro_to_percent_micro,
    rubles_to_micro,
)
from app.db.models.asset import Asset
from app.db.models.operation import Operation
from app.services import asset_service, bondization_service, portfolio_service, position_service


@dataclass(frozen=True, slots=True)
class NormalizedPrice:
    """The machine and user-facing forms of an operation price."""

    price_micro: int
    input_price_micro: int
    input_price_type: PriceType
    face_value_kopecks: int | None


def list_operations(
    session: Session,
    *,
    asset_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Operation]:
    """Return operations ordered by trade date and id, filtering inclusively."""

    statement = select(Operation)
    if asset_id is not None:
        statement = statement.where(Operation.asset_id == asset_id)
    if from_date is not None:
        statement = statement.where(Operation.trade_date >= from_date)
    if to_date is not None:
        statement = statement.where(Operation.trade_date <= to_date)
    statement = statement.order_by(Operation.trade_date, Operation.id)
    return list(session.scalars(statement))


def get_operation(session: Session, operation_id: int) -> Operation:
    """Return an operation or raise a 404 domain error."""

    operation = session.get(Operation, operation_id)
    if operation is None:
        raise AppError(
            ErrorCode.NOT_FOUND,
            f"Операция {operation_id} не найдена",
            status_code=404,
            details={"operation_id": operation_id},
        )
    return operation


def create_operation(
    session: Session,
    *,
    asset_id: int,
    type: OperationType,
    trade_date: date,
    quantity: int,
    price: Decimal,
    price_type: PriceType,
    note: str | None = None,
) -> Operation:
    """Create an operation and validate the whole history of the asset."""

    asset = asset_service.get_asset(session, asset_id)
    _ensure_quantity(quantity)
    normalized = _normalize_price(session, asset, trade_date, price, price_type)
    portfolio = portfolio_service.ensure_default_portfolio(session, commit=False)

    operation = Operation(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        type=type,
        trade_date=trade_date,
        quantity=quantity,
        price_micro=normalized.price_micro,
        input_price_micro=normalized.input_price_micro,
        input_price_type=normalized.input_price_type,
        face_value_kopecks=normalized.face_value_kopecks,
        note=note,
    )
    session.add(operation)
    try:
        session.flush()
        position_service.validate_operation_sequence(session, asset_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return operation


def update_operation(session: Session, operation_id: int, changes: dict) -> Operation:
    """Apply only the provided fields and revalidate the asset history.

    A ``price_type``-only change keeps the normalized ruble price untouched and
    only re-expresses the user input. When the trade date changes, the stored
    input is re-normalized: a percentage is recomputed against the face value
    on the new trade date, while switching the representation alongside the
    date change preserves the normalized ruble price.
    """

    operation = get_operation(session, operation_id)
    asset = asset_service.get_asset(session, operation.asset_id)
    try:
        _apply_changes(session, asset, operation, changes)
        session.flush()
        position_service.validate_operation_sequence(session, operation.asset_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return operation


def delete_operation(session: Session, operation_id: int) -> None:
    """Delete an operation if the remaining history stays valid."""

    operation = get_operation(session, operation_id)
    asset_id = operation.asset_id
    try:
        session.delete(operation)
        session.flush()
        position_service.validate_operation_sequence(session, asset_id)
        session.commit()
    except Exception:
        session.rollback()
        raise


def _apply_changes(session: Session, asset: Asset, operation: Operation, changes: dict) -> None:
    if "type" in changes:
        operation.type = changes["type"]
    if "quantity" in changes:
        _ensure_quantity(changes["quantity"])
        operation.quantity = changes["quantity"]
    if "note" in changes:
        operation.note = changes["note"]

    trade_date = changes.get("trade_date", operation.trade_date)
    price_type = changes.get("price_type", operation.input_price_type)

    if "price" in changes:
        normalized = _normalize_price(session, asset, trade_date, changes["price"], price_type)
        _assign_normalized(operation, normalized)
    elif "trade_date" in changes:
        price = _price_to_reenter(session, asset, operation, trade_date, price_type)
        normalized = _normalize_price(session, asset, trade_date, price, price_type)
        _assign_normalized(operation, normalized)
    elif price_type is not operation.input_price_type:
        _switch_price_type(session, asset, operation, trade_date, price_type)
    operation.trade_date = trade_date


def _assign_normalized(operation: Operation, normalized: NormalizedPrice) -> None:
    operation.price_micro = normalized.price_micro
    operation.input_price_micro = normalized.input_price_micro
    operation.input_price_type = normalized.input_price_type
    operation.face_value_kopecks = normalized.face_value_kopecks


def _switch_price_type(
    session: Session,
    asset: Asset,
    operation: Operation,
    trade_date: date,
    price_type: PriceType,
) -> None:
    """Change the user-facing representation without touching ``price_micro``.

    The trade date is unchanged here, so the frozen face value of the operation
    stays valid and the normalized ruble price must stay byte-for-byte stable.
    """

    _reject_percent_for_stock(asset, price_type)
    if price_type is PriceType.RUB:
        operation.input_price_micro = operation.price_micro
        operation.input_price_type = PriceType.RUB
        return

    face_value = operation.face_value_kopecks
    if not face_value:
        face_value = bondization_service.current_face_value_kopecks(session, asset, trade_date)
    percent_micro = price_micro_to_percent_micro(operation.price_micro, face_value or 0)
    if percent_micro is None:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Нельзя выразить цену в процентах: неизвестен номинал {asset.secid}",
            status_code=400,
            details={"asset_id": asset.id, "trade_date": trade_date.isoformat()},
        )
    if percent_micro <= 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Цена в процентах от номинала должна быть больше нуля",
            status_code=400,
            details={"asset_id": asset.id, "price_micro": operation.price_micro},
        )
    operation.input_price_micro = percent_micro
    operation.input_price_type = PriceType.PERCENT


def _price_to_reenter(
    session: Session,
    asset: Asset,
    operation: Operation,
    trade_date: date,
    price_type: PriceType,
) -> Decimal:
    """Return the user-facing price to normalize after a date/type change."""

    _reject_percent_for_stock(asset, price_type)
    if price_type is operation.input_price_type:
        # Same representation: the stored input is still the user's number.
        return micro_to_rubles(operation.input_price_micro)
    if price_type is PriceType.RUB:
        # Percent -> RUB: preserve the already normalized ruble price.
        return micro_to_rubles(operation.price_micro)

    # RUB -> percent: derive the percentage from the current ruble price.
    face_value = bondization_service.current_face_value_kopecks(session, asset, trade_date)
    percent_micro = price_micro_to_percent_micro(operation.price_micro, face_value or 0)
    if percent_micro is None:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Нельзя выразить цену в процентах: неизвестен номинал {asset.secid}",
            status_code=400,
            details={"asset_id": asset.id, "trade_date": trade_date.isoformat()},
        )
    return micro_to_rubles(percent_micro)


def _reject_percent_for_stock(asset: Asset, price_type: PriceType) -> None:
    """Stocks are always priced in rubles; reject percent input consistently."""

    if price_type is not PriceType.PERCENT or asset.type is AssetType.BOND:
        return
    raise AppError(
        ErrorCode.BAD_REQUEST,
        "Для акций цена указывается в рублях, а не в процентах",
        status_code=400,
        details={"asset_id": asset.id, "price_type": price_type.value},
    )


def _normalize_price(
    session: Session,
    asset: Asset,
    trade_date: date,
    price: Decimal,
    price_type: PriceType,
) -> NormalizedPrice:
    """Normalize a user price into rubles and remember the original input.

    * Stocks only accept ``RUB``; ``PERCENT`` is rejected with 400.
    * Bonds accept both. For ``PERCENT`` the face value on ``trade_date`` is
      resolved first, then the ruble price is computed as
      ``face_rub * percent / 100`` and stored in millionths.
    * The input value is stored verbatim (RUB micros or percent micros) so the
      API can echo exactly what the user entered.
    """

    input_price_micro = rubles_to_micro(price)
    if input_price_micro <= 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Цена должна быть больше нуля",
            status_code=400,
            details={"asset_id": asset.id, "price": str(price)},
        )

    if asset.type is not AssetType.BOND:
        _reject_percent_for_stock(asset, price_type)
        return NormalizedPrice(
            price_micro=input_price_micro,
            input_price_micro=input_price_micro,
            input_price_type=PriceType.RUB,
            face_value_kopecks=None,
        )

    face_value = bondization_service.current_face_value_kopecks(session, asset, trade_date)
    if not face_value:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Не удалось определить номинал облигации {asset.secid} на {trade_date.isoformat()}",
            status_code=400,
            details={"asset_id": asset.id, "trade_date": trade_date.isoformat()},
        )

    if price_type is PriceType.RUB:
        return NormalizedPrice(
            price_micro=input_price_micro,
            input_price_micro=input_price_micro,
            input_price_type=PriceType.RUB,
            face_value_kopecks=face_value,
        )

    price_micro = percent_price_to_micro(face_value, input_price_micro)
    if price_micro <= 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Цена в процентах от номинала должна быть больше нуля",
            status_code=400,
            details={"asset_id": asset.id, "price": str(price)},
        )
    return NormalizedPrice(
        price_micro=price_micro,
        input_price_micro=input_price_micro,
        input_price_type=PriceType.PERCENT,
        face_value_kopecks=face_value,
    )


def _ensure_quantity(quantity: int) -> None:
    if quantity <= 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Количество должно быть больше нуля",
            status_code=400,
            details={"quantity": quantity},
        )
