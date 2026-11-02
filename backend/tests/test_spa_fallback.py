"""Tests for production static serving and the SPA fallback."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

INDEX_HTML = "<!doctype html><html><body>spa shell</body></html>"


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    """Create a minimal Angular build outside the repository root."""

    root = tmp_path / "dist" / "browser"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (root / "assets" / "main-ABC12345.js").write_text("console.log('spa');", encoding="utf-8")
    (root / "assets" / "icon-ABCD1234.svg").write_text("<svg></svg>", encoding="utf-8")
    (root / "assets" / "logo.svg").write_text("<svg></svg>", encoding="utf-8")
    (root / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    return root


@pytest.fixture
def spa_client(dist_dir: Path) -> Generator[TestClient, None, None]:
    with TestClient(create_app(dist_dir=dist_dir)) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/", "/dashboard", "/assets/1"])
def test_spa_routes_return_index(spa_client: TestClient, path: str) -> None:
    response = spa_client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["cache-control"] == "no-cache"


def test_api_is_not_intercepted_by_spa(spa_client: TestClient) -> None:
    response = spa_client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["status"] == "ok"


def test_unknown_api_route_keeps_error_format(spa_client: TestClient) -> None:
    response = spa_client.get("/api/unknown")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_api_wrong_method_keeps_405(spa_client: TestClient) -> None:
    response = spa_client.get("/api/backup")

    assert response.status_code == 405


def test_docs_and_openapi_are_not_intercepted(spa_client: TestClient) -> None:
    docs = spa_client.get("/docs")
    openapi = spa_client.get("/openapi.json")

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert openapi.status_code == 200
    assert openapi.headers["content-type"].startswith("application/json")
    assert "/api/health" in openapi.json()["paths"]


@pytest.mark.parametrize(
    "path",
    ["/assets/main-ABC12345.js", "/assets/icon-ABCD1234.svg"],
)
def test_hashed_assets_are_served_with_immutable_cache(spa_client: TestClient, path: str) -> None:
    response = spa_client.get(path)

    assert response.status_code == 200
    assert response.text != INDEX_HTML
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize("path", ["/favicon.ico", "/assets/logo.svg"])
def test_unhashed_static_files_use_short_cache(spa_client: TestClient, path: str) -> None:
    response = spa_client.get(path)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_index_html_is_served_with_no_cache(spa_client: TestClient) -> None:
    response = spa_client.get("/index.html")

    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["cache-control"] == "no-cache"


def test_head_spa_route_returns_empty_body_with_no_cache(spa_client: TestClient) -> None:
    response = spa_client.head("/dashboard")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert response.content == b""


def test_null_byte_path_returns_json_404(spa_client: TestClient) -> None:
    response = spa_client.get("/%00")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "path",
    [
        "/../secret.txt",
        "/%2e%2e/secret.txt",
        "/%2e%2e%2fsecret.txt",
        "/assets/../../secret.txt",
    ],
)
def test_path_traversal_never_serves_files_outside_dist(
    spa_client: TestClient, dist_dir: Path, path: str
) -> None:
    secret = dist_dir.parent / "secret.txt"
    secret.write_text("top-secret", encoding="utf-8")

    response = spa_client.get(path)

    assert "top-secret" not in response.text
    # Traversal attempts are treated as unknown SPA routes, not as assets.
    assert response.text == INDEX_HTML


def test_missing_dist_dir_does_not_break_api(tmp_path: Path) -> None:
    with TestClient(create_app(dist_dir=tmp_path / "missing")) as test_client:
        health = test_client.get("/api/health")
        root = test_client.get("/")
        deep_link = test_client.get("/dashboard")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert root.status_code == 404
    assert deep_link.status_code == 404
