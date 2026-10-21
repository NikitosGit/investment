"""Quote caching, history backfilling and manual prices.

The MOEX refresh is best-effort: a failed security never breaks a batch and
never breaks asset metadata editing. Manual prices are protected from MOEX
overwrites (plan §5.5/§7.4).
"""

import logging
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, PriceType
from app.core.errors import AppError, ErrorCode
from app.core.money import rubles_to_micro
from app.core.time import today_local, utc_now_naive
from app.db.models.asset import Asset
from app.db.models.operation import Operation
from app.db.models.quote import Quote
from app.providers.moex.client import MoexClient
from app.providers.moex.errors import MoexError
from app.services import asset_service, bondization_service, portfolio_service, settings_service

logger = logging.getLogger(__name__)

MAX_HISTORY_YEARS = 10
MAX_HISTORY_DAYS = 365 * MAX_HISTORY_YEARS

GENERIC_REFRESH_ERROR = "Внутренняя ошибка обновления"

PERIOD_DAYS: dict[str, int | None] = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "3Y": 365 * 3,
    "5Y": 365 * 5,
    "ALL": None,
}

# One refresh at a time inside this process (plan §10).
_refresh_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class RefreshError:
    """A per-asset failure collected during a batch refresh."""

    asset_id: int
    secid: str
    error: str


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """Summary of a batch quote refresh.

    ``updated`` counts assets processed successfully, not written price rows.
    """

    updated: int
    failed: int
    last_refresh_at: datetime
    errors: list[RefreshError]


def get_last_quote(session: Session, asset_id: int, on_date: date | None = None) -> Quote | None:
    """Return the latest quote with ``quote_date <= on_date``.

    ``on_date`` defaults to today in the configured timezone. Ties on the same
    date resolve to the newest row id, so re-imported or corrected quotes win.
    """

    target = on_date if on_date is not None else today_local()
    statement = (
        select(Quote)
        .where(Quote.asset_id == asset_id, Quote.quote_date <= target)
        .order_by(Quote.quote_date.desc(), Quote.id.desc())
        .limit(1)
    )
    return session.scalars(statement).first()


def refresh_asset(session: Session, client: MoexClient, asset: Asset) -> Quote | None:
    """Fetch and cache today's price for one asset.

    The caller owns the transaction: this function never commits.
    """

    current = client.get_current_quote(
        asset.secid,
        asset.market,
        asset.board,
        _price_type(asset),
        quote_date=today_local(),
    )
    if current is None or current.price_micro <= 0:
        return None
    return _upsert_quote(
        session,
        asset_id=asset.id,
        quote_date=current.quote_date,
        price_micro=current.price_micro,
        price_type=current.price_type,
        source=DataSource.MOEX,
    )


def backfill_history(
    session: Session,
    client: MoexClient,
    asset: Asset,
    from_date: date | None = None,
    till_date: date | None = None,
) -> int:
    """Fetch daily closes and upsert them; return the number of written rows.

    Without an explicit start the history resumes one day before the last
    cached quote date (so an official CLOSE can still be picked up for a day
    whose page was not yet published at the previous refresh), bounded to ten
    years. With an explicit start it begins at the first operation. The caller
    owns the transaction.
    """

    today = today_local()
    till = till_date or today
    floor = today - timedelta(days=MAX_HISTORY_DAYS)
    if from_date is not None:
        start = max(from_date, floor)
    else:
        start = _default_history_start(session, asset, floor)
    if start > till:
        return 0

    points = client.get_history(
        asset.secid,
        asset.market,
        asset.board,
        start,
        till,
        _price_type(asset),
    )
    written = 0
    for point in points:
        if point.price_micro <= 0:
            continue
        saved = _upsert_quote(
            session,
            asset_id=asset.id,
            quote_date=point.quote_date,
            price_micro=point.price_micro,
            price_type=point.price_type,
            source=DataSource.MOEX,
        )
        if saved.source is DataSource.MANUAL:
            # Protected manual price: MOEX did not write anything.
            continue
        written += 1
    return written


def refresh_all(session: Session, client: MoexClient) -> RefreshResult:
    """Refresh quotes and bond schedules for all active assets.

    ``updated`` counts processed assets, not written price rows. Each asset is
    committed independently. One failure is collected in ``errors`` and does
    not stop the remaining assets. A concurrent refresh raises
    ``REFRESH_IN_PROGRESS`` instead of waiting.
    """

    if not _refresh_lock.acquire(blocking=False):
        raise AppError(
            ErrorCode.REFRESH_IN_PROGRESS,
            "Обновление котировок уже выполняется",
            status_code=409,
        )

    try:
        assets = list(
            session.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.id))
        )
        updated = 0
        failed = 0
        errors: list[RefreshError] = []

        for asset in assets:
            asset_id, secid = asset.id, asset.secid
            try:
                # The intraday quote goes first; the history page then replaces
                # today's row with the official CLOSE when MOEX returns one.
                refresh_asset(session, client, asset)
                backfill_history(session, client, asset)
                if asset.type is AssetType.BOND:
                    portfolio_id = portfolio_service.ensure_default_portfolio(
                        session, commit=False
                    ).id
                    bondization = client.get_bondization(secid)
                    bondization_service.sync_bondization(
                        session,
                        asset,
                        bondization,
                        portfolio_id=portfolio_id,
                    )
                session.commit()
                updated += 1
            except Exception as exc:
                session.rollback()
                failed += 1
                errors.append(
                    RefreshError(asset_id=asset_id, secid=secid, error=_error_message(exc))
                )
                if isinstance(exc, AppError):
                    logger.warning("Quote refresh failed for %s: %s", secid, exc.message)
                else:
                    logger.exception("Quote refresh failed for %s", secid)

        last_refresh_at = utc_now_naive()
        status = _refresh_status(updated, failed)
        settings_service.set_last_quote_refresh(session, last_refresh_at, status, commit=False)
        session.commit()
        return RefreshResult(
            updated=updated,
            failed=failed,
            last_refresh_at=last_refresh_at,
            errors=errors,
        )
    finally:
        _refresh_lock.release()


def add_manual(
    session: Session,
    *,
    asset_id: int,
    quote_date: date,
    price: Decimal,
    price_type: PriceType,
) -> Quote:
    """Store a user-provided price, overriding any price for the same date."""

    asset = asset_service.get_asset(session, asset_id)
    today = today_local()
    if quote_date > today:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Дата котировки не может быть в будущем",
            status_code=400,
            details={"asset_id": asset_id, "quote_date": quote_date.isoformat()},
        )

    expected_type = PriceType.PERCENT if asset.type is AssetType.BOND else PriceType.RUB
    if price_type is not expected_type:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            (
                "Для облигаций цена задается в процентах от номинала"
                if expected_type is PriceType.PERCENT
                else "Для акций цена задается в рублях"
            ),
            status_code=400,
            details={
                "asset_id": asset_id,
                "price_type": price_type.value,
                "expected": expected_type.value,
            },
        )

    price_micro = rubles_to_micro(price)
    if price_micro <= 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Цена должна быть больше нуля",
            status_code=400,
            details={"asset_id": asset_id},
        )

    quote = _upsert_quote(
        session,
        asset_id=asset.id,
        quote_date=quote_date,
        price_micro=price_micro,
        price_type=price_type,
        source=DataSource.MANUAL,
    )
    session.commit()
    session.refresh(quote)
    return quote


def get_history(session: Session, asset_id: int, period: str) -> list[Quote]:
    """Return cached quotes for a period, oldest first."""

    asset_service.get_asset(session, asset_id)
    if period not in PERIOD_DAYS:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Период {period} не поддерживается",
            status_code=400,
            details={"period": period, "supported": list(PERIOD_DAYS)},
        )

    days = PERIOD_DAYS[period]
    statement = select(Quote).where(Quote.asset_id == asset_id)
    if days is not None:
        start = today_local() - timedelta(days=days)
        statement = statement.where(Quote.quote_date >= start)
    statement = statement.order_by(Quote.quote_date, Quote.id)
    return list(session.scalars(statement))


def sync_asset_quotes(
    session: Session,
    client: MoexClient,
    asset: Asset,
    *,
    history_from: date | None = None,
) -> None:
    """Best-effort quote sync used after asset creation or metadata refresh.

    The asset metadata is already committed when this runs, so MOEX and
    database failures are logged and rolled back instead of surfacing: cached
    quotes are optional and must never break an asset operation.
    """

    try:
        # The intraday quote goes first; the history page then replaces today's
        # row with the official CLOSE when MOEX returns one.
        refresh_asset(session, client, asset)
        backfill_history(session, client, asset, from_date=history_from)
        session.commit()
    except (MoexError, SQLAlchemyError) as exc:
        session.rollback()
        logger.warning("Quotes were not synced for %s: %s", asset.secid, exc)


def _upsert_quote(
    session: Session,
    asset_id: int,
    quote_date: date,
    price_micro: int,
    price_type: PriceType,
    source: DataSource,
) -> Quote:
    """Insert or update the single quote of ``(asset_id, quote_date)``.

    MOEX never overwrites a manual quote; a manual quote may overwrite any
    existing source. The caller owns the transaction.
    """

    existing = session.scalar(
        select(Quote).where(Quote.asset_id == asset_id, Quote.quote_date == quote_date)
    )
    if existing is None:
        quote = Quote(
            asset_id=asset_id,
            quote_date=quote_date,
            price_micro=price_micro,
            price_type=price_type,
            source=source,
            fetched_at=utc_now_naive(),
        )
        session.add(quote)
        session.flush()
        return quote

    if source is DataSource.MOEX and existing.source is DataSource.MANUAL:
        return existing

    existing.price_micro = price_micro
    existing.price_type = price_type
    existing.source = source
    existing.fetched_at = utc_now_naive()
    session.flush()
    return existing


def _default_history_start(session: Session, asset: Asset, floor: date) -> date:
    last_quote = get_last_quote(session, asset.id)
    if last_quote is not None:
        # Overlap the previous day: ``refresh_asset`` writes today's row first,
        # but yesterday's official CLOSE may not have been published when that
        # earlier refresh ran. Yesterday's intraday row is re-fetched too (its
        # date is already cached) so the CLOSE can replace it. MANUAL rows stay
        # protected by ``_upsert_quote``.
        return max(last_quote.quote_date - timedelta(days=1), floor)

    first_operation = session.scalar(
        select(func.min(Operation.trade_date)).where(Operation.asset_id == asset.id)
    )
    if first_operation is not None:
        return max(first_operation, floor)
    return floor


def _price_type(asset: Asset) -> PriceType:
    return PriceType.PERCENT if asset.type is AssetType.BOND else PriceType.RUB


def _refresh_status(updated: int, failed: int) -> str:
    if failed == 0:
        return settings_service.REFRESH_STATUS_OK
    if updated == 0:
        return settings_service.REFRESH_STATUS_FAILED
    return settings_service.REFRESH_STATUS_PARTIAL


def _error_message(exc: Exception) -> str:
    """Return a client-safe message; details stay in the server log."""

    if isinstance(exc, AppError):
        return exc.message
    return GENERIC_REFRESH_ERROR
