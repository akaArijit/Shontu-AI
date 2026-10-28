"""
Read helpers used by the nightly pipeline.

Kept separate from `db.persistence` so orchestration can be tested with fake
readers/writers and no live database.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from api.db import get_cursor

DEFAULT_LOOKBACK_DAYS = 365 * 6


class DatabaseReader:
    """Reads pipeline inputs from PostgreSQL."""

    def __init__(self, lookback_days: int = DEFAULT_LOOKBACK_DAYS):
        self.lookback_days = lookback_days

    def active_schemes(self) -> list[dict]:
        with get_cursor() as cur:
            cur.execute("""
                SELECT scheme_code, scheme_name, amc, category, sub_category,
                       benchmark_index, fund_manager, expense_ratio, aum, inception_date
                FROM scheme_master
                WHERE is_active = TRUE
                ORDER BY scheme_code
                """)
            return [dict(r) for r in cur.fetchall()]

    def nav_history(self, as_of_date: Optional[date] = None) -> list[dict]:
        as_of = as_of_date or date.today()
        cutoff = as_of - timedelta(days=self.lookback_days)
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT scheme_code, nav_date, nav_value
                FROM nav_history
                WHERE nav_date >= %(cutoff)s AND nav_date <= %(as_of)s
                ORDER BY scheme_code, nav_date
                """,
                {"cutoff": cutoff, "as_of": as_of},
            )
            return [dict(r) for r in cur.fetchall()]

    def benchmark_history(self, as_of_date: Optional[date] = None) -> list[dict]:
        as_of = as_of_date or date.today()
        cutoff = as_of - timedelta(days=self.lookback_days)
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT benchmark_code, index_date, index_value
                FROM benchmark_history
                WHERE index_date >= %(cutoff)s AND index_date <= %(as_of)s
                ORDER BY benchmark_code, index_date
                """,
                {"cutoff": cutoff, "as_of": as_of},
            )
            return [dict(r) for r in cur.fetchall()]

    def latest_nav_dates(self) -> dict[str, date]:
        """Latest stored NAV date per scheme (for incremental ingestion)."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT scheme_code, MAX(nav_date) AS latest
                FROM nav_history
                GROUP BY scheme_code
                """)
            return {r["scheme_code"]: r["latest"] for r in cur.fetchall()}

    def latest_benchmark_dates(self) -> dict[str, date]:
        """Latest stored index date per benchmark (for incremental ingestion)."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT benchmark_code, MAX(index_date) AS latest
                FROM benchmark_history
                GROUP BY benchmark_code
                """)
            return {r["benchmark_code"]: r["latest"] for r in cur.fetchall()}

    def benchmark_codes(self) -> list[str]:
        with get_cursor() as cur:
            cur.execute("""
                SELECT DISTINCT benchmark_index
                FROM scheme_master
                WHERE is_active = TRUE AND benchmark_index IS NOT NULL
                ORDER BY benchmark_index
                """)
            return [r["benchmark_index"] for r in cur.fetchall()]

    def folio_count(self) -> int:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM client_folios")
            row = cur.fetchone()
            return int(row["n"]) if row else 0
