"""Bond schedule persistence and face-value calculations.

Coupons and amortizations fetched from MOEX are upserted by a stable
``external_id`` so repeated synchronizations stay idempotent. Paid coupons are
never overwritten by a synchronization.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, IncomeKind, IncomeStatus
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.providers.moex.schemas import Bondization


def _amortization_external_id(secid: str, amortization_date: date) -> str:
    return f"moex:amortization:{secid}:{amortization_date.isoformat()}"


def _coupon_external_id(secid: str, pay_date: date) -> str:
    return f"moex:coupon:{secid}:{pay_date.isoformat()}"


def sync_bondization(
    session: Session,
    asset: Asset,
    bondization: Bondization,
    *,
    portfolio_id: int,
) -> None:
    """Upsert amortizations and upcoming expected coupons for a bond.

    ``portfolio_id`` is supplied by the caller so synchronization never
    commits (or creates) a portfolio in the middle of a transaction.
    """

    _sync_amortizations(session, asset, bondization)
    _sync_coupons(session, asset, bondization, portfolio_id=portfolio_id)
    session.flush()


def _sync_amortizations(session: Session, asset: Asset, bondization: Bondization) -> None:
    for item in bondization.amortizations:
        external_id = _amortization_external_id(asset.secid, item.amortization_date)
        existing = session.scalar(
            select(BondAmortization).where(BondAmortization.external_id == external_id)
        )
        if existing is None:
            session.add(
                BondAmortization(
                    asset_id=asset.id,
                    amortization_date=item.amortization_date,
                    amount_per_unit_kopecks=item.amount_per_unit_kopecks,
                    source=DataSource.MOEX,
                    external_id=external_id,
                )
            )
        else:
            existing.amortization_date = item.amortization_date
            existing.amount_per_unit_kopecks = item.amount_per_unit_kopecks
            existing.source = DataSource.MOEX


def _sync_coupons(
    session: Session, asset: Asset, bondization: Bondization, *, portfolio_id: int
) -> None:
    today = today_local()
    upcoming = [coupon for coupon in bondization.coupons if coupon.pay_date >= today]
    if not upcoming:
        return

    for coupon in upcoming:
        external_id = _coupon_external_id(asset.secid, coupon.pay_date)
        existing = session.scalar(select(Income).where(Income.external_id == external_id))
        if existing is not None and existing.status == IncomeStatus.PAID:
            continue
        if existing is None:
            session.add(
                Income(
                    portfolio_id=portfolio_id,
                    asset_id=asset.id,
                    kind=IncomeKind.COUPON,
                    status=IncomeStatus.EXPECTED,
                    amount_per_unit_micro=coupon.amount_per_unit_micro,
                    currency="RUB",
                    record_date=coupon.record_date,
                    pay_date=coupon.pay_date,
                    source=DataSource.MOEX,
                    external_id=external_id,
                )
            )
        else:
            existing.asset_id = asset.id
            existing.kind = IncomeKind.COUPON
            existing.source = DataSource.MOEX
            existing.amount_per_unit_micro = coupon.amount_per_unit_micro
            existing.record_date = coupon.record_date
            existing.pay_date = coupon.pay_date


def current_face_value_kopecks(session: Session, asset: Asset, on_date: date) -> int | None:
    """Return the face value on ``on_date`` after amortization, or None for stocks."""

    if asset.type is not AssetType.BOND or asset.initial_face_value_kopecks is None:
        return None

    amortized = session.scalar(
        select(func.coalesce(func.sum(BondAmortization.amount_per_unit_kopecks), 0)).where(
            BondAmortization.asset_id == asset.id,
            BondAmortization.amortization_date <= on_date,
        )
    )
    return max(asset.initial_face_value_kopecks - int(amortized or 0), 0)


def list_amortizations(session: Session, asset_id: int) -> list[BondAmortization]:
    """Return the amortization schedule of an asset ordered by date."""

    return list(
        session.scalars(
            select(BondAmortization)
            .where(BondAmortization.asset_id == asset_id)
            .order_by(BondAmortization.amortization_date, BondAmortization.id)
        )
    )
