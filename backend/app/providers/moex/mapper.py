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

# Single source of truth for the boards supported by the MVP:
# board -> (market, asset type). The lookups below are derived views.
BOARD_SPECS: dict[str, tuple[str, AssetType]] = {
    "TQBR": ("shares", AssetType.STOCK),
    "TQCB": ("bonds", AssetType.BOND),
}

BOARD_TYPES: dict[str, AssetType] = {board: spec[1] for board, spec in BOARD_SPECS.items()}

# Markets used by the board endpoint when board-specific fields are needed.
BOARD_MARKETS: dict[str, str] = {board: spec[0] for board, spec in BOARD_SPECS.items()}

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


def requires_board_details(payload: dict[str, Any], board: str | None) -> bool:
    """Return whether board-specific fields must be fetched from the board endpoint.

    Current ISS responses carry ``description``/``boards`` and no
    board-level ``securities`` row, so fields such as ``LOTSIZE`` only exist on
    the board endpoint. A legacy ``securities`` table is enough when it already
    contains the requested board; otherwise the card row is used and the board
    endpoint supplies the missing fields.
    """

    if board is None or board not in BOARD_SPECS:
        return False
    boards = table_rows(payload, "boards")
    if not any(_text(get_field(row, "boardid", "BOARDID")) == board for row in boards):
        return False
    rows = table_rows(payload, "securities")
    if not rows:
        return True
    return not any(_text(get_field(row, "BOARDID", "boardid")) == board for row in rows)


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


def parse_security_info(
    payload: dict[str, Any],
    board: str | None = None,
    board_payload: dict[str, Any] | None = None,
) -> SecurityInfo | None:
    """Parse a security info response.

    ISS has two shapes for this endpoint. Older responses embed a
    ``securities`` table with one row per board; current responses contain a
    ``description`` table (name/value pairs) and a ``boards`` table instead.
    Board-specific trading fields such as ``LOTSIZE`` are not part of the
    current shape and are read from the board endpoint (``board_payload``).

    When ``board`` is given the matching row is preferred; otherwise the
    primary traded board is used, then the first supported board. The face
    value is the original one (``INITIALFACEVALUE`` in the current shape), not
    the current value reduced by amortization.
    """

    rows = table_rows(payload, "securities")
    chosen = _select_security_row(rows, board) if rows else None
    if chosen is None:
        # Legacy and current shapes may be mixed: the ``securities`` table can
        # exist without the requested board while ``boards`` still lists it.
        chosen = _security_row_from_card(payload, board)
    if chosen is None:
        return None
    if board_payload is not None:
        chosen = _merge_board_details(chosen, board_payload, board)

    secid = _text(get_field(chosen, "SECID", "secid"))
    if secid is None:
        return None

    chosen_board = _text(get_field(chosen, "BOARDID", "boardid")) or board or ""
    face_unit = (_text(get_field(chosen, "FACEUNIT", "faceunit")) or "SUR").upper()
    initial_face_value = get_field(chosen, "FACEVALUE", "facevalue")
    face_value_kopecks: int | None = None
    if initial_face_value not in (None, "", 0, "0"):
        if face_unit not in {"SUR", "RUB"}:
            raise MoexParseError(
                f"Валюта номинала {face_unit} не поддерживается",
                details={"face_unit": face_unit},
            )
        try:
            face_value_kopecks = rubles_to_kopecks(initial_face_value)
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise MoexParseError(
                "Некорректный номинал бумаги",
                details={"face_value": str(initial_face_value)},
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


def _security_row_from_card(payload: dict[str, Any], board: str | None) -> dict[str, Any] | None:
    """Build a security row from the current ``description``/``boards`` shape."""

    description = _description_values(payload)
    if not description:
        return None
    board_row = _select_board_row(table_rows(payload, "boards"), board)
    if board_row is None:
        return None
    row = dict(description)
    board_id = _text(get_field(board_row, "boardid", "BOARDID"))
    if board_id:
        row["BOARDID"] = board_id
    return row


def _description_values(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten the name/value pairs of a ``description`` table."""

    values: dict[str, Any] = {}
    for row in table_rows(payload, "description"):
        name = _text(get_field(row, "name", "NAME"))
        if name:
            values[name.upper()] = get_field(row, "value", "VALUE")
    secid = _text(values.get("SECID"))
    if secid is None:
        return {}
    # ``FACEVALUE`` is the *current* face value and decreases after
    # amortization payments. The asset model and the amortization schedule are
    # based on the original face value, so ``INITIALFACEVALUE`` wins whenever
    # both fields are present.
    initial_face_value = values.get("INITIALFACEVALUE")
    if initial_face_value in (None, ""):
        initial_face_value = values.get("FACEVALUE")
    return {
        "SECID": secid,
        "SECNAME": values.get("NAME"),
        "SHORTNAME": values.get("SHORTNAME"),
        "ISIN": values.get("ISIN"),
        "TYPE": values.get("TYPE"),
        "FACEVALUE": initial_face_value,
        "FACEUNIT": values.get("FACEUNIT"),
    }


def _select_board_row(rows: list[dict[str, Any]], board: str | None) -> dict[str, Any] | None:
    """Pick a row of the current ``boards`` table."""

    if board:
        for row in rows:
            if _text(get_field(row, "boardid", "BOARDID")) == board:
                return row
        return None

    candidates = (
        lambda row: _board_is_primary(row) and _board_is_traded(row),
        _board_is_primary,
        lambda row: _board_is_supported(row) and _board_is_traded(row),
        _board_is_supported,
        _board_is_traded,
    )
    for predicate in candidates:
        for row in rows:
            if predicate(row):
                return row
    return rows[0] if rows else None


def _board_is_primary(row: dict[str, Any]) -> bool:
    return _is_true(get_field(row, "is_primary", "ISPRIMARY"))


def _board_is_traded(row: dict[str, Any]) -> bool:
    return _is_true(get_field(row, "is_traded", "ISTRADED"))


def _board_is_supported(row: dict[str, Any]) -> bool:
    return _text(get_field(row, "boardid", "BOARDID")) in BOARD_TYPES


def _merge_board_details(
    row: dict[str, Any], board_payload: dict[str, Any], board: str | None
) -> dict[str, Any]:
    """Overlay board-specific fields (``LOTSIZE``) onto a security row."""

    secid = _text(get_field(row, "SECID", "secid"))
    for detail in table_rows(board_payload, "securities"):
        if _text(get_field(detail, "SECID", "secid")) != secid:
            continue
        detail_board = _text(get_field(detail, "BOARDID", "boardid"))
        if board and detail_board and detail_board != board:
            continue
        merged = dict(row)
        merged.update({key: value for key, value in detail.items() if value not in (None, "")})
        # The board endpoint reports the current face value, which is lower
        # after amortization. Never let it overwrite the original face value
        # derived from INITIALFACEVALUE in the description card.
        for field in ("FACEVALUE", "FACEUNIT"):
            value = get_field(row, field, field.lower())
            if value not in (None, ""):
                merged[field] = value
        return merged
    return row


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
                "amortdate",
                "AMORTDATE",
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
