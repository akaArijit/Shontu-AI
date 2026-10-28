"""
High-level write adapter for the nightly pipeline.

Keeps connection handling in one place so `fund_engine.services.pipeline` (and its
tests) can depend on a small, replaceable interface.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional, Sequence

from fund_engine.db.connection import get_cursor
from fund_engine.db import persistence

logger = logging.getLogger(__name__)


class DatabaseWriter:
    """Writes pipeline output to PostgreSQL (one transaction per call)."""

    def start_run(self, as_of_date: date) -> Any:
        with get_cursor() as cur:
            return persistence.start_pipeline_run(cur, as_of_date)

    def finish_run(
        self,
        run_id: Any,
        status: str,
        schemes_processed: int = 0,
        folios_processed: int = 0,
        alerts_generated: int = 0,
        scores_computed: int = 0,
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        with get_cursor() as cur:
            persistence.finish_pipeline_run(
                cur,
                run_id=run_id,
                status=status,
                schemes_processed=schemes_processed,
                folios_processed=folios_processed,
                alerts_generated=alerts_generated,
                scores_computed=scores_computed,
                error_message=error_message,
                metadata=metadata,
            )

    def upsert_benchmarks(self, rows: Sequence[dict]) -> int:
        with get_cursor() as cur:
            return persistence.upsert_benchmarks(cur, rows)

    def upsert_schemes(self, rows: Sequence[dict]) -> int:
        with get_cursor() as cur:
            return persistence.upsert_schemes(cur, rows)

    def update_scheme_benchmarks(self, rows: Sequence[dict]) -> int:
        with get_cursor() as cur:
            return persistence.update_scheme_benchmarks(cur, rows)

    def upsert_nav(self, rows: Sequence[dict]) -> int:
        with get_cursor() as cur:
            return persistence.upsert_nav_history(cur, rows)

    def upsert_benchmark_history(self, rows: Sequence[dict]) -> int:
        with get_cursor() as cur:
            return persistence.upsert_benchmark_history(cur, rows)

    def upsert_features(self, rows: Sequence[dict]) -> int:
        with get_cursor() as cur:
            return persistence.upsert_rolling_returns(cur, rows)

    def upsert_scores(self, rows: Sequence[dict]) -> int:
        with get_cursor() as cur:
            return persistence.upsert_fund_scores(cur, rows)

    def sync_alerts(self, alerts: Sequence[dict], as_of_date: date) -> dict:
        with get_cursor() as cur:
            return persistence.sync_alerts(cur, alerts, as_of_date)


class NullWriter:
    """Dry-run writer: records row counts without touching a database."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}

    def _record(self, name: str, rows: Sequence[dict]) -> int:
        self.calls[name] = self.calls.get(name, 0) + len(rows)
        return len(rows)

    def start_run(self, as_of_date: date) -> Any:
        return None

    def finish_run(self, run_id: Any, status: str, **kwargs: Any) -> None:
        self.calls["finish_run"] = 1

    def upsert_benchmarks(self, rows: Sequence[dict]) -> int:
        return self._record("benchmarks", rows)

    def upsert_schemes(self, rows: Sequence[dict]) -> int:
        return self._record("schemes", rows)

    def update_scheme_benchmarks(self, rows: Sequence[dict]) -> int:
        return self._record("scheme_benchmarks", rows)

    def upsert_nav(self, rows: Sequence[dict]) -> int:
        return self._record("nav", rows)

    def upsert_benchmark_history(self, rows: Sequence[dict]) -> int:
        return self._record("benchmark_history", rows)

    def upsert_features(self, rows: Sequence[dict]) -> int:
        return self._record("features", rows)

    def upsert_scores(self, rows: Sequence[dict]) -> int:
        return self._record("scores", rows)

    def sync_alerts(self, alerts: Sequence[dict], as_of_date: date) -> dict:
        self._record("alerts", alerts)
        return {"inserted": len(alerts), "updated": 0, "resolved": 0}
