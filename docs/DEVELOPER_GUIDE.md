# Developer Guide

## Repository layout

This is a monorepo: the backend lives in `apps/api` (FastAPI + batch pipeline,
deployed to Railway) and the dashboard in `apps/web` (Next.js, deployed to
Vercel). Run backend commands from `apps/api` and frontend commands from
`apps/web`.

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (or Supabase)
- Node.js 20+

### Installation

```bash
# Clone
git clone <repo>
cd fund-engine

# Python dependencies
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt

# Frontend dependencies
cd ../web
npm ci

# Backend tests (from apps/api)
cd ../api
python -m pytest -v
```

### Project Structure
```
fund-engine/
+-- apps/
|   +-- api/                     # FastAPI + pipeline (Railway)
|   |   +-- src/fund_engine/
|   |   |   +-- api/             # app factory, routes, HTTP contracts
|   |   |   +-- core/            # settings, logging, filesystem paths
|   |   |   +-- db/              # connection, repository, readers/writers
|   |   |   +-- domain/          # resolution, features, rules, scoring
|   |   |   +-- ingestion/       # AMFI, mfapi, NSE TRI, macro fetchers
|   |   |   +-- services/        # pipeline, benchmark seed, migrations
|   |   +-- tests/               # mirrors the package layout
|   |   +-- config/              # YAML/JSON config
|   |   +-- migrations/          # numbered SQL migrations
|   |   +-- scripts/             # thin CLI wrappers
|   |   +-- Dockerfile
|   |   +-- pyproject.toml
|   |   +-- requirements.txt
|   +-- web/                     # Next.js dashboard (Vercel)
+-- docs/
+-- docker-compose.yml
+-- package.json
```

---

## Running the Pipeline

Run these commands from `apps/api`.

### Full Nightly Run (Production)
```bash
python scripts/run_nightly.py --date 2024-01-15
```

### Individual Steps
```bash
# 1. Ingestion only (NAV + benchmark TRI history)
python scripts/run_nightly.py --steps ingestion

# 2. Resolution only (benchmark mapping for unmapped schemes)
python scripts/run_nightly.py --steps resolution

# 3. Features, rules and scoring against stored data (no network)
python scripts/run_nightly.py --no-ingest --steps features,rules,scoring,persistence

# 4. Dry run: compute everything, write nothing
python scripts/run_nightly.py --dry-run

# 5. Backfill benchmark history (one-off / after a fresh deploy)
python scripts/seed_benchmarks.py --years 6
```

### Development Mode
```bash
# Run with sample data
python -m pytest tests/test_e2e_pipeline.py -v

# Run specific module demo (PYTHONPATH=src)
python -m fund_engine.domain.resolution.demo_scheme_dedup
python -m fund_engine.domain.features.demo_feature_engineering
python -m fund_engine.domain.rules.demo_rule_engine
python -m fund_engine.domain.scoring.demo_scoring_engine
```

---

## Adding a New Data Source

### 1. Create Fetcher Class
```python
# src/fund_engine/ingestion/fetchers.py
class MyNewSourceFetcher(BaseFetcher):
    @property
    def source(self) -> DataSource:
        return DataSource.MY_NEW_SOURCE
    
    def fetch(self) -> list[NavRecord]:
        # Implement fetch logic with retry
        response = self._request_with_retry("https://api.example.com/data")
        # Parse and return standardized records
        return [NavRecord(...), ...]
```

### 2. Register in Orchestrator
```python
# In your pipeline script
orchestrator = IngestionOrchestrator()
orchestrator.register_fetcher(MyNewSourceFetcher())
```

### 3. Add Data Model (if needed)
```python
@dataclass
class MyNewRecord:
    field1: str
    field2: float
    source: DataSource = DataSource.MY_NEW_SOURCE
    fetched_at: datetime = field(default_factory=datetime.utcnow)
```

---

## Adding a New Alert Rule

### Option 1: YAML Config (No Code Changes)
```yaml
# config/rules.yaml
alert_rules:
  - id: my_custom_rule
    alert_type: high_volatility
    condition: "volatility_1y > 0.30"
    severity: high
    description: "Custom high volatility threshold for aggressive funds"
    category_overrides:
      Small Cap:
        condition: "volatility_1y > 0.35"
```

### Option 2: Programmatic
```python
from fund_engine.domain.rules.rule_engine import AlertRule, AlertType, AlertSeverity

engine = RuleEngine()
engine.add_rule(AlertRule(
    id="my_custom_rule",
    alert_type=AlertType.HIGH_VOLATILITY,
    condition="volatility_1y > 0.30",
    severity=AlertSeverity.HIGH,
    description="Custom rule",
))
```

---

## Modifying Scoring Weights

### 1. Update YAML Config
```yaml
# config/scoring_config.yaml
version: "1.1"
effective_date: "2024-06-01"
components:
  benchmark_outperformance:
    weight: 0.35      # Increased from 0.30
    max_points: 35    # Increased from 30
    # ... rest unchanged
penalty_per_month: 2.5  # Increased from 2.0
```

### 2. Versioning
- Each config change gets new version + effective_date
- Historical scores reproducible with old configs
- Load specific version: `ScoringConfig.load("config/v1.0_scoring.yaml")`

---

## Testing Your Changes

### Unit Tests
```bash
# Run specific module tests
python -m pytest tests/domain/resolution/test_scheme_dedup.py -v
python -m pytest tests/domain/scoring/test_scoring_engine.py::TestScoringEngine::test_good_fund_high_score -v
```

### Integration Test
```bash
# Full pipeline with sample data
python -m pytest tests/test_e2e_pipeline.py -v
```

### Manual Verification
```python
# Quick REPL test
from fund_engine.domain.scoring.scoring_engine import create_default_scoring_engine

engine = create_default_scoring_engine()
features = {"alpha_1y": 0.05, "category_percentile_1y": 80, ...}
score = engine.calculate(features, "TEST_SCHEME", date(2024, 1, 15))
print(score.to_json())
```

---

## Debugging Tips

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or for specific module
logging.getLogger('fund_engine.domain.features.feature_engineering').setLevel(logging.DEBUG)
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `category_percentile_1y` not defined | Feature pipeline didn't compute for scheme's category | Check `scheme_categories` mapping loaded correctly |
| Alpha is None | No benchmark data for scheme's category | Verify `benchmark_navs` loaded for benchmark_code |
| Rule eval error "name X not defined" | Feature missing from features dict | Check feature names match rule conditions exactly |
| Score > 100 or < 0 | Penalty or component calculation bug | Check `_calculate_penalty` and component scoring |

### Inspect Intermediate Data
```python
# Save features for debugging
pipeline.export_features(features, "debug_features.json")

# Save alerts
import json
with open("debug_alerts.json", "w") as f:
    json.dump([a.to_dict() for a in alerts], f, indent=2, default=str)
```

---

## Code Style & Conventions

### Python
- Type hints mandatory for public APIs
- Dataclasses for data models
- Enums for fixed value sets
- Docstrings for all public classes/functions
- Max line length: 100 chars

### Naming
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

### Error Handling
- Custom exceptions per module (`IngestionError`, `RuleEvaluationError`)
- Fail fast for data integrity issues
- Graceful degradation for optional sources (log warning, continue)

---

## Performance Optimization

### Current Benchmarks (10 schemes, 2 years data)
| Stage | Time |
|-------|------|
| Ingestion (mocked) | < 1s |
| Dedup (100 folios) | < 10ms |
| Features (10 schemes) | ~500ms |
| Rules (10 schemes) | < 50ms |
| Scoring (10 schemes) | < 50ms |
| **Total** | **~600ms** |

### Scaling to 400 Schemes
- Feature engineering: Parallelize per scheme (`multiprocessing.Pool`)
- Rules/Scoring: Already O(n), trivial
- Database: Index on `(scheme_code, as_of_date)` for all tables

---

## Contributing

1. Create feature branch: `git checkout -b feature/xxx`
2. Add tests for new functionality
3. Run full test suite: `python -m pytest`
4. Update documentation if needed
5. Submit PR with description of changes

### Pre-commit Checklist
- [ ] All tests pass
- [ ] Type hints added
- [ ] Docstrings updated
- [ ] Config versioned if changed
- [ ] No hardcoded secrets
