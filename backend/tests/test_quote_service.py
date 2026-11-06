"""QuoteService tests: upserts, backfill, history, manual prices and sync."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.enums import DataSource, OperationType, PriceType
from app.core.errors import AppError
from app.core.time import today_local
from app.db.models.operation import Operation
from app.db.models.quote import Quote
from app.providers.moex.client import MoexClient
from app.providers.moex.errors import MoexUnavailable
from app.providers.moex.schemas import HistoryPoint
from app.services import portfolio_service, quote_service

from quote_helpers import BASE_URL, HistoryClient, create_bond, create_stock  # isort: skip


def test_upsert_protects_manual_from_moex(db_session: Session) -> None:
    asset = create_stock(db_session)
    manual = quote_service._upsert_quote(
        db_session,
        asset_id=asset.id,
        quote_date=date(2026, 1, 10),
        price_micro=100_000_000,
        price_type=PriceType.RUB,
        source=DataSource.MANUAL,
    )
    db_session.commit()

    moex = quote_service._upsert_quote(
        db_session,
        asset_id=asset.id,
        quote_date=date(2026, 1, 10),
        price_micro=200_000_000,
        price_type=PriceType.RUB,
        source=DataSource.MOEX,
    )
    db_session.commit()

    assert moex.id == manual.id
    assert moex.price_micro == 100_000_000
    assert moex.source is DataSource.MANUAL


def test_manual_overwrites_existing_moex_quote(db_session: Session) -> None:
    asset = create_stock(db_session)
    quote_service._upsert_quote(
        db_session,
        asset_id=asset.id,
        quote_date=date(2026, 1, 10),
        price_micro=100_000_000,
        price_type=PriceType.RUB,
        source=DataSource.MOEX,
    )
    db_session.commit()

    quote = quote_service._upsert_quote(
        db_session,
        asset_id=asset.id,
        quote_date=date(2026, 1, 10),
        price_micro=123_456_789,
        price_type=PriceType.RUB,
        source=DataSource.MANUAL,
    )
    db_session.commit()

    assert quote.price_micro == 123_456_789
    assert quote.source is DataSource.MANUAL
    assert db_session.scalar(select(Quote)) is not None


def test_backfill_upserts_and_skips_non_positive(db_session: Session) -> None:
    asset = create_stock(db_session)
    client = HistoryClient(
        [
            HistoryPoint(date(2026, 1, 10), 100_000_000, PriceType.RUB),
            HistoryPoint(date(2026, 1, 11), 0, PriceType.RUB),
        ]
    )

    written = quote_service.backfill_history(
        db_session, client, asset, date(2026, 1, 1), date(2026, 1, 31)
    )
    db_session.commit()

    assert written == 1
    quotes = db_session.scalars(select(Quote)).all()
    assert [(quote.quote_date, quote.price_micro) for quote in quotes] == [
        (date(2026, 1, 10), 100_000_000)
    ]
    assert client.calls[0]["args"][3:5] == (date(2026, 1, 1), date(2026, 1, 31))


@respx.mock
def test_backfill_ofz_on_tqob_uses_live_history(
    db_session: Session,
    moex_client: MoexClient,
    load_fixture: Any,
) -> None:
    asset = create_bond(db_session)
    asset.board = "TQOB"
    db_session.commit()
    respx.get(
        f"{BASE_URL}/history/engines/stock/markets/bonds/boards/TQOB/securities/SU26238RMFS4.json"
    ).mock(return_value=httpx.Response(200, json=load_fixture("moex", "history_su26238_tqob.json")))

    written = quote_service.backfill_history(
        db_session, moex_client, asset, date(2026, 11, 1), date(2026, 11, 6)
    )
    db_session.commit()

    assert written == 3
    quotes = db_session.scalars(select(Quote).order_by(Quote.quote_date)).all()
    assert [(quote.quote_date, quote.price_micro) for quote in quotes] == [
        (date(2026, 11, 2), 52_045_000),
        (date(2026, 11, 3), 51_993_000),
        (date(2026, 11, 5), 51_752_000),
    ]


def test_backfill_overlaps_one_day_before_last_quote(db_session: Session) -> None:
    asset = create_stock(db_session)
    yesterday = today_local() - timedelta(days=1)
    quote_service._upsert_quote(
        db_session,
        asset_id=asset.id,
        quote_date=yesterday,
        price_micro=100_000_000,
        price_type=PriceType.RUB,
        source=DataSource.MOEX,
    )
    db_session.commit()
    client = HistoryClient([])

    assert quote_service.backfill_history(db_session, client, asset) == 0

    # One-day overlap: yesterday's official CLOSE may have been missing when the
    # previous refresh ran, so the window re-opens one day before the last quote.
    assert client.calls[0]["args"][3] == yesterday - timedelta(days=1)


def test_backfill_without_cache_starts_at_first_operation(db_session: Session) -> None:
    portfolio = portfolio_service.ensure_default_portfolio(db_session)
    recent = create_stock(db_session, "SBER")
    ancient = create_stock(db_session, "GAZP")
    today = today_local()
    first_recent = today - timedelta(days=20)
    db_session.add_all(
        [
            Operation(
                portfolio_id=portfolio.id,
                asset_id=recent.id,
                type=OperationType.BUY,
                trade_date=first_recent,
                quantity=1,
                price_micro=100_000_000,
                input_price_micro=100_000_000,
                input_price_type=PriceType.RUB,
            ),
            Operation(
                portfolio_id=portfolio.id,
                asset_id=ancient.id,
                type=OperationType.BUY,
                trade_date=today - timedelta(days=365 * 20),
                quantity=1,
                price_micro=100_000_000,
                input_price_micro=100_000_000,
                input_price_type=PriceType.RUB,
            ),
        ]
    )
    db_session.commit()
    client = HistoryClient([])

    quote_service.backfill_history(db_session, client, recent)
    quote_service.backfill_history(db_session, client, ancient)

    floor = today - timedelta(days=quote_service.MAX_HISTORY_DAYS)
    assert client.calls[0]["args"][3] == first_recent
    assert client.calls[1]["args"][3] == floor


def test_backfill_does_not_overwrite_or_count_manual_quotes(db_session: Session) -> None:
    asset = create_stock(db_session)
    manual_date = date(2026, 1, 10)
    quote_service._upsert_quote(
        db_session,
        asset_id=asset.id,
        quote_date=manual_date,
        price_micro=111_000_000,
        price_type=PriceType.RUB,
        source=DataSource.MANUAL,
    )
    db_session.commit()
    client = HistoryClient(
        [
            HistoryPoint(manual_date, 222_000_000, PriceType.RUB),
            HistoryPoint(date(2026, 1, 11), 333_000_000, PriceType.RUB),
        ]
    )

    written = quote_service.backfill_history(
        db_session, client, asset, date(2026, 1, 1), date(2026, 1, 31)
    )
    db_session.commit()

    assert written == 1
    manual = db_session.scalar(select(Quote).where(Quote.quote_date == manual_date))
    assert manual is not None
    assert manual.price_micro == 111_000_000
    assert manual.source is DataSource.MANUAL


def test_backfill_returns_zero_when_start_after_till(db_session: Session) -> None:
    asset = create_stock(db_session)
    client = HistoryClient([])

    written = quote_service.backfill_history(
        db_session,
        client,
        asset,
        date(2026, 2, 1),
        date(2026, 1, 1),
    )

    assert written == 0
    assert client.calls == []


def test_get_history_periods_order_and_missing_asset(db_session: Session) -> None:
    asset = create_stock(db_session)
    today = today_local()
    for days, price in ((40, 90_000_000), (10, 100_000_000), (100, 80_000_000)):
        quote_service._upsert_quote(
            db_session,
            asset_id=asset.id,
            quote_date=today - timedelta(days=days),
            price_micro=price,
            price_type=PriceType.RUB,
            source=DataSource.MOEX,
        )
    db_session.commit()

    one_month = quote_service.get_history(db_session, asset.id, "1M")
    assert [quote.price_micro for quote in one_month] == [100_000_000]

    three_months = quote_service.get_history(db_session, asset.id, "3M")
    assert [quote.price_micro for quote in three_months] == [90_000_000, 100_000_000]

    all_quotes = quote_service.get_history(db_session, asset.id, "ALL")
    assert [quote.price_micro for quote in all_quotes] == [
        80_000_000,
        90_000_000,
        100_000_000,
    ]

    with pytest.raises(AppError) as exc_info:
        quote_service.get_history(db_session, 999, "1Y")
    assert exc_info.value.code == "ASSET_NOT_FOUND"

    with pytest.raises(AppError) as invalid:
        quote_service.get_history(db_session, asset.id, "2Y")
    assert invalid.value.status_code == 400


def test_add_manual_validates_and_upserts(db_session: Session) -> None:
    stock = create_stock(db_session)
    bond = create_bond(db_session)
    today = today_local()

    quote = quote_service.add_manual(
        db_session,
        asset_id=stock.id,
        quote_date=today,
        price=Decimal("305.123456"),
        price_type=PriceType.RUB,
    )
    assert quote.price_micro == 305_123_456
    assert quote.source is DataSource.MANUAL

    updated = quote_service.add_manual(
        db_session,
        asset_id=stock.id,
        quote_date=today,
        price=Decimal("1.5"),
        price_type=PriceType.RUB,
    )
    assert updated.id == quote.id
    assert updated.price_micro == 1_500_000

    bond_quote = quote_service.add_manual(
        db_session,
        asset_id=bond.id,
        quote_date=today,
        price=Decimal("98.5"),
        price_type=PriceType.PERCENT,
    )
    assert bond_quote.price_type is PriceType.PERCENT

    validations = [
        (stock.id, today + timedelta(days=1), Decimal("1"), PriceType.RUB, 400),
        (stock.id, today, Decimal("1"), PriceType.PERCENT, 400),
        (bond.id, today, Decimal("1"), PriceType.RUB, 400),
        (stock.id, today, Decimal("0"), PriceType.RUB, 400),
        (999, today, Decimal("1"), PriceType.RUB, 404),
    ]
    for asset_id, quote_date, price, price_type, status in validations:
        with pytest.raises(AppError) as exc_info:
            quote_service.add_manual(
                db_session,
                asset_id=asset_id,
                quote_date=quote_date,
                price=price,
                price_type=price_type,
            )
        assert exc_info.value.status_code == status


def test_sync_asset_quotes_swallows_moex_error(db_session: Session) -> None:
    asset = create_stock(db_session)

    class _FailingClient:
        def get_current_quote(self, *args: Any, **kwargs: Any) -> None:
            raise MoexUnavailable("MOEX down")

    quote_service.sync_asset_quotes(db_session, _FailingClient(), asset)  # type: ignore[arg-type]

    assert db_session.scalars(select(Quote)).all() == []


def test_sync_asset_quotes_swallows_db_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = create_stock(db_session)

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise SQLAlchemyError("db down")

    monkeypatch.setattr(quote_service, "refresh_asset", _boom)

    quote_service.sync_asset_quotes(db_session, object(), asset)  # type: ignore[arg-type]

    assert db_session.scalars(select(Quote)).all() == []
