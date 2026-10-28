# Fund Monitoring & Scoring Engine

A deterministic, explainable fund monitoring system for MFDs (Mutual Fund
Distributors) managing 500+ clients and 5,000+ folios across ~400 unique mutual
fund schemes.

**Monorepo layout:** FastAPI API + nightly batch on **Railway**, Next.js
dashboard on **Vercel**, PostgreSQL on **Railway**.

## Core principle

**Compute once per unique scheme (~400), join to all folios (~5,000) at read
time.** This 10x+ compute reduction is the architectural foundation.

```
5000 FOLIOS -> [DEDUPLICATION] -> 400 SCHEMES -> [FEATURES] -> [RULES] -> [SCORING] -> [CLIENT OUTPUT]
     |              10x reduction          |         |         |           |
     v                                     v         v         v           v
folio_id                              scheme_code  alerts   0-100 score  JOIN
client_id                              benchmark    reason   breakdown   -> Portfolio
```

## Features

- **Scheme deduplication** — 5,000 folios to ~400 unique schemes (exact/fuzzy/heuristic matching)
- **Benchmark mapping** — explicit AMC-declared + SEBI category fallback (20 categories)
- **Data ingestion** — AMFI NAV, mfapi.in, NSE Indices TRI, RBI, MOSPI, FBIL (pluggable, error-isolated)
- **Feature engineering** — rolling returns, alpha, drawdown, volatility, category percentile, correlation
- **Rule engine** — 9 YAML-config alert rules (deterministic, explainable, category overrides)
- **Scoring engine** — 0-100 weighted fund health score with full explainability + penalty
- **MFD dashboard** — overview, alerts, category rankings, pipeline health, CSV import/export, settings

## Repository structure

```
fund-engine/
├── apps/
│   ├── api/                     # FastAPI + batch pipeline (Railway)
│   │   ├── api/                 # HTTP layer (routes, repository, models)
│   │   ├── config/              # scoring_config.yaml, rules.yaml, mappings
│   │   ├── db/                  # migrations, persistence, reader queries
│   │   ├── features/            # feature engineering
│   │   ├── ingestion/           # AMFI/mfapi/NSE fetchers
│   │   ├── resolution/          # dedup + benchmark mapping
│   │   ├── rules/               # alert rule engine
│   │   ├── scoring/             # 0-100 scoring engine
│   │   ├── scripts/             # run_nightly, seed_benchmarks, apply_migrations
│   │   ├── Dockerfile           # Railway API + batch image
│   │   ├── railway.json         # Railway API config
│   │   ├── railway.batch.json   # Railway cron config
│   │   └── requirements.txt
│   └── web/                     # Next.js 14 dashboard (Vercel)
│       ├── src/app/             # Dashboard, Alerts, Rankings, CSV, Pipeline, Settings
│       ├── src/components/      # layout, dashboard, UI primitives
│       ├── src/lib/             # API client, mock API, brand, utils
│       └── package.json
├── docs/                        # Architecture, API reference, deployment, dev guide
├── .github/workflows/ci-cd.yml  # Tests, web build, Docker build, migrations
├── docker-compose.yml           # Local Postgres + API + batch
└── package.json                 # Root convenience scripts
```

## Quick start (local)

### 1. Database

```bash
docker compose up -d postgres
```

Migrations are applied explicitly in the next step with the idempotent runner,
so local and production schemas are created the same way.

### 2. API

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt -r api/requirements.txt

# Apply pending migrations (records them in schema_migrations)
DATABASE_URL=postgresql://fund_user:fund_password@localhost:5432/fund_engine \
  python scripts/apply_migrations.py

uvicorn api.main:app --reload --port 8000
```

- Health: http://localhost:8000/health
- OpenAPI UI: http://localhost:8000/docs

### 3. Dashboard

```bash
cd apps/web
npm ci
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:3000. Set `NEXT_PUBLIC_USE_MOCK_API=true` (or
`localStorage.use_mock_api=true`) to demo the UI without an API.

### Root shortcuts

```bash
npm run dev            # dashboard dev server
npm run build          # production dashboard build
npm run test:api       # full pytest suite (194 tests)
npm run pipeline       # one nightly pipeline run (needs DATABASE_URL)
npm run seed:benchmarks
```

## Tests

```bash
cd apps/api
python -m pytest resolution ingestion features rules scoring db api scripts test_e2e_pipeline.py -q
```

| Module | Tests |
|--------|-------|
| Resolution | 40 |
| Ingestion | 27 |
| Features | 38 |
| Rules | 15 |
| Scoring | 17 |
| API | 32 |
| Database persistence | 8 |
| Pipeline & scripts | 16 |
| End-to-end | 1 |
| **Total** | **194** |

## Deployment

| Component | Platform | Root directory | Config |
|-----------|----------|----------------|--------|
| Dashboard | Vercel | `apps/web` | `apps/web/next.config.js`, env in Vercel |
| API | Railway (Dockerfile) | `apps/api` | `apps/api/railway.json` |
| Batch / cron | Railway (Dockerfile) | `apps/api` | `apps/api/railway.batch.json`, `0 2 * * *` UTC |
| Database | Railway PostgreSQL | — | plugin `DATABASE_URL` |

Both platforms auto-deploy on push to `master`. See
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the full runbook: project setup,
migrations, seeding, environment variables, CORS for Vercel previews,
monitoring, backups, rollback, and troubleshooting.

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| Deduplication first | Compute scales with scheme count, not folio count |
| No ML in v1 | Statistical/rule-based is explainable, defensible, needs no training data |
| YAML configs | Business users can tune thresholds without code changes |
| Category-relative metrics | Absolute returns meaningless without peer context |
| Explainable everything | Every alert/score includes `reason`, `raw_value`, `condition` |
| Error isolation | One failing ingestion source doesn't break the pipeline |

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, data flow, database schema |
| [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Development setup, adding sources/rules, testing |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | REST API endpoints, contracts, error codes |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Vercel + Railway infrastructure, CI/CD, runbooks |

## Roadmap

### Phase 1 (current) — deterministic foundation
- Scheme deduplication & benchmark mapping
- Data ingestion (6 sources)
- Feature engineering (returns, risk, category-relative)
- Rule engine (9 alert types)
- Scoring engine (0-100, weighted, explainable)
- Database schema, 15 MFD API endpoints, dashboard

### Phase 2 (future) — ML enhancements
- Predictive underperformance (XGBoost + SHAP)
- Manager style drift detection
- NAV anomaly detection
- Category reclassification

**Rule:** ML must beat the rule engine on backtest before deployment. SHAP
explainability is mandatory.

## License

MIT License — see LICENSE for details.
