"""
Demo: Scoring Engine — 0-100 Fund Health Score with Explainable Breakdown
"""

from datetime import date
from scoring_engine import (
    ScoringEngine,
    ScoringConfig,
    ComponentConfig,
    ScoreComponent,
    create_default_scoring_engine,
)


def main():
    print("=" * 80)
    print("SCORING ENGINE - DEMO")
    print("=" * 80)
    
    engine = create_default_scoring_engine()
    
    print(f"\nConfig version: {engine.config.version}")
    print(f"Effective date: {engine.config.effective_date}")
    print(f"Penalty: {engine.config.penalty_per_month} pts/month, capped at {engine.config.penalty_cap}")
    print("\nComponents:")
    for comp, cfg in engine.config.components.items():
        print(f"  {comp.value}: weight={cfg.weight:.0%}, max_points={cfg.max_points}")
    
    # Test funds
    print("\n" + "=" * 80)
    print("SCORING TEST FUNDS")
    print("=" * 80)
    
    # 1. Star performer
    star_fund = {
        "scheme_code": "HDFC_TOP_100",
        "category": "Large Cap",
        "alpha_1y": 0.06,
        "alpha_3y": 0.04,
        "category_percentile_1y": 90,
        "category_rank_1y": 3,
        "consecutive_underperf_months": 0,
        "max_drawdown_1y": 0.08,
        "volatility_1y": 0.14,
    }
    
    # 2. Solid performer
    solid_fund = {
        "scheme_code": "ICICI_PRU_BLUECHIP",
        "category": "Large Cap",
        "alpha_1y": 0.02,
        "alpha_3y": 0.01,
        "category_percentile_1y": 70,
        "category_rank_1y": 15,
        "consecutive_underperf_months": 1,
        "max_drawdown_1y": 0.12,
        "volatility_1y": 0.16,
    }
    
    # 3. Average fund
    avg_fund = {
        "scheme_code": "SBI_BLUECHIP",
        "category": "Large Cap",
        "alpha_1y": 0.00,
        "alpha_3y": -0.01,
        "category_percentile_1y": 50,
        "category_rank_1y": 45,
        "consecutive_underperf_months": 2,
        "max_drawdown_1y": 0.18,
        "volatility_1y": 0.20,
    }
    
    # 4. Struggling fund
    struggling_fund = {
        "scheme_code": "STRUGGLING_FUND",
        "category": "Large Cap",
        "alpha_1y": -0.05,
        "alpha_3y": -0.03,
        "category_percentile_1y": 30,
        "category_rank_1y": 80,
        "consecutive_underperf_months": 4,
        "max_drawdown_1y": 0.25,
        "volatility_1y": 0.28,
    }
    
    # 5. Small cap with high vol but good returns
    small_cap = {
        "scheme_code": "SBI_SMALL_CAP",
        "category": "Small Cap",
        "alpha_1y": 0.04,
        "alpha_3y": 0.05,
        "category_percentile_1y": 75,
        "category_rank_1y": 10,
        "consecutive_underperf_months": 0,
        "max_drawdown_1y": 0.22,
        "volatility_1y": 0.26,
    }
    
    funds = [star_fund, solid_fund, avg_fund, struggling_fund, small_cap]
    as_of_date = date(2023, 12, 29)
    
    print(f"\n{'Scheme':<25} {'Score':>5} {'Penalty':>8} {'Bench':>5} {'Rank':>5} {'Consist':>7} {'DD':>5} {'Vol':>5}")
    print("-" * 80)
    
    for fund in funds:
        score = engine.calculate(fund, fund["scheme_code"], as_of_date)
        
        breakdown = {b.component: b for b in score.breakdown}
        
        print(f"{fund['scheme_code']:<25} {score.fund_health_score:>5} {score.penalty:>7.1f} "
              f"{breakdown['benchmark_outperformance'].points:>5.1f} "
              f"{breakdown['category_ranking'].points:>5.1f} "
              f"{breakdown['consistency_of_returns'].points:>7.1f} "
              f"{breakdown['drawdown_control'].points:>5.1f} "
              f"{breakdown['volatility_adjusted'].points:>5.1f}")
    
    # Detailed breakdown for one fund
    print("\n" + "=" * 80)
    print("DETAILED BREAKDOWN: STAR FUND (HDFC_TOP_100)")
    print("=" * 80)
    
    score = engine.calculate(star_fund, "HDFC_TOP_100", as_of_date)
    
    print(f"\nFinal Score: {score.fund_health_score}/100")
    print(f"Penalty Applied: {score.penalty:.1f} points")
    print(f"Config Version: {score.scoring_config_version}")
    print("\nComponent Breakdown:")
    print("-" * 80)
    print(f"{'Component':<30} {'Points':>8} {'Max':>5} {'Reason'}")
    print("-" * 80)
    
    for b in score.breakdown:
        print(f"{b.component:<30} {b.points:>7.1f} {b.max_points:>5} {b.reason}")
    
    # JSON output (for API/storage)
    print("\n" + "=" * 80)
    print("JSON OUTPUT (for API / database storage)")
    print("=" * 80)
    print(score.to_json())
    
    # Architecture summary
    print("=" * 80)
    print("ARCHITECTURE SUMMARY")
    print("=" * 80)
    print("""
+---------------------------------------------------------------+
|                      SCORING ENGINE                            |
+---------------------------------------------------------------+
| Input:    SchemeFeatures (from feature engineering)           |
| Compute:  Per unique scheme (~400), nightly                    |
| Output:   fund_scores table (scheme_code, as_of_date, score,  |
|           category_rank, category_percentile, breakdown JSON) |
+---------------------------------------------------------------+
| Formula:                                                        |
|   Score = Sum(component_points) - Penalty                      |
|   Clamped to [0, 100]                                          |
|                                                               |
| Components (100 pts total):                                    |
|   30 pts - Benchmark Outperformance (alpha vs benchmark)      |
|   20 pts - Category Ranking (percentile within category)      |
|   20 pts - Consistency (inverse of underperformance streak)   |
|   15 pts - Drawdown Control (lower max DD = better)           |
|   15 pts - Volatility Adjusted (lower vol = better)           |
|                                                               |
| Penalty: 2 pts per consecutive underperformance month         |
|          Capped at 20 pts                                      |
+---------------------------------------------------------------+
| Explainability:                                               |
|   Every component includes: points, max_points, reason,       |
|   raw_value (for audit trail)                                 |
|   Stored as JSON in fund_scores.score_breakdown               |
+---------------------------------------------------------------+
| Config Versioning:                                            |
|   ScoringConfig versioned by date                             |
|   Historical scores reproducible even after retuning          |
+---------------------------------------------------------------+
""")
    
    print("[SUCCESS] Scoring Engine demo complete!")
    print("Next: Anomaly Detection + Database Schema + API Layer + Full Pipeline")


if __name__ == "__main__":
    main()