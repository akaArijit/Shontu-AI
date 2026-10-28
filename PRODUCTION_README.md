# Production Checklist — Fund Monitoring Engine

Internal MFD dashboard: deterministic scoring, explainable alerts, and category
rankings over ~400 unique schemes.

**Stack:** FastAPI + PostgreSQL on Railway (API + nightly batch), Next.js 14 on
Vercel. Monorepo: backend in `apps/api`, frontend in `apps/web`.

Full instructions: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## 1. Railway

- [ ] Create project → **Add PostgreSQL**
- [ ] Apply migrations: `cd apps/api && railway run python scripts/apply_migrations.py`
- [ ] Create **`fund-engine-api`**: root `apps/api`, Dockerfile auto-detected, healthcheck `/health`, restart **On failure**
- [ ] Create **`fund-engine-batch`**: root `apps/api`, start `python scripts/run_nightly.py`, cron `0 2 * * *`, restart **Never**
- [ ] Set API variables: `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `ALLOWED_ORIGINS=https://<frontend-domain>`
- [ ] Generate the API domain and verify `https://<api-domain>/health`

## 2. Vercel

- [ ] Import the repo, **Root Directory = `apps/web`**
- [ ] Set `NEXT_PUBLIC_API_URL=https://<api-domain>` (bare origin, no `/api/v1`)
- [ ] Set `NEXT_PUBLIC_USE_MOCK_API=false`
- [ ] Deploy, copy the production domain
- [ ] Add that exact origin to the Railway API's `ALLOWED_ORIGINS` and redeploy
- [ ] Optional: add `ALLOWED_ORIGIN_REGEX=https://fund-engine-[a-z0-9-]+\.vercel\.app` for previews

> `NEXT_PUBLIC_*` values are inlined at build time — always **Redeploy** after
> changing them.

## 3. Seed data

- [ ] Upload the scheme master CSV at `https://<api-domain>/docs` (`POST /api/v1/mfd/csv/upload/scheme-master`, `dry_run=true` first)
- [ ] Optionally upload benchmark mappings (`/mfd/csv/upload/benchmark-mappings`)
- [ ] Backfill benchmarks: `cd apps/api && railway run python scripts/seed_benchmarks.py --years 6`
- [ ] Run the batch once (**Run now** or `railway run python scripts/run_nightly.py`)
- [ ] Verify `GET /api/v1/mfd/health` and the dashboard

## 4. Guardrails

- [ ] CI is green (API tests, web build, Docker image, migrations)
- [ ] Railway/Vercel branches point at `master`
- [ ] Database backups enabled; test one restore
- [ ] Alerts configured for API down, batch failure, stale data
- [ ] Keep the API URL private — **v1 has no user authentication**
- [ ] Rotate `DATABASE_URL` if it ever leaks

---

## Health checks

```bash
curl https://<api-domain>/health
# {"status":"healthy","service":"mfd-fund-monitoring-api","version":"1.0.0"}

curl https://<api-domain>/api/v1/mfd/health
# pipeline freshness + last run status
```

## Key commands

| Task | Command |
|------|---------|
| Full test suite | `npm run test:api` |
| Production web build | `npm run build` |
| Apply migrations | `cd apps/api && railway run python scripts/apply_migrations.py` |
| Nightly pipeline | `cd apps/api && railway run python scripts/run_nightly.py` |
| Backfill benchmarks | `cd apps/api && railway run python scripts/seed_benchmarks.py --years 6` |
| Local stack | `docker compose up -d postgres` then `npm run dev` |

## Current limitations

- NSE TRI history comes from an unofficial endpoint; CSV import is the fallback.
- CRISIL / S&P 500 benchmark history must be uploaded via CSV.
- RBI / MOSPI / FBIL macro fetchers are not implemented (not used by scoring).
- No user authentication in v1.
- Docker image is built and validated in CI, not on the development machine.
