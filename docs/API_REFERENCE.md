# API Reference

## Base URL
```
Production:  https://api.fundmonitor.example.com/api/v1
Development: http://localhost:3000/api/v1
```

## Authentication
All endpoints require API key in header:
```
Authorization: Bearer <API_KEY>
```
Or query parameter: `?api_key=<API_KEY>`

---

## Fund Scores

### Get Fund Scores
Retrieve fund health scores for one or more schemes.

**Endpoint**: `GET /scores`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `as_of_date` | string (YYYY-MM-DD) | Yes | Score date |
| `scheme_codes` | string (comma-separated) | No | Filter by scheme codes |
| `category` | string | No | Filter by SEBI category |
| `min_score` | integer | No | Minimum score filter (0-100) |
| `max_score` | integer | No | Maximum score filter (0-100) |
| `limit` | integer | No | Max results (default: 100, max: 500) |
| `offset` | integer | No | Pagination offset |

**Response**:
```json
{
  "as_of_date": "2024-01-15",
  "total": 342,
  "limit": 100,
  "offset": 0,
  "scores": [
    {
      "scheme_code": "INF204K01VX3",
      "fund_health_score": 82,
      "category_rank": 8,
      "category_percentile": 78.5,
      "breakdown": [
        {
          "component": "benchmark_outperformance",
          "points": 12.0,
          "max_points": 30,
          "reason": "Beat benchmark by 2.4% over 1Y",
          "raw_value": 0.024
        },
        {
          "component": "category_ranking",
          "points": 15.7,
          "max_points": 20,
          "reason": "Ranked #8 in category (78th percentile)",
          "raw_value": 78.5
        },
        {
          "component": "consistency_of_returns",
          "points": 18.9,
          "max_points": 20,
          "reason": "1 consecutive underperformance month",
          "raw_value": 1.0
        },
        {
          "component": "drawdown_control",
          "points": 10.0,
          "max_points": 15,
          "reason": "Good drawdown control (12.0% max DD)",
          "raw_value": 0.12
        },
        {
          "component": "volatility_adjusted",
          "points": 10.0,
          "max_points": 15,
          "reason": "Moderate volatility (18.5% annualized)",
          "raw_value": 0.185
        }
      ],
      "penalty": 2.0,
      "scoring_config_version": "1.0"
    }
  ]
}
```

### Get Single Fund Score
**Endpoint**: `GET /scores/{scheme_code}`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `as_of_date` | string | Yes | Score date |

---

## Alerts

### Get Alerts
Retrieve triggered alerts with filtering.

**Endpoint**: `GET /alerts`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `as_of_date` | string | Yes | Alert date |
| `scheme_codes` | string | No | Filter by scheme codes |
| `alert_types` | string | No | Comma-separated alert types |
| `severities` | string | No | Comma-separated: low,medium,high |
| `resolved` | boolean | No | Include resolved alerts |
| `limit` | integer | No | Max results (default: 100) |
| `offset` | integer | No | Pagination offset |

**Response**:
```json
{
  "as_of_date": "2024-01-15",
  "total": 27,
  "limit": 100,
  "offset": 0,
  "alerts": [
    {
      "alert_id": "underperform_6m_INF204K01VX3_2024-01-15_1",
      "scheme_code": "INF204K01VX3",
      "alert_type": "underperform_6m",
      "severity": "high",
      "triggered_on": "2024-01-15",
      "resolved_on": null,
      "details": {
        "rule_id": "underperform_6m",
        "condition": "consecutive_underperf_months >= 6",
        "feature_values": {
          "consecutive_underperf_months": 7
        }
      }
    }
  ]
}
```

### Alert Types Reference
| Type | Description | Severity |
|------|-------------|----------|
| `underperform_3m` | 3+ consecutive months underperforming benchmark | medium |
| `underperform_6m` | 6+ consecutive months underperforming benchmark | high |
| `below_top25_category` | Category percentile < 75 (1Y) | medium |
| `below_top50_category` | Category percentile < 50 (1Y) | high |
| `rank_decline` | Category rank dropped >10 positions in 3M | medium |
| `benchmark_deviation` | \|1Y alpha\| > 5% (configurable per category) | low |
| `high_drawdown` | 1Y max drawdown > 20% | medium |
| `high_volatility` | 1Y annualized volatility > 25% | low |
| `consecutive_underperf` | 4+ consecutive underperformance months | medium |

---

## Client Portfolio

### Get Client Portfolio
Complete portfolio view with scores and alerts.

**Endpoint**: `GET /clients/{client_id}/portfolio`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `as_of_date` | string | Yes | Portfolio date |

**Response**:
```json
{
  "client_id": "CLIENT_001",
  "as_of_date": "2024-01-15",
  "holdings": [
    {
      "folio_id": "FOL_001",
      "scheme_code": "INF204K01VX3",
      "scheme_name": "HDFC Top 100 Fund",
      "category": "Large Cap",
      "benchmark": "Nifty 100 TRI",
      "units": 1000,
      "invested_value": 50000,
      "current_value": 65000,
      "unrealized_pnl": 15000,
      "score": 82,
      "category_rank": 8,
      "category_percentile": 78.5,
      "alerts": [
        {
          "alert_type": "benchmark_deviation",
          "severity": "low"
        }
      ]
    }
  ],
  "summary": {
    "total_invested": 500000,
    "total_current": 620000,
    "total_unrealized_pnl": 120000,
    "avg_score": 76.3,
    "high_alerts": 1,
    "medium_alerts": 2,
    "low_alerts": 3,
    "holdings_count": 12
  }
}
```

---

## Schemes

### Get Scheme Master
**Endpoint**: `GET /schemes`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scheme_codes` | string | No | Comma-separated |
| `category` | string | No | SEBI category filter |
| `amc` | string | No | AMC filter |
| `active_only` | boolean | No | Default: true |

### Get Scheme Details
**Endpoint**: `GET /schemes/{scheme_code}`

**Response**:
```json
{
  "scheme_code": "INF204K01VX3",
  "scheme_name": "HDFC Top 100 Fund",
  "amc": "HDFC Mutual Fund",
  "category": "Large Cap",
  "sub_category": null,
  "benchmark_index": "NIFTY100_TRI",
  "benchmark_name": "Nifty 100 TRI",
  "fund_manager": "Prashant Jain",
  "expense_ratio": 1.05,
  "aum": 25000,
  "inception_date": "2010-01-01",
  "last_updated": "2024-01-14",
  "is_active": true,
  "source_folio_codes": ["FOL_001", "FOL_002", ...]
}
```

---

## Benchmarks

### Get Benchmark Values
**Endpoint**: `GET /benchmarks/{benchmark_code}/history`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | No | Start date (default: 1 year ago) |
| `to_date` | string | No | End date (default: today) |

**Response**:
```json
{
  "benchmark_code": "NIFTY100_TRI",
  "benchmark_name": "Nifty 100 TRI",
  "data": [
    {"date": "2024-01-15", "value": 25432.15},
    {"date": "2024-01-12", "value": 25387.90}
  ]
}
```

---

## Macro Indicators

### Get Macro Data
**Endpoint**: `GET /macro`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `indicators` | string | No | Comma-separated: repo_rate,cpi,usd_inr,vix |
| `from_date` | string | No | Start date |
| `to_date` | string | No | End date |

**Response**:
```json
{
  "data": {
    "repo_rate": [
      {"date": "2024-01-01", "value": 6.5}
    ],
    "cpi": [
      {"date": "2024-01-01", "value": 5.69}
    ],
    "usd_inr": [
      {"date": "2024-01-15", "value": 83.12}
    ],
    "india_vix": [
      {"date": "2024-01-15", "value": 14.23}
    ]
  }
}
```

---

## Health & Metadata

### Health Check
**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "dependencies": {
    "database": "healthy",
    "ingestion_amfi": "healthy",
    "ingestion_mfapi": "healthy",
    "ingestion_nse": "healthy"
  },
  "last_pipeline_run": "2024-01-15T03:30:00Z",
  "data_freshness": {
    "nav_history": "2024-01-14",
    "fund_scores": "2024-01-15",
    "fund_alerts": "2024-01-15"
  }
}
```

### Get Scoring Config
**Endpoint**: `GET /meta/scoring-config`

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `version` | string | No | Config version (default: latest) |

### Get Rules Config
**Endpoint**: `GET /meta/rules-config`

---

## Error Responses

### Standard Error Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid query parameters",
    "details": [
      {"field": "as_of_date", "message": "Required parameter missing"}
    ]
  }
}
```

### Error Codes
| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid query parameters |
| `NOT_FOUND` | 404 | Resource not found |
| `UNAUTHORIZED` | 401 | Invalid/missing API key |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Dependency unavailable |

---

## Rate Limits

| Tier | Requests/Minute | Requests/Day |
|------|-----------------|--------------|
| Free | 60 | 10,000 |
| Pro | 300 | 100,000 |
| Enterprise | 1000 | Unlimited |

Headers:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1705312800
```

---

## Pagination

All list endpoints support:
```
?limit=50&offset=100
```

Response includes:
```json
{
  "total": 342,
  "limit": 50,
  "offset": 100,
  "data": [...]
}
```

---

## Webhooks (Optional)

Configure webhook URLs for real-time alert notifications:

**Payload**:
```json
{
  "event": "alert_triggered",
  "timestamp": "2024-01-15T03:30:00Z",
  "data": {
    "alert_id": "...",
    "scheme_code": "INF204K01VX3",
    "alert_type": "underperform_6m",
    "severity": "high"
  }
}
```