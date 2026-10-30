"""Backup API schema (plan §8.10)."""

from datetime import datetime

from app.schemas.common import ApiModel


class BackupResponse(ApiModel):
    """A created database backup.

    ``created_at`` is timezone-aware local time and is not normalized to UTC.
    """

    path: str
    size_bytes: int
    created_at: datetime
