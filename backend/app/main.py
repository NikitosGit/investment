"""FastAPI application factory and lifecycle."""

import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from starlette.routing import Match
from starlette.types import Scope

from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.db.session import SessionLocal, engine
from app.jobs.scheduler import shutdown_scheduler, start_scheduler
from app.providers.moex.client import MoexClient
from app.services import portfolio_service

logger = logging.getLogger(__name__)

DIST_DIR = (Path(__file__).resolve().parents[2] / "dist" / "browser").resolve()

# Angular appends an eight-character content hash before the extension. Only
# such files are safe to cache forever; favicon.ico and untouched public files
# keep their names across releases and must stay revalidated.
_HASHED_ASSET_RE = re.compile(r"-[A-Za-z0-9]{8}\.[^.]+$")


def _static_cache_control(path: Path) -> str:
    """Return a Cache-Control value for a file served from the SPA build."""

    if path.name == "index.html":
        return "no-cache"
    if _HASHED_ASSET_RE.search(path.name):
        return "public, max-age=31536000, immutable"
    return "public, max-age=3600"


def _is_reserved_path(full_path: str) -> bool:
    """Return True for paths that must never fall through to the SPA."""

    path = full_path.strip("/")
    if path == "api" or path.startswith("api/"):
        return True
    reserved = ("docs", "redoc", "openapi.json")
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in reserved)


class _SpaRoute(APIRoute):
    """Catch-all route that ignores paths owned by the API and docs.

    Returning ``Match.NONE`` lets Starlette keep its native behaviour for
    reserved prefixes: a known path with the wrong method still returns 405,
    and an unknown API route returns the usual JSON 404.
    """

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope["type"] == "http" and _is_reserved_path(scope.get("path", "")):
            return Match.NONE, {}
        return super().matches(scope)


def _register_spa(application: FastAPI, static_root: Path) -> None:
    """Serve the built Angular app and fall back to index.html for deep links."""

    index_file = static_root / "index.html"

    def spa_fallback(full_path: str) -> FileResponse:
        try:
            candidate = (static_root / full_path.strip("/")).resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            logger.debug("Rejected static path %r: %s", full_path, exc)
            raise HTTPException(status_code=404) from exc

        if candidate.is_file() and candidate.is_relative_to(static_root):
            return FileResponse(
                candidate,
                headers={"Cache-Control": _static_cache_control(candidate)},
            )
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})

    application.router.routes.append(
        _SpaRoute(
            "/{full_path:path}",
            endpoint=spa_fallback,
            methods=["GET", "HEAD"],
            include_in_schema=False,
        )
    )


def _prepare_directories(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)


def _ensure_portfolio() -> None:
    """Create the single portfolio when the schema is ready."""

    with SessionLocal() as session:
        try:
            portfolio_service.ensure_default_portfolio(session)
        except SQLAlchemyError:
            logger.warning(
                "База данных не готова: портфель не создан. "
                "Выполните 'uv run alembic upgrade head'.",
            )
            logger.debug("Portfolio bootstrap failed", exc_info=True)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Prepare runtime resources on startup and release them on shutdown."""

    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    _prepare_directories(settings)
    logger.info(
        "Starting investment tracker %s (env=%s, db=%s)",
        settings.app_version,
        settings.app_env,
        settings.database_url,
    )
    _ensure_portfolio()
    moex_client = MoexClient.from_settings(settings)
    application.state.moex = moex_client
    application.state.scheduler = start_scheduler(settings)
    try:
        yield
    finally:
        logger.info("Shutting down investment tracker")
        shutdown_scheduler(getattr(application.state, "scheduler", None))
        moex_client.close()
        engine.dispose()


def create_app(*, dist_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    ``dist_dir`` overrides the built frontend directory; it exists for tests
    and deployments that keep the build outside the repository root.
    """

    settings = get_settings()
    application = FastAPI(
        title="Учет инвестиций",
        description="Локальный backend для учета инвестиционного портфеля.",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )

    @application.middleware("http")
    async def _request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming[:128] or uuid4().hex
        request.state.request_id = request_id
        token = set_request_id(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "%s %s -> %s (%.1f ms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            reset_request_id(token)

    register_exception_handlers(application)
    application.include_router(api_router, prefix="/api")

    static_root = (dist_dir if dist_dir is not None else DIST_DIR).resolve()
    if (static_root / "index.html").is_file():
        _register_spa(application, static_root)
    else:
        logger.debug("SPA build not found at %s; static serving is disabled", static_root)

    return application


app = create_app()
