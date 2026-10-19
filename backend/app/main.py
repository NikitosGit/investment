"""FastAPI application factory and lifecycle."""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.db.session import SessionLocal, engine
from app.services import portfolio_service

logger = logging.getLogger(__name__)


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
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
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
    try:
        yield
    finally:
        logger.info("Shutting down investment tracker")
        engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

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
        expose_headers=["X-Request-ID"],
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
    return application


app = create_app()
