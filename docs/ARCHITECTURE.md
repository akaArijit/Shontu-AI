# Fund Monitoring & Scoring Engine — Architecture Documentation

## Overview

A deterministic, explainable fund monitoring system for MFDs (Mutual Fund Distributors) managing 500+ clients and 5,000+ folios across ~400 unique mutual fund schemes.

**Core Principle**: Compute once per unique scheme (~400), join to all folios (~5,000) at read time. This 10x+ compute reduction is the architectural foundation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         FUND MONITORING PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  INGESTION   │───►│ RESOLUTION   │───►│   FEATURES   │───►│    RULES     │  │
│  │   LAYER      │    │   LAYER      │    │  ENGINEERING │    │   ENGINE     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │                   │            │
│         ▼                   ▼                   ▼                   ▼            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ AMFI NAV     │    │ Dedup:       │    │ Rolling      │    │ 9 Alert      │  │
│  │ mfapi.in     │    │ 5000→400     │    │ returns      │    │  rules       │  │
│  │ NSE Indices  │    │ Benchmark    │    │ Alpha        │    │ YAML config  │  │
│  │ RBI/MOSPI    │    │ mapping      │    │ Drawdown     │    │ Deterministic│  │
│  │ FBIL         │    │              │    │ Volatility   │    │ Explainable  │  │
│  └──────────────┘    └──────────────┘    │ Percentile   │    └──────────────┘  │
│                                           │ Correlation  │           │          │
│                                           └──────────────┘           ▼          │
│                                                  │            ┌──────────────┐  │
│                                                  ▼            │   SCORING    │  │
│                                           ┌──────────────┐    │   ENGINE     │  │
│                                           │   STORAGE    │    │ 0-100 Score  │  │
│                                           │ PostgreSQL   │    │ Weighted     │  │
│                                           │ (Supabase)   │    │ Explainable  │  │
│                                           └──────────────┘    │ Penalty      │  │
│                                                                 └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │   API / DASHBOARD │
                          │   Next.js + Express│
                          └──────────────────┘
```

---

## Data Flow

### 1. Ingestion Layer (Nightly, ~2 AM)
| Source | Method | Frequency | Output |
|--------|--------|-----------|--------|
| AMFI NAVAll.txt | HTTP GET | Daily | ~4000 scheme NAV snapshots |
| mfapi.in | REST API (per scheme) | Daily | Full NAV history per scheme |
| NSE Indices | CSV/REST | Daily | TRI benchmark values |
| RBI | Scraping | As needed | Repo rate, bond yields |
| MOSPI | API/Scrape | Monthly | CPI, GDP |
| FBIL | API | Daily | USD/INR reference rate |

**Error Isolation**: Each source runs independently; one failure doesn't block others.

### 2. Resolution Layer
```
5000 Folios ──► [Scheme Dedup] ──► 400 Unique Schemes ──► [Benchmark Map] ──► Scheme + Benchmark
     │              │                        │                        │
     ▼              ▼                        ▼                        ▼
folio_id      scheme_code              category              benchmark_code
client_id     scheme_name              explicit >           NIFTY100_TRI, etc.
scheme_code   AMC                      fallback >           confidence: 1.0/0.7/0.3
```

**Deduplication Strategy** (in priority order):
1. Exact `scheme_code` match (AMFI/ISIN) — confidence 1.0
2. Fuzzy `scheme_name` + `AMC` match — confidence 0.9
3. Category + AMC heuristic — confidence 0.7
4. New scheme registration — confidence 0.0 (flagged for review)

**Benchmark Mapping** (two-tier):
1. Explicit AMC-declared benchmark (from factsheets) — confidence 1.0
2. SEBI category fallback rules — confidence 0.7

### 3. Feature Engineering (Per Scheme, Nightly)
| Feature | Method | Periods |
|---------|--------|---------|
| Rolling Returns | Simple (<1Y) / CAGR (≥1Y) | 1M, 3M, 6M, 1Y, 3Y, 5Y |
| Alpha | Fund Return - Benchmark Return | All periods |
| Max Drawdown | Peak-to-trough | 1Y, 3Y |
| Volatility | Annualized σ(daily returns) | 1M, 3M, 1Y, 3Y |
| Category Percentile | % peers with lower return | 1M, 3M, 1Y, 3Y |
| Category Rank | Ordinal rank (1=best) | 1M, 3M, 1Y, 3Y |
| Underperformance Streak | Consecutive months fund < bench | Months |
| Correlation | Daily returns vs benchmark | 1Y, 3Y |

### 4. Rule Engine (Deterministic, YAML-Config)
| Rule | Condition | Severity | Category Override |
|------|-----------|----------|-------------------|
| underperform_3m | streak ≥ 3 | MEDIUM | — |
| underperform_6m | streak ≥ 6 | HIGH | — |
| below_top25_category | pctl_1y < 75 | MEDIUM | — |
| below_top50_category | pctl_1y < 50 | HIGH | — |
| rank_decline | rank_1y - rank_3m > 10 | MEDIUM | — |
| benchmark_deviation | \|alpha_1y\| > 5% | LOW | Small Cap: 10%, Mid Cap: 8% |
| high_drawdown | max_dd_1y > 20% | MEDIUM | — |
| high_volatility | vol_1y > 25% | LOW | — |
| consecutive_underperf | streak ≥ 4 | MEDIUM | — |

### 5. Scoring Engine (0-100, Weighted, Explainable)
```
Score = Σ(component_points) - Penalty
Clamped to [0, 100]
```

| Component | Weight | Max Points | Scoring Method |
|-----------|--------|------------|----------------|
| Benchmark Outperformance | 30% | 30 | Alpha thresholds: >5%=30, >2%=20, >0%=10, >-2%=5, ≤-5%=0 |
| Category Ranking | 20% | 20 | Linear: 100th pctl=20, 50th=10, 0th=0 |
| Consistency | 20% | 20 | Inverse streak: 0 months=20, 36 months=0 |
| Drawdown Control | 15% | 15 | Inverse thresholds: <10%=15, <15%=10, <20%=5, ≤25%=0 |
| Volatility Adjusted | 15% | 15 | Inverse thresholds: <15%=15, <18%=10, <22%=5, ≤25%=0 |

**Penalty**: 2 pts per consecutive underperformance month, capped at 20 pts.

**Output**: JSON breakdown with `points`, `max_points`, `reason`, `raw_value` per component.

---

## Database Schema (PostgreSQL/Supabase)

```sql
-- Master scheme registry (deduplicated)
scheme_master (
    scheme_code TEXT PRIMARY KEY,
    scheme_name TEXT,
    amc TEXT,
    category TEXT,
    sub_category TEXT,
    benchmark_index TEXT REFERENCES benchmark_master,
    fund_manager TEXT,
    expense_ratio NUMERIC,
    aum NUMERIC,
    inception_date DATE,
    last_updated TIMESTAMP
)

-- Daily NAV time series
nav_history (
    scheme_code TEXT REFERENCES scheme_master,
    nav_date DATE,
    nav_value NUMERIC,
    PRIMARY KEY (scheme_code, nav_date)
)

-- Benchmark index values
benchmark_master (benchmark_code TEXT PRIMARY KEY, benchmark_name TEXT)
benchmark_history (benchmark_code, index_date, index_value, PK(benchmark_code, index_date))

-- Computed rolling returns (materialized, refreshed nightly)
fund_rolling_returns (scheme_code, as_of_date, return_1m...return_5y, PK(scheme_code, as_of_date))

-- Scoring output (versioned, explainable)
fund_scores (
    scheme_code, as_of_date,
    fund_health_score INT,          -- 0-100
    category_rank INT,
    category_percentile NUMERIC,
    score_breakdown JSONB,          -- [{"component": "...", "points": 25, "reason": "...", "raw_value": 0.06}, ...]
    PRIMARY KEY (scheme_code, as_of_date)
)

-- Alerts
fund_alerts (
    alert_id SERIAL PRIMARY KEY,
    scheme_code TEXT REFERENCES scheme_master,
    alert_type TEXT,                -- 'underperform_3m', etc.
    severity TEXT,                  -- low/medium/high
    triggered_on DATE,
    resolved_on DATE,
    details JSONB
)

-- Client folio mapping (thin, no computation)
client_folios (
    folio_id TEXT PRIMARY KEY,
    client_id TEXT,
    scheme_code TEXT REFERENCES scheme_master,
    units NUMERIC,
    invested_value NUMERIC,
    current_value NUMERIC
)

-- Macro context (not joined into scoring)
macro_indicators (indicator_name, indicator_date, value, PK(indicator_name, indicator_date))
```

**Client View** = `client_folios JOIN fund_scores JOIN fund_alerts` — zero per-client computation.

---

## Configuration

### Scoring Config (versioned, YAML)
```yaml
version: "1.0"
effective_date: "2024-01-01"
components:
  benchmark_outperformance:
    weight: 0.30
    max_points: 30
    scale_type: "alpha_threshold"
    scale_params:
      alpha_1y_thresholds:
        - [0.05, 30]
        - [0.02, 20]
        - [0.0, 10]
        - [-0.02, 5]
        - [-0.05, 0]
  category_ranking:
    weight: 0.20
    max_points: 20
    scale_type: "percentile_linear"
  consistency_of_returns:
    weight: 0.20
    max_points: 20
    scale_type: "positive_months_ratio"
    scale_params:
      lookback_months: 36
  drawdown_control:
    weight: 0.15
    max_points: 15
    scale_type: "inverse_threshold"
    scale_params:
      max_dd_thresholds:
        - [0.10, 15]
        - [0.15, 10]
        - [0.20, 5]
        - [0.25, 0]
  volatility_adjusted:
    weight: 0.15
    max_points: 15
    scale_type: "inverse_threshold"
    scale_params:
      vol_thresholds:
        - [0.15, 15]
        - [0.18, 10]
        - [0.22, 5]
        - [0.25, 0]
penalty_per_month: 2.0
penalty_cap: 20.0
```

### Rule Config (YAML)
```yaml
alert_rules:
  - id: underperform_3m
    alert_type: underperform_3m
    condition: "consecutive_underperf_months >= 3"
    severity: medium
    description: "Fund underperformed benchmark for 3+ consecutive months"
    category_overrides: {}
```

---

## API Contracts

### Get Fund Scores
```
GET /api/v1/scores?as_of_date=2024-01-15&scheme_codes=INF204K01VX3,INF767K01EW8
```
**Response**:
```json
{
  "as_of_date": "2024-01-15",
  "scores": [
    {
      "scheme_code": "INF204K01VX3",
      "fund_health_score": 82,
      "category_rank": 8,
      "category_percentile": 78.5,
      "breakdown": [
        {"component": "benchmark_outperformance", "points": 12, "max_points": 30, "reason": "Beat benchmark 24 of last 24 months", "raw_value": 0.024},
        {"component": "category_ranking", "points": 15, "max_points": 20, "reason": "Ranked #8 in category (78th percentile)", "raw_value": 78.5}
      ],
      "penalty": 0,
      "scoring_config_version": "1.0"
    }
  ]
}
```

### Get Alerts
```
GET /api/v1/alerts?as_of_date=2024-01-15&severity=high,medium
```
**Response**:
```json
{
  "as_of_date": "2024-01-15",
  "alerts": [
    {
      "alert_id": "underperform_6m_INF204K01VX3_2024-01-15_1",
      "scheme_code": "INF204K01VX3",
      "alert_type": "underperform_6m",
      "severity": "high",
      "triggered_on": "2024-01-15",
      "details": {
        "rule_id": "underperform_6m",
        "condition": "consecutive_underperf_months >= 6",
        "feature_values": {"consecutive_underperf_months": 7}
      }
    }
  ]
}
```

### Client Portfolio View
```
GET /api/v1/clients/{client_id}/portfolio?as_of_date=2024-01-15
```
**Response**:
```json
{
  "client_id": "CLIENT_001",
  "as_of_date": "2024-01-15",
  "holdings": [
    {
      "folio_id": "FOL_001",
      "scheme_code": "INF204K01VX3",
      "scheme_name": "HDFC Top 100 Fund",
      "category": "Large Cap",
      "benchmark": "Nifty 100 TRI",
      "units": 1000,
      "invested_value": 50000,
      "current_value": 65000,
      "score": 82,
      "category_rank": 8,
      "category_percentile": 78.5,
      "alerts": [
        {"alert_type": "benchmark_deviation", "severity": "low"}
      ]
    }
  ],
  "summary": {
    "total_invested": 500000,
    "total_current": 620000,
    "avg_score": 76.3,
    "high_alerts": 1,
    "medium_alerts": 2
  }
}
```

---

## Deployment

### Infrastructure
| Component | Platform | Notes |
|-----------|----------|-------|
| Database | Railway PostgreSQL (Supabase optional) | Managed, scheduled backups |
| Batch Jobs | Railway cron service | Nightly 02:00 UTC (07:30 IST) |
| API | Railway (FastAPI + Dockerfile) | `railway.json` healthcheck `/health` |
| Frontend | Railway (Next.js, Nixpacks) | `frontend/railway.json` |
| Scheduler | Railway cron schedule | Triggers Python batch |

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://...

# Config paths (defaults point at ./config)
SCORING_CONFIG_PATH=/app/config/scoring_config.yaml
RULES_CONFIG_PATH=/app/config/rules.yaml
BENCHMARK_MAPPINGS_PATH=/app/config/explicit_benchmark_mappings.json

# API
PORT=8000
ALLOWED_ORIGINS=https://fund-engine-web.up.railway.app
```

### Nightly Job Schedule
```
02:00 AM ──► Ingestion (AMFI, mfapi, NSE, RBI, MOSPI, FBIL)
02:30 AM ──► Resolution (Dedup + Benchmark Map)
02:45 AM ──► Feature Engineering (Rolling returns, alpha, DD, vol, pctl)
03:15 AM ──► Rule Engine (Evaluate 9 alert rules)
03:20 AM ──► Scoring Engine (Calculate 0-100 scores)
03:25 AM ──► Persist to PostgreSQL (fund_scores, fund_alerts, fund_rolling_returns)
03:30 AM ──► Refresh materialized views / API cache
03:35 AM ──► Notification queue (WhatsApp/email for new alerts)
```

---

## Monitoring & Observability

### Key Metrics
| Metric | Target | Alert If |
|--------|--------|----------|
| Ingestion success rate | 100% (per source) | < 100% for any source |
| Feature computation time | < 5 min | > 10 min |
| Rule evaluation time | < 30 sec | > 60 sec |
| Scoring time | < 30 sec | > 60 sec |
| End-to-end pipeline | < 30 min | > 45 min |
| Data freshness | < 24 hrs | > 36 hrs |

### Logs
- Structured JSON logging
- Correlation IDs across pipeline stages
- Alert on `ERROR` level logs

---

## Testing Strategy

| Layer | Test Type | Coverage |
|-------|-----------|----------|
| Resolution | Unit + Integration | 40 tests |
| Ingestion | Unit (mocked HTTP) | 17 tests |
| Features | Unit (statistical correctness) | 38 tests |
| Rules | Unit (condition evaluation) | 15 tests |
| Scoring | Unit (bounds, components) | 17 tests |
| E2E | Full pipeline | 1 integration test |

**Run All Tests**:
```bash
# From project root
python -m pytest resolution/ ingestion/ features/ rules/ scoring/ -v
```

---

## Extending the System

### Add New Data Source
1. Create new fetcher class extending `BaseFetcher`
2. Register in `IngestionOrchestrator`
3. Add corresponding data model (`NavRecord`, `BenchmarkRecord`, or `MacroRecord`)

### Add New Alert Rule
1. Add entry to `rules.yaml`
2. Restart rule engine (or hot-reload)
3. No code changes required

### Modify Scoring Weights
1. Update `scoring_config.yaml` with new version/date
2. Historical scores remain reproducible (config versioned)
4. No code changes required

### Add New Category
1. Add to `SchemeCategory` enum
2. Add fallback benchmark in `BenchmarkResolver`
3. Update scoring if category-specific thresholds needed

---

## Phase 2 (Future) — ML Enhancements

| Opportunity | Model | Prerequisites |
|-------------|-------|---------------|
| Predict underperformance | XGBoost/LightGBM | 12-24 months labeled alert history |
| Manager style drift | K-means on holdings | Holdings data access |
| NAV anomaly detection | Isolation Forest | Statistical z-score baseline first |
| Category reclassification | Unsupervised clustering | Return correlation profiles |

**Rule**: ML must beat rule engine on backtest before deployment. SHAP explainability mandatory.