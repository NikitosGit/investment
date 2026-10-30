"""Dashboard aggregation and the daily valuation series (plan §6.7/§8.7).

The current totals come from :mod:`position_service` and
:mod:`income_service`; the historical series is replayed locally from the
operation, quote and amortization tables. Positions are never stored, and no
monetary calculation uses binary floats.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, IncomeKind, IncomeStatus, PriceType
from app.core.errors import AppError, ErrorCode
from app.core.periods import DASHBOARD_PERIOD_DAYS, DEFAULT_DASHBOARD_PERIOD
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.db.models.quote import Quote
from app.services import (
    bondization_service,
    income_service,
    portfolio_service,
    position_service,
)
from app.services.income_service import IncomeView
from app.services.position_service import PositionView


@dataclass(frozen=True, slots=True)
class DashboardTotals:
    """Portfolio totals shown on the dashboard."""

    market_value_kopecks: int
    invested_kopecks: int
    dividends_paid_kopecks: int
    coupons_paid_kopecks: int
    income_paid_total_kopecks: int
    expected_coupons_kopecks: int
    positions_count: int
    assets_count: int


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    """One day of the portfolio value chart."""

    date: date
    market_value_kopecks: int
    invested_kopecks: int
    is_partial: bool


@dataclass(frozen=True, slots=True)
class DashboardData:
    """Everything the dashboard endpoint returns."""

    as_of: date
    currency: str
    period: str
    totals: DashboardTotals
    series: list[SeriesPoint]
    positions: list[PositionView]
    upcoming_coupons: list[IncomeView]


def period_start(period: str, *, today: date | None = None) -> date | None:
    """Return the inclusive start of a period, or ``None`` for ``ALL``.

    An unsupported period raises ``BAD_REQUEST`` in the same shape as the
    quote history endpoint.
    """

    if period not in DASHBOARD_PERIOD_DAYS:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Период {period} не поддерживается",
            status_code=400,
            details={"period": period, "supported": list(DASHBOARD_PERIOD_DAYS)},
        )

    days = DASHBOARD_PERIOD_DAYS[period]
    if days is None:
        return None
    return (today or today_local()) - timedelta(days=days)


def get_dashboard(session: Session, period: str = DEFAULT_DASHBOARD_PERIOD) -> DashboardData:
    """Build the dashboard for a period (plan §6.7)."""

    today = today_local()
    start = period_start(period, today=today)
    positions = position_service.get_positions(session)
    portfolio = portfolio_service.get_portfolio(session)
    if portfolio is None:
        # No portfolio yet: there is no income to aggregate, and reading the
        # dashboard must not create one as a side effect.
        income_totals = income_service.IncomeTotals(
            dividends_paid_kopecks=0,
            coupons_paid_kopecks=0,
            expected_coupons_kopecks=0,
        )
    else:
        income_totals = income_service.totals(session, portfolio_id=portfolio.id)

    totals = DashboardTotals(
        market_value_kopecks=sum(view.market_value_kopecks for view in positions),
        invested_kopecks=sum(view.invested_kopecks for view in positions),
        dividends_paid_kopecks=income_totals.dividends_paid_kopecks,
        coupons_paid_kopecks=income_totals.coupons_paid_kopecks,
        income_paid_total_kopecks=(
            income_totals.dividends_paid_kopecks + income_totals.coupons_paid_kopecks
        ),
        expected_coupons_kopecks=income_totals.expected_coupons_kopecks,
        positions_count=len(positions),
        assets_count=_assets_count(session),
    )
    return DashboardData(
        as_of=today,
        currency=portfolio.base_currency if portfolio is not None else "RUB",
        period=period,
        totals=totals,
        series=_series_from(session, start, today),
        positions=positions,
        upcoming_coupons=_upcoming_coupons(
            session, portfolio.id if portfolio is not None else None, today
        ),
    )


def compute_series(session: Session, period: str) -> list[SeriesPoint]:
    """Return daily chart points for a period, oldest first."""

    today = today_local()
    return _series_from(session, period_start(period, today=today), today)


def _series_from(
    session: Session,
    start: date | None,
    today: date,
) -> list[SeriesPoint]:
    """Build a series in a precomputed range, oldest first.

    The range starts at the period boundary (or the first operation for
    ``ALL``) but never before the first operation. Without operations (or when
    the first operation is still in the future) the series is empty rather than
    a long flat zero line.
    """

    first_operation = session.scalar(select(func.min(Operation.trade_date)))
    if first_operation is None:
        return []

    start = first_operation if start is None else max(start, first_operation)
    if start > today:
        return []

    return _replay_series(session, start, today)


def value_on_date(session: Session, target_date: date) -> tuple[int, int, bool]:
    """Return ``(market_value, invested, is_partial)`` for one date.

    This is the same replay used by the dashboard series, reused by the daily
    snapshot so current and historical valuations never diverge.
    """

    points = _replay_series(session, target_date, target_date)
    if not points:
        return 0, 0, False
    point = points[0]
    return point.market_value_kopecks, point.invested_kopecks, point.is_partial


def _assets_count(session: Session) -> int:
    count = session.scalar(select(func.count()).select_from(Asset))
    return int(count or 0)


def _upcoming_coupons(
    session: Session,
    portfolio_id: int | None,
    today: date,
) -> list[IncomeView]:
    """Return future expected coupons that still have an open quantity."""

    if portfolio_id is None:
        return []

    rows = list(
        session.scalars(
            select(Income)
            .where(
                Income.portfolio_id == portfolio_id,
                Income.kind == IncomeKind.COUPON,
                Income.status == IncomeStatus.EXPECTED,
                Income.pay_date >= today,
            )
            .order_by(Income.pay_date, Income.id)
        )
    )
    views = income_service.build_views(session, rows)
    return [view for view in views if (view.quantity or 0) > 0]


def _replay_series(session: Session, start: date, end: date) -> list[SeriesPoint]:
    """Replay operations, quotes and amortizations day by day."""

    operations = list(
        session.scalars(
            select(Operation)
            .where(Operation.trade_date <= end)
            .order_by(Operation.trade_date, Operation.id)
        )
    )
    asset_ids = {operation.asset_id for operation in operations}
    if not asset_ids:
        return []

    assets = {
        asset.id: asset for asset in session.scalars(select(Asset).where(Asset.id.in_(asset_ids)))
    }
    quotes_by_asset = _load_quotes(session, asset_ids, end)
    amortizations_by_asset = _load_amortizations(session, assets, end)

    states: dict[int, tuple[int, int, int]] = {}
    quote_positions: dict[int, int] = {}
    last_quotes: dict[int, Quote | None] = {}
    operation_index = 0
    points: list[SeriesPoint] = []

    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        while operation_index < len(operations) and operations[operation_index].trade_date <= day:
            operation = operations[operation_index]
            quantity, cost_kopecks, face_basis_kopecks = states.get(operation.asset_id, (0, 0, 0))
            states[operation.asset_id] = position_service.apply_operation(
                operation.asset_id,
                quantity,
                cost_kopecks,
                face_basis_kopecks,
                operation,
            )
            operation_index += 1

        market_value = 0
        invested = 0
        is_partial = False
        for asset_id, (quantity, cost_kopecks, _face_basis_kopecks) in states.items():
            if quantity <= 0:
                continue
            invested += cost_kopecks
            quote = _quote_on(
                asset_id,
                day,
                quotes_by_asset,
                quote_positions,
                last_quotes,
            )
            if quote is None:
                market_value += cost_kopecks
                is_partial = True
                continue
            asset = assets[asset_id]
            face_value = None
            if asset.type is AssetType.BOND and quote.price_type is PriceType.PERCENT:
                face_value = bondization_service.face_value_on(
                    asset,
                    amortizations_by_asset.get(asset_id, ()),
                    quote.quote_date,
                )
            market_value += position_service.market_value_kopecks(
                asset,
                quantity,
                price_type=quote.price_type,
                price_micro=quote.price_micro,
                face_value_kopecks=face_value,
            )

        points.append(
            SeriesPoint(
                date=day,
                market_value_kopecks=market_value,
                invested_kopecks=invested,
                is_partial=is_partial,
            )
        )

    return points


def _load_quotes(
    session: Session,
    asset_ids: set[int],
    end: date,
) -> dict[int, list[Quote]]:
    quotes: dict[int, list[Quote]] = {}
    rows = session.scalars(
        select(Quote)
        .where(Quote.asset_id.in_(asset_ids), Quote.quote_date <= end)
        .order_by(Quote.asset_id, Quote.quote_date, Quote.id)
    )
    for quote in rows:
        quotes.setdefault(quote.asset_id, []).append(quote)
    return quotes


def _load_amortizations(
    session: Session,
    assets: dict[int, Asset],
    end: date,
) -> dict[int, list[BondAmortization]]:
    bond_ids = {asset_id for asset_id, asset in assets.items() if asset.type is AssetType.BOND}
    if not bond_ids:
        return {}

    schedule: dict[int, list[BondAmortization]] = {}
    rows = session.scalars(
        select(BondAmortization)
        .where(
            BondAmortization.asset_id.in_(bond_ids),
            BondAmortization.amortization_date <= end,
        )
        .order_by(
            BondAmortization.asset_id,
            BondAmortization.amortization_date,
            BondAmortization.id,
        )
    )
    for amortization in rows:
        schedule.setdefault(amortization.asset_id, []).append(amortization)
    return schedule


def _quote_on(
    asset_id: int,
    day: date,
    quotes_by_asset: dict[int, list[Quote]],
    quote_positions: dict[int, int],
    last_quotes: dict[int, Quote | None],
) -> Quote | None:
    """Advance the asset's quote cursor and return the last quote <= ``day``."""

    quotes = quotes_by_asset.get(asset_id)
    if not quotes:
        return None

    index = quote_positions.get(asset_id, 0)
    while index < len(quotes) and quotes[index].quote_date <= day:
        last_quotes[asset_id] = quotes[index]
        index += 1
    quote_positions[asset_id] = index
    return last_quotes.get(asset_id)
