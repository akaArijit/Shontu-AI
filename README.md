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

- **Scheme deduplication** â€” 5,000 folios to ~400 unique schemes (exact/fuzzy/heuristic matching)
- **Benchmark mapping** â€” explicit AMC-declared + SEBI category fallback (20 categories)
- **Data ingestion** â€” AMFI NAV, mfapi.in, NSE Indices TRI, RBI, MOSPI, FBIL (pluggable, error-isolated)
- **Feature engineering** â€” rolling returns, alpha, drawdown, volatility, category percentile, correlation
- **Rule engine** â€” 9 YAML-config alert rules (deterministic, explainable, category overrides)
- **Scoring engine** â€” 0-100 weighted fund health score with full explainability + penalty
- **MFD dashboard** â€” overview, alerts, category rankings, pipeline health, CSV import/export, settings

## Repository structure

```
fund-engine/
+-- apps/
|   +-- api/                     # FastAPI + batch pipeline (Railway)
|   |   +-- src/fund_engine/
|   |   |   +-- api/             # HTTP layer (app factory, routes)
|   |   |   +-- core/            # settings, logging, paths
|   |   |   +-- db/              # connection, repository, readers/writers
|   |   |   +-- domain/          # resolution, features, rules, scoring
|   |   |   +-- ingestion/       # AMFI/mfapi/NSE fetchers
|   |   |   +-- services/        # pipeline, seeding, migrations
|   |   +-- tests/               # mirrors the package layout
|   |   +-- config/              # scoring_config.yaml, rules.yaml, mappings
|   |   +-- migrations/          # numbered SQL migrations
|   |   +-- scripts/             # thin CLI wrappers
|   |   +-- Dockerfile           # Railway API + batch image
|   |   +-- pyproject.toml       # pytest/tooling config
|   |   +-- requirements.txt
|   +-- web/                     # Next.js 14 dashboard (Vercel)
|       +-- src/app/             # Dashboard, Alerts, Rankings, CSV, Pipeline, Settings
|       +-- src/components/      # layout, dashboard, UI primitives
|       +-- src/lib/             # API client, mock API, brand, utils
|       +-- package.json
+-- docs/                        # Architecture, API reference, deployment, dev guide
+-- .github/workflows/ci-cd.yml  # Tests, web build, Docker build, migrations
+-- docker-compose.yml           # Local Postgres + API + batch
+-- package.json                 # Root convenience scripts
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
pip install -r requirements.txt

# Apply pending migrations (records them in schema_migrations)
DATABASE_URL=postgresql://fund_user:fund_password@localhost:5432/fund_engine \
  python scripts/apply_migrations.py

# The app lives in src/fund_engine; uvicorn can load it with --app-dir
uvicorn fund_engine.api.main:app --app-dir src --reload --port 8000
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
npm run migrate        # apply pending SQL migrations
npm run pipeline       # one nightly pipeline run (needs DATABASE_URL)
npm run seed:benchmarks
```

## Tests

```bash
cd apps/api
python -m pytest -q
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
| API | Railway (Dockerfile) | `apps/api` | Dockerfile auto-detected; legacy `railway.json` |
| Batch / cron | Railway (Dockerfile) | `apps/api` | Dockerfile auto-detected; cron `0 2 * * *` UTC |
| Database | Railway PostgreSQL | â€” | plugin `DATABASE_URL` |

Both platforms auto-deploy on push to `master`. Railway deprecated
Config-as-Code in 2026 â€” new services are configured in the dashboard (root
directory, start command, healthcheck, cron), and the `railway*.json` files in
`apps/api` are kept only for legacy services. See
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
| [apps/api/README.md](apps/api/README.md) | Backend src layout, local commands, batch entry points |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, data flow, database schema |
| [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Development setup, adding sources/rules, testing |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | REST API endpoints, contracts, error codes |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Vercel + Railway infrastructure, CI/CD, runbooks |

## Roadmap

### Phase 1 (current) â€” deterministic foundation
- Scheme deduplication & benchmark mapping
- Data ingestion (6 sources)
- Feature engineering (returns, risk, category-relative)
- Rule engine (9 alert types)
- Scoring engine (0-100, weighted, explainable)
- Database schema, 15 MFD API endpoints, dashboard

### Phase 2 (future) â€” ML enhancements
- Predictive underperformance (XGBoost + SHAP)
- Manager style drift detection
- NAV anomaly detection
- Category reclassification

**Rule:** ML must beat the rule engine on backtest before deployment. SHAP
explainability is mandatory.

## License

MIT License â€” see LICENSE for details.
