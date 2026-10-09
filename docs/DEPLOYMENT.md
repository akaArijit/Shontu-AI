# Deployment Guide

## Overview

| Component | Technology | Hosting |
|-----------|------------|---------|
| Database | PostgreSQL 15 | Supabase |
| Batch Jobs | Python 3.11 | Render Cron Jobs |
| API Server | Node.js 18 / Express | Render Web Service |
| Frontend | Next.js 14 | Vercel |
| File Storage | S3-compatible | Supabase Storage |

---

## Prerequisites

### Accounts Required
- [Supabase](https://supabase.com) — PostgreSQL database
- [Render](https://render.com) — Batch jobs + API
- [Vercel](https://vercel.com) — Frontend
- [GitHub](https://github.com) — Source control

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt
cd api && npm install

# Start local dev
docker-compose up -d  # PostgreSQL
python scripts/run_dev.py
```

---

## Infrastructure Setup

### 1. Supabase Database

Create new project → Note credentials:
```
DATABASE_URL=postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
```

Run migrations:
```bash
# From project root
psql $DATABASE_URL -f db/migrations/001_initial_schema.sql
psql $DATABASE_URL -f db/migrations/002_indexes.sql
psql $DATABASE_URL -f db/migrations/003_views.sql
```

### 2. Render Services

#### Batch Job (Cron)
1. New → Cron Job
2. Connect GitHub repo
3. Settings:
   - **Name**: `fund-engine-batch`
   - **Schedule**: `0 2 * * *` (2 AM UTC = 7:30 AM IST)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python scripts/run_nightly.py`
   - **Environment**: Add all env vars below

#### API Server (Web Service)
1. New → Web Service
2. Connect GitHub repo → `api/` directory
3. Settings:
   - **Name**: `fund-engine-api`
   - **Build Command**: `npm install`
   - **Start Command**: `npm start`
   - **Environment**: Node 18
   - **Auto-Deploy**: Yes

### 3. Vercel Frontend
1. Import GitHub repo → `frontend/` directory
2. Framework: Next.js (auto-detected)
3. Environment Variables: Add `NEXT_PUBLIC_API_URL`
4. Deploy

---

## Environment Variables

### Batch Job (Render)
```bash
# Database
DATABASE_URL=postgresql://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# External APIs
MFAPI_BASE_URL=https://api.mfapi.in/mf
NSE_API_KEY=xxx
RBI_SCRAPER_ENABLED=true

# Config
SCORING_CONFIG_PATH=/app/config/scoring_config.yaml
RULES_CONFIG_PATH=/app/config/rules.yaml
BENCHMARK_MAPPINGS_PATH=/app/config/explicit_benchmark_mappings.json

# Operational
LOG_LEVEL=info
TIMEZONE=Asia/Kolkata
PIPELINE_TIMEOUT_SECONDS=1800
```

### API Server (Render)
```bash
# Database
DATABASE_URL=postgresql://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx

# Auth
JWT_SECRET=xxx
API_KEY_SALT=xxx

# CORS
ALLOWED_ORIGINS=https://app.fundmonitor.example.com,https://fundmonitor.example.com

# Rate Limiting
RATE_LIMIT_WINDOW_MS=60000
RATE_LIMIT_MAX_REQUESTS=60
```

### Frontend (Vercel)
```bash
NEXT_PUBLIC_API_URL=https://fund-engine-api.onrender.com/api/v1
NEXT_PUBLIC_APP_URL=https://fundmonitor.example.com
```

---

## Database Migrations

### Migration Files
```
db/migrations/
├── 001_initial_schema.sql      # Core tables
├── 002_indexes.sql             # Performance indexes
├── 003_views.sql               # Materialized views
├── 004_rls_policies.sql        # Row-level security
└── 005_functions.sql           # Helper functions
```

### Running Migrations
```bash
# Manual
psql $DATABASE_URL -f db/migrations/001_initial_schema.sql

# Automated (in batch job startup)
python -m db.migrate
```

### Key Tables & Indexes

```sql
-- Primary lookup indexes
CREATE INDEX idx_nav_history_scheme_date ON nav_history(scheme_code, nav_date DESC);
CREATE INDEX idx_benchmark_history_code_date ON benchmark_history(benchmark_code, index_date DESC);
CREATE INDEX idx_fund_scores_scheme_date ON fund_scores(scheme_code, as_of_date DESC);
CREATE INDEX idx_fund_alerts_scheme_date ON fund_alerts(scheme_code, triggered_on DESC);
CREATE INDEX idx_client_folios_client ON client_folios(client_id);

-- Composite for portfolio queries
CREATE INDEX idx_folios_client_scheme ON client_folios(client_id, scheme_code);
```

---

## Configuration Files

### Scoring Config (`config/scoring_config.yaml`)
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
  # ... other components
penalty_per_month: 2.0
penalty_cap: 20.0
```

### Rules Config (`config/rules.yaml`)
```yaml
alert_rules:
  - id: underperform_3m
    alert_type: underperform_3m
    condition: "consecutive_underperf_months >= 3"
    severity: medium
    description: "Fund underperformed benchmark for 3+ consecutive months"
    category_overrides: {}
  # ... 8 more rules
```

### Benchmark Mappings (`config/explicit_benchmark_mappings.json`)
```json
{
  "INF204K01VX3": "NIFTY100_TRI",
  "INF767K01EW8": "NIFTY500_TRI",
  "INF179K01BE2": "NIFTY_MIDCAP150_TRI"
}
```

---

## CI/CD Pipeline

### GitHub Actions (`.github/workflows/deploy.yml`)

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python -m pytest resolution/ ingestion/ features/ rules/ scoring/ -v

  deploy-api:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: render/actions/deploy@v1
        with:
          service-id: ${{ secrets.RENDER_API_SERVICE_ID }}
          api-key: ${{ secrets.RENDER_API_KEY }}

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: ./frontend
```

---

## Monitoring & Alerts

### Render Dashboards
- **Batch Job**: Logs, runtime, success/failure
- **API**: Request latency, error rate, throughput
- **Database**: Connections, query performance, storage

### Custom Alerts (Render)
| Alert | Condition |
|-------|-----------|
| Batch job failed | Status = failed |
| Batch job timeout | Runtime > 30 min |
| API error rate | > 5% over 5 min |
| API p99 latency | > 2 seconds |
| DB connections | > 80% of max |
| Data freshness | fund_scores.max(as_of_date) < today-1 |

### Supabase Alerts
- Database size > 80%
- CPU > 80%
- Replication lag > 1 min

---

## Backup & Recovery

### Automated (Supabase)
- Daily point-in-time recovery (7 days)
- Weekly full backups (4 weeks)
- Monthly full backups (12 months)

### Manual Backup
```bash
# Schema + data
pg_dump $DATABASE_URL --no-owner --no-acl > backup_$(date +%Y%m%d).sql

# Restore
psql $DATABASE_URL < backup_20240115.sql
```

### RTO/RPO Targets
| Metric | Target |
|--------|--------|
| RTO (Recovery Time Objective) | < 2 hours |
| RPO (Recovery Point Objective) | < 24 hours |

---

## Security

### Network
- All Render services in private network
- Supabase: IP allowlist (Render IPs only)
- Vercel: Edge network, DDoS protection

### Data
- TLS 1.3 everywhere
- Database: Encryption at rest (Supabase default)
- API keys: Rotated quarterly
- JWT: RS256, 15-min expiry, refresh tokens

### Secrets Management
- Never commit secrets to Git
- Use Render/ Vercel environment variables
- Rotate: `RENDER_API_KEY`, `VERCEL_TOKEN`, `JWT_SECRET`, `DATABASE_URL`

---

## Scaling Strategy

### Current Capacity (Estimated)
| Component | Capacity | Scaling Trigger |
|-----------|----------|-----------------|
| Batch Job | 500 schemes | Runtime > 20 min → parallelize |
| API | 1000 RPS | CPU > 70% → horizontal |
| DB | 100 GB | Storage > 80% → upgrade |

### Horizontal Scaling (Future)
```python
# Parallelize feature engineering
from multiprocessing import Pool

def compute_scheme_features(args):
    scheme_code, nav_series, as_of_date = args
    return pipeline._compute_scheme_features(...)

with Pool(4) as p:
    features = p.map(compute_scheme_features, scheme_args)
```

---

## Rollback Procedure

### API Rollback
```bash
# Render: Dashboard → Deploys → Rollback to previous
# Or CLI
render deploy rollback --service-id $SERVICE_ID --deploy-id $PREVIOUS_DEPLOY_ID
```

### Database Rollback
```bash
# Point-in-time recovery (Supabase Dashboard)
# Or restore from backup
psql $DATABASE_URL < backup_20240114.sql
```

### Config Rollback
```bash
# Revert config files in Git, redeploy
git revert <commit-hash>
git push origin main
```

---

## Troubleshooting

### Batch Job Failures

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Timeout | Too many schemes | Parallelize feature engineering |
| AMFI fetch failed | Network/rate limit | Increase retry, add delay |
| mfapi 429 | Rate limit | Increase delay between calls |
| Memory error | Large NAV series | Chunk processing |

### API Issues

| Symptom | Fix |
|---------|-----|
| 500 errors | Check Render logs, DB connection |
| Slow queries | Add missing indexes |
| CORS errors | Check `ALLOWED_ORIGINS` |
| Auth failures | Verify JWT_SECRET, token expiry |

### Data Quality

| Issue | Detection | Fix |
|-------|-----------|-----|
| Missing NAV | `nav_history` gaps | Re-run ingestion for date |
| Wrong benchmark | Low confidence alerts | Update explicit mappings |
| Score anomalies | Alert on score delta > 20 | Check feature inputs |

---

## Runbook: Common Operations

### Add New Scheme
```sql
INSERT INTO scheme_master (scheme_code, scheme_name, amc, category, ...)
VALUES ('NEW_SCHEME_001', 'New Fund Name', 'New AMC', 'Large Cap', ...);
```

### Update Benchmark Mapping
```bash
# Edit config/explicit_benchmark_mappings.json
# Deploy batch job (auto-reloads on next run)
```

### Retune Scoring Weights
```bash
# 1. Edit config/scoring_config.yaml (new version/date)
# 2. Test locally: python -m scoring.test_scoring_engine
# 3. Deploy batch job
```

### Emergency: Disable Alert Rule
```yaml
# config/rules.yaml
- id: high_volatility
  enabled: false  # Temporarily disable
```

---

## Cost Estimation (Monthly)

| Service | Tier | Est. Cost |
|---------|------|-----------|
| Supabase | Pro | $25 |
| Render Cron | Standard | $7 |
| Render Web | Standard | $7 |
| Vercel | Pro | $20 |
| **Total** | | **~$59/month** |

*Scales with usage. Enterprise features add ~$200/month.*