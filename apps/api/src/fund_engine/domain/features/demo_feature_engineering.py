"""
Demo: Feature Engineering Pipeline
Nightly batch computes: Rolling returns, Alpha, Drawdown, Volatility, Category Percentile
"""

import numpy as np
import pandas as pd
from datetime import date
from fund_engine.domain.features.feature_engineering import (
    FeatureEngineeringPipeline,
    ReturnPeriod,
    create_sample_nav_series,
)


def main():
    print("=" * 80)
    print("FEATURE ENGINEERING PIPELINE - DEMO")
    print("=" * 80)
    
    # Create pipeline
    pipeline = FeatureEngineeringPipeline()
    
    # Generate sample data for 5 schemes in "Large Cap" category
    print("\n[1] Generating sample NAV data for 5 schemes (Large Cap)...")
    np.random.seed(42)
    
    nav_records = []
    benchmark_records = []
    scheme_categories = {}
    
    # 5 schemes with slightly different returns
    for i in range(5):
        scheme_code = f"SCHEME_{i+1:02d}"
        scheme_categories[scheme_code] = "Large Cap"
        
        # Different base returns for each scheme
        base_return = 0.0003 + i * 0.00005  # 0.03% to 0.05% daily
        dates = pd.date_range("2022-01-01", periods=500, freq="B")
        daily_returns = np.random.normal(base_return, 0.01, len(dates))
        navs = [100]
        for r in daily_returns:
            navs.append(navs[-1] * (1 + r))
        
        for d, nav in zip(dates, navs[1:]):
            nav_records.append({
                "scheme_code": scheme_code,
                "nav_date": d.date(),
                "nav_value": round(nav, 4),
            })
    
    # Benchmark NIFTY100_TRI
    bench_dates = pd.date_range("2022-01-01", periods=500, freq="B")
    bench_returns = np.random.normal(0.0003, 0.009, len(bench_dates))
    bench_navs = [20000]
    for r in bench_returns:
        bench_navs.append(bench_navs[-1] * (1 + r))
    
    for d, nav in zip(bench_dates, bench_navs[1:]):
        benchmark_records.append({
            "benchmark_code": "NIFTY100_TRI",
            "index_date": d.date(),
            "index_value": round(nav, 2),
        })
    
    print(f"   Generated {len(nav_records)} NAV records across 5 schemes")
    print(f"   Generated {len(benchmark_records)} benchmark records")
    
    # Load data into pipeline
    print("\n[2] Loading data into pipeline...")
    pipeline.load_nav_history(nav_records)
    pipeline.load_benchmark_history(benchmark_records)
    pipeline.load_scheme_categories(scheme_categories)
    
    print(f"   Loaded {len(pipeline.scheme_navs)} schemes")
    print(f"   Loaded {len(pipeline.benchmark_navs)} benchmarks")
    print(f"   Categories: {set(pipeline.scheme_categories.values())}")
    
    # Compute features
    print("\n[3] Computing features as of 2023-12-29...")
    features = pipeline.compute_all_features(date(2023, 12, 29))
    
    print(f"   Computed features for {len(features)} schemes")
    
    # Display results
    print("\n[4] Feature Summary (per scheme):")
    print("-" * 80)
    
    for f in features:
        print(f"\n  Scheme: {f.scheme_code}")
        print(f"    Category: {pipeline.scheme_categories.get(f.scheme_code)}")
        
        # Helper for formatting
        def fmt_pct(v):
            return f"{v:.2%}" if v is not None else "N/A"
        def fmt_val(v):
            return f"{v:.2%}" if v is not None else "N/A"
        def fmt_int(v):
            return str(v) if v is not None else "N/A"
        
        # Returns
        r = f.rolling_returns
        print(f"    Returns: 1M={fmt_pct(r.return_1m)} | 3M={fmt_pct(r.return_3m)} | "
              f"6M={fmt_pct(r.return_6m)} | 1Y={fmt_pct(r.return_1y)} | 3Y={fmt_pct(r.return_3y)}")
        
        # Alpha vs benchmark
        print(f"    Alpha:   1M={fmt_val(f.alpha_1m)} | 3M={fmt_val(f.alpha_3m)} | "
              f"1Y={fmt_val(f.alpha_1y)} | 3Y={fmt_val(f.alpha_3y)}")
        
        # Risk metrics
        print(f"    Drawdown: 1Y={fmt_pct(f.max_drawdown_1y)} | 3Y={fmt_pct(f.max_drawdown_3y)}")
        print(f"    Volatility: 1M={fmt_pct(f.volatility_1m)} | 3M={fmt_pct(f.volatility_3m)} | "
              f"1Y={fmt_pct(f.volatility_1y)} | 3Y={fmt_pct(f.volatility_3y)}")
        
        # Category-relative
        print(f"    Category Rank: 1M={fmt_int(f.category_rank_1m)} | 3M={fmt_int(f.category_rank_3m)} | "
              f"1Y={fmt_int(f.category_rank_1y)} | 3Y={fmt_int(f.category_rank_3y)}")
        print(f"    Category Pctl: 1M={fmt_int(f.category_percentile_1m)}% | "
              f"3M={fmt_int(f.category_percentile_3m)}% | 1Y={fmt_int(f.category_percentile_1y)}%")
        
        # Streaks & correlation
        print(f"    Consecutive Underperf Months: {f.consecutive_underperf_months}")
        print(f"    Correlation to Benchmark (1Y): {f.correlation_to_benchmark_1y:.3f}")
    
    # Show category ranking table
    print("\n[5] Category Ranking (1Y Return):")
    print("-" * 80)
    print(f"  {'Scheme':<12} {'Return':>8} {'Alpha':>8} {'Rank':>4} {'Pctl':>5} {'DD':>7} {'Vol':>7}")
    print("  " + "-" * 65)
    
    for f in sorted(features, key=lambda x: x.rolling_returns.return_1y or -1, reverse=True):
        r = f.rolling_returns
        ret = f"{r.return_1y:.2%}" if r.return_1y else "N/A"
        alp = f"{f.alpha_1y:.2%}" if f.alpha_1y else "N/A"
        rank = str(f.category_rank_1y) if f.category_rank_1y else "N/A"
        pctl = f"{f.category_percentile_1y:.0f}%" if f.category_percentile_1y else "N/A"
        dd = f"{f.max_drawdown_1y:.1%}" if f.max_drawdown_1y else "N/A"
        vol = f"{f.volatility_1y:.1%}" if f.volatility_1y else "N/A"
        print(f"  {f.scheme_code:<12} {ret:>8} {alp:>8} {rank:>4} {pctl:>5} {dd:>7} {vol:>7}")
    
    # Architecture summary
    print("\n" + "=" * 80)
    print("ARCHITECTURE SUMMARY")
    print("=" * 80)
    print("""
+---------------------------------------------------------------+
|              FEATURE ENGINEERING PIPELINE                      |
+-------------------+-------------------------------------------+
| Input             | nav_history (scheme_code, date, NAV)       |
|                   | benchmark_history (bench_code, date, val)  |
|                   | scheme_categories (scheme_code -> category)|
+-------------------+-------------------------------------------+
| Computation       | Per unique scheme (~400), NOT per folio    |
| Frequency         | Nightly batch                              |
| Output            | fund_rolling_returns (materialized)        |
|                   | fund_features (for rule/scoring engine)    |
+-------------------+-------------------------------------------+
| Features Computed:                                        |
|  - Rolling Returns (1M, 3M, 6M, 1Y, 3Y, 5Y)              |
|  - Alpha vs Benchmark (all periods)                      |
|  - Max Drawdown (1Y, 3Y)                                 |
|  - Volatility (1M, 3M, 1Y, 3Y) - annualized              |
|  - Category Percentile Rank (all periods)                |
|  - Consecutive Underperformance Streak                  |
|  - Correlation to Benchmark (1Y, 3Y)                    |
+-------------------+-------------------------------------------+
| Key Design Decisions:                                     |
|  1. Simple return for <1Y, CAGR for >=1Y                  |
|  2. Business-day aligned windows (not calendar)           |
|  3. Category-relative percentile (not absolute)           |
|  4. Drawdown = peak-to-trough, positive percentage        |
|  5. Volatility = annualized std dev of daily returns      |
|  6. Correlation on aligned daily returns                  |
+---------------------------------------------------------------+
""")
    
    print("[SUCCESS] Feature engineering pipeline demo complete!")
    print("Next: Rule Engine (alert rules) + Scoring Engine (0-100 fund health score)")


if __name__ == "__main__":
    main()