"""Application paths.

All private data lives in the git-ignored ``data/local`` folder.
The paths can be overridden for tests or future deployments.
"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(
    os.getenv("MFD_PROJECT_ROOT", Path(__file__).resolve().parents[5])
).resolve()

CONFIG_DIR = Path(os.getenv("MFD_CONFIG_DIR", PROJECT_ROOT / "config")).resolve()
DATA_DIR = Path(os.getenv("MFD_DATA_DIR", PROJECT_ROOT / "data" / "local")).resolve()
SAMPLES_DIR = Path(
    os.getenv("MFD_SAMPLES_DIR", PROJECT_ROOT / "samples")
).resolve()

UPLOADS_DIR = DATA_DIR / "uploads"
PREVIEWS_DIR = DATA_DIR / "previews"
DATABASE_PATH = DATA_DIR / "mfd.sqlite3"


def ensure_directories() -> None:
    """Create the local data folders if they do not exist yet."""

    for path in (DATA_DIR, UPLOADS_DIR, PREVIEWS_DIR):
        path.mkdir(parents=True, exist_ok=True)
