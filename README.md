# Fund Monitoring & Scoring Engine

A deterministic, explainable fund monitoring system for MFDs (Mutual Fund Distributors) managing 500+ clients and 5,000+ folios across ~400 unique mutual fund schemes.

## Core Principle

**Compute once per unique scheme (~400), join to all folios (~5,000) at read time.** This 10x+ compute reduction is the architectural foundation.

## Architecture

```
5000 FOLIOS → [DEDUPLICATION] → 400 SCHEMES → [FEATURES] → [RULES] → [SCORING] → [CLIENT OUTPUT]
     │              10x reduction          │         │         │           │
     ▼                                     ▼         ▼         ▼           ▼
folio_id                              scheme_code  alerts   0-100 score  JOIN
client_id                              benchmark    reason   breakdown   → Portfolio
```

## Features

- **Scheme Deduplication**: 5000 folios → 400 unique schemes (exact/fuzzy/heuristic matching)
- **Benchmark Mapping**: Explicit AMC-declared + SEBI category fallback (20 categories)
- **Data Ingestion**: AMFI NAV, mfapi.in, NSE Indices, RBI, MOSPI, FBIL (pluggable, error-isolated)
- **Feature Engineering**: Rolling returns, alpha, drawdown, volatility, category percentile, correlation
- **Rule Engine**: 9 YAML-config alert rules (deterministic, explainable, category overrides)
- **Scoring Engine**: 0-100 weighted fund health score with full explainability + penalty
- **Client Output**: Folio → Scheme → Benchmark → Score → Alerts (zero per-client computation)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline demo
python test_e2e_pipeline.py

# Run individual module demos
python resolution/demo_scheme_dedup.py
python features/demo_feature_engineering.py
python rules/demo_rule_engine.py
python scoring/demo_scoring_engine.py

# Run all tests
python -m pytest resolution/ ingestion/ features/ rules/ scoring/ -v
```

## Project Structure

```
fund-engine/
├── resolution/          # Scheme dedup + benchmark mapping
├── ingestion/           # Data fetchers (AMFI, mfapi, NSE, RBI, etc.)
├── features/            # Feature engineering pipeline
├── rules/               # Rule engine (alerts)
├── scoring/             # Scoring engine (0-100)
├── api/                 # Express API (separate repo)
├── config/              # YAML configs (scoring, rules, benchmarks)
├── db/                  # SQL migrations
├── scripts/             # Operational scripts
├── docs/                # Documentation
│   ├── ARCHITECTURE.md
│   ├── DEVELOPER_GUIDE.md
│   ├── API_REFERENCE.md
│   └── DEPLOYMENT.md
├── test_e2e_pipeline.py # End-to-end integration test
├── requirements.txt
└── fund_monitoring_engine_architecture.md  # Original spec
```

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Complete system architecture, data flow, database schema |
| [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Development setup, adding sources/rules, testing |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | REST API endpoints, contracts, error codes |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Infrastructure, CI/CD, monitoring, runbooks |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Deduplication first | Compute scales with scheme count, not folio count |
| No ML in v1 | Statistical/rule-based is explainable, defensible, needs no training data |
| YAML configs | Business users can tune thresholds without code changes |
| Category-relative metrics | Absolute returns meaningless without peer context |
| Explainable everything | Every alert/score includes `reason`, `raw_value`, `condition` |
| Error isolation | One failing ingestion source doesn't break pipeline |

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| Resolution | 40 | ✅ |
| Ingestion | 17 | ✅ |
| Features | 38 | ✅ |
| Rules | 15 | ✅ |
| Scoring | 17 | ✅ |
| **Total** | **127** | ✅ |

```bash
# Run all tests
python -m pytest resolution/ ingestion/ features/ rules/ scoring/ -v
```

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete infrastructure setup:

- **Database**: Supabase (PostgreSQL)
- **Batch Jobs**: Render Cron Jobs (nightly 2 AM)
- **API**: Render Web Service (Express)
- **Frontend**: Vercel (Next.js)
- **Monitoring**: Render dashboards + Supabase alerts

## Roadmap

### Phase 1 (Current) — Deterministic Foundation
- ✅ Scheme deduplication & benchmark mapping
- ✅ Data ingestion (6 sources)
- ✅ Feature engineering (returns, risk, category-relative)
- ✅ Rule engine (9 alert types)
- ✅ Scoring engine (0-100, weighted, explainable)
- ✅ Database schema & API contracts

### Phase 2 (Future) — ML Enhancements
- Predictive underperformance (XGBoost + SHAP)
- Manager style drift detection
- NAV anomaly detection
- Category reclassification

**Rule**: ML must beat rule engine on backtest before deployment. SHAP explainability mandatory.

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/xxx`)
3. Add tests for new functionality
4. Run full test suite (`python -m pytest`)
5. Update documentation if needed
6. Submit PR