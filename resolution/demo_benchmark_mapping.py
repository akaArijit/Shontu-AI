"""
Demo: Benchmark Mapping Service
Shows two-tier resolution: explicit mappings → category fallbacks
"""

from benchmark_mapping import BenchmarkResolver, BenchmarkCode


def main():
    # Initialize resolver with explicit mappings from JSON file
    resolver = BenchmarkResolver(
        explicit_mapping_path="explicit_benchmark_mappings.json"
    )
    
    print(f"Loaded {resolver.explicit_count} explicit benchmark mappings\n")
    
    # Sample schemes from a typical MFD portfolio
    schemes = [
        {"scheme_code": "INF204K01VX3", "scheme_name": "HDFC Top 100 Fund", "category": "Large Cap"},
        {"scheme_code": "INF767K01EW8", "scheme_name": "Parag Parikh Flexi Cap Fund", "category": "Flexi Cap"},
        {"scheme_code": "INF179K01BE2", "scheme_name": "HDFC Mid-Cap Opportunities", "category": "Mid Cap"},
        {"scheme_code": "INF090I01239", "scheme_name": "SBI Small Cap Fund", "category": "Small Cap"},
        {"scheme_code": "INF843K01AB1", "scheme_name": "ICICI Pru Large & Mid Cap", "category": "Large & Mid Cap"},
        {"scheme_code": "INF247L01AH0", "scheme_name": "ICICI Pru Equity & Debt", "category": "Hybrid Aggressive"},
        {"scheme_code": "INF109K01WO3", "scheme_name": "HDFC Ultra Short Term", "category": "Debt - Ultra Short Duration"},
        {"scheme_code": "INF336L01018", "scheme_name": "Motilal Oswal S&P 500 Index", "category": "International - US"},
        # Schemes WITHOUT explicit mappings (will use category fallback)
        {"scheme_code": "NEW_FUND_001", "scheme_name": "New Large Cap Fund", "category": "Large Cap"},
        {"scheme_code": "NEW_FUND_002", "scheme_name": "New Flexi Cap Fund", "category": "Flexi Cap"},
        {"scheme_code": "NEW_FUND_003", "scheme_name": "New Sectoral Pharma", "category": "Sectoral - Pharma"},
        {"scheme_code": "NEW_FUND_004", "scheme_name": "New Thematic Fund", "category": "Thematic"},
        # Unknown category (will default)
        {"scheme_code": "MYSTERY_FUND", "scheme_name": "Mystery Fund", "category": "Crypto Yield Strategy"},
    ]
    
    print("=" * 100)
    print(f"{'Scheme Code':<18} {'Scheme Name':<30} {'Category':<25} {'Benchmark':<25} {'Source':<10} {'Conf'}")
    print("=" * 100)
    
    for scheme in schemes:
        result = resolver.resolve(
            scheme_code=scheme["scheme_code"],
            scheme_name=scheme["scheme_name"],
            category=scheme["category"]
        )
        print(f"{result.scheme_code:<18} {result.scheme_name:<30} {result.category:<25} "
              f"{result.benchmark_name:<25} {result.source:<10} {result.confidence:.1f}")
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    
    # Count by source
    results = resolver.resolve_batch(schemes)
    explicit_count = sum(1 for r in results if r.source == "explicit")
    fallback_count = sum(1 for r in results if r.source == "fallback")
    default_count = sum(1 for r in results if r.source == "default")
    
    print(f"Explicit mappings (Tier 1): {explicit_count}")
    print(f"Category fallbacks (Tier 2): {fallback_count}")
    print(f"Defaults (no match): {default_count}")
    
    # Show unmapped schemes that need attention
    unmapped = resolver.get_unmapped_schemes(schemes)
    if unmapped:
        print(f"\n[WARNING] Schemes needing explicit mapping or category review:")
        for s in unmapped:
            print(f"   - {s['scheme_code']}: {s['scheme_name']} [{s['category']}]")
    
    # Show available fallback categories
    print(f"\nSupported fallback categories ({len(resolver.fallback_categories)}):")
    for cat in sorted(resolver.fallback_categories):
        print(f"   - {cat}")


if __name__ == "__main__":
    main()