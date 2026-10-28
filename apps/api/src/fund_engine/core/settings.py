"""Environment-backed settings shared by the API and batch pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from fund_engine.core.paths import CONFIG_DIR

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def get_cors_settings() -> tuple[list[str], str | None]:
    """Return exact allowed origins and an optional preview-origin regex."""
    origins = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS)
        ).split(",")
        if origin.strip()
    ]
    regex = os.getenv("ALLOWED_ORIGIN_REGEX", "").strip() or None
    return origins, regex


def config_path(env_var: str, default_name: str) -> Path:
    """Resolve a config file from ``env_var``, falling back to ``config/``."""
    configured = os.getenv(env_var)
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return path
    return CONFIG_DIR / default_name


def database_url() -> str | None:
    """Return ``DATABASE_URL`` if configured, otherwise ``None``."""
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None
