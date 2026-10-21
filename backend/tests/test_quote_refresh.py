"""Quote refresh tests: single-asset refresh, batch refresh and sync."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DataSource, PriceType
from app.core.errors import AppError
from app.core.time import today_local
from app.db.models.quote import Quote
from app.providers.moex.client import MoexClient
from app.services import quote_service, settings_service

from quote_helpers import BASE_URL, EMPTY_HISTORY, create_bond, create_stock  # isort: skip


@respx.mock
def test_refresh_asset_writes_today_quote(
    db_session: Session,
    moex_client: MoexClient,
    load_fixture: Callable[..., Any],
) -> None:
    asset = create_stock(db_session)
    respx.get(f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "marketdata_sber.json"))
    )

    quote = quote_service.refresh_asset(db_session, moex_client, asset)
    db_session.commit()

    assert quote is not None
    assert quote.quote_date == today_local()
    assert quote.price_micro == 310_500_000
    assert quote.price_type is PriceType.RUB
    assert quote.source is DataSource.MOEX


@respx.mock
def test_refresh_all_official_close_overwrites_intraday_today(
    db_session: Session,
    moex_client: MoexClient,
    load_fixture: Callable[..., Any],
) -> None:
    asset = create_stock(db_session)
    today = today_local()
    history = {
        "history": {
            "columns": ["TRADEDATE", "CLOSE"],
            "data": [[today.isoformat(), 300.0]],
        }
    }
    respx.get(f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "marketdata_sber.json"))
    )
    respx.get(
        f"{BASE_URL}/history/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
    ).mock(return_value=httpx.Response(200, json=history))

    result = quote_service.refresh_all(db_session, moex_client)

    assert result.updated == 1
    quote = quote_service.get_last_quote(db_session, asset.id)
    assert quote is not None
    assert quote.quote_date == today
    # 300.0 from the official CLOSE, not 310.5 from the intraday marketdata.
    assert quote.price_micro == 300_000_000


@respx.mock
def test_refresh_all_counts_errors_and_stores_status(
    db_session: Session,
    moex_client: MoexClient,
    load_fixture: Callable[..., Any],
) -> None:
    good = create_stock(db_session, "SBER")
    bad = create_stock(db_session, "GAZP")
    respx.get(
        f"{BASE_URL}/history/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
    ).mock(return_value=httpx.Response(200, json=EMPTY_HISTORY))
    respx.get(f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "marketdata_sber.json"))
    )
    respx.get(f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/GAZP.json").mock(
        return_value=httpx.Response(500)
    )

    result = quote_service.refresh_all(db_session, moex_client)

    assert (result.updated, result.failed) == (1, 1)
    assert [error.asset_id for error in result.errors] == [bad.id]
    assert result.errors[0].secid == "GAZP"
    assert result.errors[0].error
    assert result.last_refresh_at is not None
    assert settings_service.get_last_quote_refresh_at(db_session) == result.last_refresh_at
    assert (
        settings_service.get_value(db_session, settings_service.LAST_QUOTE_REFRESH_STATUS)
        == "partial"
    )
    assert db_session.scalar(select(Quote).where(Quote.asset_id == good.id)) is not None
    assert db_session.scalar(select(Quote).where(Quote.asset_id == bad.id)) is None


@respx.mock
def test_refresh_all_hides_internal_error_detail(
    db_session: Session,
    moex_client: MoexClient,
    monkeypatch: pytest.MonkeyPatch,
    load_fixture: Callable[..., Any],
) -> None:
    create_stock(db_session, "SBER")
    create_stock(db_session, "GAZP")
    respx.get(f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "marketdata_sber.json"))
    )
    respx.get(
        f"{BASE_URL}/history/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
    ).mock(return_value=httpx.Response(200, json=EMPTY_HISTORY))
    real_current_quote = moex_client.get_current_quote

    def _boom(secid: str, *args: Any, **kwargs: Any) -> Any:
        if secid == "GAZP":
            raise RuntimeError("internal-detail-xyz")
        return real_current_quote(secid, *args, **kwargs)

    monkeypatch.setattr(moex_client, "get_current_quote", _boom)

    result = quote_service.refresh_all(db_session, moex_client)

    assert result.failed == 1
    assert result.errors[0].secid == "GAZP"
    assert result.errors[0].error == quote_service.GENERIC_REFRESH_ERROR
    assert "internal-detail-xyz" not in result.errors[0].error


@respx.mock
def test_refresh_all_marks_failed_when_every_asset_fails(
    db_session: Session,
    moex_client: MoexClient,
) -> None:
    create_stock(db_session)
    respx.get(f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/SBER.json").mock(
        return_value=httpx.Response(500)
    )

    result = quote_service.refresh_all(db_session, moex_client)

    assert (result.updated, result.failed) == (0, 1)
    assert (
        settings_service.get_value(db_session, settings_service.LAST_QUOTE_REFRESH_STATUS)
        == "failed"
    )


@respx.mock
def test_refresh_all_syncs_bond_schedule(
    db_session: Session,
    moex_client: MoexClient,
    load_fixture: Callable[..., Any],
) -> None:
    create_bond(db_session)
    respx.get(
        f"{BASE_URL}/history/engines/stock/markets/bonds/boards/TQCB/securities/SU26238RMFS4.json"
    ).mock(return_value=httpx.Response(200, json=EMPTY_HISTORY))
    respx.get(
        f"{BASE_URL}/engines/stock/markets/bonds/boards/TQCB/securities/SU26238RMFS4.json"
    ).mock(return_value=httpx.Response(200, json=load_fixture("moex", "marketdata_ofz.json")))
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4/bondization.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "bondization_ofz.json"))
    )

    result = quote_service.refresh_all(db_session, moex_client)

    assert (result.updated, result.failed) == (1, 0)
    assert (
        settings_service.get_value(db_session, settings_service.LAST_QUOTE_REFRESH_STATUS) == "ok"
    )


def test_refresh_all_rejects_concurrent_run(db_session: Session, moex_client: MoexClient) -> None:
    assert quote_service._refresh_lock.acquire(blocking=False)
    try:
        with pytest.raises(AppError) as exc_info:
            quote_service.refresh_all(db_session, moex_client)
        assert exc_info.value.code == "REFRESH_IN_PROGRESS"
        assert exc_info.value.status_code == 409
    finally:
        quote_service._refresh_lock.release()
