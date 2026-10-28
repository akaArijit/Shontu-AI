"""
MFD API Routes - Fund Scores & Monitoring
Internal use only - Mutual Fund Distributors
"""

from fastapi import APIRouter, Query, HTTPException
from contextlib import contextmanager
from typing import Optional, List
from datetime import date
from pydantic import BaseModel
import logging

from fund_engine.db import repository
from fund_engine.db.connection import get_cursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mfd", tags=["MFD Fund Monitoring"])


@contextmanager
def db_cursor():
    """Open a cursor and translate infrastructure failures into 503s."""
    try:
        with get_cursor() as cur:
            yield cur
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Database error: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


def _split(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _opt_float(value) -> Optional[float]:
    return None if value is None else float(value)


# ============================================================
# Request/Response Models
# ============================================================


class ScoreBreakdownItem(BaseModel):
    component: str
    points: float
    max_points: int
    reason: str
    raw_value: Optional[float] = None


class FundScoreResponse(BaseModel):
    scheme_code: str
    scheme_name: str
    category: str
    amc: str
    benchmark_name: str
    fund_health_score: int
    category_rank: Optional[int] = None
    category_percentile: Optional[float] = None
    penalty: float
    breakdown: List[ScoreBreakdownItem]
    scoring_config_version: str
    as_of_date: date


class FundScoreListResponse(BaseModel):
    as_of_date: date
    total: int
    limit: int
    offset: int
    scores: List[FundScoreResponse]


class AlertResponse(BaseModel):
    alert_id: str
    scheme_code: str
    scheme_name: str
    category: str
    alert_type: str
    severity: str
    triggered_on: date
    resolved_on: Optional[date] = None
    details: dict


class AlertListResponse(BaseModel):
    as_of_date: date
    total: int
    limit: int
    offset: int
    alerts: List[AlertResponse]


class AlertSummaryResponse(BaseModel):
    alert_type: str
    severity: str
    count: int
    schemes_affected: int
    latest_triggered: date


class MFDSchemeSummary(BaseModel):
    scheme_code: str
    scheme_name: str
    amc: str
    category: str
    benchmark_name: str
    fund_health_score: int
    category_rank: Optional[int]
    category_percentile: Optional[float]
    return_1y: Optional[float]
    alpha_1y: Optional[float]
    max_drawdown_1y: Optional[float]
    volatility_1y: Optional[float]
    consecutive_underperf_months: int
    high_alerts: int
    medium_alerts: int
    low_alerts: int


class MFDSchemeListResponse(BaseModel):
    as_of_date: date
    total: int
    limit: int
    offset: int
    schemes: List[MFDSchemeSummary]


class CategoryRankingResponse(BaseModel):
    category: str
    scheme_code: str
    scheme_name: str
    fund_health_score: int
    category_rank: int
    category_percentile: float
    return_1y: Optional[float]
    alpha_1y: Optional[float]
    max_drawdown_1y: Optional[float]
    volatility_1y: Optional[float]


class CategoryRankingListResponse(BaseModel):
    as_of_date: date
    category: str
    rankings: List[CategoryRankingResponse]


class PipelineHealthResponse(BaseModel):
    as_of_date: date
    latest_nav_date: Optional[date]
    latest_score_date: Optional[date]
    latest_alert_date: Optional[date]
    last_run_status: str
    last_run_duration_seconds: Optional[float]
    schemes_processed: int
    alerts_generated: int


# ============================================================
# Row → Model mappers
# ============================================================


def _score_model(row: dict) -> FundScoreResponse:
    return FundScoreResponse(
        scheme_code=row["scheme_code"],
        scheme_name=row["scheme_name"],
        category=row["category"] or "Unclassified",
        amc=row["amc"] or "Unknown",
        benchmark_name=row["benchmark_name"] or "Unclassified",
        fund_health_score=int(row["fund_health_score"]),
        category_rank=row.get("category_rank"),
        category_percentile=_opt_float(row.get("category_percentile")),
        penalty=float(row.get("penalty") or 0),
        breakdown=row.get("score_breakdown") or [],
        scoring_config_version=row.get("scoring_config_version") or "",
        as_of_date=row["as_of_date"],
    )


def _scheme_model(row: dict) -> MFDSchemeSummary:
    return MFDSchemeSummary(
        scheme_code=row["scheme_code"],
        scheme_name=row["scheme_name"],
        amc=row["amc"] or "Unknown",
        category=row["category"] or "Unclassified",
        benchmark_name=row["benchmark_name"] or "Unclassified",
        fund_health_score=int(row["fund_health_score"]),
        category_rank=row.get("category_rank"),
        category_percentile=_opt_float(row.get("category_percentile")),
        return_1y=_opt_float(row.get("return_1y")),
        alpha_1y=_opt_float(row.get("alpha_1y")),
        max_drawdown_1y=_opt_float(row.get("max_drawdown_1y")),
        volatility_1y=_opt_float(row.get("volatility_1y")),
        consecutive_underperf_months=int(row.get("consecutive_underperf_months") or 0),
        high_alerts=int(row.get("high_alerts") or 0),
        medium_alerts=int(row.get("medium_alerts") or 0),
        low_alerts=int(row.get("low_alerts") or 0),
    )


def _alert_model(row: dict) -> AlertResponse:
    return AlertResponse(
        alert_id=str(row["alert_id"]),
        scheme_code=row["scheme_code"],
        scheme_name=row["scheme_name"],
        category=row["category"] or "Unclassified",
        alert_type=row["alert_type"],
        severity=row["severity"],
        triggered_on=row["triggered_on"],
        resolved_on=row.get("resolved_on"),
        details=row.get("details") or {},
    )


def _ranking_model(row: dict) -> CategoryRankingResponse:
    return CategoryRankingResponse(
        category=row["category"] or "Unclassified",
        scheme_code=row["scheme_code"],
        scheme_name=row["scheme_name"],
        fund_health_score=int(row["fund_health_score"]),
        category_rank=int(row.get("category_rank") or 0),
        category_percentile=float(row.get("category_percentile") or 0),
        return_1y=_opt_float(row.get("return_1y")),
        alpha_1y=_opt_float(row.get("alpha_1y")),
        max_drawdown_1y=_opt_float(row.get("max_drawdown_1y")),
        volatility_1y=_opt_float(row.get("volatility_1y")),
    )


# ============================================================
# Fund Scores Endpoints
# ============================================================


@router.get("/scores", response_model=FundScoreListResponse)
async def get_fund_scores(
    as_of_date: date = Query(..., description="Score date (YYYY-MM-DD)"),
    scheme_codes: Optional[str] = Query(
        None, description="Comma-separated scheme codes"
    ),
    category: Optional[str] = Query(None, description="SEBI category filter"),
    amc: Optional[str] = Query(None, description="AMC filter"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum score"),
    max_score: Optional[int] = Query(None, ge=0, le=100, description="Maximum score"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get fund health scores for MFD monitoring dashboard.
    Returns paginated list with full breakdown for each scheme.
    """
    with db_cursor() as cur:
        rows, total = repository.fetch_scores(
            cur,
            as_of_date=as_of_date,
            scheme_codes=_split(scheme_codes),
            category=category,
            amc=amc,
            min_score=min_score,
            max_score=max_score,
            limit=limit,
            offset=offset,
        )

    return FundScoreListResponse(
        as_of_date=as_of_date,
        total=total,
        limit=limit,
        offset=offset,
        scores=[_score_model(row) for row in rows],
    )


@router.get("/scores/latest", response_model=FundScoreListResponse)
async def get_latest_scores(
    category: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get latest available scores (auto-detects latest as_of_date)."""
    with db_cursor() as cur:
        latest = repository.latest_score_date(cur)
        if latest is None:
            return FundScoreListResponse(
                as_of_date=date.today(), total=0, limit=limit, offset=offset, scores=[]
            )

        rows, total = repository.fetch_scores(
            cur,
            as_of_date=latest,
            category=category,
            min_score=min_score,
            limit=limit,
            offset=offset,
        )

    return FundScoreListResponse(
        as_of_date=latest,
        total=total,
        limit=limit,
        offset=offset,
        scores=[_score_model(row) for row in rows],
    )


@router.get("/scores/{scheme_code}", response_model=FundScoreResponse)
async def get_fund_score_detail(
    scheme_code: str,
    as_of_date: date = Query(..., description="Score date (YYYY-MM-DD)"),
):
    """Get detailed score breakdown for a single scheme."""
    with db_cursor() as cur:
        row = repository.fetch_score(cur, scheme_code, as_of_date)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No score for {scheme_code} on {as_of_date.isoformat()}",
        )
    return _score_model(row)


# ============================================================
# Alerts Endpoints
# ============================================================


@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    as_of_date: date = Query(..., description="Alert date (YYYY-MM-DD)"),
    scheme_codes: Optional[str] = Query(None),
    alert_types: Optional[str] = Query(None, description="Comma-separated"),
    severities: Optional[str] = Query(None, description="low,medium,high"),
    unresolved_only: bool = Query(True, description="Only unresolved alerts"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get triggered alerts for MFD action."""
    with db_cursor() as cur:
        rows, total = repository.fetch_alerts(
            cur,
            as_of_date=as_of_date,
            scheme_codes=_split(scheme_codes),
            alert_types=_split(alert_types),
            severities=_split(severities),
            unresolved_only=unresolved_only,
            limit=limit,
            offset=offset,
        )

    return AlertListResponse(
        as_of_date=as_of_date,
        total=total,
        limit=limit,
        offset=offset,
        alerts=[_alert_model(row) for row in rows],
    )


@router.get("/alerts/summary", response_model=List[AlertSummaryResponse])
async def get_alerts_summary(
    as_of_date: date = Query(..., description="Alert date (YYYY-MM-DD)"),
    unresolved_only: bool = Query(True),
):
    """Get alert counts by type and severity for dashboard badges."""
    with db_cursor() as cur:
        rows = repository.alerts_summary(
            cur, as_of_date, unresolved_only=unresolved_only
        )

    return [
        AlertSummaryResponse(
            alert_type=row["alert_type"],
            severity=row["severity"],
            count=int(row["count"]),
            schemes_affected=int(row["schemes_affected"]),
            latest_triggered=row["latest_triggered"],
        )
        for row in rows
    ]


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str, resolved_by: str = Query(..., description="MFD user ID")
):
    """Mark alert as resolved by MFD."""
    with db_cursor() as cur:
        updated = repository.update_alert(
            cur, alert_id, resolved=True, actor=resolved_by
        )

    if not updated:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"success": True, "alert_id": alert_id, "resolved_by": resolved_by}


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: str, dismissed_by: str = Query(...), reason: str = Query(...)
):
    """Dismiss alert with reason (e.g., 'false positive', 'client informed')."""
    with db_cursor() as cur:
        updated = repository.update_alert(
            cur, alert_id, resolved=False, actor=dismissed_by, reason=reason
        )

    if not updated:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {
        "success": True,
        "alert_id": alert_id,
        "dismissed_by": dismissed_by,
        "reason": reason,
    }


# ============================================================
# MFD Scheme Monitoring (Primary Dashboard View)
# ============================================================


@router.get("/schemes", response_model=MFDSchemeListResponse)
async def get_schemes_monitoring(
    as_of_date: date = Query(..., description="Monitoring date"),
    category: Optional[str] = Query(None),
    amc: Optional[str] = Query(None),
    has_high_alerts: bool = Query(False, description="Filter schemes with high alerts"),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
    sort_by: str = Query(
        "fund_health_score", description="score, rank, return, alpha, dd, vol"
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Primary MFD monitoring view: All schemes with scores, key metrics, and alert counts.
    Optimized for MFD dashboard - single query with all needed data.
    """
    with db_cursor() as cur:
        rows, total = repository.fetch_schemes(
            cur,
            as_of_date=as_of_date,
            category=category,
            amc=amc,
            has_high_alerts=has_high_alerts,
            min_score=min_score,
            max_score=max_score,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

    return MFDSchemeListResponse(
        as_of_date=as_of_date,
        total=total,
        limit=limit,
        offset=offset,
        schemes=[_scheme_model(row) for row in rows],
    )


@router.get("/schemes/{scheme_code}", response_model=MFDSchemeSummary)
async def get_scheme_monitoring_detail(scheme_code: str, as_of_date: date = Query(...)):
    """Detailed view for single scheme with full metrics and alert history."""
    with db_cursor() as cur:
        row = repository.fetch_scheme(cur, scheme_code, as_of_date)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No monitoring data for {scheme_code} on {as_of_date.isoformat()}",
        )
    return _scheme_model(row)


# ============================================================
# Category Rankings
# ============================================================


@router.get("/rankings/category/{category}", response_model=CategoryRankingListResponse)
async def get_category_rankings(
    category: str,
    as_of_date: date = Query(...),
    metric: str = Query("score", pattern="^(score|return|alpha|dd|vol)$"),
    limit: int = Query(50, ge=1, le=200),
):
    """Category-wise rankings for MFD peer comparison."""
    with db_cursor() as cur:
        rows = repository.category_rankings(cur, category, metric=metric, limit=limit)

    return CategoryRankingListResponse(
        as_of_date=as_of_date,
        category=category,
        rankings=[_ranking_model(row) for row in rows],
    )


@router.get("/rankings/all", response_model=List[CategoryRankingListResponse])
async def get_all_category_rankings(
    as_of_date: date = Query(...), limit_per_category: int = Query(20, ge=1, le=100)
):
    """All category rankings in one call for overview dashboard."""
    with db_cursor() as cur:
        rows = repository.all_category_rankings(
            cur, limit_per_category=limit_per_category
        )

    grouped: dict[str, CategoryRankingListResponse] = {}
    for row in rows:
        model = _ranking_model(row)
        bucket = grouped.get(model.category)
        if bucket is None:
            bucket = CategoryRankingListResponse(
                as_of_date=as_of_date, category=model.category, rankings=[]
            )
            grouped[model.category] = bucket
        bucket.rankings.append(model)

    return list(grouped.values())


# ============================================================
# Benchmark & Macro Context
# ============================================================


@router.get("/benchmarks/{benchmark_code}/history")
async def get_benchmark_history(
    benchmark_code: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    """Benchmark index history for context panels."""
    with db_cursor() as cur:
        payload = repository.benchmark_history(
            cur, benchmark_code, from_date=from_date, to_date=to_date
        )

    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown benchmark {benchmark_code}"
        )
    return payload


@router.get("/macro")
async def get_macro_context(
    indicators: str = Query("repo_rate,cpi,usd_inr,india_vix"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    """Macro indicators for MFD context panel (not used in scoring)."""
    names = _split(indicators) or ["repo_rate", "cpi", "usd_inr", "india_vix"]
    with db_cursor() as cur:
        return repository.macro_series(cur, names, from_date=from_date, to_date=to_date)


# ============================================================
# Pipeline Health
# ============================================================


@router.get("/health", response_model=PipelineHealthResponse)
async def get_pipeline_health():
    """Pipeline freshness for MFD operations.

    Never fails: if the database is unreachable or no pipeline has run yet,
    returns a `degraded` snapshot with zero counters so the dashboard can
    render "no data yet" instead of erroring.
    """
    today = date.today()
    payload = {
        "as_of_date": today,
        "latest_nav_date": None,
        "latest_score_date": None,
        "latest_alert_date": None,
        "last_run_status": "degraded",
        "last_run_duration_seconds": None,
        "schemes_processed": 0,
        "alerts_generated": 0,
    }

    try:
        with get_cursor() as cur:
            health = repository.pipeline_health(cur)
        payload.update({k: v for k, v in health.items() if v is not None})
        payload["as_of_date"] = health.get("as_of_date") or today
    except Exception as exc:  # noqa: BLE001 - health must never 500
        logger.warning("Pipeline health falling back to degraded: %s", exc)

    return PipelineHealthResponse(**payload)


@router.get("/meta/scoring-config")
async def get_scoring_config(version: Optional[str] = Query(None)):
    """Current scoring configuration for audit/training."""
    try:
        config = repository.scoring_config()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scoring config not found") from exc

    return {"version": version or config.get("version", "unknown"), "config": config}


@router.get("/meta/rules-config")
async def get_rules_config():
    """Current alert rules configuration for MFD reference."""
    try:
        config = repository.rules_config()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Rules config not found") from exc

    return config


# ============================================================
# Bulk Operations (MFD Actions)
# ============================================================


class BulkResolveRequest(BaseModel):
    alert_ids: List[str]
    resolved_by: str


class BulkDismissRequest(BaseModel):
    alert_ids: List[str]
    dismissed_by: str
    reason: str


@router.post("/alerts/bulk-resolve")
async def bulk_resolve_alerts(request: BulkResolveRequest):
    """Resolve multiple alerts at once."""
    with db_cursor() as cur:
        updated = repository.bulk_update_alerts(
            cur, request.alert_ids, resolved=True, actor=request.resolved_by
        )

    return {
        "success": True,
        "requested": len(request.alert_ids),
        "updated": updated,
        "resolved_count": updated,
        "resolved_by": request.resolved_by,
    }


@router.post("/alerts/bulk-dismiss")
async def bulk_dismiss_alerts(request: BulkDismissRequest):
    """Dismiss multiple alerts with same reason."""
    with db_cursor() as cur:
        updated = repository.bulk_update_alerts(
            cur,
            request.alert_ids,
            resolved=False,
            actor=request.dismissed_by,
            reason=request.reason,
        )

    return {
        "success": True,
        "requested": len(request.alert_ids),
        "updated": updated,
        "dismissed_count": updated,
        "dismissed_by": request.dismissed_by,
        "reason": request.reason,
    }
