"""Logging setup for the API and batch processes."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(
    *,
    level: int | str = logging.INFO,
    log_file: Path | None = None,
) -> None:
    """Configure root logging to stdout, plus an optional file handler.

    File logging is best-effort: read-only container filesystems should not
    prevent the API or pipeline from starting.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError:  # pragma: no cover - environment dependent
            pass

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )
