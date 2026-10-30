"""Create a database backup from the command line.

Usage::

    python -m app.scripts.backup

The command mirrors ``POST /api/backup``: it prints the created path and size
and exits with a non-zero status when the copy fails.
"""

import sys

from app.core.errors import AppError
from app.services import backup_service


def main() -> int:
    """Create a backup and report the result; return a process exit code."""

    try:
        result = backup_service.create_backup()
    except AppError as exc:
        print(f"Не удалось создать резервную копию: {exc.message}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Не удалось создать резервную копию: {exc}", file=sys.stderr)
        return 1

    print(f"Резервная копия: {result.path} ({result.size_bytes} байт)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
