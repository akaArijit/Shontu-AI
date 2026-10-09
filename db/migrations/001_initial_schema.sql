-- Fund Monitoring & Scoring Engine - Initial Schema
-- Version: 1.0
-- Description: Core tables for scheme registry, NAV history, benchmarks, scores, alerts, and client folios

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ============================================================
-- SCHEME MASTER (Deduplicated registry)
-- ============================================================
CREATE TABLE scheme_master (
    scheme_code       TEXT PRIMARY KEY,
    scheme_name       TEXT NOT NULL,
    amc               TEXT NOT NULL,
    category          TEXT NOT NULL,
    sub_category      TEXT,
    benchmark_index   TEXT REFERENCES benchmark_master(benchmark_code),
    fund_manager      TEXT,
    expense_ratio     NUMERIC(5,2),
    aum               NUMERIC(15,2),          -- in crores
    inception_date    DATE,
    last_updated      TIMESTAMPTZ DEFAULT NOW(),
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scheme_master_category ON scheme_master(category);
CREATE INDEX idx_scheme_master_amc ON scheme_master(amc);
CREATE INDEX idx_scheme_master_benchmark ON scheme_master(benchmark_index);

-- ============================================================
-- BENCHMARK MASTER
-- ============================================================
CREATE TABLE benchmark_master (
    benchmark_code    TEXT PRIMARY KEY,
    benchmark_name    TEXT NOT NULL,
    category          TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- NAV HISTORY (Daily NAV per scheme)
-- ============================================================
CREATE TABLE nav_history (
    scheme_code       TEXT NOT NULL REFERENCES scheme_master(scheme_code),
    nav_date          DATE NOT NULL,
    nav_value         NUMERIC(15,4) NOT NULL,
    source            TEXT NOT NULL DEFAULT 'amfi',  -- amfi, mfapi, manual
    fetched_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (scheme_code, nav_date)
);

CREATE INDEX idx_nav_history_date ON nav_history(nav_date DESC);
CREATE INDEX idx_nav_history_scheme_date ON nav_history(scheme_code, nav_date DESC);

-- ============================================================
-- BENCHMARK HISTORY (Daily index values)
-- ============================================================
CREATE TABLE benchmark_history (
    benchmark_code    TEXT NOT NULL REFERENCES benchmark_master(benchmark_code),
    index_date        DATE NOT NULL,
    index_value       NUMERIC(15,4) NOT NULL,
    source            TEXT NOT NULL DEFAULT 'nse',
    fetched_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (benchmark_code, index_date)
);

CREATE INDEX idx_benchmark_history_date ON benchmark_history(index_date DESC);

-- ============================================================
-- FUND ROLLING RETURNS (Materialized, refreshed nightly)
-- ============================================================
CREATE TABLE fund_rolling_returns (
    scheme_code       TEXT NOT NULL REFERENCES scheme_master(scheme_code),
    as_of_date        DATE NOT NULL,
    return_1m         NUMERIC(8,4),
    return_3m         NUMERIC(8,4),
    return_6m         NUMERIC(8,4),
    return_1y         NUMERIC(8,4),
    return_3y         NUMERIC(8,4),
    return_5y         NUMERIC(8,4),
    alpha_1m          NUMERIC(8,4),
    alpha_3m          NUMERIC(8,4),
    alpha_6m          NUMERIC(8,4),
    alpha_1y          NUMERIC(8,4),
    alpha_3y          NUMERIC(8,4),
    alpha_5y          NUMERIC(8,4),
    max_drawdown_1y   NUMERIC(8,4),
    max_drawdown_3y   NUMERIC(8,4),
    volatility_1m     NUMERIC(8,4),
    volatility_3m     NUMERIC(8,4),
    volatility_1y     NUMERIC(8,4),
    volatility_3y     NUMERIC(8,4),
    category_percentile_1m NUMERIC(5,2),
    category_percentile_3m NUMERIC(5,2),
    category_percentile_1y NUMERIC(5,2),
    category_percentile_3y NUMERIC(5,2),
    category_rank_1m  INTEGER,
    category_rank_3m  INTEGER,
    category_rank_1y  INTEGER,
    category_rank_3y  INTEGER,
    consecutive_underperf_months INTEGER DEFAULT 0,
    consecutive_underperf_quarters INTEGER DEFAULT 0,
    correlation_to_benchmark_1y NUMERIC(5,4),
    correlation_to_benchmark_3y NUMERIC(5,4),
    computed_at       TIMESTAMPTZ DEFAULT NOW(),
    scoring_config_version TEXT,
    PRIMARY KEY (scheme_code, as_of_date)
);

CREATE INDEX idx_frr_date ON fund_rolling_returns(as_of_date DESC);

-- ============================================================
-- FUND SCORES (0-100 health score with breakdown)
-- ============================================================
CREATE TABLE fund_scores (
    scheme_code           TEXT NOT NULL REFERENCES scheme_master(scheme_code),
    as_of_date            DATE NOT NULL,
    fund_health_score     INTEGER NOT NULL CHECK (fund_health_score BETWEEN 0 AND 100),
    category_rank         INTEGER,
    category_percentile   NUMERIC(5,2),
    score_breakdown       JSONB NOT NULL,  -- [{"component": "...", "points": 25, "max_points": 30, "reason": "...", "raw_value": 0.06}, ...]
    penalty               NUMERIC(5,2) DEFAULT 0,
    scoring_config_version TEXT NOT NULL,
    computed_at           TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (scheme_code, as_of_date)
);

CREATE INDEX idx_fund_scores_date ON fund_scores(as_of_date DESC);
CREATE INDEX idx_fund_scores_score ON fund_scores(fund_health_score DESC);

-- ============================================================
-- FUND ALERTS (Rule engine output)
-- ============================================================
CREATE TABLE fund_alerts (
    alert_id            BIGSERIAL PRIMARY KEY,
    scheme_code         TEXT NOT NULL REFERENCES scheme_master(scheme_code),
    alert_type          TEXT NOT NULL,  -- 'underperform_3m', 'below_top50_category', etc.
    severity            TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    triggered_on        DATE NOT NULL,
    resolved_on         DATE,
    details             JSONB NOT NULL,  -- {"rule_id": "...", "condition": "...", "feature_values": {...}}
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fund_alerts_scheme_date ON fund_alerts(scheme_code, triggered_on DESC);
CREATE INDEX idx_fund_alerts_type_severity ON fund_alerts(alert_type, severity);
CREATE INDEX idx_fund_alerts_resolved ON fund_alerts(resolved_on) WHERE resolved_on IS NULL;

-- ============================================================
-- CLIENT FOLIOS (Thin mapping, no computation)
-- ============================================================
CREATE TABLE client_folios (
    folio_id            TEXT PRIMARY KEY,
    client_id           TEXT NOT NULL,
    scheme_code         TEXT NOT NULL REFERENCES scheme_master(scheme_code),
    units               NUMERIC(15,4) NOT NULL,
    invested_value      NUMERIC(15,2) NOT NULL,
    current_value       NUMERIC(15,2) NOT NULL,
    purchase_date       DATE,
    last_sync           TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_client_folios_client ON client_folios(client_id);
CREATE INDEX idx_client_folios_scheme ON client_folios(scheme_code);

-- ============================================================
-- MACRO INDICATORS (Context only, not joined into scoring)
-- ============================================================
CREATE TABLE macro_indicators (
    indicator_name      TEXT NOT NULL,
    indicator_date      DATE NOT NULL,
    value               NUMERIC(15,4) NOT NULL,
    source              TEXT NOT NULL,
    fetched_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (indicator_name, indicator_date)
);

CREATE INDEX idx_macro_indicators_date ON macro_indicators(indicator_date DESC);

-- ============================================================
-- SCORING CONFIG HISTORY (Audit trail)
-- ============================================================
CREATE TABLE scoring_config_history (
    version             TEXT PRIMARY KEY,
    effective_date      DATE NOT NULL,
    config_json         JSONB NOT NULL,
    created_by          TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- RULES CONFIG HISTORY (Audit trail)
-- ============================================================
CREATE TABLE rules_config_history (
    version             TEXT PRIMARY KEY,
    effective_date      DATE NOT NULL,
    config_json         JSONB NOT NULL,
    created_by          TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- PIPELINE RUN LOG (Operational monitoring)
-- ============================================================
CREATE TABLE pipeline_run_log (
    run_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    status              TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'partial')),
    as_of_date          DATE NOT NULL,
    schemes_processed   INTEGER DEFAULT 0,
    folios_processed    INTEGER DEFAULT 0,
    alerts_generated    INTEGER DEFAULT 0,
    scores_computed     INTEGER DEFAULT 0,
    error_message       TEXT,
    metadata            JSONB DEFAULT '{}'
);

CREATE INDEX idx_pipeline_run_date ON pipeline_run_log(started_at DESC);