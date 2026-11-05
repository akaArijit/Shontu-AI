"""Application settings.

The database URL can be changed to PostgreSQL later without touching the rest
of the application. SQLite is the default for the local build.
"""

from __future__ import annotations

import os

from mfd_dashboard.core.paths import DATABASE_PATH


APP_NAME = "MFD Portfolio Dashboard"
APP_VERSION = "0.2.0"
API_PREFIX = "/api/v1"

DATABASE_URL = os.getenv(
    "MFD_DATABASE_URL",
    f"sqlite:///{DATABASE_PATH.as_posix()}",
)

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000,"
    "http://127.0.0.1:3000,"
    "http://localhost:3001,"
    "http://127.0.0.1:3001"
)


def allowed_origins() -> list[str]:
    raw = os.getenv("MFD_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return [item.strip() for item in raw.split(",") if item.strip()]
