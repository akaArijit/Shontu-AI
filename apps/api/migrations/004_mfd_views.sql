-- Fund Monitoring & Scoring Engine - MFD Specific Views
-- Version: 1.0
-- Description: Views optimized for MFD dashboard and monitoring workflows

-- ============================================================
-- MFD SCHEME MONITORING VIEW (Primary Dashboard View)
-- ============================================================
-- Single-row-per-scheme with all metrics MFD needs for daily monitoring
CREATE OR REPLACE VIEW v_mfd_scheme_monitoring AS
SELECT
    -- Scheme identification
    sm.scheme_code,
    sm.scheme_name,
    sm.amc,
    sm.category,
    sm.sub_category,
    sm.benchmark_index,
    bm.benchmark_name,
    sm.fund_manager,
    sm.expense_ratio,
    sm.aum,
    sm.inception_date,
    -- Latest score (0-100)
    fs.fund_health_score,
    fs.category_rank,
    fs.category_percentile,
    fs.penalty,
    fs.scoring_config_version,
    fs.computed_at AS score_computed_at,
    -- Latest features (1Y window)
    fr.return_1y,
    fr.alpha_1y,
    fr.max_drawdown_1y,
    fr.volatility_1y,
    fr.category_percentile_1y,
    fr.category_rank_1y,
    fr.consecutive_underperf_months,
    fr.correlation_to_benchmark_1y,
    fr.computed_at AS features_computed_at,
    -- Alert summary (unresolved only)
    COALESCE(alert_counts.high, 0) AS high_alerts,
    COALESCE(alert_counts.medium, 0) AS medium_alerts,
    COALESCE(alert_counts.low, 0) AS low_alerts,
    alert_counts.total AS total_unresolved_alerts,
    -- Latest NAV
    nh.nav_value AS latest_nav,
    nh.nav_date AS latest_nav_date,
    -- Status flags for MFD quick filtering
    CASE 
        WHEN alert_counts.high > 0 THEN 'critical'
        WHEN alert_counts.medium > 0 THEN 'warning'
        WHEN alert_counts.low > 0 THEN 'watch'
        ELSE 'ok'
    END AS mfd_status,
    CASE 
        WHEN fs.fund_health_score >= 75 THEN 'green'
        WHEN fs.fund_health_score >= 50 THEN 'yellow'
        ELSE 'red'
    END AS score_band
FROM scheme_master sm
LEFT JOIN benchmark_master bm ON sm.benchmark_index = bm.benchmark_code
LEFT JOIN LATERAL (
    SELECT * FROM fund_scores fs
    WHERE fs.scheme_code = sm.scheme_code
    ORDER BY fs.as_of_date DESC LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT * FROM fund_rolling_returns fr
    WHERE fr.scheme_code = sm.scheme_code
    ORDER BY fr.as_of_date DESC LIMIT 1
) fr ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE severity = 'high') AS high,
        COUNT(*) FILTER (WHERE severity = 'medium') AS medium,
        COUNT(*) FILTER (WHERE severity = 'low') AS low,
        COUNT(*) AS total
    FROM fund_alerts fa
    WHERE fa.scheme_code = sm.scheme_code
      AND fa.resolved_on IS NULL
) alert_counts ON true
LEFT JOIN LATERAL (
    SELECT nav_value, nav_date
    FROM nav_history nh
    WHERE nh.scheme_code = sm.scheme_code
    ORDER BY nh.nav_date DESC LIMIT 1
) nh ON true
WHERE sm.is_active = true
  AND fs.fund_health_score IS NOT NULL;

-- Index for common filters
CREATE INDEX IF NOT EXISTS idx_mfd_monitoring_status ON v_mfd_scheme_monitoring(mfd_status);
CREATE INDEX IF NOT EXISTS idx_mfd_monitoring_score_band ON v_mfd_scheme_monitoring(score_band);
CREATE INDEX IF NOT EXISTS idx_mfd_monitoring_category ON v_mfd_scheme_monitoring(category);
CREATE INDEX IF NOT EXISTS idx_mfd_monitoring_amc ON v_mfd_scheme_monitoring(amc);

-- ============================================================
-- MFD CATEGORY RANKING VIEW
-- ============================================================
CREATE OR REPLACE VIEW v_mfd_category_rankings AS
SELECT
    sm.category,
    sm.scheme_code,
    sm.scheme_name,
    sm.amc,
    fs.fund_health_score,
    fs.category_rank,
    fs.category_percentile,
    fr.return_1y,
    fr.alpha_1y,
    fr.max_drawdown_1y,
    fr.volatility_1y,
    fr.consecutive_underperf_months,
    COALESCE(alert_counts.high, 0) AS high_alerts,
    COALESCE(alert_counts.medium, 0) AS medium_alerts,
    COALESCE(alert_counts.low, 0) AS low_alerts,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fs.fund_health_score DESC) AS score_rank,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fr.return_1y DESC NULLS LAST) AS return_rank,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fr.alpha_1y DESC NULLS LAST) AS alpha_rank,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fr.max_drawdown_1y ASC NULLS LAST) AS dd_rank,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fr.volatility_1y ASC NULLS LAST) AS vol_rank
FROM scheme_master sm
LEFT JOIN LATERAL (
    SELECT * FROM fund_scores fs
    WHERE fs.scheme_code = sm.scheme_code
    ORDER BY fs.as_of_date DESC LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT * FROM fund_rolling_returns fr
    WHERE fr.scheme_code = sm.scheme_code
    ORDER BY fr.as_of_date DESC LIMIT 1
) fr ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE severity = 'high') AS high,
        COUNT(*) FILTER (WHERE severity = 'medium') AS medium,
        COUNT(*) FILTER (WHERE severity = 'low') AS low
    FROM fund_alerts fa
    WHERE fa.scheme_code = sm.scheme_code
      AND fa.resolved_on IS NULL
) alert_counts ON true
WHERE sm.is_active = true
  AND fs.fund_health_score IS NOT NULL;

-- ============================================================
-- MFD ALERT ACTION VIEW (For bulk operations)
-- ============================================================
CREATE OR REPLACE VIEW v_mfd_alert_actions AS
SELECT
    fa.alert_id,
    fa.scheme_code,
    sm.scheme_name,
    sm.category,
    sm.amc,
    fa.alert_type,
    fa.severity,
    fa.triggered_on,
    fa.details->>'condition' AS trigger_condition,
    fa.details->'feature_values' AS trigger_values,
    fs.fund_health_score,
    fs.category_percentile,
    fr.return_1y,
    fr.alpha_1y,
    fr.max_drawdown_1y,
    fr.consecutive_underperf_months,
    CASE 
        WHEN fa.severity = 'high' THEN 1
        WHEN fa.severity = 'medium' THEN 2
        ELSE 3
    END AS priority_order
FROM fund_alerts fa
JOIN scheme_master sm ON fa.scheme_code = sm.scheme_code
LEFT JOIN LATERAL (
    SELECT fund_health_score, category_percentile
    FROM fund_scores fs
    WHERE fs.scheme_code = sm.scheme_code
    ORDER BY fs.as_of_date DESC LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT return_1y, alpha_1y, max_drawdown_1y, consecutive_underperf_months
    FROM fund_rolling_returns fr
    WHERE fr.scheme_code = sm.scheme_code
    ORDER BY fr.as_of_date DESC LIMIT 1
) fr ON true
WHERE fa.resolved_on IS NULL
ORDER BY priority_order, fa.triggered_on DESC;

-- ============================================================
-- MFD PIPELINE HEALTH VIEW
-- ============================================================
CREATE OR REPLACE VIEW v_mfd_pipeline_health AS
SELECT
    prl.as_of_date,
    prl.status,
    prl.schemes_processed,
    prl.folios_processed,
    prl.alerts_generated,
    prl.scores_computed,
    prl.started_at,
    prl.completed_at,
    EXTRACT(EPOCH FROM (prl.completed_at - prl.started_at)) AS duration_seconds,
    -- Data freshness indicators
    (SELECT MAX(nav_date) FROM nav_history) AS latest_nav_date,
    (SELECT MAX(as_of_date) FROM fund_scores) AS latest_score_date,
    (SELECT MAX(triggered_on) FROM fund_alerts) AS latest_alert_date,
    -- Data completeness
    (SELECT COUNT(*) FROM scheme_master WHERE is_active = true) AS total_active_schemes,
    (SELECT COUNT(DISTINCT scheme_code) FROM fund_scores WHERE as_of_date = prl.as_of_date) AS schemes_scored,
    (SELECT COUNT(DISTINCT scheme_code) FROM fund_alerts WHERE triggered_on = prl.as_of_date) AS schemes_with_alerts
FROM pipeline_run_log prl
ORDER BY prl.started_at DESC
LIMIT 30;

-- ============================================================
-- MFD MATERIALIZED VIEWS (For high-performance dashboards)
-- ============================================================

-- Category peer comparison for MFD peer analysis
CREATE MATERIALIZED VIEW mv_mfd_category_peer_stats AS
SELECT
    sm.category,
    COUNT(*) AS scheme_count,
    ROUND(AVG(fs.fund_health_score)::numeric, 2) AS avg_score,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY fs.fund_health_score) AS p25_score,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY fs.fund_health_score) AS median_score,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY fs.fund_health_score) AS p75_score,
    ROUND(AVG(fr.return_1y)::numeric, 4) AS avg_return_1y,
    ROUND(AVG(fr.alpha_1y)::numeric, 4) AS avg_alpha_1y,
    ROUND(AVG(fr.max_drawdown_1y)::numeric, 4) AS avg_dd_1y,
    ROUND(AVG(fr.volatility_1y)::numeric, 4) AS avg_vol_1y,
    COUNT(*) FILTER (WHERE alert_counts.high > 0) AS schemes_with_high_alerts,
    COUNT(*) FILTER (WHERE alert_counts.medium > 0) AS schemes_with_medium_alerts
FROM scheme_master sm
LEFT JOIN LATERAL (
    SELECT * FROM fund_scores fs
    WHERE fs.scheme_code = sm.scheme_code
    ORDER BY fs.as_of_date DESC LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT * FROM fund_rolling_returns fr
    WHERE fr.scheme_code = sm.scheme_code
    ORDER BY fr.as_of_date DESC LIMIT 1
) fr ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE severity = 'high') AS high,
        COUNT(*) FILTER (WHERE severity = 'medium') AS medium
    FROM fund_alerts fa
    WHERE fa.scheme_code = sm.scheme_code
      AND fa.resolved_on IS NULL
) alert_counts ON true
WHERE sm.is_active = true
  AND fs.fund_health_score IS NOT NULL
GROUP BY sm.category;

CREATE UNIQUE INDEX idx_mv_mfd_category_peer_stats_category
    ON mv_mfd_category_peer_stats(category);

-- MFD portfolio summary (if folios are loaded)
CREATE MATERIALIZED VIEW mv_mfd_folio_summary AS
SELECT
    sm.amc,
    sm.category,
    COUNT(DISTINCT cf.folio_id) AS folio_count,
    COUNT(DISTINCT cf.scheme_code) AS scheme_count,
    SUM(cf.invested_value) AS total_invested,
    SUM(cf.current_value) AS total_current,
    SUM(cf.current_value - cf.invested_value) AS total_unrealized_pnl,
    ROUND(AVG(fs.fund_health_score)::numeric, 2) AS avg_fund_score,
    MIN(fs.fund_health_score) AS min_fund_score,
    MAX(fs.fund_health_score) AS max_fund_score,
    COUNT(DISTINCT CASE WHEN alert_counts.high > 0 THEN cf.scheme_code END) AS schemes_with_high_alerts,
    COUNT(DISTINCT CASE WHEN alert_counts.medium > 0 THEN cf.scheme_code END) AS schemes_with_medium_alerts
FROM client_folios cf
JOIN scheme_master sm ON cf.scheme_code = sm.scheme_code
LEFT JOIN LATERAL (
    SELECT * FROM fund_scores fs
    WHERE fs.scheme_code = sm.scheme_code
    ORDER BY fs.as_of_date DESC LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE severity = 'high') AS high,
        COUNT(*) FILTER (WHERE severity = 'medium') AS medium
    FROM fund_alerts fa
    WHERE fa.scheme_code = sm.scheme_code
      AND fa.resolved_on IS NULL
) alert_counts ON true
GROUP BY sm.amc, sm.category;

CREATE INDEX idx_mv_mfd_folio_summary_amc ON mv_mfd_folio_summary(amc);
CREATE INDEX idx_mv_mfd_folio_summary_category ON mv_mfd_folio_summary(category);

-- ============================================================
-- REFRESH FUNCTION FOR MATERIALIZED VIEWS
-- ============================================================
CREATE OR REPLACE FUNCTION refresh_mfd_materialized_views()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_mfd_category_peer_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_mfd_folio_summary;
END;
$$;

-- ============================================================
-- GRANTS FOR MFD ROLE
-- ============================================================
-- GRANT SELECT ON v_mfd_scheme_monitoring TO mfd_role;
-- GRANT SELECT ON v_mfd_category_rankings TO mfd_role;
-- GRANT SELECT ON v_mfd_alert_actions TO mfd_role;
-- GRANT SELECT ON v_mfd_pipeline_health TO mfd_role;
-- GRANT SELECT ON mv_mfd_category_peer_stats TO mfd_role;
-- GRANT SELECT ON mv_mfd_folio_summary TO mfd_role;
-- GRANT EXECUTE ON FUNCTION refresh_mfd_materialized_views TO mfd_role;