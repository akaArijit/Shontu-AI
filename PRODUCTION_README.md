# MFD Fund Monitoring & Scoring Engine - Production Ready

**Internal Use Only - Mutual Fund Distributors (MFD)**

A deterministic, explainable fund monitoring system for MFDs managing 500+ clients and 5,000+ folios across ~400 unique mutual fund schemes.

---

## 🎯 MFD-Focused Features

| Feature | Description |
|---------|-------------|
| **Scheme Monitoring Dashboard** | All 400 schemes with health scores, key metrics, alert counts |
| **Alert Action Center** | 9 alert types with bulk resolve/dismiss for MFD workflow |
| **Category Peer Rankings** | Within-category rankings for fund selection/review |
| **Pipeline Health** | Data freshness, job status, completeness monitoring |
| **Macro Context Panel** | Repo rate, CPI, USD/INR, VIX for MFD client conversations |

---

## 🚀 Quick Start (Production)

### Prerequisites
- Docker & Docker Compose
- PostgreSQL 15+ (or Supabase)
- Redis 7+ (for API caching)

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start Services
```bash
docker-compose up -d
```

### 3. Verify Deployment
```bash
# API health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

---

## 📊 MFD API Endpoints

### Scheme Monitoring (Primary Dashboard)
```
GET  /mfd/schemes                    # All schemes with scores, metrics, alerts
GET  /mfd/schemes/{scheme_code}      # Single scheme detail
GET  /mfd/schemes?has_high_alerts=1  # Filter schemes needing attention
```

### Scores & Breakdown
```
GET  /mfd/scores                     # Paginated fund health scores
GET  /mfd/scores/{scheme_code}       # Full breakdown (30+20+20+15+15 pts)
GET  /mfd/scores/latest              # Latest available scores
```

### Alerts (Action Center)
```
GET  /mfd/alerts                     # All unresolved alerts
GET  /mfd/alerts/summary             # Counts by type/severity for badges
POST /mfd/alerts/{id}/resolve        # Mark resolved
POST /mfd/alerts/{id}/dismiss        # Dismiss with reason
POST /mfd/alerts/bulk-resolve        # Bulk actions
POST /mfd/alerts/bulk-dismiss        # Bulk dismiss
```

### Category Rankings
```
GET  /mfd/rankings/category/{category}  # Peer rankings within category
GET  /mfd/rankings/all                  # All categories overview
```

### Context & Health
```
GET  /mfd/benchmarks/{code}/history    # Benchmark charts
GET  /mfd/macro                        # Repo rate, CPI, USD/INR, VIX
GET  /mfd/health                       # Pipeline status, data freshness
GET  /mfd/meta/scoring-config          # Current scoring weights
GET  /mfd/meta/rules-config            # Current alert rules
```

---

## 🏗 Architecture (MFD-Optimized)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MFD FUND MONITORING PIPELINE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. INGESTION (Nightly 2 AM)                                     │
│     AMFI NAV │ mfapi.in │ NSE Indices │ RBI/MOSPI/FBIL          │
│         │                                                     │  │
│         ▼                                                     ▼  │
│  2. RESOLUTION                                                   │
│     Dedup: 5000 folios → 400 schemes                            │
│     Benchmark Map: Explicit + Category Fallback (20 categories) │
│         │                                                     │  │
│         ▼                                                     ▼  │
│  3. FEATURE ENGINEERING (Per Scheme)                            │
│     Returns │ Alpha │ Drawdown │ Volatility │ Percentile       │
│     Correlation │ Underperformance Streak                      │
│         │                                                     │  │
│         ▼                                                     ▼  │
│  4. RULE ENGINE (9 Alert Types)                                 │
│     Underperformance │ Rank Drop │ Deviation │ DD │ Volatility  │
│         │                                                     │  │
│         ▼                                                     ▼  │
│  5. SCORING ENGINE (0-100)                                      │
│     30% Benchmark Outperformance                                │
│     20% Category Ranking                                        │
│     20% Consistency                                             │
│     15% Drawdown Control                                        │
│     15% Volatility Adjusted                                     │
│     Penalty: 2pts/month underperformance (cap 20)              │
│         │                                                     │  │
│         ▼                                                     ▼  │
│  6. MFD OUTPUT (Zero Client Computation)                        │
│     v_mfd_scheme_monitoring   → Primary Dashboard              │
│     v_mfd_category_rankings   → Peer Analysis                  │
│     v_mfd_alert_actions       → Action Center                  │
│     v_mfd_pipeline_health     → Operations                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗄 Database Views (MFD Ready)

| View | Purpose |
|------|---------|
| `v_mfd_scheme_monitoring` | Primary dashboard - all schemes with scores, metrics, alerts, status |
| `v_mfd_category_rankings` | Peer rankings within each SEBI category |
| `v_mfd_alert_actions` | Alert action center with priority ordering |
| `v_mfd_pipeline_health` | Data freshness, job status, completeness |

---

## 📈 Scoring Methodology (0-100)

| Component | Weight | Max Points | Method |
|-----------|--------|------------|--------|
| Benchmark Outperformance | 30% | 30 | Alpha thresholds: >5%=30, >2%=20, >0%=10, >-2%=5, ≤-5%=0 |
| Category Ranking | 20% | 20 | Linear percentile: 100th=20, 50th=10, 0th=0 |
| Consistency | 20% | 20 | Inverse streak: 0 months=20, 36 months=0 |
| Drawdown Control | 15% | 15 | Inverse: <10%=15, <15%=10, <20%=5, ≤25%=0 |
| Volatility Adjusted | 15% | 15 | Inverse: <15%=15, <18%=10, <22%=5, ≤25%=0 |

**Penalty**: 2 pts per consecutive underperformance month (cap 20)

---

## 🔧 Configuration (YAML - No Code Changes)

### Scoring Weights (`config/scoring_config.yaml`)
```yaml
components:
  benchmark_outperformance: {weight: 0.30, max_points: 30}
  category_ranking: {weight: 0.20, max_points: 20}
  consistency_of_returns: {weight: 0.20, max_points: 20}
  drawdown_control: {weight: 0.15, max_points: 15}
  volatility_adjusted: {weight: 0.15, max_points: 15}
penalty_per_month: 2.0
penalty_cap: 20.0
```

### Alert Rules (`config/rules.yaml`)
```yaml
alert_rules:
  - id: underperform_3m
    condition: "consecutive_underperf_months >= 3"
    severity: medium
    category_overrides: {}
```

---

## 🧪 Testing

```bash
# All tests (187 tests)
python -m pytest resolution ingestion features rules scoring test_e2e_pipeline.py db/test_persistence.py api scripts/test_pipeline.py scripts/test_seed_benchmarks.py -v

# Individual modules
python -m pytest scoring/ -v

# Integration test
python test_e2e_pipeline.py
```

**Results**: 187 tests passing

---

## 📦 Deployment

### Railway (Recommended)
1. Railway → **New Project** → **Deploy from GitHub repo** (`akaArijit/Shontu-AI`)
2. Add **PostgreSQL** plugin, then run `db/migrations/*.sql` in order
3. Create three services from the same repo:
   - `fund-engine-api` — root `/`, Dockerfile builder, healthcheck `/health`
   - `fund-engine-batch` — root `/`, Dockerfile, Config-as-code `/railway.batch.json` (start `python scripts/run_nightly.py`), cron `0 2 * * *`, restart policy **Never**
   - `fund-engine-web` — root `/frontend`, Nixpacks, start `npx next start -p ${PORT:-3000}`
4. Add variables from `.env.example` (use `DATABASE_URL=${{Postgres.DATABASE_URL}}`)
5. Backfill benchmarks once: `railway run python scripts/seed_benchmarks.py --years 6`
6. Set `NEXT_PUBLIC_API_URL` to the API domain, then set `ALLOWED_ORIGINS` on the API to the frontend domain

Repo config: `railway.json` (API), `railway.batch.json` (batch), `frontend/railway.json` (web). Full guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

### Database Migrations
```bash
psql $DATABASE_URL -f db/migrations/001_initial_schema.sql
psql $DATABASE_URL -f db/migrations/002_indexes.sql
psql $DATABASE_URL -f db/migrations/003_views.sql
psql $DATABASE_URL -f db/migrations/004_mfd_views.sql
```

### CI/CD
GitHub Actions workflow (`.github/workflows/ci-cd.yml`):
- Tests → Docker Build → Optional Railway CLI Deploys → Run Migrations
- Default deploys come from Railway's GitHub integration on `master`

---

## 🔐 Security

- Non-root Docker user
- JWT authentication (RS256)
- API key rotation
- Rate limiting (100 req/min default)
- CORS restricted to MFD dashboard domain
- TLS 1.3 everywhere

---

## 📋 MFD Operations Runbook

| Task | Command |
|------|---------|
| Run pipeline manually | `docker-compose run --rm batch --date 2024-01-15` |
| Retune scoring weights | Edit `config/scoring_config.yaml` → redeploy batch |
| Add alert rule | Edit `config/rules.yaml` → redeploy batch |
| Update benchmark mapping | Edit `config/explicit_benchmark_mappings.json` |
| Refresh materialized views | `SELECT refresh_mfd_materialized_views();` |
| Check pipeline health | `curl /mfd/health` |
| View unresolved alerts | `SELECT * FROM v_mfd_alert_actions;` |

---

## 📄 License

MIT License - Internal MFD Use Only

---

## 📞 Support

For MFD technical issues: Check pipeline health endpoint, review batch job logs, verify data freshness.