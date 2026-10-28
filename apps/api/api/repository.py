"""
SQL access layer for the MFD API.

Routes stay thin: they validate input, call one repository function, and map
rows to Pydantic models. Functions accept an open dict cursor so a request can
share one connection.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Optional, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCORE_SORTS = {
    "score": "fs.fund_health_score",
    "fund_health_score": "fs.fund_health_score",
    "rank": "fs.category_rank",
    "name": "sm.scheme_name",
}

SCHEME_SORTS = {
    "score": "fs.fund_health_score",
    "fund_health_score": "fs.fund_health_score",
    "rank": "fs.category_rank",
    "return": "fr.return_1y",
    "alpha": "fr.alpha_1y",
    "dd": "fr.max_drawdown_1y",
    "vol": "fr.volatility_1y",
    "name": "sm.scheme_name",
}

RANKING_SORTS = {
    "score": "score_rank",
    "return": "return_rank",
    "alpha": "alpha_rank",
    "dd": "dd_rank",
    "vol": "vol_rank",
}


def _order(
    column_map: dict[str, str], requested: str, fallback: str, direction: str
) -> str:
    column = column_map.get(requested, column_map[fallback])
    safe_direction = "ASC" if str(direction).lower() == "asc" else "DESC"
    return f"{column} {safe_direction} NULLS LAST"


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------
# Scores
# ------------------------------------------------------------

SCORE_SELECT = """
SELECT
    fs.scheme_code,
    sm.scheme_name,
    sm.category,
    sm.amc,
    COALESCE(bm.benchmark_name, sm.benchmark_index, 'Unclassified') AS benchmark_name,
    fs.fund_health_score,
    fs.category_rank,
    fs.category_percentile,
    fs.score_breakdown,
    fs.penalty,
    fs.scoring_config_version,
    fs.as_of_date
FROM fund_scores fs
JOIN scheme_master sm ON sm.scheme_code = fs.scheme_code
LEFT JOIN benchmark_master bm ON bm.benchmark_code = sm.benchmark_index
"""


def latest_score_date(cur: Any) -> Optional[date]:
    cur.execute("SELECT MAX(as_of_date) AS latest FROM fund_scores")
    row = cur.fetchone()
    return row["latest"] if row else None


def fetch_scores(
    cur: Any,
    as_of_date: date,
    scheme_codes: Optional[Sequence[str]] = None,
    category: Optional[str] = None,
    amc: Optional[str] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    sort_by: str = "score",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    where = ["fs.as_of_date = %(as_of_date)s"]
    params: dict[str, Any] = {
        "as_of_date": as_of_date,
        "limit": limit,
        "offset": offset,
    }

    if scheme_codes:
        where.append("fs.scheme_code = ANY(%(scheme_codes)s)")
        params["scheme_codes"] = list(scheme_codes)
    if category:
        where.append("sm.category = %(category)s")
        params["category"] = category
    if amc:
        where.append("sm.amc = %(amc)s")
        params["amc"] = amc
    if min_score is not None:
        where.append("fs.fund_health_score >= %(min_score)s")
        params["min_score"] = min_score
    if max_score is not None:
        where.append("fs.fund_health_score <= %(max_score)s")
        params["max_score"] = max_score

    where_sql = " AND ".join(where)
    order_sql = _order(SCORE_SORTS, sort_by, "score", sort_order)

    cur.execute(
        f"{SCORE_SELECT} WHERE {where_sql} ORDER BY {order_sql} LIMIT %(limit)s OFFSET %(offset)s",
        params,
    )
    rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM fund_scores fs
        JOIN scheme_master sm ON sm.scheme_code = fs.scheme_code
        WHERE {where_sql}
        """,
        params,
    )
    total_row = cur.fetchone()
    total = int(total_row["total"]) if total_row else 0
    return rows, total


def fetch_score(cur: Any, scheme_code: str, as_of_date: date) -> Optional[dict]:
    cur.execute(
        f"{SCORE_SELECT} WHERE fs.scheme_code = %(scheme_code)s AND fs.as_of_date = %(as_of_date)s",
        {"scheme_code": scheme_code, "as_of_date": as_of_date},
    )
    row = cur.fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------
# Scheme monitoring
# ------------------------------------------------------------

SCHEME_SELECT = """
SELECT
    sm.scheme_code,
    sm.scheme_name,
    sm.amc,
    sm.category,
    COALESCE(bm.benchmark_name, sm.benchmark_index, 'Unclassified') AS benchmark_name,
    fs.fund_health_score,
    fs.category_rank,
    fs.category_percentile,
    fr.return_1y,
    fr.alpha_1y,
    fr.max_drawdown_1y,
    fr.volatility_1y,
    COALESCE(fr.consecutive_underperf_months, 0) AS consecutive_underperf_months,
    COALESCE(ac.high, 0)   AS high_alerts,
    COALESCE(ac.medium, 0) AS medium_alerts,
    COALESCE(ac.low, 0)    AS low_alerts
FROM scheme_master sm
JOIN fund_scores fs
    ON fs.scheme_code = sm.scheme_code
   AND fs.as_of_date = %(as_of_date)s
LEFT JOIN benchmark_master bm ON bm.benchmark_code = sm.benchmark_index
LEFT JOIN LATERAL (
    SELECT * FROM fund_rolling_returns fr
    WHERE fr.scheme_code = sm.scheme_code
    ORDER BY fr.as_of_date DESC
    LIMIT 1
) fr ON TRUE
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE severity = 'high')   AS high,
        COUNT(*) FILTER (WHERE severity = 'medium') AS medium,
        COUNT(*) FILTER (WHERE severity = 'low')    AS low
    FROM fund_alerts fa
    WHERE fa.scheme_code = sm.scheme_code
      AND fa.resolved_on IS NULL
) ac ON TRUE
WHERE sm.is_active = TRUE
"""


def fetch_schemes(
    cur: Any,
    as_of_date: date,
    category: Optional[str] = None,
    amc: Optional[str] = None,
    has_high_alerts: bool = False,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    sort_by: str = "fund_health_score",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    where = []
    params: dict[str, Any] = {
        "as_of_date": as_of_date,
        "limit": limit,
        "offset": offset,
    }

    if category:
        where.append("sm.category = %(category)s")
        params["category"] = category
    if amc:
        where.append("sm.amc = %(amc)s")
        params["amc"] = amc
    if min_score is not None:
        where.append("fs.fund_health_score >= %(min_score)s")
        params["min_score"] = min_score
    if max_score is not None:
        where.append("fs.fund_health_score <= %(max_score)s")
        params["max_score"] = max_score
    if has_high_alerts:
        where.append("COALESCE(ac.high, 0) > 0")

    where_sql = f" AND {' AND '.join(where)}" if where else ""
    order_sql = _order(SCHEME_SORTS, sort_by, "score", sort_order)

    cur.execute(
        f"{SCHEME_SELECT}{where_sql} ORDER BY {order_sql} LIMIT %(limit)s OFFSET %(offset)s",
        params,
    )
    rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM scheme_master sm
        JOIN fund_scores fs
            ON fs.scheme_code = sm.scheme_code
           AND fs.as_of_date = %(as_of_date)s
        LEFT JOIN LATERAL (
            SELECT COUNT(*) FILTER (WHERE severity = 'high') AS high
            FROM fund_alerts fa
            WHERE fa.scheme_code = sm.scheme_code AND fa.resolved_on IS NULL
        ) ac ON TRUE
        WHERE sm.is_active = TRUE
        {(' AND ' + ' AND '.join(where)) if where else ''}
        """,
        params,
    )
    total_row = cur.fetchone()
    total = int(total_row["total"]) if total_row else 0
    return rows, total


def fetch_scheme(cur: Any, scheme_code: str, as_of_date: date) -> Optional[dict]:
    cur.execute(
        f"{SCHEME_SELECT} AND sm.scheme_code = %(scheme_code)s",
        {"as_of_date": as_of_date, "scheme_code": scheme_code},
    )
    row = cur.fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------
# Alerts
# ------------------------------------------------------------

ALERT_SELECT = """
SELECT
    fa.alert_id::text AS alert_id,
    fa.scheme_code,
    sm.scheme_name,
    sm.category,
    fa.alert_type,
    fa.severity,
    fa.triggered_on,
    fa.resolved_on,
    fa.details
FROM fund_alerts fa
JOIN scheme_master sm ON sm.scheme_code = fa.scheme_code
"""


def fetch_alerts(
    cur: Any,
    as_of_date: date,
    scheme_codes: Optional[Sequence[str]] = None,
    alert_types: Optional[Sequence[str]] = None,
    severities: Optional[Sequence[str]] = None,
    unresolved_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    where = ["fa.triggered_on <= %(as_of_date)s"]
    params: dict[str, Any] = {
        "as_of_date": as_of_date,
        "limit": limit,
        "offset": offset,
    }

    if unresolved_only:
        where.append("fa.resolved_on IS NULL")
    if scheme_codes:
        where.append("fa.scheme_code = ANY(%(scheme_codes)s)")
        params["scheme_codes"] = list(scheme_codes)
    if alert_types:
        where.append("fa.alert_type = ANY(%(alert_types)s)")
        params["alert_types"] = list(alert_types)
    if severities:
        where.append("fa.severity = ANY(%(severities)s)")
        params["severities"] = list(severities)

    where_sql = " AND ".join(where)

    cur.execute(
        f"""
        {ALERT_SELECT}
        WHERE {where_sql}
        ORDER BY
            CASE fa.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            fa.triggered_on DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        f"SELECT COUNT(*) AS total FROM fund_alerts fa WHERE {where_sql}",
        params,
    )
    total_row = cur.fetchone()
    total = int(total_row["total"]) if total_row else 0
    return rows, total


def alerts_summary(
    cur: Any, as_of_date: date, unresolved_only: bool = True
) -> list[dict]:
    where = ["fa.triggered_on <= %(as_of_date)s"]
    if unresolved_only:
        where.append("fa.resolved_on IS NULL")

    cur.execute(
        f"""
        SELECT
            fa.alert_type,
            fa.severity,
            COUNT(*) AS count,
            COUNT(DISTINCT fa.scheme_code) AS schemes_affected,
            MAX(fa.triggered_on) AS latest_triggered
        FROM fund_alerts fa
        WHERE {' AND '.join(where)}
        GROUP BY fa.alert_type, fa.severity
        ORDER BY fa.severity, fa.alert_type
        """,
        {"as_of_date": as_of_date},
    )
    return [dict(r) for r in cur.fetchall()]


def update_alert(
    cur: Any,
    alert_id: str | int,
    resolved: bool,
    actor: Optional[str] = None,
    reason: Optional[str] = None,
) -> bool:
    numeric_id = _as_int(alert_id)
    if numeric_id is None:
        return False

    extra = {}
    if actor:
        extra["handled_by"] = actor
    if reason:
        extra["resolution_reason"] = reason
        extra["dismissed"] = not resolved

    cur.execute(
        """
        UPDATE fund_alerts
        SET resolved_on = CASE WHEN %(resolved)s THEN CURRENT_DATE ELSE resolved_on END,
            details = COALESCE(details, '{}'::jsonb) || %(extra)s::jsonb,
            updated_at = NOW()
        WHERE alert_id = %(alert_id)s
        """,
        {"alert_id": numeric_id, "resolved": resolved, "extra": _json(extra)},
    )
    return (cur.rowcount or 0) > 0


def bulk_update_alerts(
    cur: Any,
    alert_ids: Sequence[str],
    resolved: bool,
    actor: Optional[str] = None,
    reason: Optional[str] = None,
) -> int:
    numeric_ids = [i for i in (_as_int(a) for a in alert_ids) if i is not None]
    if not numeric_ids:
        return 0

    extra = {}
    if actor:
        extra["handled_by"] = actor
    if reason:
        extra["resolution_reason"] = reason
        extra["dismissed"] = not resolved

    cur.execute(
        """
        UPDATE fund_alerts
        SET resolved_on = CASE WHEN %(resolved)s THEN CURRENT_DATE ELSE resolved_on END,
            details = COALESCE(details, '{}'::jsonb) || %(extra)s::jsonb,
            updated_at = NOW()
        WHERE alert_id = ANY(%(alert_ids)s)
        """,
        {"alert_ids": numeric_ids, "resolved": resolved, "extra": _json(extra)},
    )
    return max(cur.rowcount or 0, 0)


def _json(payload: dict) -> str:
    import json

    return json.dumps(payload)


# ------------------------------------------------------------
# Rankings
# ------------------------------------------------------------

RANKING_SELECT = """
SELECT
    category,
    scheme_code,
    scheme_name,
    fund_health_score,
    category_rank,
    category_percentile,
    return_1y,
    alpha_1y,
    max_drawdown_1y,
    volatility_1y,
    score_rank,
    return_rank,
    alpha_rank,
    dd_rank,
    vol_rank
FROM v_mfd_category_rankings
"""


def category_rankings(
    cur: Any, category: str, metric: str = "score", limit: int = 50
) -> list[dict]:
    order_column = RANKING_SORTS.get(metric, "score_rank")
    cur.execute(
        f"""
        {RANKING_SELECT}
        WHERE category = %(category)s
        ORDER BY {order_column} ASC NULLS LAST
        LIMIT %(limit)s
        """,
        {"category": category, "limit": limit},
    )
    return [dict(r) for r in cur.fetchall()]


def all_category_rankings(cur: Any, limit_per_category: int = 20) -> list[dict]:
    cur.execute(f"""
        {RANKING_SELECT}
        ORDER BY category, score_rank
        """)
    rows = [dict(r) for r in cur.fetchall()]

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        bucket = grouped.setdefault(row["category"], [])
        if len(bucket) < limit_per_category:
            bucket.append(row)
    return [row for rows_ in grouped.values() for row in rows_]


# ------------------------------------------------------------
# Benchmarks & macro
# ------------------------------------------------------------


def benchmark_history(
    cur: Any,
    benchmark_code: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> Optional[dict]:
    cur.execute(
        "SELECT benchmark_name FROM benchmark_master WHERE benchmark_code = %(code)s",
        {"code": benchmark_code},
    )
    meta = cur.fetchone()
    if not meta:
        return None

    where = ["benchmark_code = %(code)s"]
    params: dict[str, Any] = {"code": benchmark_code}
    if from_date:
        where.append("index_date >= %(from_date)s")
        params["from_date"] = from_date
    if to_date:
        where.append("index_date <= %(to_date)s")
        params["to_date"] = to_date

    cur.execute(
        f"""
        SELECT index_date, index_value
        FROM benchmark_history
        WHERE {' AND '.join(where)}
        ORDER BY index_date
        """,
        params,
    )
    points = [
        {"date": r["index_date"].isoformat(), "value": float(r["index_value"])}
        for r in cur.fetchall()
    ]

    return {
        "benchmark_code": benchmark_code,
        "benchmark_name": meta["benchmark_name"],
        "data": points,
    }


def macro_series(
    cur: Any,
    indicators: Sequence[str],
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> dict:
    where = ["indicator_name = ANY(%(indicators)s)"]
    params: dict[str, Any] = {"indicators": list(indicators)}
    if from_date:
        where.append("indicator_date >= %(from_date)s")
        params["from_date"] = from_date
    if to_date:
        where.append("indicator_date <= %(to_date)s")
        params["to_date"] = to_date

    cur.execute(
        f"""
        SELECT indicator_name, indicator_date, value
        FROM macro_indicators
        WHERE {' AND '.join(where)}
        ORDER BY indicator_name, indicator_date
        """,
        params,
    )

    data: dict[str, list[dict]] = {name: [] for name in indicators}
    for row in cur.fetchall():
        data.setdefault(row["indicator_name"], []).append(
            {
                "date": row["indicator_date"].isoformat(),
                "value": float(row["value"]),
            }
        )
    return {"data": data}


# ------------------------------------------------------------
# Pipeline health
# ------------------------------------------------------------


def pipeline_health(cur: Any) -> dict:
    payload: dict[str, Any] = {}

    cur.execute("""
        SELECT
            (SELECT MAX(nav_date) FROM nav_history)     AS latest_nav_date,
            (SELECT MAX(as_of_date) FROM fund_scores)   AS latest_score_date,
            (SELECT MAX(triggered_on) FROM fund_alerts) AS latest_alert_date
        """)
    freshness = cur.fetchone() or {}
    payload.update(
        {
            "latest_nav_date": freshness.get("latest_nav_date"),
            "latest_score_date": freshness.get("latest_score_date"),
            "latest_alert_date": freshness.get("latest_alert_date"),
        }
    )

    cur.execute("""
        SELECT status,
               as_of_date,
               schemes_processed,
               alerts_generated,
               EXTRACT(EPOCH FROM (completed_at - started_at)) AS duration_seconds
        FROM pipeline_run_log
        ORDER BY started_at DESC
        LIMIT 1
        """)
    run = cur.fetchone()
    if run:
        duration = run.get("duration_seconds")
        payload.update(
            {
                "as_of_date": run.get("as_of_date"),
                "last_run_status": run.get("status") or "degraded",
                "last_run_duration_seconds": (
                    float(duration) if duration is not None else None
                ),
                "schemes_processed": run.get("schemes_processed") or 0,
                "alerts_generated": run.get("alerts_generated") or 0,
            }
        )

    return payload


# ------------------------------------------------------------
# Config snapshots
# ------------------------------------------------------------


def _config_path(env_var: str, default_name: str) -> Path:
    configured = os.getenv(env_var)
    if configured:
        path = Path(configured)
        if path.exists():
            return path
    return PROJECT_ROOT / "config" / default_name


def scoring_config() -> dict:
    path = _config_path("SCORING_CONFIG_PATH", "scoring_config.yaml")
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def rules_config() -> dict:
    path = _config_path("RULES_CONFIG_PATH", "rules.yaml")
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
