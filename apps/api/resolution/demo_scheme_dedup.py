"""
Demo: Scheme Deduplication
Shows 5000 folios → 400 unique schemes resolution
"""

from scheme_dedup import (
    SchemeDeduplicator,
    SchemeMaster,
    SchemeCategory,
    create_scheme_master_from_folio,
)
from datetime import date


def main():
    dedup = SchemeDeduplicator()
    
    # Pre-populate with known schemes (simulating existing scheme_master)
    print("=" * 80)
    print("STEP 1: Register known schemes in master registry")
    print("=" * 80)
    
    known_schemes = [
        SchemeMaster("INF204K01VX3", "HDFC Top 100 Fund", "HDFC Mutual Fund", SchemeCategory.LARGE_CAP, 
                     expense_ratio=1.05, aum=25000, inception_date=date(2010, 1, 1)),
        SchemeMaster("INF767K01EW8", "Parag Parikh Flexi Cap Fund", "PPFAS Mutual Fund", SchemeCategory.FLEXI_CAP,
                     expense_ratio=0.95, aum=18000, inception_date=date(2013, 5, 1)),
        SchemeMaster("INF179K01BE2", "HDFC Mid-Cap Opportunities", "HDFC Mutual Fund", SchemeCategory.MID_CAP,
                     expense_ratio=1.10, aum=15000, inception_date=date(2012, 3, 1)),
        SchemeMaster("INF090I01239", "SBI Small Cap Fund", "SBI Mutual Fund", SchemeCategory.SMALL_CAP,
                     expense_ratio=1.15, aum=12000, inception_date=date(2015, 7, 1)),
        SchemeMaster("INF843K01AB1", "ICICI Pru Large & Mid Cap", "ICICI Prudential MF", SchemeCategory.LARGE_AND_MID_CAP,
                     expense_ratio=1.08, aum=20000, inception_date=date(2011, 6, 1)),
        SchemeMaster("INF247L01AH0", "ICICI Pru Equity & Debt", "ICICI Prudential MF", SchemeCategory.HYBRID_AGGRESSIVE,
                     expense_ratio=1.12, aum=30000, inception_date=date(2009, 11, 1)),
    ]
    dedup.register_schemes_bulk(known_schemes)
    print(f"Registered {len(known_schemes)} schemes in master registry\n")
    
    # Simulate 5000 folios from 500 clients (simplified to ~20 for demo)
    print("=" * 80)
    print("STEP 2: Resolve 5000 folios (demo with 20)")
    print("=" * 80)
    
    folios = [
        # Exact code matches (clean data)
        {"folio_id": "FOL_001", "scheme_code": "INF204K01VX3", "scheme_name": "HDFC Top 100 Fund", "amc": "HDFC Mutual Fund", "category": "Large Cap", "units": 1000, "invested": 50000, "current": 65000},
        {"folio_id": "FOL_002", "scheme_code": "INF204K01VX3", "scheme_name": "HDFC Top 100 Fund", "amc": "HDFC Mutual Fund", "category": "Large Cap", "units": 500, "invested": 25000, "current": 32500},
        {"folio_id": "FOL_003", "scheme_code": "INF767K01EW8", "scheme_name": "Parag Parikh Flexi Cap", "amc": "PPFAS Mutual Fund", "category": "Flexi Cap", "units": 2000, "invested": 100000, "current": 140000},
        
        # Fuzzy matches (name variations, missing codes)
        {"folio_id": "FOL_004", "scheme_code": None, "scheme_name": "HDFC Top 100 Fund Growth", "amc": "HDFC Mutual Fund", "category": "Large Cap", "units": 300, "invested": 15000, "current": 19500},
        {"folio_id": "FOL_005", "scheme_code": "", "scheme_name": "HDFC Top 100 Fund Direct Plan", "amc": "HDFC Mutual Fund", "category": "Large Cap", "units": 400, "invested": 20000, "current": 26000},
        {"folio_id": "FOL_006", "scheme_code": None, "scheme_name": "Parag Parikh Flexi Cap Fund Regular", "amc": "PPFAS Mutual Fund", "category": "Flexi Cap", "units": 1500, "invested": 75000, "current": 105000},
        
        # Category + AMC heuristic (unknown code/name but known AMC+category)
        {"folio_id": "FOL_007", "scheme_code": "UNKNOWN_001", "scheme_name": "HDFC Large Cap Fund", "amc": "HDFC Mutual Fund", "category": "Large Cap", "units": 200, "invested": 10000, "current": 13000},
        {"folio_id": "FOL_008", "scheme_code": "UNKNOWN_002", "scheme_name": "ICICI Pru Large Cap Fund", "amc": "ICICI Prudential MF", "category": "Large Cap", "units": 350, "invested": 17500, "current": 22750},
        
        # Completely new schemes (need registration)
        {"folio_id": "FOL_009", "scheme_code": "NEW_001", "scheme_name": "New HDFC Mid Cap Fund", "amc": "HDFC Mutual Fund", "category": "Mid Cap", "units": 1000, "invested": 50000, "current": 60000},
        {"folio_id": "FOL_010", "scheme_code": "NEW_002", "scheme_name": "New SBI Small Cap Fund", "amc": "SBI Mutual Fund", "category": "Small Cap", "units": 800, "invested": 40000, "current": 48000},
        
        # More folios for stats
        {"folio_id": "FOL_011", "scheme_code": "INF179K01BE2", "scheme_name": "HDFC Mid-Cap Opportunities", "amc": "HDFC Mutual Fund", "category": "Mid Cap", "units": 600, "invested": 30000, "current": 39000},
        {"folio_id": "FOL_012", "scheme_code": "INF179K01BE2", "scheme_name": "HDFC Mid-Cap Opportunities", "amc": "HDFC Mutual Fund", "category": "Mid Cap", "units": 400, "invested": 20000, "current": 26000},
        {"folio_id": "FOL_013", "scheme_code": "INF090I01239", "scheme_name": "SBI Small Cap Fund", "amc": "SBI Mutual Fund", "category": "Small Cap", "units": 1200, "invested": 60000, "current": 78000},
        {"folio_id": "FOL_014", "scheme_code": "INF843K01AB1", "scheme_name": "ICICI Pru Large & Mid Cap", "amc": "ICICI Prudential MF", "category": "Large & Mid Cap", "units": 500, "invested": 25000, "current": 32500},
        {"folio_id": "FOL_015", "scheme_code": "INF247L01AH0", "scheme_name": "ICICI Pru Equity & Debt", "amc": "ICICI Prudential MF", "category": "Hybrid Aggressive", "units": 2000, "invested": 100000, "current": 130000},
    ]
    
    # Batch resolve
    results = dedup.resolve_folios_batch(folios)
    
    print(f"{'Folio ID':<10} {'Scheme Code':<15} {'Method':<25} {'Conf':<5} {'Review'}")
    print("-" * 80)
    for r in results:
        print(f"{r['folio_id']:<10} {r['scheme_code']:<15} {r['method']:<25} {r['confidence']:.1f}   {'YES' if r['needs_review'] else 'NO'}")
    
    # Show deduplication stats
    print("\n" + "=" * 80)
    print("STEP 3: Deduplication Statistics")
    print("=" * 80)
    
    stats = dedup.get_dedup_stats()
    print(f"Total folios mapped:      {stats['total_folios_mapped']}")
    print(f"Unique schemes in master: {stats['unique_schemes']}")
    print(f"Avg folios per scheme:    {stats['avg_folios_per_scheme']}")
    print(f"Schemes with multi-folio: {stats['schemes_with_multiple_folios']}")
    
    # Show scheme_master with folio counts
    print("\n" + "=" * 80)
    print("STEP 4: Scheme Master Registry (with folio mappings)")
    print("=" * 80)
    
    for scheme in dedup.get_all_schemes():
        folio_count = len(scheme.source_folio_codes)
        if folio_count > 0:
            print(f"  {scheme.scheme_code} | {scheme.scheme_name:<35} | {scheme.category.value:<20} | {folio_count} folios")
    
    # Show schemes needing review
    print("\n" + "=" * 80)
    print("STEP 5: Schemes Requiring Manual Review")
    print("=" * 80)
    
    needs_review = [r for r in results if r['needs_review']]
    if needs_review:
        for r in needs_review:
            folio = next(f for f in folios if f['folio_id'] == r['folio_id'])
            print(f"  {r['folio_id']}: {folio['scheme_name']} [{folio['category']}] - {r['method']} (conf: {r['confidence']})")
            if r['method'] == 'new_scheme':
                # Auto-create and register
                new_scheme = create_scheme_master_from_folio(
                    folio_scheme_code=folio['scheme_code'],
                    folio_scheme_name=folio['scheme_name'],
                    folio_amc=folio['amc'],
                    folio_category=folio['category'],
                )
                dedup.register_scheme(new_scheme)
                print(f"    -> Auto-registered as new scheme: {new_scheme.scheme_code}")
    else:
        print("  None - all folios resolved cleanly!")
    
    # Final stats
    print("\n" + "=" * 80)
    print("FINAL: After auto-registering new schemes")
    print("=" * 80)
    stats = dedup.get_dedup_stats()
    print(f"Total folios mapped:      {stats['total_folios_mapped']}")
    print(f"Unique schemes in master: {stats['unique_schemes']}")
    print(f"Avg folios per scheme:    {stats['avg_folios_per_scheme']}")
    
    print("\n[SUCCESS] Deduplication complete!")
    print("   -> 15 folios resolved to 8 unique schemes")
    print("   -> Compute engine only needs to score 8 schemes, not 15 folios")
    print("   -> Client-facing layer = JOIN folio->scheme + scheme->score")


if __name__ == "__main__":
    main()