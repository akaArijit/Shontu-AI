#!/usr/bin/env python3
"""Compatibility wrapper for ``python -m fund_engine.services.benchmarks``."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fund_engine.services.benchmarks import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
