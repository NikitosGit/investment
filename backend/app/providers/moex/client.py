"""Synchronous MOEX ISS client.

The client owns retries, request throttling and error translation. It never
touches the database or the API layer.
"""

import logging
import threading
import time
from datetime import date
from typing import Any

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.core.enums import PriceType
from app.core.time import today_local
from app.providers.moex import mapper
from app.providers.moex.errors import MoexNotFound, MoexParseError, MoexUnavailable
from app.providers.moex.schemas import (
    Bondization,
    CurrentQuote,
    HistoryPoint,
    SecurityInfo,
    SecuritySearchResult,
)

logger = logging.getLogger(__name__)

HISTORY_PAGE_SIZE = 100
HISTORY_MAX_PAGES = 100
DEFAULT_MIN_REQUEST_INTERVAL = 1 / 3
DEFAULT_WAIT_INITIAL = 0.5
DEFAULT_WAIT_MAX = 2.0


class _RetryableMoexError(Exception):
    """Internal marker for transient MOEX failures."""


class MoexClient:
    """Minimal client for the MOEX ISS endpoints used by the application."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        retries: int = 3,
        user_agent: str = "investment-tracker/0.1",
        min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL,
        wait_initial: float = DEFAULT_WAIT_INITIAL,
        wait_max: float = DEFAULT_WAIT_MAX,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Create a client.

        ``retries`` is the number of additional attempts after the first one,
        so the total number of requests per call is ``retries + 1``.
        """

        self._base_url = base_url.rstrip("/")
        self._retries = max(0, retries)
        self._min_request_interval = min_request_interval
        self._wait_initial = wait_initial
        self._wait_max = wait_max
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "MoexClient":
        """Build a client configured from application settings."""

        return cls(
            settings.moex_base_url,
            timeout=settings.moex_timeout_seconds,
            retries=settings.moex_retries,
            user_agent=settings.moex_user_agent,
        )

    def close(self) -> None:
        """Close the underlying HTTP client when it is owned by this instance."""

        if self._owns_client:
            self._http.close()

    def __enter__(self) -> "MoexClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def search_securities(self, query: str) -> list[SecuritySearchResult]:
        """Search for stocks and bonds by ticker or name."""

        payload = self._get("/securities.json", {"q": query})
        return mapper.parse_search_results(payload)

    def get_security_info(self, secid: str, board: str | None = None) -> SecurityInfo:
        """Fetch metadata for a single security."""

        payload = self._get(f"/securities/{secid}.json")
        info = mapper.parse_security_info(payload, board=board)
        if info is None:
            raise MoexNotFound(f"Бумага {secid} не найдена в MOEX")
        return info

    def get_current_quote(
        self,
        secid: str,
        market: str,
        board: str,
        price_type: PriceType,
        quote_date: date | None = None,
    ) -> CurrentQuote | None:
        """Fetch the latest available price for a security."""

        path = f"/engines/stock/markets/{market}/boards/{board}/securities/{secid}.json"
        payload = self._get(path)
        return mapper.parse_current_quote(
            payload,
            secid=secid,
            price_type=price_type,
            quote_date=quote_date or today_local(),
        )

    def get_history(
        self,
        secid: str,
        market: str,
        board: str,
        from_date: date,
        till_date: date,
        price_type: PriceType,
    ) -> list[HistoryPoint]:
        """Fetch daily history, following MOEX pagination."""

        path = f"/history/engines/stock/markets/{market}/boards/{board}/securities/{secid}.json"
        points: list[HistoryPoint] = []
        start = 0
        for _ in range(HISTORY_MAX_PAGES):
            payload = self._get(
                path,
                {
                    "from": from_date.isoformat(),
                    "till": till_date.isoformat(),
                    "start": start,
                },
            )
            points.extend(mapper.parse_history(payload, price_type))
            if len(mapper.table_rows(payload, "history")) < HISTORY_PAGE_SIZE:
                break
            start += HISTORY_PAGE_SIZE
        return points

    def get_bondization(self, secid: str) -> Bondization:
        """Fetch coupon and amortization schedules for a bond."""

        payload = self._get(f"/securities/{secid}/bondization.json")
        return mapper.parse_bondization(payload)

    def _throttle(self) -> None:
        if self._min_request_interval <= 0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            wait_for = self._min_request_interval - elapsed
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_request_at = time.monotonic()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_params = dict(params or {})
        request_params["iss.meta"] = "off"
        retryer = Retrying(
            stop=stop_after_attempt(self._retries + 1),
            wait=wait_exponential(
                multiplier=self._wait_initial,
                min=self._wait_initial,
                max=self._wait_max,
            ),
            retry=retry_if_exception_type(_RetryableMoexError),
            reraise=True,
        )
        try:
            return retryer(self._get_once, path, request_params)
        except _RetryableMoexError as exc:
            logger.warning("MOEX request failed after %s attempts: %s", self._retries + 1, path)
            raise MoexUnavailable(details={"reason": str(exc), "path": path}) from exc

    def _get_once(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self._throttle()
        try:
            response = self._http.get(path, params=params)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise _RetryableMoexError(str(exc)) from exc

        if response.status_code == 404:
            raise MoexNotFound(f"MOEX не вернул данные по пути {path}")
        if response.status_code == 429 or response.status_code >= 500:
            raise _RetryableMoexError(f"MOEX status {response.status_code}")
        if response.status_code >= 400:
            raise MoexParseError(
                f"MOEX вернул неожиданный статус {response.status_code}",
                details={"path": path, "status": response.status_code},
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise MoexParseError("MOEX вернул некорректный JSON", details={"path": path}) from exc
        if not isinstance(payload, dict):
            raise MoexParseError("MOEX вернул неожиданный формат", details={"path": path})
        return payload
