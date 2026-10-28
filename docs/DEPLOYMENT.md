# Deployment Guide — Railway

Everything runs on [Railway](https://railway.app): PostgreSQL, the FastAPI backend, the nightly batch job, and the Next.js dashboard.

| Component | Technology | Railway service | Root directory |
|-----------|------------|-----------------|----------------|
| Database | PostgreSQL 15 | Postgres plugin | — |
| API | Python 3.11 / FastAPI | `fund-engine-api` (Dockerfile) | `/` |
| Batch job | Python 3.11 (cron) | `fund-engine-batch` (Dockerfile) | `/` |
| Frontend | Next.js 14 | `fund-engine-web` (Nixpacks) | `/frontend` |

Config files already in the repo:

- `railway.json` — API service build (Dockerfile) + `/health` healthcheck + restart policy
- `railway.batch.json` — nightly/cron service (no healthcheck, restart Never)
- `frontend/railway.json` — Nixpacks build, `next start` on `$PORT`
- `Dockerfile` — installs both `requirements.txt` and `api/requirements.txt`, binds `$PORT`

---

## Prerequisites

- [Railway account](https://railway.app) + [Railway CLI](https://docs.railway.app/guides/cli) (`npm i -g @railway/cli`)
- GitHub repo connected: https://github.com/akaArijit/Shontu-AI
- `psql` locally (optional, for migrations)

```bash
railway login
```

---

## 1. Create the project and database

1. Railway → **New Project** → **Deploy from GitHub repo** → pick `Shontu-AI`.
2. In the project canvas: **New** → **Database** → **Add PostgreSQL**.
3. Railway creates `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` on the Postgres service.

Run migrations against it (in order):

```bash
railway link                      # select project
railway service Postgres
railway run psql "$DATABASE_URL" -f db/migrations/001_initial_schema.sql
railway run psql "$DATABASE_URL" -f db/migrations/002_indexes.sql
railway run psql "$DATABASE_URL" -f db/migrations/003_views.sql
railway run psql "$DATABASE_URL" -f db/migrations/004_mfd_views.sql
```

Or from the Postgres service shell: `railway connect Postgres` then `\i db/migrations/001_initial_schema.sql`.

---

## 2. API service

If the GitHub import created a service from the repo root, rename it `fund-engine-api` and confirm:

| Setting | Value |
|---------|-------|
| Source repo / branch | `akaArijit/Shontu-AI` / `master` |
| Root directory | `/` (repo root) |
| Builder | Dockerfile (from `railway.json`) |
| Healthcheck path | `/health` |
| Start command | `sh -c 'uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2'` |

Variables (Settings → Variables):

```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
SCORING_CONFIG_PATH=/app/config/scoring_config.yaml
RULES_CONFIG_PATH=/app/config/rules.yaml
BENCHMARK_MAPPINGS_PATH=/app/config/explicit_benchmark_mappings.json
ALLOWED_ORIGINS=https://<your-frontend-domain>
```

`PORT` is injected by Railway; config paths default to `./config`, so the path
variables are optional if you keep that layout.

Then **Settings → Networking → Generate Domain**. Verify:

```bash
curl https://<api-domain>/health
# {"status":"healthy","service":"mfd-fund-monitoring-api","version":"1.0.0"}
curl https://<api-domain>/docs     # OpenAPI UI
```

> `railway.json` sets `healthcheckPath: /health`, so Railway only promotes a deploy once the app answers 200 there.

---

## 3. Frontend service

**New** → **GitHub Repo** → same repo, then:

| Setting | Value |
|---------|-------|
| Service name | `fund-engine-web` |
| Root directory | `/frontend` |
| Builder | Nixpacks (`frontend/railway.json`) |
| Build command | `npm ci && npm run build` |
| Start command | `npx next start -p ${PORT:-3000}` |
| Healthcheck path | `/` |

Variables:

```bash
NEXT_PUBLIC_API_URL=https://<your-api-domain>
NEXT_PUBLIC_USE_MOCK_API=false
NEXT_PUBLIC_APP_URL=https://<your-frontend-domain>
```

`NEXT_PUBLIC_*` values are baked in at build time — after changing them, trigger a redeploy (**Deploy → Redeploy**, or push a commit).

Then generate a domain, and finally set the API's `ALLOWED_ORIGINS` to that exact origin (scheme `https://`, no trailing slash) and redeploy the API.

> The app calls `NEXT_PUBLIC_API_URL + /api/v1/...`, so set the bare domain (no `/api/v1` suffix).

---

## 4. Nightly batch / cron service

**New** → **GitHub Repo** → same repo (repo root, Dockerfile builder), name it `fund-engine-batch`.

| Setting | Value |
|---------|-------|
| Root directory | `/` |
| Config-as-code file | `/railway.batch.json` (Settings → Config-as-code) |
| Builder | Dockerfile |
| Start command | `python scripts/run_nightly.py` (from `railway.batch.json`) |
| Cron schedule | `0 2 * * *` (02:00 UTC = 07:30 IST) |
| Restart policy | Never (cron services should exit) |

> Pointing the batch service at `railway.batch.json` keeps it from inheriting the
> API's `/health` check and `ON_FAILURE` restart policy.

**Sizing:** the pipeline loads all active schemes' 6-year NAV/benchmark history
into memory. Budget ~1 GB for a few hundred schemes; if the service hits its
memory limit, raise the batch service memory or shorten the lookback
(`DEFAULT_LOOKBACK_DAYS` in `db/queries.py` and the benchmark window in
`scripts/run_nightly.py`). Keep at least 6 years for 5-year metrics.

Variables: same as the API. No batch-specific variables are required.

Keep **Restart policy = Never** and enable **Cron Schedule**; otherwise Railway restarts the container after each successful run. Logs land in the service's **Deployments → Logs**, and nightly files in `logs/`.

Trigger a manual run: **Deploy → Redeploy**, or locally:

```bash
railway link
railway service fund-engine-batch
railway run python scripts/run_nightly.py --date 2026-10-27
```

---

## 5. Environment variable reference

| Variable | API | Batch | Frontend | Notes |
|----------|-----|-------|----------|-------|
| `DATABASE_URL` | ✅ | ✅ | — | `${{Postgres.DATABASE_URL}}` |
| `PORT` | auto | auto | auto | Injected by Railway |
| `ALLOWED_ORIGINS` | ✅ | — | — | Frontend origin(s), comma-separated |
| `SCORING_CONFIG_PATH` | ✅ | ✅ | — | `/app/config/scoring_config.yaml` |
| `RULES_CONFIG_PATH` | ✅ | ✅ | — | `/app/config/rules.yaml` |
| `BENCHMARK_MAPPINGS_PATH` | ✅ | ✅ | — | `…explicit_benchmark_mappings.json` |
| `NEXT_PUBLIC_API_URL` | — | — | ✅ | Build-time |
| `NEXT_PUBLIC_USE_MOCK_API` | — | — | ✅ | `false` in production |

Copy `.env.example` for the full list. Never commit real secrets.

---

## 6. CI/CD

`.github/workflows/ci-cd.yml` runs on push/PR to `master`, `main`, or `develop`:

1. **test** — `pytest` (187 tests) + e2e pipeline
2. **docker-build** — builds the image, pushes to GHCR
3. **migrate-db** — applies `db/migrations/*.sql` when `DATABASE_URL` secret is set
4. **deploy-*** — optional Railway CLI deploys

**Default (recommended): Railway auto-deploy.** In each service: **Settings → Source → Connected branch = `master`**. Every push deploys automatically after CI is green, with zero extra secrets.

**Optional: deploy from CI.** Set repository variable `RAILWAY_CLI_DEPLOY=true` and secrets:

| Secret | Value |
|--------|-------|
| `RAILWAY_TOKEN` | Project token (Project Settings → Tokens) |
| `RAILWAY_API_SERVICE` | API service name, e.g. `fund-engine-api` |
| `RAILWAY_BATCH_SERVICE` | `fund-engine-batch` |
| `RAILWAY_FRONTEND_SERVICE` | `fund-engine-web` |
| `DATABASE_URL` | Postgres public URL (for migrations) |

```bash
gh variable set RAILWAY_CLI_DEPLOY --body true
gh secret set RAILWAY_TOKEN
```

---

## 7. Monitoring

### Railway built-ins
- **Deployments → Logs** — structured app logs per service
- **Metrics** — CPU, memory, network, restart counts
- **Healthchecks** — `/health` for API, `/` for frontend; failed checks block promotion
- **Alerts** — Project Settings → Alerts → email/webhook on deploy failure or resource spikes

### Application-level checks
```bash
curl https://<api-domain>/health          # process alive
curl https://<api-domain>/api/v1/mfd/health   # pipeline freshness
```

| Alert | Condition |
|-------|-----------|
| API down | `/health` != 200 for 2 min |
| Batch failed | cron run exit code != 0 |
| Stale data | `max(fund_scores.as_of_date) < today - 1` |
| Error rate | 5xx > 5% over 5 min (Railway metrics) |

---

## 8. Backups & recovery

Railway Postgres supports scheduled backups on paid plans (Project → Postgres → Backups). Also take manual dumps:

```bash
railway service Postgres
railway run pg_dump "$DATABASE_URL" --no-owner --no-acl > backup_$(date +%Y%m%d).sql
```

Restore:

```bash
railway run psql "$DATABASE_URL" < backup_20261027.sql
```

Targets: RTO < 2 h, RPO < 24 h. Keep the last 7 daily + 4 weekly dumps in object storage.

---

## 9. Security

- Services communicate over Railway's private network — use `${{Postgres.DATABASE_URL}}`, not the public proxy, from API/batch
- Only the frontend domain should be public; keep the API behind HTTPS + `ALLOWED_ORIGINS`
- TLS terminated by Railway for all generated domains
- Postgres: encryption at rest, no public access unless you enable TCP Proxy
- Secrets only in Railway variables; rotate `RAILWAY_TOKEN` quarterly
- Non-root container user (`appuser`) in `Dockerfile`
- **No user authentication in v1** — CORS only limits browser origins. Share the API
  URL only with the dashboard build; add an auth layer before exposing it to clients.

---

## 10. Scaling

| Component | Capacity | Trigger |
|-----------|----------|---------|
| API | ~1000 RPS | CPU > 70% → raise replicas (Railway: Settings → Replicas) |
| Batch | 500 schemes in ~20 min | runtime > 20 min → parallelise feature engineering |
| Postgres | 100 GB | storage > 80% → upgrade plan |

`railway.json` pins `numReplicas: 1`; scale via the dashboard when needed.

---

## 11. Rollback

- **Service rollback**: Deployments → pick previous successful deploy → **Redeploy**
- **CLI**: `railway rollback` (interactive) or `railway redeploy --service <name>`
- **Code**: `git revert <sha> && git push` (Railway redeploys automatically)
- **Database**: restore the last dump (no automatic PITR on the free tier)

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Deploy fails at healthcheck | App not binding `$PORT` | Keep the `--port ${PORT:-8000}` start command |
| `502` on API domain | Container crashed on boot | Check Logs; usually missing `python-multipart`, `DATABASE_URL`, or a bad import |
| CORS error in browser | `ALLOWED_ORIGINS` mismatch | Set exact origin incl. scheme, then redeploy API |
| Frontend shows zeros / mock data | `NEXT_PUBLIC_USE_MOCK_API=true` or API URL stale | Fix variable, **rebuild** (values are inlined) |
| `railway up` uploads `node_modules` | `.gitignore` not respected | Ensure `frontend/node_modules` and `.next` stay ignored |
| Cron runs every few minutes | Restart policy not `Never` | Settings → Restart Policy → Never |
| Migrations not applied | `migrate-db` skipped | Run the `psql` commands above manually |
| Slow dashboard | Missing indexes | Re-run `db/migrations/002_indexes.sql` |

---

## 13. Operations runbook

| Task | Command |
|------|---------|
| Run pipeline manually | `railway run python scripts/run_nightly.py` |
| Retune scoring weights | Edit `config/scoring_config.yaml` → push (auto-redeploy batch) |
| Add alert rule | Edit `config/rules.yaml` → push |
| Update benchmark mapping | Edit `config/explicit_benchmark_mappings.json` → push |
| Refresh materialized views | `railway run psql "$DATABASE_URL" -c "SELECT refresh_mfd_materialized_views();"` |
| Check pipeline health | `curl https://<api-domain>/api/v1/mfd/health` |
| Tail logs | `railway logs --service fund-engine-api` |
| Open a DB shell | `railway connect Postgres` |
| List variables | `railway variables --service fund-engine-api` |

---

## 14. Cost estimate

Railway bills by usage (vCPU-minutes, GB-minutes, egress) plus plan fee; Postgres counts as a service.

| Item | Approx. monthly |
|------|-----------------|
| Hobby plan (includes usage credit) | $5 |
| API service (small, always on) | $3–8 |
| Frontend service | $2–6 |
| Batch cron (≤ 300 runs-min/day) | $1–3 |
| Postgres (1 GB) | ~$2–5 |
| **Total** | **~$13–27** |

Verify current pricing at https://railway.app/pricing. Supabase remains an option if you prefer a managed DB with PITR — point `DATABASE_URL` at it and skip the Postgres plugin.

---

## 15. Current implementation status (read before go-live)

Deployment plumbing and the data layer are complete:

| Layer | Status |
|-------|--------|
| Scheme dedup, benchmark mapping, features, rules, scoring | ✅ Implemented, 187 tests passing |
| Benchmark TRI ingestion (`NseIndicesFetcher`) | ✅ Live niftyindices.com endpoint, chunked ranges, incremental nightly fetch, `scripts/seed_benchmarks.py` backfill |
| CSV upload/validation/persistence (`/mfd/csv/*`) | ✅ Validates then upserts `scheme_master` / `benchmark_master`; `dry_run=true` skips writes |
| Benchmark history CSV (`/mfd/csv/upload/benchmark-history`) | ✅ Columns `benchmark_code,index_date,index_value`; overwrites existing points |
| CSV export (`/mfd/csv/download/scheme-master`) | ✅ Reads `scheme_master`; falls back to the template when the DB is empty |
| `/health`, `/` | ✅ Working |
| `/api/v1/mfd/health` | ✅ Queries `pipeline_run_log`; returns `degraded` when DB is empty/unreachable |
| `/api/v1/mfd/scores`, `/alerts`, `/schemes`, `/rankings`, `/macro`, `/meta/*` | ✅ DB-backed (see `api/repository.py`) |
| `scripts/run_nightly.py` | ✅ Full orchestration + persistence (`db/persistence.py`, `db/writer.py`) |
| Frontend | ✅ Builds and runs; shows empty states when the API has no data |

### Seeding a fresh deployment

1. Open `/api/v1/docs` and call `POST /api/v1/mfd/csv/upload/scheme-master` with a
   scheme master CSV (template: `GET /api/v1/mfd/csv/template`). Set
   `dry_run=true` first to validate.
2. Optionally override benchmarks with
   `POST /api/v1/mfd/csv/upload/benchmark-mappings` (`scheme_code,benchmark_code`).
   Manual mappings are preserved by the nightly resolver.
3. Backfill benchmark history once (needed for alpha/correlation metrics):
   - Preferred: run `python scripts/seed_benchmarks.py --years 6` inside the batch
     service (`railway run` from the repo root, or a one-off Railway shell). It
     resolves benchmark codes from `scheme_master`, writes `benchmark_master`
     placeholders and upserts `benchmark_history`.
   - Offline/alternative: `POST /api/v1/mfd/csv/upload/benchmark-history` with
     `benchmark_code,index_date,index_value`. Use this for CRISIL/S&P benchmarks
     that niftyindices.com does not publish.
4. Run the batch service once (Railway → `fund-engine-batch` → *Run now*). It
   fetches NAV history from mfapi.in, computes features/rules/scores and writes
   `fund_rolling_returns`, `fund_scores`, `fund_alerts`, `pipeline_run_log`.
   Later nightly runs fetch only new NAV/benchmark points.
5. Re-run the frontend only if you changed `NEXT_PUBLIC_*` variables (they are
   baked in at build time).

### Known limitations

- The NSE historical-data endpoint is unofficial: it can rate-limit or change
  shape. Failures are logged per benchmark and do not abort the run; use the CSV
  import as the fallback.
- CRISIL and S&P 500 benchmarks have no NSE TRI series and must be loaded via
  `POST /api/v1/mfd/csv/upload/benchmark-history`.
- Docker is not installed on the development machine, so the Railway image build
  is validated by CI (GitHub Actions) rather than locally.

Until real data exists, set `NEXT_PUBLIC_USE_MOCK_API=true` on the frontend
service to demo the UI with generated data.

