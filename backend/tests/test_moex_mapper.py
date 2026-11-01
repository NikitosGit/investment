"""Unit tests for the MOEX payload mappers."""

from datetime import date
from typing import Any

import pytest

from app.core.enums import AssetType, PriceType
from app.providers.moex.errors import MoexParseError
from app.providers.moex.mapper import (
    get_field,
    parse_bondization,
    parse_current_quote,
    parse_history,
    parse_search_results,
    parse_security_info,
    requires_board_details,
    table_rows,
)


def test_search_keeps_only_traded_supported_boards(load_fixture: Any) -> None:
    results = parse_search_results(load_fixture("moex", "search_sber.json"))

    by_secid = {item.secid: item for item in results}
    assert set(by_secid) == {"SBER", "SBERP", "SU26238RMFS4"}
    assert by_secid["SBER"].type is AssetType.STOCK
    assert by_secid["SBER"].board == "TQBR"
    assert by_secid["SU26238RMFS4"].type is AssetType.BOND
    assert by_secid["SU26238RMFS4"].isin == "RU000A0JX0J2"


def test_security_info_prefers_requested_board(load_fixture: Any) -> None:
    payload = load_fixture("moex", "security_sber.json")

    info = parse_security_info(payload, board="TQBR")

    assert info is not None
    assert info.board == "TQBR"
    assert info.type is AssetType.STOCK
    assert info.lot_size == 10
    assert info.isin == "RU0009029540"


def test_security_info_parses_bond_face_value(load_fixture: Any) -> None:
    info = parse_security_info(load_fixture("moex", "security_ofz.json"), board="TQCB")

    assert info is not None
    assert info.type is AssetType.BOND
    assert info.face_value_kopecks == 100_000
    assert info.lot_size == 1


def test_security_info_rejects_foreign_currency(load_fixture: Any) -> None:
    payload = load_fixture("moex", "security_ofz.json")
    payload["securities"]["data"][0][8] = "USD"

    with pytest.raises(MoexParseError):
        parse_security_info(payload, board="TQCB")


def test_security_info_returns_none_for_unknown_board(load_fixture: Any) -> None:
    assert parse_security_info(load_fixture("moex", "security_sber.json"), board="TQXX") is None


def test_security_info_parses_current_description_and_boards(load_fixture: Any) -> None:
    """Current ISS responses use ``description`` + ``boards``, not ``securities``."""

    payload = load_fixture("moex", "security_gazp.json")
    assert "securities" not in payload

    info = parse_security_info(
        payload,
        board="TQBR",
        board_payload=load_fixture("moex", "security_gazp_board.json"),
    )

    assert info is not None
    assert info.secid == "GAZP"
    assert info.board == "TQBR"
    assert info.type is AssetType.STOCK
    assert info.lot_size == 10
    assert info.isin == "RU0007661625"
    assert info.name == '"Газпром" (ПАО) ао'
    assert info.face_value_kopecks == 500


def test_security_info_current_shape_prefers_primary_board(load_fixture: Any) -> None:
    info = parse_security_info(load_fixture("moex", "security_gazp.json"))

    assert info is not None
    assert info.board == "TQBR"
    assert info.type is AssetType.STOCK
    # Board-specific LOTSIZE is only available from the board endpoint.
    assert info.lot_size == 1


def test_security_info_current_shape_selects_primary_board_not_first_row(
    load_fixture: Any,
) -> None:
    """Board selection must not depend on the order of ``boards.data``."""

    payload = load_fixture("moex", "security_gazp.json")
    payload["boards"]["data"].reverse()
    # A traded but non-primary board is now the first row.
    assert payload["boards"]["data"][0][1] == "RPEY"

    info = parse_security_info(payload)

    assert info is not None
    assert info.board == "TQBR"
    assert info.type is AssetType.STOCK


def test_security_info_current_shape_rejects_unknown_board(load_fixture: Any) -> None:
    assert parse_security_info(load_fixture("moex", "security_gazp.json"), board="TQCB") is None


def test_security_info_current_shape_prefers_initial_face_value() -> None:
    """``FACEVALUE`` is the current value; the asset needs the initial one."""

    payload = {
        "description": {
            "columns": ["name", "value"],
            "data": [
                ["SECID", "BOND"],
                ["NAME", "Амортизируемая облигация"],
                ["TYPE", "exchange_bond"],
                ["FACEVALUE", "600"],
                ["INITIALFACEVALUE", "1000"],
                ["FACEUNIT", "SUR"],
            ],
        },
        "boards": {
            "columns": ["secid", "boardid", "is_traded", "is_primary"],
            "data": [["BOND", "TQCB", 1, 1]],
        },
    }
    board_payload = {
        "securities": {
            "columns": ["SECID", "BOARDID", "LOTSIZE", "FACEVALUE", "FACEUNIT"],
            "data": [["BOND", "TQCB", 5, 600, "SUR"]],
        }
    }

    info = parse_security_info(payload, board="TQCB", board_payload=board_payload)

    assert info is not None
    assert info.type is AssetType.BOND
    assert info.face_value_kopecks == 100_000
    assert info.lot_size == 5
    # The board endpoint must not replace the original face value.
    assert info.raw["FACEVALUE"] == "1000"
    assert info.raw["FACEUNIT"] == "SUR"


def test_security_info_falls_back_to_card_when_board_is_missing_from_securities() -> None:
    """A legacy ``securities`` table may not contain the requested board."""

    payload = {
        "securities": {
            "columns": ["SECID", "BOARDID", "SECNAME", "TYPE", "LOTSIZE", "FACEVALUE"],
            "data": [["BOND", "TQBR", "Акция", "common_share", 10, 5]],
        },
        "description": {
            "columns": ["name", "value"],
            "data": [
                ["SECID", "BOND"],
                ["NAME", "Облигация"],
                ["TYPE", "exchange_bond"],
                ["INITIALFACEVALUE", "1000"],
                ["FACEUNIT", "SUR"],
            ],
        },
        "boards": {
            "columns": ["secid", "boardid", "is_traded", "is_primary"],
            "data": [["BOND", "TQCB", 1, 1]],
        },
    }

    info = parse_security_info(payload, board="TQCB")

    assert info is not None
    assert info.board == "TQCB"
    assert info.type is AssetType.BOND
    assert info.face_value_kopecks == 100_000


def test_requires_board_details_detects_current_shape(load_fixture: Any) -> None:
    payload = load_fixture("moex", "security_gazp.json")

    assert requires_board_details(payload, "TQBR") is True
    assert requires_board_details(payload, "TQCB") is False
    assert requires_board_details(payload, None) is False
    assert requires_board_details(load_fixture("moex", "security_sber.json"), "TQBR") is False


def test_requires_board_details_mixed_shape_needs_missing_board() -> None:
    """A ``securities`` table without the requested board still needs details."""

    payload = {
        "securities": {
            "columns": ["SECID", "BOARDID"],
            "data": [["BOND", "TQBR"]],
        },
        "boards": {
            "columns": ["secid", "boardid"],
            "data": [["BOND", "TQBR"], ["BOND", "TQCB"]],
        },
    }

    assert requires_board_details(payload, "TQCB") is True
    assert requires_board_details(payload, "TQBR") is False


def test_merge_board_details_keeps_face_unit_from_description() -> None:
    """A board-level currency must not replace the card's face currency."""

    payload = {
        "description": {
            "columns": ["name", "value"],
            "data": [
                ["SECID", "BOND"],
                ["NAME", "Облигация"],
                ["TYPE", "exchange_bond"],
                ["INITIALFACEVALUE", "1000"],
                ["FACEUNIT", "SUR"],
            ],
        },
        "boards": {
            "columns": ["secid", "boardid", "is_traded", "is_primary"],
            "data": [["BOND", "TQCB", 1, 1]],
        },
    }
    board_payload = {
        "securities": {
            "columns": ["SECID", "BOARDID", "LOTSIZE", "FACEVALUE", "FACEUNIT"],
            "data": [["BOND", "TQCB", 1, 600, "CNY"]],
        }
    }

    info = parse_security_info(payload, board="TQCB", board_payload=board_payload)

    assert info is not None
    assert info.face_value_kopecks == 100_000
    assert info.raw["FACEUNIT"] == "SUR"
    assert info.raw["FACEVALUE"] == "1000"


def test_merge_board_details_filters_by_requested_board() -> None:
    """Only the row of the requested board may contribute board fields."""

    payload = {
        "description": {
            "columns": ["name", "value"],
            "data": [
                ["SECID", "BOND"],
                ["NAME", "Облигация"],
                ["TYPE", "exchange_bond"],
                ["INITIALFACEVALUE", "1000"],
                ["FACEUNIT", "SUR"],
            ],
        },
        "boards": {
            "columns": ["secid", "boardid", "is_traded", "is_primary"],
            "data": [["BOND", "TQCB", 1, 1]],
        },
    }
    board_payload = {
        "securities": {
            "columns": ["SECID", "BOARDID", "LOTSIZE", "FACEVALUE", "FACEUNIT"],
            "data": [
                ["BOND", "TQBR", 10, 1000, "SUR"],
                ["BOND", "TQCB", 5, 600, "SUR"],
            ],
        }
    }

    info = parse_security_info(payload, board="TQCB", board_payload=board_payload)

    assert info is not None
    assert info.lot_size == 5


def test_merge_board_details_does_not_restore_empty_face_value() -> None:
    """An empty card value must not hide a usable board-level value."""

    payload = {
        "description": {
            "columns": ["name", "value"],
            "data": [
                ["SECID", "BOND"],
                ["NAME", "Облигация"],
                ["TYPE", "exchange_bond"],
                ["FACEVALUE", ""],
                ["FACEUNIT", "SUR"],
            ],
        },
        "boards": {
            "columns": ["secid", "boardid", "is_traded", "is_primary"],
            "data": [["BOND", "TQCB", 1, 1]],
        },
    }
    board_payload = {
        "securities": {
            "columns": ["SECID", "BOARDID", "LOTSIZE", "FACEVALUE", "FACEUNIT"],
            "data": [["BOND", "TQCB", 1, 600, "SUR"]],
        }
    }

    info = parse_security_info(payload, board="TQCB", board_payload=board_payload)

    assert info is not None
    assert info.face_value_kopecks == 60_000


def test_security_info_rejects_malformed_face_value() -> None:
    payload = {
        "securities": {
            "columns": ["SECID", "BOARDID", "SECNAME", "LOTSIZE", "FACEVALUE", "FACEUNIT"],
            "data": [["BOND", "TQCB", "Облигация", 1, "abc", "SUR"]],
        }
    }

    with pytest.raises(MoexParseError):
        parse_security_info(payload, board="TQCB")


def test_security_info_rejects_malformed_lot_size(load_fixture: Any) -> None:
    payload = load_fixture("moex", "security_sber.json")
    lot_size_index = payload["securities"]["columns"].index("LOTSIZE")
    payload["securities"]["data"][1][lot_size_index] = "x"

    with pytest.raises(MoexParseError):
        parse_security_info(payload, board="TQBR")


def test_current_quote_picks_first_positive_field(load_fixture: Any) -> None:
    quote = parse_current_quote(
        load_fixture("moex", "marketdata_sber.json"),
        secid="SBER",
        price_type=PriceType.RUB,
        quote_date=date(2026, 10, 19),
    )

    assert quote is not None
    assert quote.price_micro == 310_500_000
    assert quote.price_type is PriceType.RUB


def test_current_quote_returns_none_without_prices() -> None:
    payload = {"marketdata": {"columns": ["SECID", "LAST"], "data": [["SBER", None]]}}

    quote = parse_current_quote(
        payload, secid="SBER", price_type=PriceType.RUB, quote_date=date(2026, 10, 19)
    )

    assert quote is None


def test_history_prefers_close_and_falls_back_to_legal(load_fixture: Any) -> None:
    points = parse_history(load_fixture("moex", "history_sber_page1.json"), PriceType.RUB)

    assert [(point.quote_date, point.price_micro) for point in points] == [
        (date(2026, 1, 10), 100_000_000),
        (date(2026, 1, 11), 101_000_000),
    ]


def test_bondization_parses_coupons_and_amortizations(load_fixture: Any) -> None:
    bondization = parse_bondization(load_fixture("moex", "bondization_ofz.json"))

    assert [coupon.amount_per_unit_micro for coupon in bondization.coupons] == [
        35_400_000,
        35_400_000,
        36_000_000,
    ]
    assert bondization.coupons[0].record_date == date(2026, 5, 25)
    assert bondization.amortizations[0].amortization_date == date(2030, 1, 1)
    assert bondization.amortizations[0].amount_per_unit_kopecks == 20_000


def test_bondization_parses_live_amortdate_column(load_fixture: Any) -> None:
    """Live ISS bondization names the amortization date ``amortdate``."""

    bondization = parse_bondization(load_fixture("moex", "bondization_ru000a10g5k5.json"))

    assert [
        (item.amortization_date, item.amount_per_unit_kopecks) for item in bondization.amortizations
    ] == [(date(2031, 8, 23), 100_000)]


def test_table_rows_handles_missing_table() -> None:
    assert table_rows({}, "history") == []


def test_get_field_is_case_insensitive() -> None:
    assert get_field({"SECID": "SBER"}, "secid") == "SBER"
    assert get_field({"secid": "SBER"}, "SECID") == "SBER"
    assert get_field({"secid": "SBER"}, "unknown") is None


def test_search_skips_rows_without_secid() -> None:
    payload = {
        "securities": {
            "columns": ["secid", "primary_boardid", "is_traded"],
            "data": [[None, "TQBR", 1]],
        }
    }

    assert parse_search_results(payload) == []


def test_security_info_returns_none_for_empty_payload() -> None:
    assert parse_security_info({}) is None
    assert parse_security_info({"securities": {"columns": [], "data": []}}) is None


def test_security_info_without_board_prefers_supported_board(load_fixture: Any) -> None:
    info = parse_security_info(load_fixture("moex", "security_sber.json"))

    assert info is not None
    assert info.board == "TQBR"


def test_security_info_detects_bond_from_type_field() -> None:
    payload = {
        "securities": {
            "columns": ["SECID", "BOARDID", "SECNAME", "TYPE", "LOTSIZE", "FACEVALUE"],
            "data": [["SU26238RMFS4", "TQCB", "ОФЗ 26238", "ofz_bond", 1, 1000.0]],
        }
    }

    info = parse_security_info(payload)

    assert info is not None
    assert info.type is AssetType.BOND
    assert info.face_value_kopecks == 100_000


def test_security_info_current_shape_reads_bond_face_value() -> None:
    payload = {
        "description": {
            "columns": ["name", "value"],
            "data": [
                ["SECID", "BOND"],
                ["NAME", "Облигация"],
                ["TYPE", "ofz_bond"],
                ["INITIALFACEVALUE", "1000"],
                ["FACEUNIT", "SUR"],
            ],
        },
        "boards": {
            "columns": ["secid", "boardid", "is_traded", "is_primary"],
            "data": [["BOND", "TQCB", 1, 1]],
        },
    }

    info = parse_security_info(payload, board="TQCB")

    assert info is not None
    assert info.type is AssetType.BOND
    assert info.face_value_kopecks == 100_000
    assert info.lot_size == 1


def test_current_quote_without_matching_secid_uses_first_row() -> None:
    payload = {
        "marketdata": {
            "columns": ["SECID", "LAST"],
            "data": [["OTHER", 42.0]],
        }
    }

    quote = parse_current_quote(
        payload, secid="SBER", price_type=PriceType.RUB, quote_date=date(2026, 10, 19)
    )

    assert quote is not None
    assert quote.price_micro == 42_000_000


def test_history_skips_invalid_rows() -> None:
    payload = {
        "history": {
            "columns": ["TRADEDATE", "CLOSE", "LEGALCLOSEPRICE"],
            "data": [
                ["not-a-date", 100.0, 99.0],
                ["2026-01-10", 0, None],
                [None, 100.0, 99.0],
            ],
        }
    }

    assert parse_history(payload, PriceType.RUB) == []


def test_bondization_skips_rows_without_date_or_amount() -> None:
    payload = {
        "coupons": {
            "columns": ["coupondate", "value_rub"],
            "data": [[None, "35.4"], ["2026-06-01", None]],
        },
        "amortizations": {
            "columns": ["amortizationdate", "value_rub"],
            "data": [[None, "200"], ["2030-01-01", None]],
        },
    }

    bondization = parse_bondization(payload)

    assert bondization.coupons == []
    assert bondization.amortizations == []
