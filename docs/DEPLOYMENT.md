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
REDIS_URL=                      # optional; leave blank if unused
SCORING_CONFIG_PATH=/app/config/scoring_config.yaml
RULES_CONFIG_PATH=/app/config/rules.yaml
BENCHMARK_MAPPINGS_PATH=/app/config/explicit_benchmark_mappings.json
LOG_LEVEL=info
TIMEZONE=Asia/Kolkata
JWT_SECRET=<generate-a-long-random-string>
API_KEY_SALT=<generate-a-long-random-string>
ALLOWED_ORIGINS=https://<your-frontend-domain>
MFAPI_BASE_URL=https://api.mfapi.in/mf
```

Generate secrets: `openssl rand -hex 32`.

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
| Builder | Dockerfile |
| Start command | `python scripts/run_nightly.py` |
| Cron schedule | `0 2 * * *` (02:00 UTC = 07:30 IST) |
| Restart policy | Never (cron services should exit) |

Variables: same as the API plus:

```bash
PIPELINE_TIMEOUT_SECONDS=1800
INGESTION_MAX_RETRIES=3
INGESTION_RETRY_DELAY_SECONDS=5
```

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
| `JWT_SECRET` / `API_KEY_SALT` | ✅ | — | — | Rotate quarterly |
| `SCORING_CONFIG_PATH` | ✅ | ✅ | — | `/app/config/scoring_config.yaml` |
| `RULES_CONFIG_PATH` | ✅ | ✅ | — | `/app/config/rules.yaml` |
| `BENCHMARK_MAPPINGS_PATH` | ✅ | ✅ | — | `…explicit_benchmark_mappings.json` |
| `NEXT_PUBLIC_API_URL` | — | — | ✅ | Build-time |
| `NEXT_PUBLIC_USE_MOCK_API` | — | — | ✅ | `false` in production |
| `MFAPI_BASE_URL` | ✅ | ✅ | — | `https://api.mfapi.in/mf` |
| `PIPELINE_TIMEOUT_SECONDS` | — | ✅ | — | Default 1800 |

Copy `.env.example` for the full list. Never commit real secrets.

---

## 6. CI/CD

`.github/workflows/ci-cd.yml` runs on push/PR to `master`, `main`, or `develop`:

1. **test** — `pytest` (128 tests) + e2e pipeline
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
- Secrets only in Railway variables; rotate `JWT_SECRET`, `API_KEY_SALT`, `RAILWAY_TOKEN` quarterly
- Non-root container user (`appuser`) in `Dockerfile`

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
