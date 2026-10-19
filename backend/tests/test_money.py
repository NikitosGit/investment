"""Tests for exact money helpers."""

from decimal import Decimal

import pytest

from app.core.money import (
    format_money,
    format_price,
    kopecks_to_rubles,
    micro_to_rubles,
    rubles_to_kopecks,
    rubles_to_micro,
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
