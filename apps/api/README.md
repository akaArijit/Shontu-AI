# Fund Engine API

FastAPI service and nightly batch pipeline for the Fund Monitoring & Scoring
Engine. Deployed to Railway from this directory (`apps/api`).

## Layout

```
apps/api/
├── src/fund_engine/
│   ├── api/                      # HTTP layer
│   │   ├── main.py               # create_app(), CORS, /health
│   │   └── routes/               # /api/v1/mfd/* endpoints
│   ├── core/                     # settings, logging, filesystem paths
│   ├── db/                       # connection, repository, readers/writers
│   ├── domain/
│   │   ├── resolution/           # scheme dedup + benchmark mapping
│   │   ├── features/             # rolling returns, alpha, drawdown, ...
│   │   ├── rules/                # deterministic alert rules
│   │   └── scoring/              # 0-100 fund health score
│   ├── ingestion/                # AMFI, mfapi, NSE TRI, macro fetchers
│   └── services/                 # pipeline, benchmark seed, migrations
├── tests/                        # mirrors the package layout
├── config/                       # scoring_config.yaml, rules.yaml, mappings
├── migrations/                   # numbered SQL migrations (001-004)
├── scripts/                      # thin CLI wrappers (backwards compatible)
├── Dockerfile                    # Railway API + batch image
├── pyproject.toml                # pytest/tooling and package metadata
└── requirements.txt              # canonical API + pipeline dependencies
```

## Setup

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

Apply migrations, then start the API:

```bash
python scripts/apply_migrations.py          # needs DATABASE_URL
uvicorn fund_engine.api.main:app --app-dir src --reload --port 8000
```

- Health: `http://localhost:8000/health`
- OpenAPI UI: `http://localhost:8000/docs`
- Versioned API: `http://localhost:8000/api/v1/mfd/*`

## Batch pipeline

```bash
python scripts/run_nightly.py --no-ingest --dry-run
python scripts/seed_benchmarks.py --years 6
```

The wrappers add `src/` to `sys.path`. The module entry points are equivalent:

```bash
PYTHONPATH=src python -m fund_engine.services.pipeline
PYTHONPATH=src python -m fund_engine.services.benchmarks --years 6
PYTHONPATH=src python -m fund_engine.services.migrations --dry-run
```

## Tests

```bash
python -m pytest -q
```

`pyproject.toml` sets `testpaths = ["tests"]` and `pythonpath = ["src"]`, so no
extra environment variables are needed. The suite does not require a live
database or network.

## Configuration

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (Railway plugin reference) |
| `ALLOWED_ORIGINS` | Comma-separated exact browser origins |
| `ALLOWED_ORIGIN_REGEX` | Optional regex for Vercel preview deployments |
| `SCORING_CONFIG_PATH` | Override `config/scoring_config.yaml` |
| `RULES_CONFIG_PATH` | Override `config/rules.yaml` |
| `BENCHMARK_MAPPINGS_PATH` | Override `config/explicit_benchmark_mappings.json` |

Filesystem defaults are resolved in `core/paths.py`: the app root is the
directory containing `src/`, `config/`, and `migrations/` (`apps/api` locally,
`/app` in Docker). Override with `FUND_ENGINE_ROOT`, `FUND_ENGINE_CONFIG_DIR`,
`FUND_ENGINE_MIGRATIONS_DIR`, or `FUND_ENGINE_LOG_DIR`.

## Deployment

Railway service root: `apps/api`. The Dockerfile is auto-detected. API start
command:

```bash
sh -c 'uvicorn fund_engine.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2'
```

Batch start command:

```bash
python -m fund_engine.services.pipeline
```

See `docs/DEPLOYMENT.md` at the repository root for the full runbook.
