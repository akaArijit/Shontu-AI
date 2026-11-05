"""Load the InvestWell column mapping configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from mfd_dashboard.core.paths import CONFIG_DIR


@lru_cache(maxsize=2)
def load_column_config(path: str | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else CONFIG_DIR / "investwell_columns.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def date_formats() -> list[str]:
    return list(load_column_config().get("date_formats", []))


def file_config(kind: str) -> dict[str, Any]:
    files = load_column_config().get("files", {})
    if kind not in files:
        raise ValueError(f"No column configuration for {kind}.")
    return files[kind]


def column_aliases(kind: str) -> dict[str, list[str]]:
    """Return aliases in configuration order.

    Order matters: a file can contain both ``SCHEME NAME`` and ``FUND NAME`` or
    both ``FOLIO NO`` and ``ACCOUNT NO``.  The first configured alias is the
    intended canonical column.
    """

    fields = file_config(kind).get("fields", {})
    aliases: dict[str, list[str]] = {}
    for canonical, values in fields.items():
        aliases[canonical] = [str(value) for value in values]
    return aliases
