"""
Demo: Rule Engine
YAML-config deterministic alert rules evaluated nightly per scheme
"""

from datetime import date
from rule_engine import (
    RuleEngine,
    AlertRule,
    AlertType,
    AlertSeverity,
    create_default_engine,
)


def main():
    print("=" * 80)
    print("RULE ENGINE - DEMO")
    print("=" * 80)
    
    # Create engine with default rules
    engine = create_default_engine()
    print(f"\nLoaded {len(engine.rules)} default rules:")
    for rule in engine.rules:
        print(f"  {rule.id}: {rule.alert_type.value} ({rule.severity.value}) - {rule.description}")
    
    # Test schemes
    print("\n" + "=" * 80)
    print("TESTING SCHEMES")
    print("=" * 80)
    
    # Good fund
    good_fund = {
        "scheme_code": "HDFC_TOP_100",
        "category": "Large Cap",
        "alpha_1y": 0.03,
        "alpha_3m": 0.01,
        "category_percentile_1y": 85,
        "category_percentile_3m": 80,
        "category_rank_1y": 5,
        "category_rank_3m": 8,
        "max_drawdown_1y": 0.12,
        "volatility_1y": 0.16,
        "consecutive_underperf_months": 0,
        "correlation_to_benchmark_1y": 0.85,
    }
    
    # Bad fund
    bad_fund = {
        "scheme_code": "POOR_PERFORMER",
        "category": "Large Cap",
        "alpha_1y": -0.08,
        "alpha_3m": -0.03,
        "category_percentile_1y": 30,
        "category_percentile_3m": 25,
        "category_rank_1y": 85,
        "category_rank_3m": 50,
        "max_drawdown_1y": 0.25,
        "volatility_1y": 0.30,
        "consecutive_underperf_months": 6,
        "correlation_to_benchmark_1y": 0.60,
    }
    
    # Small cap fund (tests category overrides)
    small_cap_fund = {
        "scheme_code": "SMALL_CAP_FUND",
        "category": "Small Cap",
        "alpha_1y": -0.08,  # Would trigger for Large Cap (5% threshold)
        "alpha_3m": -0.03,
        "category_percentile_1y": 30,
        "category_percentile_3m": 25,
        "category_rank_1y": 85,
        "category_rank_3m": 50,
        "max_drawdown_1y": 0.25,
        "volatility_1y": 0.30,
        "consecutive_underperf_months": 6,
    }
    
    as_of_date = date(2023, 12, 29)
    
    # Evaluate good fund
    print("\n[1] GOOD FUND (HDFC_TOP_100 - Large Cap)")
    print("-" * 60)
    alerts = engine.evaluate(good_fund, "HDFC_TOP_100", as_of_date)
    if alerts:
        for a in alerts:
            print(f"  [{a.severity.value.upper()}] {a.alert_type.value}: {a.details.get('condition')}")
    else:
        print("  No alerts triggered [OK]")
    
    # Evaluate bad fund
    print("\n[2] BAD FUND (POOR_PERFORMER - Large Cap)")
    print("-" * 60)
    alerts = engine.evaluate(bad_fund, "POOR_PERFORMER", as_of_date)
    for a in alerts:
        print(f"  [{a.severity.value.upper()}] {a.alert_type.value}")
        print(f"       Condition: {a.details.get('condition')}")
        print(f"       Features: {a.details.get('feature_values')}")
    
    # Evaluate small cap fund (category override test)
    print("\n[3] SMALL CAP FUND (tests category override)")
    print("-" * 60)
    print("  Alpha 1Y: -8% (Large Cap threshold: 5%, Small Cap threshold: 10%)")
    alerts = engine.evaluate(small_cap_fund, "SMALL_CAP_FUND", as_of_date)
    alert_types = {a.alert_type for a in alerts}
    
    if AlertType.BENCHMARK_DEVIATION in alert_types:
        print("  [WARNING] BENCHMARK_DEVIATION triggered (override NOT working)")
    else:
        print("  [OK] BENCHMARK_DEVIATION NOT triggered (Small Cap 10% override working)")
    
    # Show other alerts for small cap
    for a in alerts:
        if a.alert_type != AlertType.BENCHMARK_DEVIATION:
            print(f"  [{a.severity.value.upper()}] {a.alert_type.value}")
    
    # Batch evaluation
    print("\n[4] BATCH EVALUATION")
    print("-" * 60)
    all_schemes = [good_fund, bad_fund, small_cap_fund]
    all_alerts = engine.evaluate_batch(all_schemes, as_of_date)
    
    by_scheme = {}
    for a in all_alerts:
        by_scheme.setdefault(a.scheme_code, []).append(a)
    
    for scheme_code, alerts in by_scheme.items():
        print(f"  {scheme_code}: {len(alerts)} alerts")
        for a in alerts:
            print(f"    [{a.severity.value[0].upper()}] {a.alert_type.value}")
    
    # YAML config demo
    print("\n[5] YAML CONFIGURATION")
    print("-" * 60)
    print("Rules can be defined in YAML for easy tuning without code changes:")
    print("""
alert_rules:
  - id: underperform_3m
    alert_type: underperform_3m
    condition: "consecutive_underperf_months >= 3"
    severity: medium
    description: "Fund underperformed benchmark for 3+ consecutive months"
    category_overrides:
      Small Cap:
        condition: "consecutive_underperf_months >= 4"
        severity: medium
  - id: custom_rule
    alert_type: high_volatility
    condition: "volatility_1y > 0.30"
    severity: high
    description: "Custom high volatility threshold"
""")
    
    # Architecture summary
    print("=" * 80)
    print("ARCHITECTURE SUMMARY")
    print("=" * 80)
    print("""
+---------------------------------------------------------------+
|                      RULE ENGINE                               |
+---------------------------------------------------------------+
| Input:    SchemeFeatures (from feature engineering pipeline)  |
| Eval:     Nightly, per unique scheme (~400)                   |
| Output:   fund_alerts table (alert_id, scheme_code, type,     |
|           severity, triggered_on, details JSON)               |
+---------------------------------------------------------------+
| Default Rules (9):                                             |
|  1. underperform_3m      - 3+ months underperf (MEDIUM)       |
|  2. underperform_6m      - 6+ months underperf (HIGH)         |
|  3. below_top25_category - Pctl < 75 in category (MEDIUM)     |
|  4. below_top50_category - Pctl < 50 in category (HIGH)       |
|  5. rank_decline         - Rank drop >10 in 3M (MEDIUM)       |
|  6. benchmark_deviation  - |Alpha| > 5% (LOW, cat overrides) |
|  7. high_drawdown        - DD > 20% (MEDIUM)                  |
|  8. high_volatility      - Vol > 25% (LOW)                    |
|  9. consecutive_underperf- 4+ months underperf (MEDIUM)       |
+---------------------------------------------------------------+
| Key Design Decisions:                                          |
|  1. Pure Python expressions in YAML - no DSL needed           |
|  2. Category overrides for different risk profiles            |
|  3. Safe eval with restricted builtins                        |
|  4. Alert details include triggering feature values           |
|  5. Rules versioned in YAML - audit trail                     |
|  6. No ML - deterministic, explainable, tunable               |
+---------------------------------------------------------------+
""")
    
    print("[SUCCESS] Rule Engine demo complete!")
    print("Next: Scoring Engine (0-100 fund health score with explainable breakdown)")


if __name__ == "__main__":
    main()