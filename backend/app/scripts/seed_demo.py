"""Seed a self-contained demo portfolio (plan §15).

Usage::

    python -m app.scripts.seed_demo

The demo does not touch the network: assets, operations, quotes, incomes and
amortization are written directly, so the frontend can be developed without
MOEX. The seed is idempotent: a version marker plus an anchor date are stored
in ``app_setting`` and a second run does nothing.
"""

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.enums import (
    AssetType,
    DataSource,
    IncomeKind,
    IncomeStatus,
    OperationType,
    PriceType,
)
from app.core.money import percent_price_to_micro, rubles_to_micro
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.db.models.quote import Quote
from app.db.models.snapshot import PortfolioSnapshot
from app.db.session import SessionLocal
from app.services import (
    portfolio_service,
    position_service,
    settings_service,
    snapshot_service,
)

DEMO_SEED_VERSION_KEY = "demo_seed_version"
DEMO_SEED_ANCHOR_KEY = "demo_seed_anchor"
DEMO_SEED_VERSION = "1"

STOCK_SECID = "SBER"
BOND_SECID = "SU26238RMFS4"
BOND_FACE_VALUE_KOPECKS = 100_000
WEEKLY_POINTS = 26
WEEKLY_START_DAYS = 180


@dataclass(frozen=True, slots=True)
class SeedSummary:
    """What a seed run created."""

    already_seeded: bool
    assets_created: int
    operations_created: int
    quotes_created: int
    income_created: int
    amortizations_created: int
    snapshot_created: bool


def seed_demo(session: Session, *, today: date | None = None) -> SeedSummary:
    """Create the demo data once and return the created row counts.

    The marker is written last, so a failed run leaves no trace and a partial
    run can be repaired by rerunning the command. Existing rows are matched by
    their natural keys and are never duplicated.
    """

    if settings_service.get_value(session, DEMO_SEED_VERSION_KEY) == DEMO_SEED_VERSION:
        return SeedSummary(
            already_seeded=True,
            assets_created=0,
            operations_created=0,
            quotes_created=0,
            income_created=0,
            amortizations_created=0,
            snapshot_created=False,
        )

    anchor = _resolve_anchor(session, today)

    try:
        settings_service.set_value(session, DEMO_SEED_ANCHOR_KEY, anchor.isoformat(), commit=False)
        portfolio = portfolio_service.ensure_default_portfolio(session, commit=False)

        stock, stock_created = _ensure_asset(
            session,
            secid=STOCK_SECID,
            name="Сбербанк",
            isin="RU0009029540",
            asset_type=AssetType.STOCK,
            market="shares",
            board="TQBR",
            lot_size=10,
        )
        bond, bond_created = _ensure_asset(
            session,
            secid=BOND_SECID,
            name="ОФЗ 26238",
            isin="RU000A0JX0J2",
            asset_type=AssetType.BOND,
            market="bonds",
            board="TQCB",
            lot_size=1,
            initial_face_value_kopecks=BOND_FACE_VALUE_KOPECKS,
        )
        session.flush()

        operations_created = _seed_operations(session, portfolio.id, stock, bond, anchor)
        session.flush()
        position_service.validate_operation_sequence(session, stock.id)
        position_service.validate_operation_sequence(session, bond.id)

        quotes_created = _seed_quotes(session, stock, bond, anchor)
        amortizations_created = _seed_amortization(session, bond, anchor)
        income_created = _seed_income(session, portfolio.id, stock, bond, anchor)
        session.flush()

        snapshot_date = anchor
        had_snapshot = (
            session.scalar(
                select(PortfolioSnapshot.id).where(
                    PortfolioSnapshot.portfolio_id == portfolio.id,
                    PortfolioSnapshot.snapshot_date == snapshot_date,
                )
            )
            is not None
        )
        snapshot_service.compute_and_store(session, snapshot_date)

        settings_service.set_value(session, DEMO_SEED_VERSION_KEY, DEMO_SEED_VERSION, commit=False)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return SeedSummary(
        already_seeded=False,
        assets_created=int(stock_created) + int(bond_created),
        operations_created=operations_created,
        quotes_created=quotes_created,
        income_created=income_created,
        amortizations_created=amortizations_created,
        snapshot_created=not had_snapshot,
    )


def _resolve_anchor(session: Session, today: date | None) -> date:
    """Use the stored anchor so a repaired seed does not shift its dates."""

    stored = settings_service.get_value(session, DEMO_SEED_ANCHOR_KEY)
    if stored:
        try:
            return date.fromisoformat(stored)
        except ValueError:
            pass
    return today or today_local()


def _ensure_asset(
    session: Session,
    *,
    secid: str,
    name: str,
    isin: str,
    asset_type: AssetType,
    market: str,
    board: str,
    lot_size: int,
    initial_face_value_kopecks: int | None = None,
) -> tuple[Asset, bool]:
    """Return the asset, creating it only when the ``(secid, board)`` is absent."""

    asset = session.scalar(select(Asset).where(Asset.secid == secid, Asset.board == board))
    if asset is not None:
        return asset, False

    asset = Asset(
        secid=secid,
        isin=isin,
        name=name,
        short_name=name,
        type=asset_type,
        engine="stock",
        market=market,
        board=board,
        currency="RUB",
        initial_face_value_kopecks=initial_face_value_kopecks,
        lot_size=lot_size,
        is_active=True,
    )
    session.add(asset)
    return asset, True


def _seed_operations(
    session: Session,
    portfolio_id: int,
    stock: Asset,
    bond: Asset,
    anchor: date,
) -> int:
    """Insert the demo trade history, skipping rows that already exist."""

    existing: dict[int, set[tuple[OperationType, date, int]]] = {}
    for asset in (stock, bond):
        rows = session.scalars(select(Operation).where(Operation.asset_id == asset.id))
        existing[asset.id] = {
            (operation.type, operation.trade_date, operation.quantity) for operation in rows
        }

    stock_price = rubles_to_micro(Decimal("100.00"))
    second_stock_price = rubles_to_micro(Decimal("120.00"))
    sale_price = rubles_to_micro(Decimal("150.00"))
    bond_percent_micro = rubles_to_micro(Decimal("95.123"))

    demo: list[tuple[Asset, OperationType, date, int, int, int, PriceType, int | None]] = [
        (
            stock,
            OperationType.BUY,
            anchor - timedelta(days=180),
            10,
            stock_price,
            stock_price,
            PriceType.RUB,
            None,
        ),
        (
            stock,
            OperationType.BUY,
            anchor - timedelta(days=120),
            10,
            second_stock_price,
            second_stock_price,
            PriceType.RUB,
            None,
        ),
        (
            stock,
            OperationType.SELL,
            anchor - timedelta(days=60),
            5,
            sale_price,
            sale_price,
            PriceType.RUB,
            None,
        ),
        (
            bond,
            OperationType.BUY,
            anchor - timedelta(days=150),
            15,
            percent_price_to_micro(BOND_FACE_VALUE_KOPECKS, bond_percent_micro),
            bond_percent_micro,
            PriceType.PERCENT,
            BOND_FACE_VALUE_KOPECKS,
        ),
    ]

    created = 0
    for (
        asset,
        operation_type,
        trade_date,
        quantity,
        price_micro,
        input_price_micro,
        input_price_type,
        face_value_kopecks,
    ) in demo:
        key = (operation_type, trade_date, quantity)
        if key in existing[asset.id]:
            continue
        session.add(
            Operation(
                portfolio_id=portfolio_id,
                asset_id=asset.id,
                type=operation_type,
                trade_date=trade_date,
                quantity=quantity,
                price_micro=price_micro,
                input_price_micro=input_price_micro,
                input_price_type=input_price_type,
                face_value_kopecks=face_value_kopecks,
                note="Демо-данные",
            )
        )
        existing[asset.id].add(key)
        created += 1
    return created


def _seed_quotes(session: Session, stock: Asset, bond: Asset, anchor: date) -> int:
    """Insert weekly manual quotes plus a current quote for both assets."""

    existing = {
        (quote.asset_id, quote.quote_date)
        for quote in session.scalars(select(Quote).where(Quote.asset_id.in_((stock.id, bond.id))))
    }

    dates = [anchor - timedelta(days=WEEKLY_START_DAYS - 7 * step) for step in range(WEEKLY_POINTS)]
    dates.append(anchor)

    created = 0
    for step, quote_date in enumerate(dates):
        weekly = step < WEEKLY_POINTS
        stock_price = (
            rubles_to_micro(Decimal("250.00") + Decimal("2.00") * step)
            if weekly
            else rubles_to_micro(Decimal("302.00"))
        )
        bond_percent = (
            rubles_to_micro(Decimal("95.0") + Decimal("0.1") * step)
            if weekly
            else rubles_to_micro(Decimal("97.6"))
        )
        for asset, price_micro, price_type in (
            (stock, stock_price, PriceType.RUB),
            (bond, bond_percent, PriceType.PERCENT),
        ):
            key = (asset.id, quote_date)
            if key in existing:
                continue
            session.add(
                Quote(
                    asset_id=asset.id,
                    quote_date=quote_date,
                    price_micro=price_micro,
                    price_type=price_type,
                    source=DataSource.MANUAL,
                )
            )
            existing.add(key)
            created += 1
    return created


def _seed_amortization(session: Session, bond: Asset, anchor: date) -> int:
    """Insert the demo partial repayment of the bond at 200 RUB per unit."""

    amortization_date = anchor - timedelta(days=30)
    external_id = f"demo:amortization:{bond.secid}:{amortization_date.isoformat()}"
    if session.scalar(
        select(BondAmortization.id).where(BondAmortization.external_id == external_id)
    ):
        return 0

    session.add(
        BondAmortization(
            asset_id=bond.id,
            amortization_date=amortization_date,
            amount_per_unit_kopecks=20_000,
            source=DataSource.MANUAL,
            external_id=external_id,
        )
    )
    return 1


def _seed_income(
    session: Session,
    portfolio_id: int,
    stock: Asset,
    bond: Asset,
    anchor: date,
) -> int:
    """Insert paid dividend/coupon records and three expected coupons."""

    dividends_pay_date = anchor - timedelta(days=45)
    coupons_pay_date = anchor - timedelta(days=40)
    expected_dates = (
        anchor + timedelta(days=10),
        anchor + timedelta(days=100),
        anchor + timedelta(days=190),
    )

    rows: list[Income] = [
        Income(
            portfolio_id=portfolio_id,
            asset_id=stock.id,
            kind=IncomeKind.DIVIDEND,
            status=IncomeStatus.PAID,
            amount_per_unit_micro=rubles_to_micro(Decimal("10.00")),
            quantity=20,
            amount_total_kopecks=20_000,
            currency="RUB",
            record_date=anchor - timedelta(days=70),
            pay_date=dividends_pay_date,
            source=DataSource.MANUAL,
            external_id=f"demo:dividend:{stock.secid}:{dividends_pay_date.isoformat()}",
            note="Демо-дивиденд",
        ),
        Income(
            portfolio_id=portfolio_id,
            asset_id=bond.id,
            kind=IncomeKind.COUPON,
            status=IncomeStatus.PAID,
            amount_per_unit_micro=rubles_to_micro(Decimal("35.00")),
            quantity=15,
            amount_total_kopecks=52_500,
            currency="RUB",
            pay_date=coupons_pay_date,
            source=DataSource.MANUAL,
            external_id=f"demo:coupon:{bond.secid}:paid:{coupons_pay_date.isoformat()}",
            note="Демо-купон",
        ),
    ]
    rows.extend(
        Income(
            portfolio_id=portfolio_id,
            asset_id=bond.id,
            kind=IncomeKind.COUPON,
            status=IncomeStatus.EXPECTED,
            amount_per_unit_micro=rubles_to_micro(Decimal("35.00")),
            quantity=None,
            amount_total_kopecks=None,
            currency="RUB",
            pay_date=pay_date,
            source=DataSource.MANUAL,
            external_id=f"demo:coupon:{bond.secid}:{pay_date.isoformat()}",
        )
        for pay_date in expected_dates
    )

    existing = {
        external_id
        for external_id in session.scalars(
            select(Income.external_id).where(
                Income.external_id.in_([row.external_id for row in rows])
            )
        )
    }
    created = 0
    for row in rows:
        if row.external_id in existing:
            continue
        session.add(row)
        created += 1
    return created


def main() -> int:
    """Seed the configured database and print a Russian summary."""

    try:
        with SessionLocal() as session:
            summary = seed_demo(session)
    except SQLAlchemyError:
        print(
            "Не удалось загрузить демо-данные: база недоступна или не мигрирована. "
            "Выполните 'python -m uv run alembic upgrade head' и повторите.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            f"Не удалось загрузить демо-данные: {exc}. "
            "Если база не мигрирована, выполните 'python -m uv run alembic upgrade head'.",
            file=sys.stderr,
        )
        return 1

    if summary.already_seeded:
        print("Демо-данные уже загружены (версия 1). Изменений нет.")
        return 0

    print("Демо-данные загружены:")
    print(f"  активов: {summary.assets_created}")
    print(f"  операций: {summary.operations_created}")
    print(f"  котировок: {summary.quotes_created}")
    print(f"  доходов: {summary.income_created}")
    print(f"  амортизаций: {summary.amortizations_created}")
    print(f"  snapshot на сегодня: {'да' if summary.snapshot_created else 'обновлён'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
