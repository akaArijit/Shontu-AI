-- Fund Monitoring & Scoring Engine - Performance Indexes
-- Version: 1.0
-- Description: Additional indexes for query performance

-- ============================================================
-- NAV HISTORY - Composite indexes for feature engineering
-- ============================================================
-- Used by RollingReturnsCalculator._get_nav_as_of()
CREATE INDEX IF NOT EXISTS idx_nav_history_scheme_date_desc
    ON nav_history(scheme_code, nav_date DESC);

-- Used for date-range queries
CREATE INDEX IF NOT EXISTS idx_nav_history_date_scheme
    ON nav_history(nav_date DESC, scheme_code);

-- ============================================================
-- BENCHMARK HISTORY
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_benchmark_history_code_date_desc
    ON benchmark_history(benchmark_code, index_date DESC);

-- ============================================================
-- FUND ROLLING RETURNS - Most queried table
-- ============================================================
-- Primary lookup: scheme_code + as_of_date (already PK)
-- Additional for category-relative queries
CREATE INDEX IF NOT EXISTS idx_frr_date_scheme
    ON fund_rolling_returns(as_of_date DESC, scheme_code);

-- For percentile calculations within category/date
CREATE INDEX IF NOT EXISTS idx_frr_date_return_1y
    ON fund_rolling_returns(as_of_date DESC, return_1y) WHERE return_1y IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_frr_date_alpha_1y
    ON fund_rolling_returns(as_of_date DESC, alpha_1y) WHERE alpha_1y IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_frr_date_pctl_1y
    ON fund_rolling_returns(as_of_date DESC, category_percentile_1y) WHERE category_percentile_1y IS NOT NULL;

-- ============================================================
-- FUND SCORES
-- ============================================================
-- Primary lookup (already PK: scheme_code, as_of_date)
CREATE INDEX IF NOT EXISTS idx_fund_scores_date_score
    ON fund_scores(as_of_date DESC, fund_health_score DESC);

-- For score range queries
CREATE INDEX IF NOT EXISTS idx_fund_scores_score_date
    ON fund_scores(fund_health_score DESC, as_of_date DESC);

-- For category rank queries
CREATE INDEX IF NOT EXISTS idx_fund_scores_date_rank
    ON fund_scores(as_of_date DESC, category_rank) WHERE category_rank IS NOT NULL;

-- ============================================================
-- FUND ALERTS
-- ============================================================
-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_fund_alerts_scheme_triggered
    ON fund_alerts(scheme_code, triggered_on DESC);

-- For alert dashboard queries
CREATE INDEX IF NOT EXISTS idx_fund_alerts_type_severity_date
    ON fund_alerts(alert_type, severity, triggered_on DESC);

-- Unresolved alerts (for notification queue)
CREATE INDEX IF NOT EXISTS idx_fund_alerts_unresolved
    ON fund_alerts(triggered_on DESC) WHERE resolved_on IS NULL;

-- Client-specific alert queries
CREATE INDEX IF NOT EXISTS idx_fund_alerts_client_scheme
    ON fund_alerts(scheme_code, alert_type, triggered_on DESC);

-- ============================================================
-- CLIENT FOLIOS
-- ============================================================
-- Primary: folio_id (PK)
CREATE INDEX IF NOT EXISTS idx_client_folios_client_scheme
    ON client_folios(client_id, scheme_code);

-- For portfolio valuation queries
CREATE INDEX IF NOT EXISTS idx_client_folios_client_date
    ON client_folios(client_id, last_sync DESC);

-- ============================================================
-- SCHEME MASTER
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_scheme_master_category_active
    ON scheme_master(category, is_active) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_scheme_master_amc_category
    ON scheme_master(amc, category);

-- ============================================================
-- PIPELINE RUN LOG
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_pipeline_run_status_date
    ON pipeline_run_log(status, started_at DESC);

-- ============================================================
-- PARTIAL INDEXES FOR COMMON FILTERS
-- ============================================================
-- Active schemes only
CREATE INDEX IF NOT EXISTS idx_frr_active_schemes
    ON fund_rolling_returns(as_of_date DESC, scheme_code)
    WHERE scheme_code IN (SELECT scheme_code FROM scheme_master WHERE is_active = true);

-- Recent scores (last 30 days)
CREATE INDEX IF NOT EXISTS idx_fund_scores_recent
    ON fund_scores(as_of_date DESC, fund_health_score DESC)
    WHERE as_of_date >= CURRENT_DATE - INTERVAL '30 days';

-- High severity unresolved alerts
CREATE INDEX IF NOT EXISTS idx_alerts_high_unresolved
    ON fund_alerts(triggered_on DESC)
    WHERE severity = 'high' AND resolved_on IS NULL;