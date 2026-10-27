"""
Market-data adapters for the nightly pipeline.

Wraps the low-level fetchers so orchestration can stay simple and so a single
failing scheme/source never aborts the run.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from ingestion.fetchers import (
    BenchmarkRecord,
    MfapiFetcher,
    NseIndicesFetcher,
    NavRecord,
)

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetches NAV (mfapi) and benchmark index data (NSE, when available)."""

    def __init__(self, timeout: int = 30, max_retries: int = 2):
        self.mfapi = MfapiFetcher(timeout=timeout, max_retries=max_retries)
        self.nse = NseIndicesFetcher(timeout=timeout, max_retries=max_retries)

    def fetch_nav(
        self, scheme_codes: Sequence[str], since: Optional[dict[str, object]] = None
    ) -> tuple[list[dict], list[str]]:
        """Fetch NAV history per scheme. Returns (rows, errors).

        ``since`` maps scheme_code -> latest stored NAV date so repeat runs only
        buffer new points before upserting.
        """
        rows: list[dict] = []
        errors: list[str] = []
        since = since or {}

        for scheme_code in scheme_codes:
            try:
                records: list[NavRecord] = self.mfapi.fetch_scheme_history(scheme_code)
                cutoff = since.get(scheme_code)
                if cutoff is not None:
                    records = [r for r in records if r.nav_date > cutoff]
                rows.extend(
                    {
                        "scheme_code": r.scheme_code,
                        "nav_date": r.nav_date,
                        "nav_value": r.nav_value,
                        "source": "mfapi",
                    }
                    for r in records
                )
            except Exception as exc:  # noqa: BLE001 - isolate per scheme
                logger.warning("NAV fetch failed for %s: %s", scheme_code, exc)
                errors.append(f"{scheme_code}: {exc}")

        return rows, errors

    def fetch_benchmarks(
        self, benchmark_codes: Sequence[str], from_date, to_date
    ) -> tuple[list[dict], list[str]]:
        """Fetch benchmark index history. NSE integration is optional."""
        rows: list[dict] = []
        errors: list[str] = []

        for benchmark_code in benchmark_codes:
            try:
                records: list[BenchmarkRecord] = self.nse.fetch_index_history(
                    benchmark_code, from_date, to_date
                )
                rows.extend(
                    {
                        "benchmark_code": r.benchmark_code,
                        "index_date": r.index_date,
                        "index_value": r.index_value,
                        "source": "nse",
                    }
                    for r in records
                )
            except NotImplementedError:
                logger.info(
                    "NSE benchmark history not configured; keeping existing data for %s",
                    benchmark_code,
                )
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Benchmark fetch failed for %s: %s", benchmark_code, exc)
                errors.append(f"{benchmark_code}: {exc}")

        return rows, errors
