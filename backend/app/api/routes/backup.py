"""Backup and export endpoints (plan §8.10).

Backup files are only written to the configured backup directory; they are
never served over HTTP. Exports are returned inline as JSON or as a ZIP with
CSV files.
"""

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.api.deps import DbSession
from app.core.time import local_now
from app.schemas.backup import BackupResponse
from app.services import backup_service

ExportFormat = Literal["json", "csv"]

router = APIRouter(tags=["backup"])


@router.post("/backup", response_model=BackupResponse, summary="Создать резервную копию")
def create_backup() -> BackupResponse:
    """Create a consistent copy of the SQLite database."""

    result = backup_service.create_backup()
    return BackupResponse(
        path=result.path.as_posix(),
        size_bytes=result.size_bytes,
        created_at=result.created_at,
    )


@router.get("/export", summary="Экспорт данных")
def export_data(
    session: DbSession,
    export_format: Annotated[ExportFormat, Query(alias="format")] = "json",
) -> Response:
    """Export the whole portfolio as JSON or as a ZIP of CSV files."""

    stamp = local_now().strftime("%Y%m%d-%H%M%S")
    if export_format == "csv":
        content = backup_service.export_csv_zip(session)
        media_type = "application/zip"
        filename = f"investments-export-{stamp}.zip"
    else:
        content = json.dumps(
            backup_service.export_json(session),
            ensure_ascii=False,
        ).encode("utf-8")
        media_type = "application/json"
        filename = f"investments-export-{stamp}.json"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
