"""
Minimal PostgreSQL access for the MFD API.

Uses DATABASE_URL (Railway injects it via ${{Postgres.DATABASE_URL}}).
Every helper is best-effort: callers handle connection failures so a
missing/unreachable database degrades the API instead of crashing it.

The psycopg2 import is lazy so the app (and its tests) still boot on hosts
where the driver is unavailable — health checks then report `degraded`.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator, Optional

CONNECT_TIMEOUT_SECONDS = 5


def database_url() -> Optional[str]:
    """Return the configured database URL (empty string -> None)."""
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None


@contextmanager
def get_cursor() -> Iterator[Any]:
    """Yield a dict cursor, committing on success and closing always."""
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"PostgreSQL driver unavailable: {exc}") from exc

    conn = psycopg2.connect(url, connect_timeout=CONNECT_TIMEOUT_SECONDS)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
