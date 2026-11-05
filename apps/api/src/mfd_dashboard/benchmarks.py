"""Default benchmark categories and automatic keyword suggestions.

Every automatic mapping produced here is only a suggestion and is stored as
``needs_review``.  The local Benchmark Mapping screen updates SQLite review
state; this module does not read reviewed mappings or levels from YAML.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from mfd_dashboard.core.paths import CONFIG_DIR
from mfd_dashboard.ingest.values import normalize_header


@lru_cache(maxsize=2)
def load_benchmark_config(path: str | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else CONFIG_DIR / "benchmark_mapping.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=2)
def load_benchmark_master(path: str | None = None) -> dict[str, Any]:
    master_path = Path(path) if path else CONFIG_DIR / "benchmark_master.yaml"
    if not master_path.exists():
        return {}
    with master_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def benchmark_master_names() -> list[str]:
    """Return the full NSE benchmark catalogue shown in mapping dropdowns.

    These names are selectable without imported closing levels.  They do not
    create graph nuclei or comparisons on their own.
    """

    raw = load_benchmark_master()
    return [str(name) for name in raw.get("benchmarks", []) if str(name).strip()]


def benchmark_names() -> list[str]:
    """Return the benchmarks configured with automatic keyword rules."""

    raw = load_benchmark_config()
    return [str(item["name"]) for item in raw.get("benchmarks", [])]


def default_benchmark_name() -> str:
    raw = load_benchmark_config()
    return str(raw.get("default", "Other / Unmapped"))


def _normalize_for_match(value: str) -> str:
    """Normalize a string for keyword matching.
    - lower case
    - replace '&' with 'and'
    - replace hyphens with spaces
    - remove the word 'fund'
    - collapse multiple spaces
    - strip
    """
    v = value.lower()
    v = v.replace("&", " and ")
    v = v.replace("-", " ")
    # remove standalone word 'fund'
    v = re.sub(r"\bfund\b", "", v)
    # collapse whitespace
    v = re.sub(r"\s+", " ", v).strip()
    return v


def _matches(text: str, keyword: str) -> bool:
    """Case‑insensitive, word‑boundary match after normalisation."""
    norm_text = _normalize_for_match(text)
    norm_kw = _normalize_for_match(keyword)
    if not norm_kw:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(norm_kw)}(?![a-z0-9])"
    return re.search(pattern, norm_text) is not None


def _classify_keyword(keyword: str) -> str:
    """Classify a keyword by type for better suggestion context."""
    kw = keyword.lower().strip()
    # Fund house names (major AMCs)
    fund_houses = {
        "hdfc", "icici", "icici pru", "sbi", "kotak", "axis", "nippon", "nippon india",
        "aditya birla", "birla", "sun life", "tata", "dsp", "uti", "utic",
        "parag parikh", "ppfas", "mirae", "mirae asset", "canara", "robeco",
        "hdfc mf", "icici mf", "sbi mf", "kotak mf", "axis mf", "nippon mf"
    }
    if any(fh in kw for fh in fund_houses):
        return "fund_house"

    # Category keywords
    categories = {
        "large cap", "largecap", "mid cap", "midcap", "small cap", "smallcap",
        "flexi cap", "flexicap", "multi cap", "multicap", "large & mid", "large & midcap",
        "elss", "tax saver", "taxsaver", "80c", "section 80c",
        "hybrid", "balanced", "balanced advantage", "dynamic asset allocation",
        "asset allocation", "arbitrage", "liquid", "overnight", "money market",
        "short term", "short duration", "index fund", "etf", "exchange traded",
        "elss", "tax saver", "taxsaver", "elss fund", "tax saving",
        "value", "contra", "focused", "dividend", "dividend yield", "high dividend",
        "growth", "growth sectors", "high beta", "low volatility", "low vol",
        "alpha", "quality", "momentum", "low volatility", "equal weight",
        "psu", "public sector", "bank", "banking", "financial services",
        "healthcare", "pharma", "health", "pharmaceutical", "auto", "automobile",
        "fmcg", "consumer goods", "metal", "mining", "infrastructure", "infra",
        "energy", "power", "oil", "gas", "commodities", "consumption", "consumer",
        "realty", "real estate", "media", "entertainment", "private bank",
        "psu bank", "mnc", "multinational", "defence", "defense", "tourism",
        "travel", "manufacturing", "capital goods", "services sector",
        "esg", "sustainable", "responsible"
    }
    if any(cat in kw for cat in categories):
        return "category"

    # Abbreviations
    abbreviations = {"elss", "etf", "psu", "mnc", "esg", "baf", "dca", "sip"}
    if any(ab in kw for ab in abbreviations):
        return "abbreviation"

    return "other"


def match_benchmark_detail(
    scheme_name: str,
    provided: str | None = None,
) -> dict[str, str | None]:
    """Return the suggested benchmark and the rule that produced it.

    A benchmark supplied by the file is used only when it exactly matches one
    of the configured sample names.  Otherwise the scheme name is checked
    against the keyword rules.  The result is always stored with status
    ``needs_review`` by the importer, and the matched keyword is surfaced so
    the user can see exactly why a suggestion was made.
    """

    raw = load_benchmark_config()
    default = str(raw.get("default", "Other / Unmapped"))
    rules = raw.get("benchmarks", [])

    if provided:
        provided_key = normalize_header(provided)
        for rule in rules:
            if provided_key == normalize_header(rule.get("name", "")):
                return {
                    "benchmark_name": str(rule.get("name", default)),
                    "matched_keyword": None,
                    "matched_on": "provided benchmark",
                    "match_type": "provided",
                    "confidence": "high",
                    "reason": "Benchmark explicitly provided in import file",
                }

    search_text = normalize_header(scheme_name)
    for rule in rules:
        for keyword in rule.get("keywords", []):
            if _matches(search_text, normalize_header(keyword)):
                match_type = _classify_keyword(keyword)
                # Determine confidence based on match type
                confidence_map = {
                    "category": "high",
                    "fund_house": "medium",
                    "abbreviation": "low",
                    "other": "low",
                }
                reason_map = {
                    "category": f"Matched category keyword: '{keyword}'",
                    "fund_house": f"Matched fund house keyword: '{keyword}'",
                    "abbreviation": f"Matched abbreviation: '{keyword}'",
                    "other": f"Matched keyword: '{keyword}'",
                }
                return {
                    "benchmark_name": str(rule.get("name", default)),
                    "matched_keyword": str(keyword),
                    "matched_on": "scheme name",
                    "match_type": match_type,
                    "confidence": confidence_map.get(match_type, "low"),
                    "reason": reason_map.get(match_type, f"Matched keyword: '{keyword}'"),
                }
    return {
        "benchmark_name": default,
        "matched_keyword": None,
        "matched_on": None,
        "match_type": None,
        "confidence": None,
        "reason": "No matching keyword rules found",
    }


def match_benchmark(scheme_name: str, provided: str | None = None) -> str:
    """Return a suggested benchmark name for a scheme."""

    return str(
        match_benchmark_detail(scheme_name, provided=provided)["benchmark_name"]
    )
