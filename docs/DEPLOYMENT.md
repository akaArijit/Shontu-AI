# Deployment Guide — Vercel + Railway

The production topology is split by workload:

| Component | Platform | Root directory | Config |
|-----------|----------|----------------|--------|
| Dashboard (Next.js 14) | **Vercel** | `apps/web` | `apps/web/next.config.js`, Vercel env vars |
| API (FastAPI) | **Railway** (Dockerfile) | `apps/api` | Dockerfile auto-detected; legacy `apps/api/railway.json` |
| Nightly batch (cron) | **Railway** (Dockerfile) | `apps/api` | Dockerfile auto-detected; legacy `apps/api/railway.batch.json` |
| PostgreSQL 15 | **Railway** plugin | — | plugin `DATABASE_URL` |

> **Railway deprecated Config-as-Code in 2026.** New services no longer read
> `railway.json` / `railway.toml`, and legacy files stop being read on
> **2026-12-01**. The files under `apps/api` are kept only for services that
> already used them. For a new project, configure the services in the Railway
> dashboard using the tables below — Railway auto-detects `apps/api/Dockerfile`
> from the service root, so no config file is required.

Files that matter:

- `apps/api/Dockerfile` — installs pipeline + API deps, runs as non-root `appuser`, binds `$PORT`
- `apps/web/next.config.js` — security headers, `poweredByHeader: false`
- `apps/api/railway.json` / `railway.batch.json` — **legacy** CaC only (not read by new services)

Both platforms deploy automatically from GitHub on push to `master`. CI
(`.github/workflows/ci-cd.yml`) runs tests, a production web build, a Docker
image build, and pending migrations — it does **not** deploy.

---

## Prerequisites

- GitHub repo: `akaArijit/Shontu-AI` (branch `master`)
- [Railway account](https://railway.app)
- [Vercel account](https://vercel.com)
- Railway CLI (optional, for migrations/seeding): `npm i -g @railway/cli`
- `psql` (optional fallback)

---

## 1. Railway project + PostgreSQL

1. Railway → **New Project** → **Deploy from GitHub repo** → pick `Shontu-AI`.
   This first service can be deleted once the API service is created.
2. **New** → **Database** → **Add PostgreSQL**.
3. The Postgres service exposes `DATABASE_URL` (and `PGHOST`, `PGPORT`, ...).
   Reference it from app services as `${{Postgres.DATABASE_URL}}` — never copy
   the value.

---

## 2. Migrations

Migrations live in `apps/api/migrations/` (`001` → `004`). Apply them with
the idempotent runner, which records applied files in `schema_migrations` and
refuses to re-run modified files.

### Option A — from your machine (recommended)

```bash
cd apps/api
pip install psycopg2-binary
railway login
railway link                 # select the project
railway service fund-engine-api
railway run python scripts/apply_migrations.py --dry-run   # preview
railway run python scripts/apply_migrations.py             # apply
```

`railway run` injects the linked service's variables, including
`DATABASE_URL=${{Postgres.DATABASE_URL}}`.

### Option B — raw psql (fallback)

```bash
cd apps/api
railway service Postgres
railway run psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_initial_schema.sql
railway run psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/002_indexes.sql
railway run psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/003_views.sql
railway run psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/004_mfd_views.sql
```

If you applied the schema manually before adopting the runner, mark it as
already applied once:

```bash
railway run python scripts/apply_migrations.py --baseline
```

CI also applies pending migrations on pushes to `master` when the repository
secret `DATABASE_URL` is set (use the Postgres **public** URL with SSL).

---

## 3. API service (Railway)

**New** → **GitHub Repo** → same repo. Name it `fund-engine-api`.

| Setting | Value |
|---------|-------|
| Source | `akaArijit/Shontu-AI` / `master` |
| Root directory | `apps/api` |
| Builder | Dockerfile (auto-detected; no config file needed) |
| Config-as-code | leave blank for new services (legacy: `/apps/api/railway.json`) |
| Healthcheck path | `/health` |
| Restart policy | On failure |
| Start command | `sh -c 'uvicorn fund_engine.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2'` |
| Watch paths | `/apps/api/**` (optional; avoids redeploys on dashboard-only changes) |

Variables:

```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
ALLOWED_ORIGINS=https://<your-frontend-domain>   # update after the Vercel deploy (step 6)
# Optional: allow Vercel preview deployments
# ALLOWED_ORIGIN_REGEX=https://fund-engine-[a-z0-9-]+\.vercel\.app
```

Config paths default to `./config` relative to `apps/api`; the image contains
`/app/config`, so `SCORING_CONFIG_PATH`, `RULES_CONFIG_PATH`, and
`BENCHMARK_MAPPINGS_PATH` are optional. `PORT` is injected by Railway.

Generate a domain: **Settings → Networking → Generate Domain**. Verify:

```bash
curl https://<api-domain>/health
# {"status":"healthy","service":"mfd-fund-monitoring-api","version":"1.0.0"}
curl https://<api-domain>/docs      # OpenAPI UI
```

Railway only promotes a deploy once `/health` returns 200.

---

## 4. Batch / cron service (Railway)

**New** → **GitHub Repo** → same repo. Name it `fund-engine-batch`.

| Setting | Value |
|---------|-------|
| Root directory | `apps/api` |
| Config-as-code file | leave blank for new services (legacy: `/apps/api/railway.batch.json`) |
| Builder | Dockerfile (auto-detected) |
| Start command | `python -m fund_engine.services.pipeline` |
| Cron schedule | `0 2 * * *` (02:00 UTC = 07:30 IST) |
| Restart policy | **Never** |
| Healthcheck | none |
| Watch paths | `/apps/api/**` (optional) |

> The batch service must not inherit the API's `/health` check or `ON_FAILURE`
> restart policy. Set **Restart policy = Never** and **Cron schedule =
> `0 2 * * *`** in the service settings (Settings → Deploy). Without `NEVER`,
> Railway restarts the container after every successful cron run.

Variables: same as the API (`DATABASE_URL` + optional config paths). No
batch-specific variables are required.

**Sizing:** the pipeline loads every active scheme's 6-year NAV/benchmark
history into memory. Budget ~1 GB for a few hundred schemes. If the service
hits its memory limit, raise batch memory or shorten the lookback
(`DEFAULT_LOOKBACK_DAYS` in `src/fund_engine/db/queries.py` and the benchmark
window in `src/fund_engine/services/pipeline.py`). Keep at least 6 years for
5-year metrics.

Manual run:

```bash
cd apps/api
railway service fund-engine-batch
railway run python scripts/run_nightly.py --date 2026-10-27
```

Or **Deployments → Run now** in the Railway dashboard. Logs are under the
service's **Deployments → Logs**; per-run files under `logs/` inside the
container.

---

## 5. Dashboard (Vercel)

1. Vercel → **Add New → Project** → import `akaArijit/Shontu-AI`.
2. **Root Directory:** `apps/web` (important — the monorepo root is not a
   Next.js app).
3. Framework preset: **Next.js**; build command `npm run build`; install
   command `npm ci`; Node 20.x.
4. Environment variables (Production **and** Preview):

   ```bash
   NEXT_PUBLIC_API_URL=https://<api-domain>       # bare origin, no /api/v1, no trailing slash
   NEXT_PUBLIC_USE_MOCK_API=false
   NEXT_PUBLIC_SITE_URL=https://<frontend-domain> # optional, metadata only
   ```

5. Deploy, then copy the resulting production domain.

> `NEXT_PUBLIC_*` values are inlined at **build** time. After changing them,
> trigger **Redeploy** (a plain refresh will not pick them up).

The client calls `NEXT_PUBLIC_API_URL + /api/v1/...` directly from the browser,
so the API must allow the dashboard origin via CORS (next step). Vercel preview
deployments use per-branch URLs; add `ALLOWED_ORIGIN_REGEX` on the API if you
want previews to work.

---

## 6. Wire CORS

On the Railway **API** service:

```bash
ALLOWED_ORIGINS=https://<frontend-domain>
ALLOWED_ORIGIN_REGEX=https://fund-engine-[a-z0-9-]+\.vercel\.app
```

- Exact origins are comma-separated, include the scheme, no trailing slash.
- `ALLOWED_ORIGIN_REGEX` is optional and only for preview/custom domains.
- Defaults (no variables) are `http://localhost:3000,http://127.0.0.1:3000`.

Redeploy the API after changing origins. A CORS failure appears in the browser
console as a blocked request with no `Access-Control-Allow-Origin` header.

---

## 7. Seed a fresh deployment

1. Open `https://<api-domain>/docs` and call
   `POST /api/v1/mfd/csv/upload/scheme-master` with a scheme master CSV.
   Get the template from `GET /api/v1/mfd/csv/template`. Use `dry_run=true`
   first to validate.
2. Optionally override benchmark mappings with
   `POST /api/v1/mfd/csv/upload/benchmark-mappings` (`scheme_code,benchmark_code`).
   Manual mappings survive nightly re-resolution.
3. Backfill benchmark history (needed for alpha/correlation):

   ```bash
   cd apps/api
   railway service fund-engine-batch
   railway run python scripts/seed_benchmarks.py --years 6 --dry-run
   railway run python scripts/seed_benchmarks.py --years 6
   ```

   For CRISIL / S&P 500 (no NSE TRI series), use
   `POST /api/v1/mfd/csv/upload/benchmark-history` with
   `benchmark_code,index_date,index_value`.
4. Run the batch once (**Run now**, or `railway run python scripts/run_nightly.py`).
   It fetches NAV history from mfapi.in, resolves benchmarks, computes
   features/rules/scores, and writes `fund_rolling_returns`, `fund_scores`,
   `fund_alerts`, `pipeline_run_log`. Subsequent runs fetch only new points.
5. Verify `GET /api/v1/mfd/health` and open the dashboard.

Until real data exists, set `NEXT_PUBLIC_USE_MOCK_API=true` on Vercel and
redeploy to demo the UI with generated data.

---

## 8. Environment variable reference

| Variable | API | Batch | Web | Notes |
|----------|-----|-------|-----|-------|
| `DATABASE_URL` | yes | yes | — | `${{Postgres.DATABASE_URL}}` |
| `PORT` | auto | auto | auto | Injected by the platform |
| `ALLOWED_ORIGINS` | yes | — | — | Comma-separated browser origins |
| `ALLOWED_ORIGIN_REGEX` | optional | — | — | Vercel preview URLs |
| `SCORING_CONFIG_PATH` | optional | optional | — | `/app/config/scoring_config.yaml` |
| `RULES_CONFIG_PATH` | optional | optional | — | `/app/config/rules.yaml` |
| `BENCHMARK_MAPPINGS_PATH` | optional | optional | — | `/app/config/explicit_benchmark_mappings.json` |
| `NEXT_PUBLIC_API_URL` | — | — | yes | Build-time; bare API origin |
| `NEXT_PUBLIC_USE_MOCK_API` | — | — | yes | `false` in production |
| `NEXT_PUBLIC_SITE_URL` | — | — | optional | Metadata/canonical URL |

Templates: [`apps/api/.env.example`](../apps/api/.env.example) and
[`apps/web/.env.example`](../apps/web/.env.example). Never commit real secrets.

---

## 9. CI/CD

`.github/workflows/ci-cd.yml` runs on pushes/PRs to `master`, `main`, and
`develop`:

1. **API tests** — 194 tests plus the end-to-end pipeline
2. **Web build** — `npm ci && npm run build` with the Vercel toolchain
3. **Docker image** — builds `apps/api/Dockerfile` (no registry push) to prove the Railway image works
4. **Migrations** — applies pending migrations on `master` when the
   `DATABASE_URL` repository secret exists

Deployment is intentionally left to the platform Git integrations:

- **Railway:** each service → Settings → Source → branch `master`; every push
  deploys after build/healthcheck.
- **Vercel:** project → Git → Production Branch `master`; previews for PRs.

There is no CLI deploy job and no `RAILWAY_TOKEN` requirement. If you prefer a
manual deploy, run `railway up` from `apps/api` with the target service linked.

Repository secret for CI migrations:

| Secret | Value |
|--------|-------|
| `DATABASE_URL` | Postgres **public** URL (SSL enabled) |

---

## 10. Monitoring

### Platform
- **Railway → Deployments → Logs** — structured API/batch logs
- **Railway → Metrics** — CPU, memory, network, restarts
- **Railway → Project Settings → Alerts** — email/webhook on failures
- **Vercel → Deployments → Functions/Logs** — build and runtime logs
- **Vercel → Analytics** — optional Web Vitals

### Application

```bash
curl https://<api-domain>/health                # process alive
curl https://<api-domain>/api/v1/mfd/health     # pipeline freshness
```

| Alert | Condition |
|-------|-----------|
| API down | `/health` != 200 for 2 min |
| Batch failed | cron run exit code != 0 |
| Stale data | `max(fund_scores.as_of_date) < today - 1` |
| Error rate | 5xx > 5% over 5 min |

---

## 11. Backups & recovery

Railway Postgres supports scheduled backups on paid plans. Also take manual
dumps:

```bash
railway service Postgres
railway run pg_dump "$DATABASE_URL" --no-owner --no-acl > backup_20261027.sql
```

Restore:

```bash
railway run psql "$DATABASE_URL" < backup_20261027.sql
```

Targets: RTO < 2 h, RPO < 24 h. Keep the last 7 daily + 4 weekly dumps in
object storage. Vercel has no persistent state — the dashboard is stateless.

---

## 12. Security

- API and batch talk to Postgres over Railway's private network; use
  `${{Postgres.DATABASE_URL}}`, not the public proxy.
- Only the Vercel domain needs to be public; the API can stay on its Railway
  domain with CORS restricted to the dashboard origins.
- TLS is terminated by Railway/Vercel for generated domains.
- Postgres is encrypted at rest; leave the TCP proxy disabled unless needed.
- Secrets live only in platform variables; rotate database credentials if a
  token leaks.
- The API container runs as non-root `appuser`.
- Security headers are set in `apps/web/next.config.js` (HSTS, `X-Frame-Options`,
  `nosniff`, referrer and permissions policies).
- **No user authentication in v1.** CORS restricts browser origins but is not
  auth. Treat the dashboard/API as internal, keep URLs private, and add an auth
  layer (e.g. Vercel Password Protection or an API gateway) before exposing
  client data.

---

## 13. Scaling

| Component | Capacity | Trigger |
|-----------|----------|---------|
| API | ~1,000 RPS | CPU > 70% → raise replicas (Railway → Settings → Replicas) |
| Batch | ~500 schemes / ~20 min | runtime > 20 min → parallelise feature engineering |
| Postgres | 100 GB | storage > 80% → upgrade plan |
| Dashboard | Vercel edge CDN | serverless functions scale automatically |

Set replicas to `1` in the Railway dashboard (Settings → Deploy) to keep DB load
predictable; raise it when needed. Multiple API replicas are safe (stateless).

---

## 14. Rollback

- **Railway:** Deployments → pick a previous successful deploy → **Redeploy**
- **Vercel:** Deployments → previous deployment → **Promote to Production**
- **Code:** `git revert <sha> && git push` (both platforms redeploy)
- **Database:** restore the last dump. Migrations are additive; the runner
  records checksums, so do not edit an applied file — add a new migration.

---

## 15. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Railway build fails "Dockerfile not found" | Root directory not `apps/api` | Set service root to `apps/api` |
| Deploy fails at healthcheck | App not binding `$PORT` | Keep `--port ${PORT:-8000}` |
| `502` on API domain | Container crashed on boot | Check logs; missing `python-multipart`, `DATABASE_URL`, or bad import |
| CORS error in browser | `ALLOWED_ORIGINS` mismatch | Set the exact Vercel origin (scheme, no trailing slash) and redeploy API |
| CORS works on prod but not previews | Preview URL not allowed | Add `ALLOWED_ORIGIN_REGEX` |
| Dashboard shows zeros / mock data | `NEXT_PUBLIC_USE_MOCK_API=true` or stale API URL | Fix Vercel env, then **Redeploy** (values are inlined) |
| Vercel build "No Next.js version detected" | Root directory not `apps/web` | Set project root to `apps/web` |
| Vercel build calls localhost API | `NEXT_PUBLIC_API_URL` missing at build | Add it to Production + Preview, redeploy |
| Cron runs every few minutes | Restart policy not `Never` | Settings → Restart Policy → Never |
| Migrations not applied | Runner skipped / no secret | Run `scripts/apply_migrations.py` manually |
| Slow dashboard | Missing indexes | Re-run `002_indexes.sql` |
| Batch OOM | 6-year history too large | Raise memory or shorten lookback |
| NSE benchmark fetch fails | Unofficial endpoint / rate limit | Retry; CSV-import the missing history |

---

## 16. Operations runbook

| Task | Command |
|------|---------|
| Apply migrations | `cd apps/api && railway run python scripts/apply_migrations.py` |
| Preview migrations | `... --dry-run` |
| Run pipeline manually | `cd apps/api && railway run python scripts/run_nightly.py` |
| Backfill benchmarks | `cd apps/api && railway run python scripts/seed_benchmarks.py --years 6` |
| Retune scoring weights | Edit `apps/api/config/scoring_config.yaml` → push |
| Add alert rule | Edit `apps/api/config/rules.yaml` → push |
| Update benchmark mapping | Edit `apps/api/config/explicit_benchmark_mappings.json` → push |
| Refresh materialized views | `railway run psql "$DATABASE_URL" -c "SELECT refresh_mfd_materialized_views();"` |
| Check pipeline health | `curl https://<api-domain>/api/v1/mfd/health` |
| Tail API logs | `railway logs --service fund-engine-api` |
| Open a DB shell | `railway connect Postgres` |
| List variables | `railway variables --service fund-engine-api` |
| Redeploy dashboard | Vercel → Deployments → Redeploy |

---

## 17. Cost estimate

| Item | Approx. monthly |
|------|-----------------|
| Railway Hobby plan (includes usage credit) | $5 |
| API service (small, always on) | $3–8 |
| Batch cron (≤ 300 run-min/day) | $1–3 |
| Postgres (1 GB) | ~$2–5 |
| Vercel Hobby/Pro | $0–20 |
| **Total** | **~$11–41** |

Verify current pricing at https://railway.app/pricing and
https://vercel.com/pricing. Supabase remains an option for Postgres with PITR:
point `DATABASE_URL` at it and skip the Railway plugin.

---

## 18. Implementation status (read before go-live)

| Layer | Status |
|-------|--------|
| Scheme dedup, benchmark mapping, features, rules, scoring | Implemented, 194 tests passing |
| Benchmark TRI ingestion (`NseIndicesFetcher`) | Live niftyindices.com endpoint, chunked ranges, incremental nightly fetch, `seed_benchmarks.py` backfill |
| CSV upload/validation/persistence (`/mfd/csv/*`) | Validates then upserts `scheme_master` / `benchmark_master`; `dry_run=true` skips writes |
| Benchmark history CSV (`/mfd/csv/upload/benchmark-history`) | Columns `benchmark_code,index_date,index_value`; overwrites existing points |
| CSV export (`/mfd/csv/download/scheme-master`) | Reads `scheme_master`; falls back to the template when empty |
| `/health`, `/` | Working |
| `/api/v1/mfd/health` | Queries `pipeline_run_log`; `degraded` when DB is empty/unreachable |
| `/api/v1/mfd/scores`, `/alerts`, `/schemes`, `/rankings`, `/macro`, `/meta/*` | DB-backed (see `src/fund_engine/db/repository.py`) |
| `src/fund_engine/services/pipeline.py` | Full orchestration + persistence |
| `src/fund_engine/services/migrations.py` | Idempotent runner with checksum tracking |
| Frontend | Builds on Vercel; empty states when the API has no data; error/not-found/loading boundaries |

### Known limitations

- The NSE historical-data endpoint is unofficial: it can rate-limit or change
  shape. Failures are logged per benchmark and do not abort the run; use the CSV
  import as the fallback.
- CRISIL and S&P 500 benchmarks have no NSE TRI series and must be loaded via
  `POST /api/v1/mfd/csv/upload/benchmark-history`.
- RBI/MOSPI/FBIL macro fetchers are declared but not implemented; macro panels
  read whatever is in `macro_indicators` and are not used by scoring.
- No user authentication (see Security).
- Docker is not installed on the development machine; the image is validated by
  CI (`Docker image` job) rather than locally.
