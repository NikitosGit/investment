"""Tests for exact money helpers."""

from decimal import Decimal

import pytest

from app.core.money import (
    bond_market_value_kopecks,
    format_money,
    format_price,
    format_ratio,
    kopecks_to_rubles,
    micro_to_kopecks,
    micro_to_rubles,
    percent_price_to_micro,
    price_micro_to_percent_micro,
    quantity_cost_kopecks,
    rubles_to_kopecks,
    rubles_to_micro,
    unit_price_from_total_micro,
)


@pytest.mark.parametrize(
    ("rubles", "expected"),
    [
        ("1234.56", 123_456),
        ("951.23", 95_123),
        ("0.005", 1),
        ("0.004", 0),
        (100, 10_000),
    ],
)
def test_rubles_to_kopecks_rounds_half_up(rubles: str | int, expected: int) -> None:
    assert rubles_to_kopecks(rubles) == expected


@pytest.mark.parametrize(
    ("rubles", "expected"),
    [
        ("110.50", 110_500_000),
        ("95.123", 95_123_000),
        ("0.0000005", 1),
        ("0.0000004", 0),
    ],
)
def test_rubles_to_micro_rounds_half_up(rubles: str, expected: int) -> None:
    assert rubles_to_micro(rubles) == expected


def test_back_conversions() -> None:
    assert kopecks_to_rubles(123_456) == Decimal("1234.56")
    assert micro_to_rubles(110_500_000) == Decimal("110.500000")


def test_formatting_matches_api_contract() -> None:
    assert format_money(123_456) == "1234.56"
    assert format_price(110_500_000) == "110.500000"
    assert format_price(95_123_000) == "95.123000"


def test_percent_price_conversion_round_trip() -> None:
    assert percent_price_to_micro(100_000, 95_123_000) == 951_230_000
    assert price_micro_to_percent_micro(951_230_000, 100_000) == 95_123_000
    assert percent_price_to_micro(1, 5_000) == 1  # 0.5 kopeck rounds half up
    assert percent_price_to_micro(0, 95_123_000) == 0
    assert price_micro_to_percent_micro(951_230_000, 0) is None


def test_quantity_cost_rounds_half_up() -> None:
    assert quantity_cost_kopecks(10, 100_000_000) == 100_000
    assert quantity_cost_kopecks(20, 110_000_000) == 220_000
    assert quantity_cost_kopecks(3, 33_333_333) == 10_000
    assert quantity_cost_kopecks(1, 5_000) == 1
    assert quantity_cost_kopecks(1, 4_999) == 0


def test_bond_market_value() -> None:
    assert bond_market_value_kopecks(15, 100_000, 98_500_000) == 1_477_500
    assert bond_market_value_kopecks(0, 100_000, 98_500_000) == 0


def test_format_ratio_uses_four_decimals() -> None:
    assert format_ratio(Decimal("0.1532")) == "0.1532"
    assert format_ratio(Decimal(1) / Decimal(3)) == "0.3333"
    assert format_ratio(Decimal(0)) == "0.0000"


@pytest.mark.parametrize(
    ("micro", "expected"),
    [
        (10_000_000, 1_000),
        (35_400_000, 3_540),
        (12_345_600, 1_235),
        (5_000, 1),
        (4_999, 0),
        (0, 0),
    ],
)
def test_micro_to_kopecks_rounds_half_up(micro: int, expected: int) -> None:
    assert micro_to_kopecks(micro) == expected


def test_unit_price_from_total() -> None:
    assert unit_price_from_total_micro(20_000, 20) == 10_000_000
    assert unit_price_from_total_micro(53_100, 15) == 35_400_000
    assert unit_price_from_total_micro(20_000, 15) == 13_333_333
    assert unit_price_from_total_micro(10_000, 3) == 33_333_333
    assert unit_price_from_total_micro(10_000, 0) is None
    assert unit_price_from_total_micro(10_000, -1) is None


def test_derived_unit_price_converts_back_to_the_same_kopecks() -> None:
    total = 20_000
    quantity = 7
    unit_micro = unit_price_from_total_micro(total, quantity)

    assert unit_micro is not None
    assert quantity_cost_kopecks(quantity, unit_micro) == total
