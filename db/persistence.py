"""
PostgreSQL writers for the nightly pipeline.

Every function takes an open ``RealDictCursor`` so a whole nightly run can be
committed atomically by the caller. Rows are plain dicts; JSONB values are
serialised with ``json.dumps`` so no psycopg2 adapters are required.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Iterable, Sequence

CHUNK_SIZE = 500

# ------------------------------------------------------------
# Reference data
# ------------------------------------------------------------

UPSERT_BENCHMARKS_SQL = """
INSERT INTO benchmark_master (benchmark_code, benchmark_name, category)
VALUES (%(benchmark_code)s, %(benchmark_name)s, %(category)s)
ON CONFLICT (benchmark_code) DO UPDATE SET
    benchmark_name = EXCLUDED.benchmark_name,
    category = COALESCE(EXCLUDED.category, benchmark_master.category)
"""

UPSERT_SCHEMES_SQL = """
INSERT INTO scheme_master (
    scheme_code, scheme_name, amc, category, sub_category,
    benchmark_index, fund_manager, expense_ratio, aum, inception_date, is_active
) VALUES (
    %(scheme_code)s, %(scheme_name)s, %(amc)s, %(category)s, %(sub_category)s,
    %(benchmark_index)s, %(fund_manager)s, %(expense_ratio)s, %(aum)s,
    %(inception_date)s, %(is_active)s
)
ON CONFLICT (scheme_code) DO UPDATE SET
    scheme_name = EXCLUDED.scheme_name,
    amc = EXCLUDED.amc,
    category = EXCLUDED.category,
    sub_category = COALESCE(EXCLUDED.sub_category, scheme_master.sub_category),
    benchmark_index = COALESCE(EXCLUDED.benchmark_index, scheme_master.benchmark_index),
    fund_manager = COALESCE(EXCLUDED.fund_manager, scheme_master.fund_manager),
    expense_ratio = COALESCE(EXCLUDED.expense_ratio, scheme_master.expense_ratio),
    aum = COALESCE(EXCLUDED.aum, scheme_master.aum),
    inception_date = COALESCE(EXCLUDED.inception_date, scheme_master.inception_date),
    is_active = EXCLUDED.is_active,
    last_updated = NOW()
"""

UPDATE_SCHEME_BENCHMARK_SQL = """
UPDATE scheme_master
SET benchmark_index = %(benchmark_index)s, last_updated = NOW()
WHERE scheme_code = %(scheme_code)s
"""

# ------------------------------------------------------------
# Market data
# ------------------------------------------------------------

UPSERT_NAV_SQL = """
INSERT INTO nav_history (scheme_code, nav_date, nav_value, source)
VALUES (%(scheme_code)s, %(nav_date)s, %(nav_value)s, %(source)s)
ON CONFLICT (scheme_code, nav_date) DO UPDATE SET
    nav_value = EXCLUDED.nav_value,
    source = EXCLUDED.source,
    fetched_at = NOW()
"""

UPSERT_BENCHMARK_HISTORY_SQL = """
INSERT INTO benchmark_history (benchmark_code, index_date, index_value, source)
VALUES (%(benchmark_code)s, %(index_date)s, %(index_value)s, %(source)s)
ON CONFLICT (benchmark_code, index_date) DO UPDATE SET
    index_value = EXCLUDED.index_value,
    source = EXCLUDED.source,
    fetched_at = NOW()
"""

# ------------------------------------------------------------
# Computed data
# ------------------------------------------------------------

ROLLING_RETURN_COLUMNS = [
    "return_1m",
    "return_3m",
    "return_6m",
    "return_1y",
    "return_3y",
    "return_5y",
    "alpha_1m",
    "alpha_3m",
    "alpha_6m",
    "alpha_1y",
    "alpha_3y",
    "alpha_5y",
    "max_drawdown_1y",
    "max_drawdown_3y",
    "volatility_1m",
    "volatility_3m",
    "volatility_1y",
    "volatility_3y",
    "category_percentile_1m",
    "category_percentile_3m",
    "category_percentile_1y",
    "category_percentile_3y",
    "category_rank_1m",
    "category_rank_3m",
    "category_rank_1y",
    "category_rank_3y",
    "consecutive_underperf_months",
    "consecutive_underperf_quarters",
    "correlation_to_benchmark_1y",
    "correlation_to_benchmark_3y",
    "scoring_config_version",
]

UPSERT_ROLLING_RETURNS_SQL = f"""
INSERT INTO fund_rolling_returns (scheme_code, as_of_date, {", ".join(ROLLING_RETURN_COLUMNS)})
VALUES (%(scheme_code)s, %(as_of_date)s, {", ".join("%(" + c + ")s" for c in ROLLING_RETURN_COLUMNS)})
ON CONFLICT (scheme_code, as_of_date) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in ROLLING_RETURN_COLUMNS)},
    computed_at = NOW()
"""

UPSERT_FUND_SCORES_SQL = """
INSERT INTO fund_scores (
    scheme_code, as_of_date, fund_health_score, category_rank,
    category_percentile, score_breakdown, penalty, scoring_config_version
) VALUES (
    %(scheme_code)s, %(as_of_date)s, %(fund_health_score)s, %(category_rank)s,
    %(category_percentile)s, %(score_breakdown)s, %(penalty)s, %(scoring_config_version)s
)
ON CONFLICT (scheme_code, as_of_date) DO UPDATE SET
    fund_health_score = EXCLUDED.fund_health_score,
    category_rank = EXCLUDED.category_rank,
    category_percentile = EXCLUDED.category_percentile,
    score_breakdown = EXCLUDED.score_breakdown,
    penalty = EXCLUDED.penalty,
    scoring_config_version = EXCLUDED.scoring_config_version,
    computed_at = NOW()
"""

INSERT_ALERT_SQL = """
INSERT INTO fund_alerts (scheme_code, alert_type, severity, triggered_on, details)
VALUES (%(scheme_code)s, %(alert_type)s, %(severity)s, %(triggered_on)s, %(details)s)
"""

UPDATE_OPEN_ALERT_SQL = """
UPDATE fund_alerts
SET severity = %(severity)s,
    triggered_on = LEAST(triggered_on, %(triggered_on)s),
    details = %(details)s::jsonb,
    updated_at = NOW()
WHERE scheme_code = %(scheme_code)s
  AND alert_type = %(alert_type)s
  AND resolved_on IS NULL
"""

# ------------------------------------------------------------
# Pipeline run log
# ------------------------------------------------------------

INSERT_PIPELINE_RUN_SQL = """
INSERT INTO pipeline_run_log (status, as_of_date, started_at)
VALUES ('running', %(as_of_date)s, %(started_at)s)
RETURNING run_id
"""

FINISH_PIPELINE_RUN_SQL = """
UPDATE pipeline_run_log
SET completed_at = NOW(),
    status = %(status)s,
    schemes_processed = %(schemes_processed)s,
    folios_processed = %(folios_processed)s,
    alerts_generated = %(alerts_generated)s,
    scores_computed = %(scores_computed)s,
    error_message = %(error_message)s,
    metadata = %(metadata)s
WHERE run_id = %(run_id)s
"""


def _chunks(rows: Sequence[dict], size: int = CHUNK_SIZE) -> Iterable[Sequence[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _executemany(cur: Any, sql: str, rows: Sequence[dict]) -> int:
    total = 0
    for chunk in _chunks(rows):
        cur.executemany(sql, list(chunk))
        total += len(chunk)
    return total


def upsert_benchmarks(cur: Any, benchmarks: Sequence[dict]) -> int:
    """Insert/update benchmark master rows."""
    if not benchmarks:
        return 0
    rows = [
        {
            "benchmark_code": b["benchmark_code"],
            "benchmark_name": b.get("benchmark_name") or b["benchmark_code"],
            "category": b.get("category"),
        }
        for b in benchmarks
    ]
    return _executemany(cur, UPSERT_BENCHMARKS_SQL, rows)


def upsert_schemes(cur: Any, schemes: Sequence[dict]) -> int:
    """Insert/update scheme master rows (idempotent)."""
    if not schemes:
        return 0
    rows = [
        {
            "scheme_code": s["scheme_code"],
            "scheme_name": s.get("scheme_name") or s["scheme_code"],
            "amc": s.get("amc") or "Unknown",
            "category": s.get("category") or "Unclassified",
            "sub_category": s.get("sub_category"),
            "benchmark_index": s.get("benchmark_index"),
            "fund_manager": s.get("fund_manager"),
            "expense_ratio": s.get("expense_ratio"),
            "aum": s.get("aum"),
            "inception_date": s.get("inception_date"),
            "is_active": s.get("is_active", True),
        }
        for s in schemes
    ]
    return _executemany(cur, UPSERT_SCHEMES_SQL, rows)


def update_scheme_benchmarks(cur: Any, mappings: Sequence[dict]) -> int:
    """Point schemes at their resolved benchmark index."""
    if not mappings:
        return 0
    cur.executemany(UPDATE_SCHEME_BENCHMARK_SQL, list(mappings))
    return len(mappings)


def upsert_nav_history(cur: Any, records: Sequence[dict]) -> int:
    """Upsert NAV points (dicts with scheme_code/nav_date/nav_value/source)."""
    if not records:
        return 0
    rows = [
        {
            "scheme_code": r["scheme_code"],
            "nav_date": r["nav_date"],
            "nav_value": float(r["nav_value"]),
            "source": r.get("source") or "mfapi",
        }
        for r in records
    ]
    return _executemany(cur, UPSERT_NAV_SQL, rows)


def upsert_benchmark_history(cur: Any, records: Sequence[dict]) -> int:
    """Upsert benchmark index points."""
    if not records:
        return 0
    rows = [
        {
            "benchmark_code": r["benchmark_code"],
            "index_date": r["index_date"],
            "index_value": float(r["index_value"]),
            "source": r.get("source") or "nse",
        }
        for r in records
    ]
    return _executemany(cur, UPSERT_BENCHMARK_HISTORY_SQL, rows)


def upsert_rolling_returns(cur: Any, features: Sequence[dict]) -> int:
    """Upsert computed feature rows for an as-of date."""
    if not features:
        return 0
    rows = []
    for f in features:
        row = {
            "scheme_code": f["scheme_code"],
            "as_of_date": f["as_of_date"],
        }
        for column in ROLLING_RETURN_COLUMNS:
            row[column] = f.get(column)
        rows.append(row)
    return _executemany(cur, UPSERT_ROLLING_RETURNS_SQL, rows)


def upsert_fund_scores(cur: Any, scores: Sequence[dict]) -> int:
    """Upsert 0-100 health scores with JSON breakdown."""
    if not scores:
        return 0
    rows = [
        {
            "scheme_code": s["scheme_code"],
            "as_of_date": s["as_of_date"],
            "fund_health_score": int(s["fund_health_score"]),
            "category_rank": s.get("category_rank"),
            "category_percentile": s.get("category_percentile"),
            "score_breakdown": json.dumps(s.get("breakdown", [])),
            "penalty": s.get("penalty", 0),
            "scoring_config_version": s.get("scoring_config_version", ""),
        }
        for s in scores
    ]
    return _executemany(cur, UPSERT_FUND_SCORES_SQL, rows)


def sync_alerts(cur: Any, alerts: Sequence[dict], as_of_date: date) -> dict:
    """
    Sync open alerts for each (scheme, alert_type) with the latest evaluation.

    An alert that is still triggered keeps its original ``triggered_on`` date
    (``LEAST``), so alert age is preserved across nightly runs. Alerts that were
    not re-triggered are auto-resolved.

    Returns {"inserted": n, "updated": n, "resolved": n}.
    """
    inserted = 0
    updated = 0
    active_keys = []

    for alert in alerts:
        details = alert.get("details", {})
        params = {
            "scheme_code": alert["scheme_code"],
            "alert_type": alert["alert_type"],
            "severity": alert["severity"],
            "triggered_on": alert["triggered_on"],
            "details": json.dumps(details if isinstance(details, dict) else {}),
        }
        cur.execute(UPDATE_OPEN_ALERT_SQL, params)
        if (cur.rowcount or 0) > 0:
            updated += 1
        else:
            cur.execute(INSERT_ALERT_SQL, params)
            inserted += 1
        active_keys.append(f"{alert['scheme_code']}::{alert['alert_type']}")

    resolved = 0
    cur.execute(
        """
        UPDATE fund_alerts
        SET resolved_on = %(as_of_date)s, updated_at = NOW()
        WHERE resolved_on IS NULL
          AND triggered_on < %(as_of_date)s
          AND (scheme_code || '::' || alert_type) <> ALL(%(active_keys)s::text[])
        """,
        {"as_of_date": as_of_date, "active_keys": active_keys},
    )
    resolved = max(cur.rowcount or 0, 0)

    return {"inserted": inserted, "updated": updated, "resolved": resolved}


def start_pipeline_run(cur: Any, as_of_date: date, started_at: datetime = None) -> Any:
    """Insert a 'running' pipeline log row and return its run_id."""
    cur.execute(
        INSERT_PIPELINE_RUN_SQL,
        {"as_of_date": as_of_date, "started_at": started_at or datetime.now()},
    )
    row = cur.fetchone()
    if isinstance(row, dict):
        return row.get("run_id")
    return row[0] if row else None


def finish_pipeline_run(
    cur: Any,
    run_id: Any,
    status: str,
    schemes_processed: int,
    folios_processed: int,
    alerts_generated: int,
    scores_computed: int,
    error_message: str = None,
    metadata: dict = None,
) -> None:
    """Close out a pipeline log row."""
    if run_id is None:
        return
    cur.execute(
        FINISH_PIPELINE_RUN_SQL,
        {
            "run_id": run_id,
            "status": status,
            "schemes_processed": schemes_processed,
            "folios_processed": folios_processed,
            "alerts_generated": alerts_generated,
            "scores_computed": scores_computed,
            "error_message": error_message,
            "metadata": json.dumps(metadata or {}),
        },
    )
