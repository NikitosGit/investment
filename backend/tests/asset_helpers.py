"""Shared MOEX stubs for asset API tests."""

from collections.abc import Callable
from typing import Any

import httpx
import respx

BASE_URL = "https://iss.moex.com/iss"
EMPTY_HISTORY = {
    "history": {
        "columns": ["TRADEDATE", "CLOSE", "LEGALCLOSEPRICE"],
        "data": [],
    }
}


def stub_quotes(
    load_fixture: Callable[..., Any],
    *,
    secid: str = "SBER",
    market: str = "shares",
    board: str = "TQBR",
    marketdata: str = "marketdata_sber.json",
) -> None:
    """Serve an empty history and one marketdata quote for a test."""

    respx.get(
        f"{BASE_URL}/history/engines/stock/markets/{market}/boards/{board}/securities/{secid}.json"
    ).mock(return_value=httpx.Response(200, json=EMPTY_HISTORY))
    respx.get(
        f"{BASE_URL}/engines/stock/markets/{market}/boards/{board}/securities/{secid}.json"
    ).mock(return_value=httpx.Response(200, json=load_fixture("moex", marketdata)))


def security_payload(
    *,
    secid: str,
    board: str,
    security_type: str,
    face_value: float | None,
) -> dict[str, Any]:
    """Build a minimal MOEX ``securities`` payload for edge cases."""

    return {
        "securities": {
            "columns": [
                "SECID",
                "BOARDID",
                "SECNAME",
                "SHORTNAME",
                "ISIN",
                "TYPE",
                "LOTSIZE",
                "FACEVALUE",
                "FACEUNIT",
            ],
            "data": [
                [
                    secid,
                    board,
                    "Тестовая бумага",
                    "Тест",
                    "RU0000000001",
                    security_type,
                    1,
                    face_value,
                    "SUR",
                ]
            ],
        }
    }
