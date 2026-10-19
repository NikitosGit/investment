"""Mapping of raw MOEX ISS payloads to provider schemas.

MOEX returns tables as ``{"columns": [...], "data": [[...], ...]}``. Field
names and availability differ between securities, so the mappers use tolerant
lookups and documented fallbacks.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from app.core.enums import AssetType, PriceType
from app.core.money import rubles_to_kopecks, rubles_to_micro
from app.providers.moex.errors import MoexParseError
from app.providers.moex.schemas import (
    AmortizationInfo,
    Bondization,
    CouponInfo,
    CurrentQuote,
    HistoryPoint,
    SecurityInfo,
    SecuritySearchResult,
)

BOARD_TYPES: dict[str, AssetType] = {
    "TQBR": AssetType.STOCK,
    "TQCB": AssetType.BOND,
}

_CURRENT_PRICE_FIELDS = ("LAST", "LCURRENTPRICE", "MARKETPRICE", "PREVPRICE")


def table_rows(payload: dict[str, Any], table: str) -> list[dict[str, Any]]:
    """Convert an ISS table into a list of row dictionaries."""

    table_payload = payload.get(table) or {}
    columns = table_payload.get("columns") or []
    data = table_payload.get("data") or []
    return [dict(zip(columns, row, strict=False)) for row in data]


def get_field(row: dict[str, Any], *names: str) -> Any:
    """Look up a field by any of the given names, ignoring case."""

    for name in names:
        if name in row:
            return row[name]
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    return str(value).strip().lower() in {"1", "true", "yes"}


def _positive_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None
    return number if number > 0 else None


def _first_positive(row: dict[str, Any], *names: str) -> Decimal | None:
    """Return the first positive value among the given field names."""

    for name in names:
        amount = _positive_decimal(get_field(row, name))
        if amount is not None:
            return amount
    return None


def _parse_date(value: Any) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _type_for_board(board: str | None, row: dict[str, Any] | None = None) -> AssetType:
    if board and board in BOARD_TYPES:
        return BOARD_TYPES[board]
    raw_type = _text(get_field(row or {}, "TYPE", "type")) or ""
    return AssetType.BOND if "bond" in raw_type.lower() else AssetType.STOCK


def parse_search_results(payload: dict[str, Any]) -> list[SecuritySearchResult]:
    """Parse the ``securities`` table of a search response.

    Only traded securities on a supported board (TQBR/TQCB) are returned.
    """

    results: list[SecuritySearchResult] = []
    for row in table_rows(payload, "securities"):
        board = _text(get_field(row, "primary_boardid", "PRIMARYBOARDID", "boardid", "BOARDID"))
        if board not in BOARD_TYPES or not _is_true(get_field(row, "is_traded", "IS_TRADED")):
            continue
        secid = _text(get_field(row, "secid", "SECID"))
        if secid is None:
            continue
        results.append(
            SecuritySearchResult(
                secid=secid,
                name=_text(get_field(row, "name", "NAME", "secname", "SECNAME")) or secid,
                short_name=_text(get_field(row, "shortname", "SHORTNAME", "short_name")),
                isin=_text(get_field(row, "isin", "ISIN")),
                type=_type_for_board(board, row),
                board=board,
            )
        )
    return results


def parse_security_info(payload: dict[str, Any], board: str | None = None) -> SecurityInfo | None:
    """Parse the ``securities`` table of a security info response.

    When ``board`` is given the matching row is preferred; otherwise the first
    row on a supported board is used.
    """

    rows = table_rows(payload, "securities")
    if not rows:
        return None

    chosen = _select_security_row(rows, board)
    if chosen is None:
        return None
    secid = _text(get_field(chosen, "SECID", "secid"))
    if secid is None:
        return None

    chosen_board = _text(get_field(chosen, "BOARDID", "boardid")) or board or ""
    face_unit = (_text(get_field(chosen, "FACEUNIT", "faceunit")) or "SUR").upper()
    face_value = get_field(chosen, "FACEVALUE", "facevalue")
    face_value_kopecks: int | None = None
    if face_value not in (None, "", 0, "0"):
        if face_unit not in {"SUR", "RUB"}:
            raise MoexParseError(
                f"Валюта номинала {face_unit} не поддерживается",
                details={"face_unit": face_unit},
            )
        try:
            face_value_kopecks = rubles_to_kopecks(face_value)
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise MoexParseError(
                "Некорректный номинал бумаги",
                details={"face_value": str(face_value)},
            ) from exc

    lot_size = _parse_lot_size(get_field(chosen, "LOTSIZE", "lotsize"))

    return SecurityInfo(
        secid=secid,
        name=_text(get_field(chosen, "SECNAME", "secname", "NAME", "name")) or secid,
        short_name=_text(get_field(chosen, "SHORTNAME", "shortname")),
        isin=_text(get_field(chosen, "ISIN", "isin")),
        type=_type_for_board(chosen_board, chosen),
        board=chosen_board,
        currency="RUB",
        lot_size=lot_size,
        face_value_kopecks=face_value_kopecks,
        raw=chosen,
    )


def _parse_lot_size(value: Any) -> int:
    if value in (None, "", 0, "0"):
        return 1
    try:
        lot_size = int(value)
    except (TypeError, ValueError) as exc:
        raise MoexParseError("Некорректный размер лота", details={"lotsize": str(value)}) from exc
    return lot_size if lot_size > 0 else 1


def _select_security_row(rows: list[dict[str, Any]], board: str | None) -> dict[str, Any] | None:
    if board:
        for row in rows:
            if _text(get_field(row, "BOARDID", "boardid")) == board:
                return row
        return None
    for row in rows:
        if _text(get_field(row, "BOARDID", "boardid")) in BOARD_TYPES:
            return row
    return rows[0]


def parse_current_quote(
    payload: dict[str, Any],
    *,
    secid: str,
    price_type: PriceType,
    quote_date: date,
) -> CurrentQuote | None:
    """Extract the first positive price from the ``marketdata`` table."""

    rows = table_rows(payload, "marketdata")
    row = next(
        (item for item in rows if _text(get_field(item, "SECID", "secid")) == secid),
        rows[0] if rows else None,
    )
    if row is None:
        return None

    for field in _CURRENT_PRICE_FIELDS:
        price = _positive_decimal(get_field(row, field, field.lower()))
        if price is not None:
            return CurrentQuote(
                quote_date=quote_date,
                price_micro=rubles_to_micro(price),
                price_type=price_type,
            )
    return None


def parse_history(payload: dict[str, Any], price_type: PriceType) -> list[HistoryPoint]:
    """Parse a ``history`` page, preferring CLOSE and falling back to LEGALCLOSEPRICE."""

    points: list[HistoryPoint] = []
    for row in table_rows(payload, "history"):
        trade_date = _parse_date(get_field(row, "TRADEDATE", "tradedate", "TRADE_DATE"))
        if trade_date is None:
            continue
        price = _positive_decimal(get_field(row, "CLOSE", "close")) or _positive_decimal(
            get_field(row, "LEGALCLOSEPRICE", "legalcloseprice")
        )
        if price is None:
            continue
        points.append(
            HistoryPoint(
                quote_date=trade_date,
                price_micro=rubles_to_micro(price),
                price_type=price_type,
            )
        )
    return points


def parse_bondization(payload: dict[str, Any]) -> Bondization:
    """Parse coupon and amortization schedules, tolerating field variations."""

    coupons: list[CouponInfo] = []
    for row in table_rows(payload, "coupons"):
        pay_date = _parse_date(
            get_field(row, "coupondate", "coupon_date", "COUPONDATE", "COUPON_DATE")
        )
        amount = _first_positive(row, "value_rub", "VALUE_RUB", "value", "VALUE")
        if pay_date is None or amount is None:
            continue
        coupons.append(
            CouponInfo(
                pay_date=pay_date,
                record_date=_parse_date(
                    get_field(row, "recorddate", "record_date", "RECORDDATE", "RECORD_DATE")
                ),
                amount_per_unit_micro=rubles_to_micro(amount),
            )
        )

    amortizations: list[AmortizationInfo] = []
    for row in table_rows(payload, "amortizations"):
        amortization_date = _parse_date(
            get_field(
                row,
                "amortizationdate",
                "amortization_date",
                "AMORTIZATIONDATE",
                "AMORTIZATION_DATE",
            )
        )
        amount = _first_positive(row, "value_rub", "VALUE_RUB", "value", "VALUE")
        if amortization_date is None or amount is None:
            continue
        amortizations.append(
            AmortizationInfo(
                amortization_date=amortization_date,
                amount_per_unit_kopecks=rubles_to_kopecks(amount),
            )
        )

    return Bondization(coupons=coupons, amortizations=amortizations)
