"""Factories shared by the income service tests."""

from datetime import date

from sqlalchemy.orm import Session

from app.core.enums import (
    AssetType,
    DataSource,
    IncomeKind,
    IncomeStatus,
    OperationType,
    PriceType,
)
from app.db.models.asset import Asset
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.services import portfolio_service

TODAY = date(2026, 6, 15)
FACE_MICRO = 35_400_000


def make_asset(
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


def buy(
    session: Session,
    asset: Asset,
    *,
    quantity: int = 10,
    trade_date: date = date(2026, 1, 10),
) -> Operation:
    portfolio = portfolio_service.ensure_default_portfolio(session)
    operation = Operation(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        type=OperationType.BUY,
        trade_date=trade_date,
        quantity=quantity,
        price_micro=100_000_000,
        input_price_micro=100_000_000,
        input_price_type=PriceType.RUB,
    )
    session.add(operation)
    session.commit()
    return operation


def make_expected(
    session: Session,
    asset: Asset,
    *,
    pay_date: date = date(2026, 7, 1),
    per_unit_micro: int | None = FACE_MICRO,
    external_id: str | None = "moex:coupon:TEST:2026-07-01",
) -> Income:
    portfolio = portfolio_service.ensure_default_portfolio(session)
    income = Income(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.EXPECTED,
        amount_per_unit_micro=per_unit_micro,
        currency="RUB",
        pay_date=pay_date,
        source=DataSource.MOEX if external_id else DataSource.MANUAL,
        external_id=external_id,
    )
    session.add(income)
    session.commit()
    return income


def make_paid(
    session: Session,
    asset: Asset,
    *,
    quantity: int = 10,
    total_kopecks: int = 10_000,
    per_unit_micro: int | None = 10_000_000,
    kind: IncomeKind = IncomeKind.DIVIDEND,
    pay_date: date = date(2026, 5, 1),
) -> Income:
    portfolio = portfolio_service.ensure_default_portfolio(session)
    income = Income(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        kind=kind,
        status=IncomeStatus.PAID,
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
