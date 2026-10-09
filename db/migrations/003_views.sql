-- Fund Monitoring & Scoring Engine - Materialized Views & Helper Views
-- Version: 1.0
-- Description: Pre-computed views for common query patterns

-- ============================================================
-- SCHEME SUMMARY VIEW (Latest score + key metrics)
-- ============================================================
CREATE OR REPLACE VIEW v_scheme_summary AS
SELECT
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
    sm.is_active,
    -- Latest score
    fs.fund_health_score,
    fs.category_rank,
    fs.category_percentile,
    fs.penalty,
    fs.scoring_config_version,
    fs.computed_at AS score_computed_at,
    -- Latest features
    fr.return_1y,
    fr.alpha_1y,
    fr.max_drawdown_1y,
    fr.volatility_1y,
    fr.category_percentile_1y,
    fr.category_rank_1y,
    fr.consecutive_underperf_months,
    fr.correlation_to_benchmark_1y,
    fr.computed_at AS features_computed_at,
    -- Alert summary
    COALESCE(alert_counts.high, 0) AS high_alerts,
    COALESCE(alert_counts.medium, 0) AS medium_alerts,
    COALESCE(alert_counts.low, 0) AS low_alerts,
    alert_counts.total AS total_alerts
FROM scheme_master sm
LEFT JOIN benchmark_master bm ON sm.benchmark_index = bm.benchmark_code
LEFT JOIN LATERAL (
    SELECT * FROM fund_scores fs
    WHERE fs.scheme_code = sm.scheme_code
    ORDER BY fs.as_of_date DESC
    LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT * FROM fund_rolling_returns fr
    WHERE fr.scheme_code = sm.scheme_code
    ORDER BY fr.as_of_date DESC
    LIMIT 1
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
WHERE sm.is_active = true;

-- ============================================================
-- CATEGORY RANKING VIEW (Latest rankings per category)
-- ============================================================
CREATE OR REPLACE VIEW v_category_rankings AS
SELECT
    sm.category,
    sm.scheme_code,
    sm.scheme_name,
    fs.fund_health_score,
    fs.category_rank,
    fs.category_percentile,
    fs.fund_health_score,
    fr.return_1y,
    fr.alpha_1y,
    fr.max_drawdown_1y,
    fr.volatility_1y,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fs.fund_health_score DESC) AS score_rank,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fr.return_1y DESC NULLS LAST) AS return_rank,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fr.alpha_1y DESC NULLS LAST) AS alpha_rank,
    ROW_NUMBER() OVER (PARTITION BY sm.category ORDER BY fr.max_drawdown_1y ASC NULLS LAST) AS dd_rank
FROM scheme_master sm
LEFT JOIN LATERAL (
    SELECT * FROM fund_scores fs
    WHERE fs.scheme_code = sm.scheme_code
    ORDER BY fs.as_of_date DESC
    LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT * FROM fund_rolling_returns fr
    WHERE fr.scheme_code = sm.scheme_code
    ORDER BY fr.as_of_date DESC
    LIMIT 1
) fr ON true
WHERE sm.is_active = true
  AND fs.fund_health_score IS NOT NULL;

-- ============================================================
-- CLIENT PORTFOLIO VIEW (Denormalized for API)
-- ============================================================
CREATE OR REPLACE VIEW v_client_portfolio AS
SELECT
    cf.client_id,
    cf.folio_id,
    cf.scheme_code,
    sm.scheme_name,
    sm.category,
    sm.benchmark_index,
    bm.benchmark_name,
    cf.units,
    cf.invested_value,
    cf.current_value,
    (cf.current_value - cf.invested_value) AS unrealized_pnl,
    CASE WHEN cf.invested_value > 0
         THEN ROUND(((cf.current_value - cf.invested_value) / cf.invested_value) * 100, 2)
         ELSE NULL END AS pnl_percentage,
    fs.fund_health_score,
    fs.category_rank,
    fs.category_percentile,
    fs.penalty,
    -- Alert summary
    COALESCE(alert_counts.high, 0) AS high_alerts,
    COALESCE(alert_counts.medium, 0) AS medium_alerts,
    COALESCE(alert_counts.low, 0) AS low_alerts,
    -- Latest NAV
    nh.nav_value AS latest_nav,
    nh.nav_date AS latest_nav_date
FROM client_folios cf
JOIN scheme_master sm ON cf.scheme_code = sm.scheme_code
LEFT JOIN benchmark_master bm ON sm.benchmark_index = bm.benchmark_code
LEFT JOIN LATERAL (
    SELECT * FROM fund_scores fs
    WHERE fs.scheme_code = sm.scheme_code
    ORDER BY fs.as_of_date DESC
    LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE severity = 'high') AS high,
        COUNT(*) FILTER (WHERE severity = 'medium') AS medium,
        COUNT(*) FILTER (WHERE severity = 'low') AS low
    FROM fund_alerts fa
    WHERE fa.scheme_code = sm.scheme_code
      AND fa.resolved_on IS NULL
) alert_counts ON true
LEFT JOIN LATERAL (
    SELECT nav_value, nav_date
    FROM nav_history nh
    WHERE nh.scheme_code = sm.scheme_code
    ORDER BY nh.nav_date DESC
    LIMIT 1
) nh ON true;

-- ============================================================
-- ALERT SUMMARY VIEW (For dashboard)
-- ============================================================
CREATE OR REPLACE VIEW v_alert_summary AS
SELECT
    fa.alert_type,
    fa.severity,
    COUNT(*) AS count,
    COUNT(DISTINCT fa.scheme_code) AS schemes_affected,
    MAX(fa.triggered_on) AS latest_triggered
FROM fund_alerts fa
WHERE fa.resolved_on IS NULL
GROUP BY fa.alert_type, fa.severity
ORDER BY
    CASE fa.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
    COUNT(*) DESC;

-- ============================================================
-- PIPELINE HEALTH VIEW
-- ============================================================
CREATE OR REPLACE VIEW v_pipeline_health AS
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
    -- Data freshness
    (SELECT MAX(nav_date) FROM nav_history) AS latest_nav_date,
    (SELECT MAX(as_of_date) FROM fund_scores) AS latest_score_date,
    (SELECT MAX(triggered_on) FROM fund_alerts) AS latest_alert_date
FROM pipeline_run_log prl
ORDER BY prl.started_at DESC
LIMIT 30;

-- ============================================================
-- MATERIALIZED VIEW: CATEGORY PEER COMPARISON
-- ============================================================
CREATE MATERIALIZED VIEW mv_category_peer_comparison AS
SELECT
    sm.category,
    COUNT(*) AS scheme_count,
    AVG(fs.fund_health_score)::numeric(5,2) AS avg_score,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fs.fund_health_score) AS median_score,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY fs.fund_health_score) AS p25_score,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY fs.fund_health_score) AS p75_score,
    AVG(fr.return_1y)::numeric(8,4) AS avg_return_1y,
    AVG(fr.alpha_1y)::numeric(8,4) AS avg_alpha_1y,
    AVG(fr.max_drawdown_1y)::numeric(8,4) AS avg_dd_1y,
    AVG(fr.volatility_1y)::numeric(8,4) AS avg_vol_1y
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
WHERE sm.is_active = true
  AND fs.fund_health_score IS NOT NULL
GROUP BY sm.category;

CREATE UNIQUE INDEX idx_mv_category_peer_comparison_category
    ON mv_category_peer_comparison(category);

-- ============================================================
-- MATERIALIZED VIEW: FOLIO AGGREGATION PER CLIENT
-- ============================================================
CREATE MATERIALIZED VIEW mv_client_portfolio_summary AS
SELECT
    cf.client_id,
    COUNT(DISTINCT cf.folio_id) AS folio_count,
    COUNT(DISTINCT cf.scheme_code) AS scheme_count,
    SUM(cf.invested_value) AS total_invested,
    SUM(cf.current_value) AS total_current,
    SUM(cf.current_value - cf.invested_value) AS total_unrealized_pnl,
    CASE WHEN SUM(cf.invested_value) > 0
         THEN ROUND((SUM(cf.current_value) - SUM(cf.invested_value)) / SUM(cf.invested_value) * 100, 2)
         ELSE NULL END AS total_pnl_percentage,
    AVG(fs.fund_health_score)::numeric(5,2) AS avg_fund_score,
    MIN(fs.fund_health_score) AS min_fund_score,
    MAX(fs.fund_health_score) AS max_fund_score,
    COUNT(DISTINCT CASE WHEN alert_counts.high > 0 THEN cf.scheme_code END) AS schemes_with_high_alerts,
    COUNT(DISTINCT CASE WHEN alert_counts.medium > 0 THEN cf.scheme_code END) AS schemes_with_medium_alerts,
    COUNT(DISTINCT CASE WHEN alert_counts.low > 0 THEN cf.scheme_code END) AS schemes_with_low_alerts
FROM client_folios cf
LEFT JOIN LATERAL (
    SELECT * FROM fund_scores fs
    WHERE fs.scheme_code = cf.scheme_code
    ORDER BY fs.as_of_date DESC LIMIT 1
) fs ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE severity = 'high') AS high,
        COUNT(*) FILTER (WHERE severity = 'medium') AS medium,
        COUNT(*) FILTER (WHERE severity = 'low') AS low
    FROM fund_alerts fa
    WHERE fa.scheme_code = cf.scheme_code
      AND fa.resolved_on IS NULL
) alert_counts ON true
GROUP BY cf.client_id;

CREATE UNIQUE INDEX idx_mv_client_portfolio_summary_client
    ON mv_client_portfolio_summary(client_id);

-- ============================================================
-- REFRESH FUNCTIONS
-- ============================================================
CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_category_peer_comparison;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_client_portfolio_summary;
END;
$$;

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;