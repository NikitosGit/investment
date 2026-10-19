"""Structured logging with request correlation identifiers."""

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Return the correlation id of the current request, if any."""

    return _request_id.get()


def set_request_id(value: str | None) -> Token[str | None]:
    """Bind a correlation id to the current context and return a reset token."""

    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous correlation id."""

    _request_id.reset(token)


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable log format for local development."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", None)
        prefix = f"[{request_id}] " if request_id else ""
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        return f"{timestamp} {record.levelname:<8} {prefix}{record.getMessage()}"


def configure_logging(level: str = "INFO", *, json_logs: bool = False) -> None:
    """Configure the root logger once per process."""

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter() if json_logs else TextFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())
    root.addHandler(handler)

    for noisy_logger in ("httpx", "httpcore", "apscheduler"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
