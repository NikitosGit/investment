"""MOEX client tests backed by respx; no real network access."""

from collections.abc import Callable, Generator
from datetime import date
from typing import Any

import httpx
import pytest
import respx

from app.core.enums import AssetType, PriceType
from app.providers.moex import client as client_module
from app.providers.moex.client import MoexClient
from app.providers.moex.errors import MoexNotFound, MoexParseError, MoexUnavailable
from app.providers.moex.schemas import Bondization

BASE_URL = "https://iss.moex.com/iss"


@pytest.fixture
def make_client() -> Generator[Callable[..., MoexClient], None, None]:
    created: list[MoexClient] = []

    def _make(**overrides: Any) -> MoexClient:
        options: dict[str, Any] = {
            "retries": 3,
            "min_request_interval": 0,
            "wait_initial": 0,
            "wait_max": 0,
        }
        options.update(overrides)
        instance = MoexClient(BASE_URL, **options)
        created.append(instance)
        return instance

    yield _make
    for instance in created:
        instance.close()


@respx.mock
def test_search_securities(make_client: Callable[..., MoexClient], load_fixture: Any) -> None:
    route = respx.get(f"{BASE_URL}/securities.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "search_sber.json"))
    )
    client = make_client()

    results = client.search_securities("SBER")

    assert [item.secid for item in results] == ["SBER", "SBERP", "SU26238RMFS4"]
    request = route.calls.last.request
    assert request.url.params["q"] == "SBER"
    assert request.url.params["iss.meta"] == "off"


@respx.mock
def test_get_security_info(make_client: Callable[..., MoexClient], load_fixture: Any) -> None:
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_ofz.json"))
    )

    info = make_client().get_security_info("SU26238RMFS4", board="TQCB")

    assert info.type is AssetType.BOND
    assert info.face_value_kopecks == 100_000


@respx.mock
def test_get_security_info_raises_not_found(make_client: Callable[..., MoexClient]) -> None:
    respx.get(f"{BASE_URL}/securities/UNKNOWN.json").mock(return_value=httpx.Response(404))

    with pytest.raises(MoexNotFound):
        make_client().get_security_info("UNKNOWN")


@respx.mock
def test_current_quote_prefers_available_field(
    make_client: Callable[..., MoexClient], load_fixture: Any
) -> None:
    respx.get(f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "marketdata_sber.json"))
    )

    quote = make_client().get_current_quote(
        "SBER", "shares", "TQBR", PriceType.RUB, quote_date=date(2026, 10, 19)
    )

    assert quote is not None
    assert quote.price_micro == 310_500_000


@respx.mock
def test_history_follows_pagination(
    make_client: Callable[..., MoexClient],
    load_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "HISTORY_PAGE_SIZE", 2)
    route = respx.get(
        f"{BASE_URL}/history/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
    ).mock(
        side_effect=[
            httpx.Response(200, json=load_fixture("moex", "history_sber_page1.json")),
            httpx.Response(200, json=load_fixture("moex", "history_sber_page2.json")),
        ]
    )

    points = make_client().get_history(
        "SBER", "shares", "TQBR", date(2026, 1, 1), date(2026, 1, 31), PriceType.RUB
    )

    assert [point.price_micro for point in points] == [100_000_000, 101_000_000, 102_000_000]
    assert [call.request.url.params["start"] for call in route.calls] == ["0", "2"]
    assert route.calls.last.request.url.params["from"] == "2026-01-01"


@respx.mock
def test_history_stops_on_empty_page(
    make_client: Callable[..., MoexClient], load_fixture: Any
) -> None:
    route = respx.get(
        f"{BASE_URL}/history/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
    ).mock(return_value=httpx.Response(200, json=load_fixture("moex", "history_sber_page1.json")))

    points = make_client().get_history(
        "SBER", "shares", "TQBR", date(2026, 1, 1), date(2026, 1, 31), PriceType.RUB
    )

    assert len(points) == 2
    assert len(route.calls) == 1


@respx.mock
def test_get_bondization(make_client: Callable[..., MoexClient], load_fixture: Any) -> None:
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4/bondization.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "bondization_ofz.json"))
    )

    bondization = make_client().get_bondization("SU26238RMFS4")

    assert isinstance(bondization, Bondization)
    assert len(bondization.coupons) == 3
    assert len(bondization.amortizations) == 1


@respx.mock
def test_retries_transient_server_error_then_succeeds(
    make_client: Callable[..., MoexClient], load_fixture: Any
) -> None:
    route = respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=load_fixture("moex", "security_sber.json")),
        ]
    )

    info = make_client().get_security_info("SBER", board="TQBR")

    assert info.secid == "SBER"
    assert len(route.calls) == 2


@respx.mock
def test_unavailable_after_exhausting_retries(make_client: Callable[..., MoexClient]) -> None:
    route = respx.get(f"{BASE_URL}/securities/SBER.json").mock(return_value=httpx.Response(500))

    with pytest.raises(MoexUnavailable) as exc_info:
        make_client(retries=3).get_security_info("SBER")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "MOEX_UNAVAILABLE"
    assert len(route.calls) == 4


@respx.mock
def test_rate_limit_response_is_retried(
    make_client: Callable[..., MoexClient], load_fixture: Any
) -> None:
    route = respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json=load_fixture("moex", "security_sber.json")),
        ]
    )

    info = make_client(retries=2).get_security_info("SBER", board="TQBR")

    assert info.secid == "SBER"
    assert len(route.calls) == 2


@respx.mock
def test_timeout_is_reported_as_unavailable(make_client: Callable[..., MoexClient]) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )

    with pytest.raises(MoexUnavailable):
        make_client(retries=2).get_security_info("SBER")


@respx.mock
def test_invalid_json_is_reported_as_parse_error(make_client: Callable[..., MoexClient]) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, text="<html>not json</html>")
    )

    with pytest.raises(MoexParseError):
        make_client().get_security_info("SBER")


@respx.mock
def test_non_object_json_is_reported_as_parse_error(
    make_client: Callable[..., MoexClient],
) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )

    with pytest.raises(MoexParseError):
        make_client().get_security_info("SBER")


@respx.mock
def test_client_error_status_is_reported_as_parse_error(
    make_client: Callable[..., MoexClient],
) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(return_value=httpx.Response(400))

    with pytest.raises(MoexParseError):
        make_client(retries=1).get_security_info("SBER")


@respx.mock
def test_client_can_be_used_as_context_manager() -> None:
    with MoexClient(BASE_URL, min_request_interval=0) as client:
        assert client is not None


_MARKETDATA_FIELDS = ("LAST", "LCURRENTPRICE", "MARKETPRICE", "PREVPRICE")


def _marketdata_row(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "marketdata": {
            "columns": ["SECID", *_MARKETDATA_FIELDS],
            "data": [["SBER", *(values.get(field) for field in _MARKETDATA_FIELDS)]],
        }
    }


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            {"LAST": 100.0, "LCURRENTPRICE": 101.0, "MARKETPRICE": 102.0, "PREVPRICE": 99.0},
            100_000_000,
        ),
        (
            {"LAST": None, "LCURRENTPRICE": 101.0, "MARKETPRICE": 102.0, "PREVPRICE": 99.0},
            101_000_000,
        ),
        (
            {"LAST": None, "LCURRENTPRICE": None, "MARKETPRICE": 102.0, "PREVPRICE": 99.0},
            102_000_000,
        ),
        ({"LAST": None, "LCURRENTPRICE": None, "MARKETPRICE": None, "PREVPRICE": 99.0}, 99_000_000),
    ],
)
@respx.mock
def test_current_price_priority(
    make_client: Callable[..., MoexClient],
    values: dict[str, Any],
    expected: int,
) -> None:
    respx.get(f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=_marketdata_row(values))
    )

    quote = make_client().get_current_quote("SBER", "shares", "TQBR", PriceType.RUB)

    assert quote is not None
    assert quote.price_micro == expected


@respx.mock
def test_bond_quote_is_percent(make_client: Callable[..., MoexClient], load_fixture: Any) -> None:
    respx.get(
        f"{BASE_URL}/engines/stock/markets/bonds/boards/TQCB/securities/SU26238RMFS4.json"
    ).mock(return_value=httpx.Response(200, json=load_fixture("moex", "marketdata_ofz.json")))

    quote = make_client().get_current_quote("SU26238RMFS4", "bonds", "TQCB", PriceType.PERCENT)

    assert quote is not None
    assert quote.price_micro == 98_500_000
    assert quote.price_type is PriceType.PERCENT


@respx.mock
def test_history_is_bounded_by_max_pages(
    make_client: Callable[..., MoexClient],
    load_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "HISTORY_PAGE_SIZE", 1)
    monkeypatch.setattr(client_module, "HISTORY_MAX_PAGES", 2)
    route = respx.get(
        f"{BASE_URL}/history/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
    ).mock(return_value=httpx.Response(200, json=load_fixture("moex", "history_sber_page1.json")))

    make_client().get_history(
        "SBER", "shares", "TQBR", date(2026, 1, 1), date(2026, 1, 31), PriceType.RUB
    )

    assert len(route.calls) == 2


@respx.mock
def test_request_throttling(
    make_client: Callable[..., MoexClient],
    load_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_sber.json"))
    )
    sleeps: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", sleeps.append)
    client = make_client(min_request_interval=0.5, retries=0)

    client.get_security_info("SBER")
    client.get_security_info("SBER")

    assert len(sleeps) == 1
    assert 0.45 < sleeps[0] <= 0.5


@respx.mock
def test_from_settings_configures_client(load_fixture: Any) -> None:
    from app.core.config import Settings

    route = respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        return_value=httpx.Response(200, json=load_fixture("moex", "security_sber.json"))
    )
    settings = Settings(
        moex_base_url=BASE_URL,
        moex_user_agent="ua-test",
        moex_retries=1,
        cors_origins=[],
    )

    with MoexClient.from_settings(settings) as client:
        client.get_security_info("SBER", board="TQBR")

    assert route.calls.last.request.headers["user-agent"] == "ua-test"
