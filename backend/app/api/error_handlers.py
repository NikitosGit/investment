"""FastAPI exception handlers translating domain errors to HTTP responses."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode, error_payload

logger = logging.getLogger(__name__)

_HTTP_MESSAGES = {
    400: "Некорректный запрос",
    404: "Объект не найден",
    405: "Метод не поддерживается",
    409: "Конфликт данных",
    415: "Неподдерживаемый тип данных",
}


def _http_message(status_code: int) -> str:
    return _HTTP_MESSAGES.get(status_code, "Ошибка запроса")


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
