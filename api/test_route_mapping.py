"""Contract tests for the API row → response mappers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from api.routes import mfd_scores

AS_OF = date(2026, 10, 27)


def test_score_model_maps_breakdown_and_decimals():
    row = {
        "scheme_code": "100001",
        "scheme_name": "Alpha Fund",
        "category": None,
        "amc": None,
        "benchmark_name": None,
        "fund_health_score": 72,
        "category_rank": 3,
        "category_percentile": Decimal("88.50"),
        "score_breakdown": [
            {
                "component": "1Y Return",
                "points": 22.0,
                "max_points": 25,
                "reason": "Top quartile",
                "raw_value": 0.18,
            }
        ],
        "penalty": Decimal("1.5"),
        "scoring_config_version": "1.0",
        "as_of_date": AS_OF,
    }

    model = mfd_scores._score_model(row)

    assert model.category == "Unclassified"
    assert model.amc == "Unknown"
    assert model.benchmark_name == "Unclassified"
    assert model.category_percentile == 88.5
    assert model.penalty == 1.5
    assert model.breakdown[0].component == "1Y Return"
    assert model.as_of_date == AS_OF


def test_scheme_model_defaults_missing_metrics():
    row = {
        "scheme_code": "100001",
        "scheme_name": "Alpha Fund",
        "amc": "Alpha AMC",
        "category": "Large Cap",
        "benchmark_name": "Nifty 100 TRI",
        "fund_health_score": 55,
        "category_rank": None,
        "category_percentile": None,
        "return_1y": None,
        "alpha_1y": None,
        "max_drawdown_1y": None,
        "volatility_1y": None,
        "consecutive_underperf_months": None,
        "high_alerts": None,
        "medium_alerts": None,
        "low_alerts": None,
    }

    model = mfd_scores._scheme_model(row)

    assert model.category_rank is None
    assert model.return_1y is None
    assert model.consecutive_underperf_months == 0
    assert (model.high_alerts, model.medium_alerts, model.low_alerts) == (0, 0, 0)


def test_ranking_model_handles_missing_percentile():
    row = {
        "category": "Large Cap",
        "scheme_code": "100001",
        "scheme_name": "Alpha Fund",
        "fund_health_score": 61,
        "category_rank": None,
        "category_percentile": None,
        "return_1y": Decimal("0.1234"),
        "alpha_1y": None,
        "max_drawdown_1y": Decimal("-0.0500"),
        "volatility_1y": None,
    }

    model = mfd_scores._ranking_model(row)

    assert model.category_rank == 0
    assert model.category_percentile == 0.0
    assert model.return_1y == 0.1234
    assert model.max_drawdown_1y == -0.05


def test_split_trims_and_ignores_empty_values():
    assert mfd_scores._split(None) is None
    assert mfd_scores._split("  ") is None
    assert mfd_scores._split(" a, ,b ") == ["a", "b"]
