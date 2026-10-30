"""Factories shared by the dashboard and snapshot tests."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.enums import (
    AssetType,
    DataSource,
    IncomeKind,
    IncomeStatus,
    OperationType,
    PriceType,
)
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.db.models.quote import Quote
from app.services import portfolio_service


def days_ago(days: int) -> date:
    """Return a date ``days`` before today in the configured timezone."""

    return today_local() - timedelta(days=days)


def days_ahead(days: int) -> date:
    """Return a date ``days`` after today in the configured timezone."""

    return today_local() + timedelta(days=days)


def make_asset(
    session: Session,
    *,
    secid: str = "SBER",
    asset_type: AssetType = AssetType.STOCK,
    face_value_kopecks: int | None = None,
) -> Asset:
    """Create a stock or bond and commit it."""

    is_bond = asset_type is AssetType.BOND
    if is_bond and face_value_kopecks is None:
        face_value_kopecks = 100_000
    asset = Asset(
        secid=secid,
        name=f"{secid} name",
        type=asset_type,
        engine="stock",
        market="bonds" if is_bond else "shares",
        board="TQCB" if is_bond else "TQBR",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=face_value_kopecks,
    )
    session.add(asset)
    session.commit()
    return asset


def add_operation(
    session: Session,
    asset: Asset,
    *,
    trade_date: date,
    quantity: int,
    price_micro: int,
    type: OperationType = OperationType.BUY,
    note: str | None = None,
) -> Operation:
    """Append a validated-shape operation without going through the API service."""

    portfolio = portfolio_service.ensure_default_portfolio(session)
    operation = Operation(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        type=type,
        trade_date=trade_date,
        quantity=quantity,
        price_micro=price_micro,
        input_price_micro=price_micro,
        input_price_type=(PriceType.PERCENT if asset.type is AssetType.BOND else PriceType.RUB),
        face_value_kopecks=asset.initial_face_value_kopecks,
        note=note,
    )
    session.add(operation)
    session.commit()
    return operation


def add_quote(
    session: Session,
    asset: Asset,
    *,
    quote_date: date,
    price_micro: int,
    price_type: PriceType | None = None,
    source: DataSource = DataSource.MOEX,
) -> Quote:
    """Store one cached quote."""

    if price_type is None:
        price_type = PriceType.PERCENT if asset.type is AssetType.BOND else PriceType.RUB
    quote = Quote(
        asset_id=asset.id,
        quote_date=quote_date,
        price_micro=price_micro,
        price_type=price_type,
        source=source,
    )
    session.add(quote)
    session.commit()
    return quote


def add_amortization(
    session: Session,
    asset: Asset,
    *,
    amortization_date: date,
    amount_per_unit_kopecks: int,
) -> BondAmortization:
    """Store one amortization event."""

    amortization = BondAmortization(
        asset_id=asset.id,
        amortization_date=amortization_date,
        amount_per_unit_kopecks=amount_per_unit_kopecks,
        source=DataSource.MANUAL,
    )
    session.add(amortization)
    session.commit()
    return amortization


def add_income(
    session: Session,
    asset: Asset,
    *,
    pay_date: date,
    kind: IncomeKind = IncomeKind.COUPON,
    status: IncomeStatus = IncomeStatus.EXPECTED,
    per_unit_micro: int | None = None,
    quantity: int | None = None,
    amount_total_kopecks: int | None = None,
    external_id: str | None = None,
) -> Income:
    """Store an expected or paid income row."""

    portfolio = portfolio_service.ensure_default_portfolio(session)
    income = Income(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        kind=kind,
        status=status,
        amount_per_unit_micro=per_unit_micro,
        quantity=quantity,
        amount_total_kopecks=amount_total_kopecks,
        currency="RUB",
        pay_date=pay_date,
        source=DataSource.MANUAL,
        external_id=external_id,
    )
    session.add(income)
    session.commit()
    return income


def build_dashboard_portfolio(session: Session) -> tuple[Asset, Asset]:
    """Create the shared stock + bond portfolio used by dashboard tests.

    The set contains current quotes and paid dividend/coupon income. Tests add
    expected coupons, closed positions and empty assets explicitly.
    """

    portfolio_service.ensure_default_portfolio(session)
    stock = make_asset(session, secid="SBER")
    add_operation(session, stock, trade_date=days_ago(60), quantity=10, price_micro=100_000_000)
    add_quote(session, stock, quote_date=days_ago(1), price_micro=110_000_000)

    bond = make_asset(session, secid="SU26238RMFS4", asset_type=AssetType.BOND)
    add_operation(
        session,
        bond,
        trade_date=days_ago(50),
        quantity=15,
        price_micro=951_230_000,
    )
    add_quote(session, bond, quote_date=days_ago(1), price_micro=98_500_000)

    add_income(
        session,
        stock,
        kind=IncomeKind.DIVIDEND,
        status=IncomeStatus.PAID,
        pay_date=days_ago(10),
        quantity=10,
        amount_total_kopecks=20_000,
    )
    add_income(
        session,
        bond,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.PAID,
        pay_date=days_ago(5),
        quantity=15,
        amount_total_kopecks=52_500,
    )
    return stock, bond
