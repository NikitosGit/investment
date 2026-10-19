"""MOEX provider errors mapped to the unified API error format."""

from typing import Any

from app.core.errors import AppError, ErrorCode


class MoexError(AppError):
    """Base class for MOEX provider failures."""


class MoexUnavailable(MoexError):
    """MOEX is unreachable, timing out or returning a server error."""

    def __init__(
        self, message: str = "Сервис MOEX недоступен", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(ErrorCode.MOEX_UNAVAILABLE, message, status_code=502, details=details)


class MoexNotFound(MoexError):
    """MOEX returned no data for the requested security."""

    def __init__(self, message: str = "Бумага не найдена в MOEX") -> None:
        super().__init__(ErrorCode.MOEX_NOT_FOUND, message, status_code=404)


class MoexParseError(MoexError):
    """MOEX returned an unexpected payload."""

    def __init__(
        self,
        message: str = "Не удалось разобрать ответ MOEX",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(ErrorCode.MOEX_PARSE_ERROR, message, status_code=502, details=details)
