"""
Demo: Data Ingestion Layer
Shows pluggable fetchers for AMFI NAV, mfapi, NSE Indices, RBI, MOSPI, FBIL
"""

from fund_engine.ingestion.fetchers import (
    AmfiNavFetcher,
    MfapiFetcher,
    NseIndicesFetcher,
    RbiFetcher,
    MospiFetcher,
    FbilFetcher,
    IngestionOrchestrator,
    DataSource,
    NavRecord,
    SchemeInfo,
)
from datetime import date


def main():
    print("=" * 80)
    print("DATA INGESTION LAYER - DEMO")
    print("=" * 80)
    
    # Create orchestrator with all fetchers
    orchestrator = IngestionOrchestrator()
    orchestrator.register_fetcher(AmfiNavFetcher(timeout=10, max_retries=1))
    orchestrator.register_fetcher(MfapiFetcher(timeout=10, max_retries=1))
    orchestrator.register_fetcher(NseIndicesFetcher())
    orchestrator.register_fetcher(RbiFetcher())
    orchestrator.register_fetcher(MospiFetcher())
    orchestrator.register_fetcher(FbilFetcher())
    
    print(f"\nRegistered fetchers: {list(orchestrator.fetchers.keys())}")
    
    # Demo 1: AMFI NAV Fetch
    print("\n" + "=" * 80)
    print("DEMO 1: AMFI NAV Fetch (simulated)")
    print("=" * 80)
    print("URL: https://www.amfiindia.com/spages/NAVAll.txt")
    print("Format: Tab-separated, ~4000+ schemes, daily snapshot")
    print("\nSample output structure:")
    print("  Scheme Code | Scheme Name | ISIN | NAV | Date")
    print("  123456      | HDFC Top 100 | INF... | 123.45 | 01-Jan-2024")
    
    # Demo 2: mfapi historical
    print("\n" + "=" * 80)
    print("DEMO 2: mfapi.in Historical NAV (simulated)")
    print("=" * 80)
    print("API: https://api.mfapi.in/mf/{scheme_code}")
    print("Provides: Full NAV history for a scheme")
    print("\nSample output structure:")
    print("  scheme_code: '123456'")
    print("  data: [")
    print("    {'date': '01-01-2024', 'nav': '123.456'},")
    print("    {'date': '31-12-2023', 'nav': '122.111'},")
    print("    ... (years of history)")
    print("  ]")
    
    # Demo 3: Scheme info from mfapi
    print("\n" + "=" * 80)
    print("DEMO 3: Scheme Metadata from mfapi")
    print("=" * 80)
    print("meta: {")
    print("  'fund_house': 'HDFC Mutual Fund',")
    print("  'scheme_category': 'Equity - Large Cap',")
    print("  'scheme_name': 'HDFC Top 100 Fund - Growth',")
    print("  'scheme_code': 123456")
    print("}")
    
    # Demo 4: NSE Indices
    print("\n" + "=" * 80)
    print("DEMO 4: NSE Benchmark Indices (TRI)")
    print("=" * 80)
    print("Tracked benchmarks:")
    for code, name in NseIndicesFetcher.INDEX_MAPPING.items():
        print(f"  {code}: {name}")
    
    # Demo 5: Macro indicators
    print("\n" + "=" * 80)
    print("DEMO 5: Macro Indicators (RBI, MOSPI, FBIL)")
    print("=" * 80)
    print("Indicators:")
    print("  RBI: Repo rate, Bond yields (10Y, 5Y)")
    print("  MOSPI: CPI inflation, GDP, IIP")
    print("  FBIL: USD/INR reference rate")
    print("  NSE: India VIX")
    
    # Demo 6: Orchestrator pattern
    print("\n" + "=" * 80)
    print("DEMO 6: Ingestion Orchestrator - Error Isolation")
    print("=" * 80)
    print("Key principle: One failing source doesn't break the pipeline")
    print("")
    print("fetch_all_nav(['SCHEME_1', 'SCHEME_2'])")
    print("  -> AMFI: succeeds (returns all schemes)")
    print("  -> mfapi: fails (API down)")
    print("  -> Result: {AMFI: [...], MFAPI: {}}  # Empty dict, not crash")
    print("")
    print("Health check:")
    health = orchestrator.get_health_status()
    for source, status in health.items():
        print(f"  {source}: {status}")
    
    # Demo 7: Architecture summary
    print("\n" + "=" * 80)
    print("ARCHITECTURE SUMMARY")
    print("=" * 80)
    print("""
+---------------------------------------------------------------+
|                    INGESTION LAYER                            |
+--------------+--------------+--------------+------------------+
|   Source     |   Method     |   Frequency  |   Notes          |
+--------------+--------------+--------------+------------------+
| AMFI NAV     | HTTP GET     | Daily        | Single file, all |
|              | (NAVAll.txt) |              | schemes, snap    |
+--------------+--------------+--------------+------------------+
| mfapi.in     | REST API     | Daily        | Per-scheme, full |
|              | (per scheme) |              | history, rate    |
+--------------+--------------+--------------+------------------+
| NSE Indices  | CSV/REST     | Daily        | TRI benchmarks   |
+--------------+--------------+--------------+------------------+
| RBI          | Scraping     | As needed    | Repo rate, yields|
+--------------+--------------+--------------+------------------+
| MOSPI        | API/Scrape   | Monthly      | CPI, GDP         |
+--------------+--------------+--------------+------------------+
| FBIL         | API          | Daily        | USD/INR          |
+--------------+--------------+--------------+------------------+

KEY DESIGN DECISIONS:
1. Pluggable adapters - each source independent
2. Error isolation - one failure != pipeline failure
3. Retry with exponential backoff
4. Rate limiting for mfapi (0.5s between calls)
5. Raw data -> standardized records (NavRecord, BenchmarkRecord, MacroRecord)
6. Fetched timestamp for audit trail
""")
    
    print("[SUCCESS] Ingestion layer demo complete!")
    print("Next: Feature Engineering Pipeline (rolling returns, alpha, drawdown, volatility)")


if __name__ == "__main__":
    main()