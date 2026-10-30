"""Backup and export service (plan §8.10/§9).

A backup is a consistent snapshot of the SQLite database taken through the
SQLite backup API, because a raw file copy of a WAL database may miss the
write-ahead log. Exports are read-only projections built from the same API
schemas as the HTTP endpoints, so their formatting never diverges.
"""

import csv
import io
import logging
import sqlite3
import threading
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.money import format_price
from app.core.time import local_now
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.operation import Operation
from app.db.models.quote import Quote
from app.db.models.snapshot import PortfolioSnapshot
from app.db.session import engine
from app.schemas.asset import AmortizationItem, AssetDetail
from app.schemas.income import IncomeItem
from app.schemas.operation import OperationResponse
from app.schemas.portfolio import PortfolioResponse
from app.schemas.position import PositionItem
from app.schemas.quote import QuoteItem
from app.schemas.snapshot import SnapshotItem
from app.services import (
    asset_service,
    income_service,
    portfolio_service,
    position_service,
    settings_service,
)

logger = logging.getLogger(__name__)

BACKUP_FILENAME_PREFIX = "investments"
BACKUP_FILENAME_FORMAT = "%Y%m%d-%H%M%S"

# Name selection and the copy must be one critical section: two concurrent
# backups of the same database must never resolve to the same file or delete
# each other's partial output.
_BACKUP_LOCK = threading.Lock()

POSITION_COLUMNS = (
    "asset_id",
    "secid",
    "name",
    "type",
    "quantity",
    "avg_price",
    "avg_price_percent",
    "current_price",
    "current_price_type",
    "current_face_value",
    "market_value",
    "invested",
    "share",
    "price_date",
    "price_source",
    "is_stale",
)

OPERATION_COLUMNS = (
    "id",
    "portfolio_id",
    "asset_id",
    "secid",
    "type",
    "trade_date",
    "quantity",
    "input_price",
    "input_price_type",
    "price_rub",
    "note",
)

INCOME_COLUMNS = (
    "id",
    "portfolio_id",
    "asset_id",
    "secid",
    "kind",
    "status",
    "amount_per_unit",
    "quantity",
    "amount_total",
    "currency",
    "record_date",
    "pay_date",
    "source",
    "note",
    "is_overdue",
)


@dataclass(frozen=True, slots=True)
class BackupResult:
    """A successfully created database copy."""

    path: Path
    size_bytes: int
    created_at: datetime


def create_backup() -> BackupResult:
    """Copy the configured SQLite database into the backup directory.

    The SQLite backup API is used instead of a file copy so the WAL contents
    are included. The source is opened read-only and validated first, so a
    missing, empty or unmigrated database can never be created or backed up.
    Copy failures are translated into a generic 500 response: filesystem paths
    and driver details must not leak through the API.
    """

    source_path = _database_path()
    try:
        return _write_backup(source_path)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Database backup failed")
        raise AppError(
            ErrorCode.INTERNAL_ERROR,
            "Не удалось создать резервную копию",
            status_code=500,
        ) from exc


def _write_backup(source_path: Path) -> BackupResult:
    """Reserve a destination name and copy the database into it."""

    backup_dir = get_settings().backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    created_at = local_now()
    destination: Path | None = None
    try:
        with _BACKUP_LOCK:
            destination = _next_available_path(backup_dir, created_at)
            _copy_sqlite_database(source_path, destination)
            size_bytes = destination.stat().st_size
    except Exception:
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise

    # The copy above succeeded, so the destination is guaranteed to be set.
    if destination is None:  # pragma: no cover - defensive invariant
        raise RuntimeError("Backup destination was not reserved")
    return BackupResult(path=destination, size_bytes=size_bytes, created_at=created_at)


def export_json(session: Session) -> dict[str, Any]:
    """Return a human-readable API projection of the portfolio.

    This is intentionally not a lossless, restorable backup: it only exposes
    fields the API schemas expose and formats money as strings. The canonical
    backup is the SQLite copy produced by :func:`create_backup`.
    """

    portfolio = portfolio_service.get_portfolio(session)
    return {
        "exported_at": local_now().isoformat(),
        "app_version": __version__,
        "portfolio": (
            PortfolioResponse.model_validate(portfolio).model_dump(mode="json")
            if portfolio is not None
            else None
        ),
        "assets": [
            AssetDetail.from_asset(
                card.asset,
                current_face_value_kopecks=card.current_face_value_kopecks,
                amortizations=card.amortizations,
            ).model_dump(mode="json")
            for card in (
                asset_service.build_asset_card(session, asset)
                for asset in asset_service.list_assets(session)
            )
        ],
        "operations": [
            OperationResponse.from_operation(operation).model_dump(mode="json")
            for operation in _operations(session)
        ],
        "income": [
            IncomeItem.from_view(view).model_dump(mode="json")
            for view in income_service.list_income_views(session)
        ],
        "quotes": [
            QuoteItem.from_quote(quote).model_dump(mode="json") for quote in _quotes(session)
        ],
        "amortizations": [
            AmortizationItem.from_model(amortization).model_dump(mode="json")
            for amortization in _amortizations(session)
        ],
        "snapshots": [
            SnapshotItem.from_snapshot(snapshot).model_dump(mode="json")
            for snapshot in _snapshots(session)
        ],
        "settings": settings_service.all_values(session),
    }


def export_csv_zip(session: Session) -> bytes:
    """Return a ZIP archive with positions, operations and income CSV files."""

    files = {
        "positions.csv": _positions_csv(session),
        "operations.csv": _operations_csv(session),
        "income.csv": _income_csv(session),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _database_path() -> Path:
    """Return an existing, non-empty file backing the configured database."""

    url = engine.url
    database = url.database
    if (
        url.get_backend_name() != "sqlite"
        or not database
        or database == ":memory:"
        or database.startswith("file::memory:")
    ):
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Резервное копирование поддерживается только для файловой базы SQLite",
            status_code=400,
        )

    path = Path(database)
    if not path.is_file() or path.stat().st_size == 0:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Файл базы данных не найден или пуст",
            status_code=400,
        )
    return path


def _next_available_path(backup_dir: Path, created_at: datetime) -> Path:
    """Return a free timestamped file name, adding a numeric suffix if needed."""

    stem = f"{BACKUP_FILENAME_PREFIX}-{created_at.strftime(BACKUP_FILENAME_FORMAT)}"
    candidate = backup_dir / f"{stem}.db"
    suffix = 1
    while candidate.exists():
        candidate = backup_dir / f"{stem}-{suffix}.db"
        suffix += 1
    return candidate


def _copy_sqlite_database(source_path: Path, destination: Path) -> None:
    """Copy through the SQLite backup API to capture WAL contents.

    The source is opened read-only so a typo in the path can never create an
    empty database. Its schema is verified before the destination is created.
    """

    source = _connect_read_only(source_path)
    try:
        _require_application_schema(source)
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def _connect_read_only(path: Path) -> sqlite3.Connection:
    """Open an existing SQLite file without write access or implicit creation."""

    try:
        return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Файл базы данных не найден или недоступен",
            status_code=400,
        ) from exc


def _require_application_schema(source: sqlite3.Connection) -> None:
    """Reject an empty or unmigrated database before copying it."""

    try:
        found = source.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'portfolio'"
        ).fetchone()
    except sqlite3.Error as exc:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "Не удалось прочитать схему базы данных",
            status_code=400,
        ) from exc
    if found is None:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "База данных не инициализирована: отсутствует схема приложения",
            status_code=400,
        )


def _operations(session: Session) -> list[Operation]:
    return list(session.scalars(select(Operation).order_by(Operation.trade_date, Operation.id)))


def _quotes(session: Session) -> list[Quote]:
    return list(session.scalars(select(Quote).order_by(Quote.asset_id, Quote.quote_date, Quote.id)))


def _amortizations(session: Session) -> list[BondAmortization]:
    return list(
        session.scalars(
            select(BondAmortization).order_by(
                BondAmortization.asset_id,
                BondAmortization.amortization_date,
                BondAmortization.id,
            )
        )
    )


def _snapshots(session: Session) -> list[PortfolioSnapshot]:
    return list(
        session.scalars(
            select(PortfolioSnapshot).order_by(
                PortfolioSnapshot.snapshot_date, PortfolioSnapshot.id
            )
        )
    )


def _positions_csv(session: Session) -> bytes:
    rows = []
    for view in position_service.get_positions(session):
        item = PositionItem.from_view(view)
        rows.append(
            (
                item.asset.id,
                item.asset.secid,
                item.asset.name,
                item.asset.type,
                item.quantity,
                item.avg_price,
                item.avg_price_percent,
                item.current_price,
                item.current_price_type,
                item.current_face_value,
                item.market_value,
                item.invested,
                item.share,
                item.price_date,
                item.price_source,
                item.is_stale,
            )
        )
    return _csv_bytes(POSITION_COLUMNS, rows)


def _operations_csv(session: Session) -> bytes:
    operations = _operations(session)
    asset_ids = {operation.asset_id for operation in operations}
    secids = (
        dict(session.execute(select(Asset.id, Asset.secid).where(Asset.id.in_(asset_ids))).all())
        if asset_ids
        else {}
    )
    return _csv_bytes(
        OPERATION_COLUMNS,
        [
            (
                operation.id,
                operation.portfolio_id,
                operation.asset_id,
                secids.get(operation.asset_id),
                operation.type,
                operation.trade_date,
                operation.quantity,
                format_price(operation.input_price_micro),
                operation.input_price_type,
                format_price(operation.price_micro),
                operation.note,
            )
            for operation in operations
        ],
    )


def _income_csv(session: Session) -> bytes:
    rows = []
    for view in income_service.list_income_views(session):
        income = view.income
        item = IncomeItem.from_view(view)
        rows.append(
            (
                item.id,
                income.portfolio_id,
                item.asset_id,
                item.asset_secid,
                item.kind,
                item.status,
                item.amount_per_unit,
                item.quantity,
                item.amount_total,
                item.currency,
                item.record_date,
                item.pay_date,
                item.source,
                item.note,
                item.is_overdue,
            )
        )
    return _csv_bytes(INCOME_COLUMNS, rows)


def _csv_bytes(columns: tuple[str, ...], rows: list[tuple[Any, ...]]) -> bytes:
    """Build a UTF-8-BOM CSV with CRLF endings and formula-safe cells."""

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return buffer.getvalue().encode("utf-8-sig")


def _cell(value: Any) -> str:
    """Format one CSV cell and neutralize spreadsheet formula prefixes."""

    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text
