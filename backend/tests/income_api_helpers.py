"""Shared factories for the income API tests."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, IncomeKind, IncomeStatus, OperationType, PriceType
from app.db.models.asset import Asset
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.services import portfolio_service


def api_asset(
    session: Session,
    *,
    asset_type: AssetType = AssetType.STOCK,
    secid: str = "SBER",
) -> Asset:
    is_bond = asset_type is AssetType.BOND
    asset = Asset(
        secid=secid,
        name=secid,
        type=asset_type,
        engine="stock",
        market="bonds" if is_bond else "shares",
        board="TQCB" if is_bond else "TQBR",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=100_000 if is_bond else None,
    )
    session.add(asset)
    session.commit()
    return asset


def api_buy(session: Session, asset: Asset, *, quantity: int = 20) -> None:
    portfolio = portfolio_service.ensure_default_portfolio(session)
    session.add(
        Operation(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            type=OperationType.BUY,
            trade_date=date(2025, 12, 31),
            quantity=quantity,
            price_micro=100_000_000,
            input_price_micro=100_000_000,
            input_price_type=PriceType.RUB,
        )
    )
    session.commit()


def api_income(
    session: Session,
    asset: Asset,
    *,
    kind: IncomeKind = IncomeKind.DIVIDEND,
    status: IncomeStatus = IncomeStatus.PAID,
    quantity: int | None = 20,
    total_kopecks: int | None = 20_000,
    per_unit_micro: int | None = 10_000_000,
    pay_date: date = date(2026, 7, 15),
) -> Income:
    portfolio = portfolio_service.ensure_default_portfolio(session)
    income = Income(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        kind=kind,
        status=status,
        amount_per_unit_micro=per_unit_micro,
        quantity=quantity,
        amount_total_kopecks=total_kopecks,
        currency="RUB",
        pay_date=pay_date,
        source=DataSource.MANUAL,
    )
    session.add(income)
    session.commit()
    return income


def api_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, object] = {
        "asset_id": 1,
        "kind": "DIVIDEND",
        "amount_total": "200.00",
        "pay_date": "2026-07-15",
        "quantity": 20,
        "amount_per_unit": "10.00",
        "note": "Выплата за 2025 год",
    }
    payload.update(overrides)
    return payload
