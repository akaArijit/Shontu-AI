"""Filesystem locations for the Fund Engine backend.

The application root is the directory that contains ``src/``, ``config/`` and
``migrations/``. In the monorepo that is ``apps/api``; in the Docker image it
is ``/app``. Override the defaults with environment variables when deploying
the package somewhere else.
"""

from __future__ import annotations

import os
from pathlib import Path


def _as_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _project_root() -> Path:
    override = os.getenv("FUND_ENGINE_ROOT")
    if override:
        return _as_path(override)
    # .../apps/api/src/fund_engine/core/paths.py -> .../apps/api
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _project_root()
SRC_DIR = PROJECT_ROOT / "src"
CONFIG_DIR = _as_path(os.getenv("FUND_ENGINE_CONFIG_DIR", PROJECT_ROOT / "config"))
MIGRATIONS_DIR = _as_path(
    os.getenv("FUND_ENGINE_MIGRATIONS_DIR", PROJECT_ROOT / "migrations")
)
LOG_DIR = _as_path(os.getenv("FUND_ENGINE_LOG_DIR", PROJECT_ROOT / "logs"))
