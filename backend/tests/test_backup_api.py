"""Backup and export API tests (plan §8.10)."""

import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dashboard_helpers import build_dashboard_portfolio  # isort: skip

BACKUP_NAME = re.compile(r"investments-\d{8}-\d{6}(?:-\d+)?\.db")


def test_create_backup_returns_the_file(client: TestClient, db_session: Session) -> None:
    build_dashboard_portfolio(db_session)

    response = client.post("/api/backup")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"path", "size_bytes", "created_at"}
    assert "\\" not in body["path"]
    path = Path(body["path"])
    assert path.exists()
    assert BACKUP_NAME.fullmatch(path.name)
    assert body["size_bytes"] == path.stat().st_size
    assert body["size_bytes"] > 0
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


def test_export_json_default(client: TestClient, db_session: Session) -> None:
    build_dashboard_portfolio(db_session)

    response = client.get("/api/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert re.fullmatch(r'attachment; filename="investments-export-\d{8}-\d{6}\.json"', disposition)
    body = response.json()
    assert body["portfolio"]["id"] == 1
    assert len(body["assets"]) == 2
    assert len(body["operations"]) == 2


def test_export_json_of_an_empty_database(client: TestClient) -> None:
    body = client.get("/api/export", params={"format": "json"}).json()

    assert body["portfolio"]["id"] == 1
    assert body["assets"] == []
    assert body["operations"] == []
    assert body["income"] == []
    assert body["quotes"] == []
    assert body["amortizations"] == []
    assert body["snapshots"] == []
    assert body["settings"] == {}


def test_export_csv_returns_a_zip(client: TestClient, db_session: Session) -> None:
    build_dashboard_portfolio(db_session)

    response = client.get("/api/export", params={"format": "csv"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    disposition = response.headers["content-disposition"]
    assert re.fullmatch(r'attachment; filename="investments-export-\d{8}-\d{6}\.zip"', disposition)
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"positions.csv", "operations.csv", "income.csv"}
        rows = archive.read("positions.csv").decode("utf-8-sig").splitlines()
        assert len(rows) == 3


def test_export_invalid_format_is_422(client: TestClient) -> None:
    response = client.get("/api/export", params={"format": "xml"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["errors"][0]["field"] == "query.format"


def test_openapi_documents_backup_and_export(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/backup"]["post"]["summary"] == "Создать резервную копию"
    export = schema["paths"]["/api/export"]["get"]
    assert export["summary"] == "Экспорт данных"
    parameter = next(item for item in export["parameters"] if item["name"] == "format")
    assert parameter["schema"]["default"] == "json"
    assert set(parameter["schema"]["enum"]) == {"json", "csv"}


def test_backup_files_are_not_served_over_http(client: TestClient) -> None:
    response = client.get("/api/backup")

    assert response.status_code == 405
