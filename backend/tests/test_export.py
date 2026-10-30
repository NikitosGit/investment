"""Export tests: JSON shape and CSV archive contents (plan §8.10)."""

import csv
import io
import sqlite3
import zipfile
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import AssetType, IncomeKind, IncomeStatus
from app.db.session import engine
from app.services import backup_service, portfolio_service, settings_service, snapshot_service

from dashboard_helpers import (  # isort: skip
    add_amortization,
    add_income,
    add_operation,
    add_quote,
    days_ago,
    days_ahead,
    make_asset,
)

EXPORT_KEYS = {
    "exported_at",
    "app_version",
    "portfolio",
    "assets",
    "operations",
    "income",
    "quotes",
    "amortizations",
    "snapshots",
    "settings",
}


def _build_portfolio(session: Session) -> None:
    """Create a small portfolio with quotes, income, a schedule and settings."""

    stock = make_asset(session, secid="SBER")
    add_operation(
        session,
        stock,
        trade_date=days_ago(60),
        quantity=10,
        price_micro=100_000_000,
        note="=SUM(1,2)",
    )
    add_quote(session, stock, quote_date=days_ago(2), price_micro=100_000_000)
    add_quote(session, stock, quote_date=days_ago(1), price_micro=110_000_000)

    bond = make_asset(session, secid="SU26238RMFS4", asset_type=AssetType.BOND)
    add_operation(
        session,
        bond,
        trade_date=days_ago(50),
        quantity=15,
        price_micro=951_230_000,
        note="@cmd",
    )
    add_quote(session, bond, quote_date=days_ago(1), price_micro=98_500_000)
    add_amortization(
        session,
        bond,
        amortization_date=days_ago(20),
        amount_per_unit_kopecks=20_000,
    )

    add_income(
        session,
        stock,
        kind=IncomeKind.DIVIDEND,
        status=IncomeStatus.PAID,
        pay_date=days_ago(10),
        quantity=10,
        amount_total_kopecks=20_000,
    )
    add_income(
        session,
        bond,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.PAID,
        pay_date=days_ago(5),
        quantity=15,
        amount_total_kopecks=52_500,
    )
    add_income(
        session,
        bond,
        pay_date=days_ahead(10),
        per_unit_micro=35_000_000,
    )

    snapshot_service.upsert_snapshot(
        session,
        days_ago(1),
        market_value_kopecks=1_000_000,
        invested_kopecks=900_000,
        income_paid_kopecks=72_500,
    )
    settings_service.set_dashboard_period(session, "3M")
    session.commit()


def test_json_export_contract_and_counts(db_session: Session) -> None:
    _build_portfolio(db_session)

    export = backup_service.export_json(db_session)

    assert set(export) == EXPORT_KEYS
    exported_at = datetime.fromisoformat(export["exported_at"])
    assert exported_at.tzinfo is not None
    assert export["app_version"] == "0.1.0"

    assert export["portfolio"]["id"] == 1
    assert export["portfolio"]["name"] == "Мой портфель"
    assert export["portfolio"]["base_currency"] == "RUB"
    assert "created_at" in export["portfolio"]

    assert len(export["assets"]) == 2
    assert [asset["secid"] for asset in export["assets"]] == ["SBER", "SU26238RMFS4"]
    stock, bond = export["assets"]
    assert stock["current_face_value"] is None
    assert stock["amortizations"] == []
    assert bond["initial_face_value"] == "1000.00"
    assert bond["current_face_value"] == "800.00"
    assert bond["amortizations"] == [
        {
            "id": bond["amortizations"][0]["id"],
            "amortization_date": days_ago(20).isoformat(),
            "amount_per_unit": "200.00",
            "source": "MANUAL",
        }
    ]

    assert len(export["operations"]) == 2
    assert [operation["type"] for operation in export["operations"]] == ["BUY", "BUY"]
    assert export["operations"][0]["trade_date"] == days_ago(60).isoformat()
    assert export["operations"][1]["trade_date"] == days_ago(50).isoformat()
    assert export["operations"][0]["input_price"] == "100.000000"
    assert export["operations"][1]["price_rub"] == "951.230000"

    assert len(export["income"]) == 3
    assert [item["pay_date"] for item in export["income"]] == [
        days_ago(10).isoformat(),
        days_ago(5).isoformat(),
        days_ahead(10).isoformat(),
    ]
    assert export["income"][0]["amount_total"] == "200.00"
    assert export["income"][2]["amount_total"] == "525.00"
    assert export["income"][2]["quantity"] == 15

    assert len(export["quotes"]) == 3
    assert [(quote["asset_id"], quote["quote_date"]) for quote in export["quotes"]] == [
        (stock["id"], days_ago(2).isoformat()),
        (stock["id"], days_ago(1).isoformat()),
        (bond["id"], days_ago(1).isoformat()),
    ]
    assert export["quotes"][0]["price"] == "100.000000"

    assert len(export["amortizations"]) == 1
    assert export["amortizations"][0]["amortization_date"] == days_ago(20).isoformat()

    assert len(export["snapshots"]) == 1
    assert export["snapshots"][0]["date"] == days_ago(1).isoformat()
    assert export["snapshots"][0]["market_value"] == "10000.00"

    assert export["settings"] == {
        settings_service.DASHBOARD_PERIOD: "3M",
    }


def test_json_export_before_a_portfolio_exists(db_session: Session) -> None:
    # The schema exists, but no lifespan/startup portfolio has been created yet.
    export = backup_service.export_json(db_session)

    assert set(export) == EXPORT_KEYS
    assert export["portfolio"] is None
    assert export["assets"] == []
    assert export["operations"] == []
    assert export["income"] == []
    assert export["quotes"] == []
    assert export["amortizations"] == []
    assert export["snapshots"] == []
    assert export["settings"] == {}


def _read_csv(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    with archive.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        return list(csv.DictReader(text))


def test_csv_export_contains_exactly_the_three_files(db_session: Session) -> None:
    _build_portfolio(db_session)

    payload = backup_service.export_csv_zip(db_session)

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {"positions.csv", "operations.csv", "income.csv"}
        for name in archive.namelist():
            content = archive.read(name)
            assert content.startswith(b"\xef\xbb\xbf")
            assert b"\r\n" in content


def test_positions_csv_columns_and_computed_values(db_session: Session) -> None:
    _build_portfolio(db_session)

    with zipfile.ZipFile(io.BytesIO(backup_service.export_csv_zip(db_session))) as archive:
        rows = _read_csv(archive, "positions.csv")

    assert list(rows[0]) == list(backup_service.POSITION_COLUMNS)
    assert len(rows) == 2
    stock, bond = rows
    assert stock["secid"] == "SBER"
    assert stock["type"] == "STOCK"
    assert stock["quantity"] == "10"
    assert stock["avg_price"] == "100.000000"
    assert stock["current_price"] == "110.000000"
    assert stock["current_price_type"] == "RUB"
    assert stock["current_face_value"] == ""
    assert stock["market_value"] == "1100.00"
    assert stock["invested"] == "1000.00"
    assert stock["share"] == "0.0851"
    assert stock["price_date"] == days_ago(1).isoformat()
    assert stock["price_source"] == "MOEX"
    assert stock["is_stale"] == "true"

    assert bond["secid"] == "SU26238RMFS4"
    assert bond["quantity"] == "15"
    assert bond["current_price_type"] == "PERCENT"
    assert bond["current_face_value"] == "800.00"
    assert bond["market_value"] == "11820.00"
    assert bond["invested"] == "14268.45"
    assert bond["share"] == "0.9149"


def test_operations_csv_columns_values_and_formula_sanitization(db_session: Session) -> None:
    _build_portfolio(db_session)

    with zipfile.ZipFile(io.BytesIO(backup_service.export_csv_zip(db_session))) as archive:
        rows = _read_csv(archive, "operations.csv")

    assert list(rows[0]) == list(backup_service.OPERATION_COLUMNS)
    assert [row["secid"] for row in rows] == ["SBER", "SU26238RMFS4"]
    assert rows[0]["trade_date"] == days_ago(60).isoformat()
    assert rows[0]["input_price"] == "100.000000"
    assert rows[0]["input_price_type"] == "RUB"
    assert rows[0]["note"] == "'=SUM(1,2)"
    assert rows[1]["note"] == "'@cmd"
    assert rows[1]["input_price_type"] == "PERCENT"


def test_income_csv_columns_and_computed_values(db_session: Session) -> None:
    _build_portfolio(db_session)

    with zipfile.ZipFile(io.BytesIO(backup_service.export_csv_zip(db_session))) as archive:
        rows = _read_csv(archive, "income.csv")

    assert list(rows[0]) == list(backup_service.INCOME_COLUMNS)
    assert [row["kind"] for row in rows] == ["DIVIDEND", "COUPON", "COUPON"]
    assert [row["status"] for row in rows] == ["PAID", "PAID", "EXPECTED"]
    assert rows[0]["amount_total"] == "200.00"
    assert rows[2]["quantity"] == "15"
    assert rows[2]["amount_total"] == "525.00"
    assert rows[2]["is_overdue"] == "false"


def test_csv_export_of_an_empty_database_has_only_headers(db_session: Session) -> None:
    with zipfile.ZipFile(io.BytesIO(backup_service.export_csv_zip(db_session))) as archive:
        assert _read_csv(archive, "positions.csv") == []
        assert _read_csv(archive, "operations.csv") == []
        assert _read_csv(archive, "income.csv") == []
        header = archive.read("positions.csv").decode("utf-8-sig").strip("\r\n")
        assert header.split(",") == list(backup_service.POSITION_COLUMNS)


def test_cell_sanitizes_formula_prefixes_and_formats_scalars() -> None:
    assert backup_service._cell(None) == ""
    assert backup_service._cell(True) == "true"
    assert backup_service._cell(False) == "false"
    assert backup_service._cell(42) == "42"
    assert backup_service._cell(date(2026, 1, 2)) == "2026-01-02"
    assert backup_service._cell("normal") == "normal"
    for prefix in ("=", "+", "-", "@", "\t", "\r"):
        assert backup_service._cell(f"{prefix}cmd") == f"'{prefix}cmd"


def test_export_csv_rows_are_deterministic(db_session: Session) -> None:
    _build_portfolio(db_session)

    first: Any = backup_service.export_csv_zip(db_session)
    second: Any = backup_service.export_csv_zip(db_session)

    assert isinstance(first, bytes)
    with zipfile.ZipFile(io.BytesIO(first)) as left, zipfile.ZipFile(io.BytesIO(second)) as right:
        for name in ("positions.csv", "operations.csv", "income.csv"):
            assert left.read(name) == right.read(name)


def test_json_export_orders_operations_and_income_by_date_then_id(db_session: Session) -> None:
    stock = make_asset(db_session, secid="SBER")
    later = add_operation(
        db_session, stock, trade_date=days_ago(10), quantity=1, price_micro=100_000_000
    )
    earlier = add_operation(
        db_session, stock, trade_date=days_ago(30), quantity=1, price_micro=100_000_000
    )
    latest_same_day = add_operation(
        db_session, stock, trade_date=days_ago(10), quantity=1, price_micro=100_000_000
    )
    income_later = add_income(db_session, stock, pay_date=days_ago(5), amount_total_kopecks=100)
    income_earlier = add_income(db_session, stock, pay_date=days_ago(20), amount_total_kopecks=100)
    income_latest_same_day = add_income(
        db_session, stock, pay_date=days_ago(5), amount_total_kopecks=100
    )

    export = backup_service.export_json(db_session)

    assert [operation["id"] for operation in export["operations"]] == [
        earlier.id,
        later.id,
        latest_same_day.id,
    ]
    assert [item["id"] for item in export["income"]] == [
        income_earlier.id,
        income_later.id,
        income_latest_same_day.id,
    ]


def test_csv_exports_order_operations_and_income_by_date_then_id(db_session: Session) -> None:
    stock = make_asset(db_session, secid="SBER")
    later = add_operation(
        db_session, stock, trade_date=days_ago(10), quantity=1, price_micro=100_000_000
    )
    earlier = add_operation(
        db_session, stock, trade_date=days_ago(30), quantity=1, price_micro=100_000_000
    )
    latest_same_day = add_operation(
        db_session, stock, trade_date=days_ago(10), quantity=1, price_micro=100_000_000
    )
    income_later = add_income(db_session, stock, pay_date=days_ago(5), amount_total_kopecks=100)
    income_earlier = add_income(db_session, stock, pay_date=days_ago(20), amount_total_kopecks=100)
    income_latest_same_day = add_income(
        db_session, stock, pay_date=days_ago(5), amount_total_kopecks=100
    )

    with zipfile.ZipFile(io.BytesIO(backup_service.export_csv_zip(db_session))) as archive:
        operations = _read_csv(archive, "operations.csv")
        income = _read_csv(archive, "income.csv")

    assert [int(row["id"]) for row in operations] == [
        earlier.id,
        later.id,
        latest_same_day.id,
    ]
    assert [int(row["id"]) for row in income] == [
        income_earlier.id,
        income_later.id,
        income_latest_same_day.id,
    ]


def test_operations_csv_keeps_operations_with_a_missing_asset(db_session: Session) -> None:
    portfolio = portfolio_service.ensure_default_portfolio(db_session)
    connection = sqlite3.connect(engine.url.database)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            """
            INSERT INTO operation (
                portfolio_id, asset_id, type, trade_date, quantity, price_micro,
                input_price_micro, input_price_type, note, created_at, updated_at
            )
            VALUES (?, 424242, 'BUY', ?, 1, 100000000, 100000000, 'RUB',
                    'orphan', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
            """,
            (portfolio.id, days_ago(15).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()

    with zipfile.ZipFile(io.BytesIO(backup_service.export_csv_zip(db_session))) as archive:
        rows = _read_csv(archive, "operations.csv")

    assert len(rows) == 1
    assert rows[0]["asset_id"] == "424242"
    assert rows[0]["secid"] == ""
    assert rows[0]["note"] == "orphan"


def test_income_exports_keep_rows_with_a_missing_asset(db_session: Session) -> None:
    portfolio = portfolio_service.ensure_default_portfolio(db_session)
    connection = sqlite3.connect(engine.url.database)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.executemany(
            """
            INSERT INTO income (
                portfolio_id, asset_id, kind, status, amount_per_unit_micro,
                quantity, amount_total_kopecks, currency, record_date, pay_date,
                source, external_id, note, created_at, updated_at
            )
            VALUES (?, 424243, ?, ?, ?, ?, ?, 'RUB', NULL, ?, 'MANUAL', NULL, ?,
                    '2026-01-01 00:00:00', '2026-01-01 00:00:00')
            """,
            [
                (
                    portfolio.id,
                    "DIVIDEND",
                    "PAID",
                    100_000_000,
                    1,
                    100,
                    days_ago(10).isoformat(),
                    "orphan-paid",
                ),
                (
                    portfolio.id,
                    "COUPON",
                    "EXPECTED",
                    35_000_000,
                    None,
                    None,
                    days_ahead(10).isoformat(),
                    "orphan-expected",
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    export = backup_service.export_json(db_session)
    orphan_items = [item for item in export["income"] if item["asset_id"] == 424243]

    assert len(orphan_items) == 2
    assert {item["asset_secid"] for item in orphan_items} == {""}
    assert {item["note"] for item in orphan_items} == {"orphan-paid", "orphan-expected"}

    with zipfile.ZipFile(io.BytesIO(backup_service.export_csv_zip(db_session))) as archive:
        rows = [row for row in _read_csv(archive, "income.csv") if row["asset_id"] == "424243"]

    assert len(rows) == 2
    assert {row["secid"] for row in rows} == {""}
    assert {row["note"] for row in rows} == {"orphan-paid", "orphan-expected"}
