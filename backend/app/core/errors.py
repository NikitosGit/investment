"""Unified application errors and FastAPI exception handlers."""

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    """Stable machine-readable error codes exposed by the API."""

    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND"
    ASSET_ALREADY_EXISTS = "ASSET_ALREADY_EXISTS"
    ASSET_IN_USE = "ASSET_IN_USE"
    INSUFFICIENT_QUANTITY = "INSUFFICIENT_QUANTITY"
    INCOME_ALREADY_PAID = "INCOME_ALREADY_PAID"
    REFRESH_IN_PROGRESS = "REFRESH_IN_PROGRESS"
    MOEX_UNAVAILABLE = "MOEX_UNAVAILABLE"
    MOEX_NOT_FOUND = "MOEX_NOT_FOUND"
    MOEX_PARSE_ERROR = "MOEX_PARSE_ERROR"


class AppError(Exception):
    """A domain error that maps to a stable HTTP response."""

    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_payload(
    code: ErrorCode | str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical error response body."""

    return {"error": {"code": str(code), "message": message, "details": details or {}}}


def _validation_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details = []
    for error in errors:
        location = [str(part) for part in error.get("loc", ())]
        details.append(
            {
                "field": ".".join(location),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
        )
    return details


_HTTP_MESSAGES = {
    400: "Некорректный запрос",
    404: "Объект не найден",
    405: "Метод не поддерживается",
    409: "Конфликт данных",
    415: "Неподдерживаемый тип данных",
}


def _http_message(status_code: int) -> str:
    return _HTTP_MESSAGES.get(status_code, "Ошибка запроса")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach API error handlers to the application."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                ErrorCode.VALIDATION_ERROR,
                "Ошибка валидации данных",
                {"errors": _validation_details(exc.errors())},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.BAD_REQUEST
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, _http_message(exc.status_code)),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        headers = {"X-Request-ID": request_id} if request_id else None
        return JSONResponse(
            status_code=500,
            content=error_payload(ErrorCode.INTERNAL_ERROR, "Внутренняя ошибка сервера"),
            headers=headers,
        )
