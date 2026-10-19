"""Unified application errors.

This module is framework-free on purpose: the provider layer raises
:class:`AppError` without depending on FastAPI. HTTP handlers live in
``app.api.error_handlers``.
"""

from enum import StrEnum
from typing import Any


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
