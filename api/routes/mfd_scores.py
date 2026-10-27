"""
MFD API Routes - Fund Scores & Monitoring
Internal use only - Mutual Fund Distributors
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List
from datetime import date, timedelta
from pydantic import BaseModel
from enum import Enum
import logging

from api.db import get_cursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mfd", tags=["MFD Fund Monitoring"])


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
# Fund Scores Endpoints
# ============================================================

@router.get("/scores", response_model=FundScoreListResponse)
async def get_fund_scores(
    as_of_date: date = Query(..., description="Score date (YYYY-MM-DD)"),
    scheme_codes: Optional[str] = Query(None, description="Comma-separated scheme codes"),
    category: Optional[str] = Query(None, description="SEBI category filter"),
    amc: Optional[str] = Query(None, description="AMC filter"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum score"),
    max_score: Optional[int] = Query(None, ge=0, le=100, description="Maximum score"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get fund health scores for MFD monitoring dashboard.
    Returns paginated list with full breakdown for each scheme.
    """
    # Implementation: Query fund_scores table with filters
    # Join scheme_master for scheme_name, category, amc, benchmark_name
    # Return paginated results
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.get("/scores/{scheme_code}", response_model=FundScoreResponse)
async def get_fund_score_detail(
    scheme_code: str,
    as_of_date: date = Query(..., description="Score date (YYYY-MM-DD)")
):
    """Get detailed score breakdown for a single scheme."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.get("/scores/latest", response_model=FundScoreListResponse)
async def get_latest_scores(
    category: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Get latest available scores (auto-detects latest as_of_date)."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


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
    offset: int = Query(0, ge=0)
):
    """Get triggered alerts for MFD action."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.get("/alerts/summary", response_model=List[AlertSummaryResponse])
async def get_alerts_summary(
    as_of_date: date = Query(..., description="Alert date (YYYY-MM-DD)"),
    unresolved_only: bool = Query(True)
):
    """Get alert counts by type and severity for dashboard badges."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolved_by: str = Query(..., description="MFD user ID")
):
    """Mark alert as resolved by MFD."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: str,
    dismissed_by: str = Query(...),
    reason: str = Query(...)
):
    """Dismiss alert with reason (e.g., 'false positive', 'client informed')."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


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
    sort_by: str = Query("fund_health_score", description="score, rank, return, alpha, dd, vol"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Primary MFD monitoring view: All schemes with scores, key metrics, and alert counts.
    Optimized for MFD dashboard - single query with all needed data.
    """
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.get("/schemes/{scheme_code}", response_model=MFDSchemeSummary)
async def get_scheme_monitoring_detail(
    scheme_code: str,
    as_of_date: date = Query(...)
):
    """Detailed view for single scheme with full metrics and alert history."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


# ============================================================
# Category Rankings
# ============================================================

@router.get("/rankings/category/{category}", response_model=CategoryRankingListResponse)
async def get_category_rankings(
    category: str,
    as_of_date: date = Query(...),
    metric: str = Query("score", pattern="^(score|return|alpha|dd|vol)$"),
    limit: int = Query(50, ge=1, le=200)
):
    """Category-wise rankings for MFD peer comparison."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.get("/rankings/all", response_model=List[CategoryRankingListResponse])
async def get_all_category_rankings(
    as_of_date: date = Query(...),
    limit_per_category: int = Query(20, ge=1, le=100)
):
    """All category rankings in one call for overview dashboard."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


# ============================================================
# Benchmark & Macro Context
# ============================================================

@router.get("/benchmarks/{benchmark_code}/history")
async def get_benchmark_history(
    benchmark_code: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None)
):
    """Benchmark index history for context panels."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.get("/macro")
async def get_macro_context(
    indicators: str = Query("repo_rate,cpi,usd_inr,india_vix"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None)
):
    """Macro indicators for MFD context panel (not used in scoring)."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


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
            cur.execute(
                """
                SELECT
                    (SELECT MAX(nav_date) FROM nav_history)      AS latest_nav_date,
                    (SELECT MAX(as_of_date) FROM fund_scores)    AS latest_score_date,
                    (SELECT MAX(triggered_on) FROM fund_alerts)  AS latest_alert_date
                """
            )
            freshness = cur.fetchone() or {}

            cur.execute(
                """
                SELECT status,
                       as_of_date,
                       schemes_processed,
                       alerts_generated,
                       EXTRACT(EPOCH FROM (completed_at - started_at)) AS duration_seconds
                FROM pipeline_run_log
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            run = cur.fetchone()

            if freshness:
                payload.update(
                    {
                        "latest_nav_date": freshness.get("latest_nav_date"),
                        "latest_score_date": freshness.get("latest_score_date"),
                        "latest_alert_date": freshness.get("latest_alert_date"),
                    }
                )

            if run:
                duration = run.get("duration_seconds")
                payload.update(
                    {
                        "as_of_date": run.get("as_of_date") or today,
                        "last_run_status": run.get("status") or "degraded",
                        "last_run_duration_seconds": (
                            float(duration) if duration is not None else None
                        ),
                        "schemes_processed": run.get("schemes_processed") or 0,
                        "alerts_generated": run.get("alerts_generated") or 0,
                    }
                )
    except Exception as exc:  # noqa: BLE001 - health must never 500
        logger.warning("Pipeline health falling back to degraded: %s", exc)

    return PipelineHealthResponse(**payload)


@router.get("/meta/scoring-config")
async def get_scoring_config(
    version: Optional[str] = Query(None)
):
    """Current scoring configuration for audit/training."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.get("/meta/rules-config")
async def get_rules_config():
    """Current alert rules configuration for MFD reference."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


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
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")


@router.post("/alerts/bulk-dismiss")
async def bulk_dismiss_alerts(request: BulkDismissRequest):
    """Dismiss multiple alerts with same reason."""
    raise HTTPException(status_code=503, detail="Endpoint not yet wired to the database")
