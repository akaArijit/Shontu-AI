"""
End-to-End Integration Test: Complete Fund Monitoring Pipeline
Demonstrates: Resolution → Ingestion → Features → Rules → Scoring → Output
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
import tempfile
import os

# Import all modules
from resolution.scheme_dedup import SchemeDeduplicator, SchemeMaster, SchemeCategory, create_scheme_master_from_folio
from resolution.benchmark_mapping import BenchmarkResolver
from ingestion.fetchers import IngestionOrchestrator, AmfiNavFetcher, MfapiFetcher
from features.feature_engineering import FeatureEngineeringPipeline, create_sample_nav_series
from rules.rule_engine import create_default_engine, AlertSeverity
from scoring.scoring_engine import create_default_scoring_engine


def generate_test_data():
    """Generate realistic test data for 10 schemes, 100 folios"""
    np.random.seed(42)
    
    # 10 unique schemes across categories
    schemes = [
        ("SCHEME_01", "HDFC Top 100", "HDFC MF", "Large Cap"),
        ("SCHEME_02", "PPFAS Flexi Cap", "PPFAS MF", "Flexi Cap"),
        ("SCHEME_03", "HDFC Mid-Cap Opp", "HDFC MF", "Mid Cap"),
        ("SCHEME_04", "SBI Small Cap", "SBI MF", "Small Cap"),
        ("SCHEME_05", "ICICI Pru L&M Cap", "ICICI MF", "Large & Mid Cap"),
        ("SCHEME_06", "ICICI Pru Equity & Debt", "ICICI MF", "Hybrid Aggressive"),
        ("SCHEME_07", "HDFC Ultra Short", "HDFC MF", "Debt - Ultra Short Duration"),
        ("SCHEME_08", "Nippon India ETF Nifty 50", "Nippon MF", "Large Cap"),
        ("SCHEME_09", "Kotak Small Cap", "Kotak MF", "Small Cap"),
        ("SCHEME_10", "UTI Nifty 50 Index", "UTI MF", "Large Cap"),
    ]
    
    # 100 folios mapping to schemes (some multiple folios per scheme)
    folios = []
    for i in range(100):
        scheme_idx = i % 10
        scheme_code, scheme_name, amc, category = schemes[scheme_idx]
        folios.append({
            "folio_id": f"FOL_{i+1:04d}",
            "client_id": f"CLIENT_{(i // 5) + 1:03d}",  # 20 clients
            "scheme_code": scheme_code,
            "scheme_name": scheme_name,
            "amc": amc,
            "category": category,
            "units": np.random.randint(100, 10000),
            "invested_value": np.random.randint(50000, 5000000),
            "current_value": np.random.randint(50000, 6000000),
        })
    
    return schemes, folios


def run_e2e_pipeline():
    """Run the complete pipeline end-to-end"""
    print("=" * 80)
    print("END-TO-END PIPELINE: Fund Monitoring & Scoring Engine")
    print("=" * 80)
    
    # Generate test data
    schemes_data, folios = generate_test_data()
    print(f"\n[1] Generated test data: {len(folios)} folios across {len(schemes_data)} unique schemes")
    
    # ============================================================
    # STEP 1: SCHEME DEDUPLICATION (Resolution Layer)
    # ============================================================
    print("\n" + "=" * 80)
    print("STEP 1: SCHEME DEDUPLICATION")
    print("=" * 80)
    
    dedup = SchemeDeduplicator()
    
    # Register master schemes
    master_schemes = []
    for scheme_code, scheme_name, amc, category in schemes_data:
        master = SchemeMaster(
            scheme_code=scheme_code,
            scheme_name=scheme_name,
            amc=amc,
            category=SchemeCategory(category),
        )
        master_schemes.append(master)
    dedup.register_schemes_bulk(master_schemes)
    print(f"  Registered {len(master_schemes)} schemes in master registry")
    
    # Resolve folios to schemes
    resolution_results = dedup.resolve_folios_batch(folios)
    print(f"  Resolved {len(resolution_results)} folios -> {dedup.get_dedup_stats()['unique_schemes']} unique schemes")
    
    # Show dedup stats
    stats = dedup.get_dedup_stats()
    print(f"  Dedup ratio: {stats['avg_folios_per_scheme']:.1f} folios per scheme")
    
    # ============================================================
    # STEP 2: BENCHMARK MAPPING (Resolution Layer)
    # ============================================================
    print("\n" + "=" * 80)
    print("STEP 2: BENCHMARK MAPPING")
    print("=" * 80)
    
    benchmark = BenchmarkResolver(
        explicit_mapping_path="C:/Users/ariji/Desktop/Shontu AI/fund-engine/resolution/explicit_benchmark_mappings.json"
    )
    
    # Resolve benchmarks for all schemes
    scheme_benchmarks = {}
    for scheme in master_schemes:
        bm = benchmark.resolve(scheme.scheme_code, scheme.scheme_name, scheme.category.value)
        scheme_benchmarks[scheme.scheme_code] = {
            "benchmark_code": bm.benchmark_code.value,
            "benchmark_name": bm.benchmark_name,
            "source": bm.source,
            "confidence": bm.confidence,
        }
        print(f"  {scheme.scheme_code}: {bm.benchmark_name} ({bm.source}, conf={bm.confidence})")
    
    # ============================================================
    # STEP 3: FEATURE ENGINEERING
    # ============================================================
    print("\n" + "=" * 80)
    print("STEP 3: FEATURE ENGINEERING")
    print("=" * 80)
    
    # Generate NAV history for each scheme (2 years of data)
    pipeline = FeatureEngineeringPipeline()
    nav_records = []
    benchmark_records = []
    scheme_categories = {}
    
    for scheme_code, scheme_name, amc, category in schemes_data:
        scheme_categories[scheme_code] = category
        
        # Scheme NAV with different characteristics per category
        if category == "Large Cap":
            base_return, vol = 0.0004, 0.009
        elif category == "Mid Cap":
            base_return, vol = 0.0005, 0.012
        elif category == "Small Cap":
            base_return, vol = 0.0006, 0.015
        elif category == "Flexi Cap":
            base_return, vol = 0.00045, 0.010
        elif category == "Large & Mid Cap":
            base_return, vol = 0.00045, 0.010
        elif category == "Hybrid Aggressive":
            base_return, vol = 0.00035, 0.008
        elif category == "Debt - Ultra Short Duration":
            base_return, vol = 0.00015, 0.001
        else:
            base_return, vol = 0.0004, 0.009
        
        dates = pd.date_range("2022-01-01", periods=500, freq="B")
        daily_returns = np.random.normal(base_return, vol, len(dates))
        navs = [100]
        for r in daily_returns:
            navs.append(navs[-1] * (1 + r))
        
        for d, nav in zip(dates, navs[1:]):
            nav_records.append({
                "scheme_code": scheme_code,
                "nav_date": d.date(),
                "nav_value": round(nav, 4),
            })
    
    # Benchmark NAV (NIFTY100_TRI for Large Cap)
    bench_dates = pd.date_range("2022-01-01", periods=500, freq="B")
    bench_returns = np.random.normal(0.00035, 0.009, len(bench_dates))
    bench_navs = [20000]
    for r in bench_returns:
        bench_navs.append(bench_navs[-1] * (1 + r))
    
    for d, nav in zip(bench_dates, bench_navs[1:]):
        benchmark_records.append({
            "benchmark_code": "NIFTY100_TRI",
            "index_date": d.date(),
            "index_value": round(nav, 2),
        })
    
    # Load and compute
    pipeline.load_nav_history(nav_records)
    pipeline.load_benchmark_history(benchmark_records)
    pipeline.load_scheme_categories(scheme_categories)
    
    as_of_date = date(2023, 12, 29)
    features_list = pipeline.compute_all_features(as_of_date)
    print(f"  Computed features for {len(features_list)} schemes")
    
    # Convert to dict for downstream
    features_dicts = [f.to_dict() for f in features_list]
    for f in features_dicts:
        f["category"] = scheme_categories[f["scheme_code"]]
    
    # ============================================================
    # STEP 4: RULE ENGINE (Alerts)
    # ============================================================
    print("\n" + "=" * 80)
    print("STEP 4: RULE ENGINE (ALERTS)")
    print("=" * 80)
    
    rule_engine = create_default_engine()
    alerts = rule_engine.evaluate_batch(features_dicts, as_of_date)
    print(f"  Generated {len(alerts)} alerts across {len(features_dicts)} schemes")
    
    # Group by severity
    by_severity = {}
    for a in alerts:
        by_severity.setdefault(a.severity, []).append(a)
    
    for sev in [AlertSeverity.HIGH, AlertSeverity.MEDIUM, AlertSeverity.LOW]:
        if sev in by_severity:
            print(f"  {sev.value.upper()}: {len(by_severity[sev])} alerts")
            for a in by_severity[sev][:3]:  # Show first 3
                print(f"    - {a.scheme_code}: {a.alert_type.value}")
    
    # ============================================================
    # STEP 5: SCORING ENGINE
    # ============================================================
    print("\n" + "=" * 80)
    print("STEP 5: SCORING ENGINE (0-100 Fund Health Score)")
    print("=" * 80)
    
    scoring_engine = create_default_scoring_engine()
    scores = scoring_engine.calculate_batch(features_dicts, as_of_date)
    
    # Sort by score descending
    scores.sort(key=lambda s: s.fund_health_score, reverse=True)
    
    print(f"\n  {'Scheme':<25} {'Score':>5} {'Penalty':>8} {'Bench':>5} {'Rank':>5} {'Consist':>7} {'DD':>5} {'Vol':>5}")
    print("  " + "-" * 75)
    for score in scores:
        breakdown = {b.component: b for b in score.breakdown}
        print(f"  {score.scheme_code:<25} {score.fund_health_score:>5} {score.penalty:>7.1f} "
              f"{breakdown['benchmark_outperformance'].points:>5.1f} "
              f"{breakdown['category_ranking'].points:>5.1f} "
              f"{breakdown['consistency_of_returns'].points:>7.1f} "
              f"{breakdown['drawdown_control'].points:>5.1f} "
              f"{breakdown['volatility_adjusted'].points:>5.1f}")
    
    # ============================================================
    # STEP 6: FINAL OUTPUT (Client-ready)
    # ============================================================
    print("\n" + "=" * 80)
    print("STEP 6: CLIENT-READY OUTPUT")
    print("=" * 80)
    
    # Combine everything for final output
    print("\n  Sample client folio report:")
    print("  " + "-" * 70)
    
    # Take first 3 folios
    for folio in folios[:3]:
        scheme_code = folio["scheme_code"]
        scheme_master = dedup.get_scheme_master(scheme_code)
        scheme_features = next(f for f in features_dicts if f["scheme_code"] == scheme_code)
        scheme_score = next(s for s in scores if s.scheme_code == scheme_code)
        scheme_alerts = [a for a in alerts if a.scheme_code == scheme_code]
        
        print(f"\n  Folio: {folio['folio_id']} | Client: {folio['client_id']}")
        print(f"    Fund: {scheme_master.scheme_name} ({scheme_code})")
        print(f"    Category: {scheme_master.category.value} | Benchmark: {scheme_benchmarks[scheme_code]['benchmark_name']}")
        print(f"    Score: {scheme_score.fund_health_score}/100")
        rank_str = f"#{scheme_score.category_rank}" if scheme_score.category_rank else "N/A"
        pctl_str = f"{scheme_score.category_percentile:.0f}th percentile" if scheme_score.category_percentile else "N/A"
        print(f"    Category Rank: {rank_str} ({pctl_str})")
        
        if scheme_alerts:
            print(f"    Alerts ({len(scheme_alerts)}):")
            for a in scheme_alerts:
                print(f"      [{a.severity.value.upper()}] {a.alert_type.value}")
        else:
            print(f"    Alerts: None")
    
    # Summary stats
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"""
  Input:     {len(folios)} folios, {len(schemes_data)} unique schemes
  Dedup:     {stats['total_folios_mapped']} folios -> {stats['unique_schemes']} schemes ({stats['avg_folios_per_scheme']:.1f}x reduction)
  Features:  {len(features_list)} schemes scored
  Alerts:    {len(alerts)} total ({len(by_severity.get(AlertSeverity.HIGH, []))} HIGH, {len(by_severity.get(AlertSeverity.MEDIUM, []))} MEDIUM, {len(by_severity.get(AlertSeverity.LOW, []))} LOW)
  Scores:    Avg={np.mean([s.fund_health_score for s in scores]):.1f}, Range={min(s.fund_health_score for s in scores)}-{max(s.fund_health_score for s in scores)}
  
  Compute:   Per unique scheme ({stats['unique_schemes']}), NOT per folio ({len(folios)})
  Storage:   fund_scores + fund_alerts + scheme_master (JOIN for client views)
""")
    
    print("[SUCCESS] End-to-end pipeline completed successfully!")
    
    return {
        "dedup_stats": stats,
        "features": features_dicts,
        "alerts": alerts,
        "scores": scores,
        "benchmarks": scheme_benchmarks,
    }


if __name__ == "__main__":
    results = run_e2e_pipeline()