"""
Integration Test: Scheme Deduplication + Benchmark Mapping
Verifies the two resolution layers work together end-to-end
"""

import pytest
from fund_engine.core.paths import CONFIG_DIR
from fund_engine.domain.resolution.scheme_dedup import SchemeDeduplicator, SchemeMaster, SchemeCategory, create_scheme_master_from_folio
from fund_engine.domain.resolution.benchmark_mapping import BenchmarkResolver, BenchmarkCode


class TestDedupBenchmarkIntegration:
    
    @pytest.fixture
    def setup_resolvers(self):
        """Create and populate both resolvers"""
        # Scheme deduplicator with known schemes
        dedup = SchemeDeduplicator()
        schemes = [
            SchemeMaster("INF204K01VX3", "HDFC Top 100 Fund", "HDFC Mutual Fund", SchemeCategory.LARGE_CAP),
            SchemeMaster("INF767K01EW8", "Parag Parikh Flexi Cap Fund", "PPFAS Mutual Fund", SchemeCategory.FLEXI_CAP),
            SchemeMaster("INF179K01BE2", "HDFC Mid-Cap Opportunities", "HDFC Mutual Fund", SchemeCategory.MID_CAP),
            SchemeMaster("INF090I01239", "SBI Small Cap Fund", "SBI Mutual Fund", SchemeCategory.SMALL_CAP),
            SchemeMaster("INF843K01AB1", "ICICI Pru Large & Mid Cap", "ICICI Prudential MF", SchemeCategory.LARGE_AND_MID_CAP),
        ]
        dedup.register_schemes_bulk(schemes)
        
        # Benchmark resolver with explicit mappings
        benchmark = BenchmarkResolver(
            explicit_mapping_path=str(CONFIG_DIR / "explicit_benchmark_mappings.json")
        )
        
        return dedup, benchmark
    
    def test_folio_to_benchmark_resolution(self, setup_resolvers):
        """Full flow: folio -> scheme_code -> benchmark"""
        dedup, benchmark = setup_resolvers
        
        # Simulate folios from client portfolio
        folios = [
            {"folio_id": "F1", "scheme_code": "INF204K01VX3", "scheme_name": "HDFC Top 100", "amc": "HDFC Mutual Fund", "category": "Large Cap"},
            {"folio_id": "F2", "scheme_code": None, "scheme_name": "Parag Parikh Flexi Cap Fund", "amc": "PPFAS Mutual Fund", "category": "Flexi Cap"},
            {"folio_id": "F3", "scheme_code": "INF179K01BE2", "scheme_name": "HDFC Mid-Cap Opportunities", "amc": "HDFC Mutual Fund", "category": "Mid Cap"},
            {"folio_id": "F4", "scheme_code": None, "scheme_name": "New SBI Small Cap Fund", "amc": "SBI Mutual Fund", "category": "Small Cap"},
        ]
        
        # Step 1: Resolve folios to scheme codes
        dedup_results = dedup.resolve_folios_batch(folios)
        
        # Step 2: For each resolved scheme, get benchmark
        final_results = []
        for dr in dedup_results:
            if dr["scheme_code"]:
                scheme_master = dedup.get_scheme_master(dr["scheme_code"])
                bm_result = benchmark.resolve(
                    scheme_code=dr["scheme_code"],
                    scheme_name=scheme_master.scheme_name,
                    category=scheme_master.category.value
                )
                final_results.append({
                    "folio_id": dr["folio_id"],
                    "scheme_code": dr["scheme_code"],
                    "scheme_name": scheme_master.scheme_name,
                    "category": scheme_master.category.value,
                    "benchmark_code": bm_result.benchmark_code.value,
                    "benchmark_name": bm_result.benchmark_name,
                    "benchmark_source": bm_result.source,
                    "benchmark_confidence": bm_result.confidence,
                })
            else:
                final_results.append({
                    "folio_id": dr["folio_id"],
                    "scheme_code": None,
                    "needs_review": True,
                })
        
        # Verify results
        assert len(final_results) == 4
        
        # F1: Exact code -> explicit benchmark
        assert final_results[0]["scheme_code"] == "INF204K01VX3"
        assert final_results[0]["benchmark_code"] == "NIFTY100_TRI"
        assert final_results[0]["benchmark_source"] == "explicit"
        assert final_results[0]["benchmark_confidence"] == 1.0
        
        # F2: Fuzzy match -> explicit benchmark (PPFAS has explicit mapping)
        assert final_results[1]["scheme_code"] == "INF767K01EW8"
        assert final_results[1]["benchmark_code"] == "NIFTY500_TRI"
        assert final_results[1]["benchmark_source"] == "explicit"
        
        # F3: Exact code -> explicit benchmark
        assert final_results[2]["scheme_code"] == "INF179K01BE2"
        assert final_results[2]["benchmark_code"] == "NIFTY_MIDCAP150_TRI"
        assert final_results[2]["benchmark_source"] == "explicit"
        
        # F4: Gets heuristic match to existing SBI Small Cap -> explicit benchmark
        assert final_results[3]["scheme_code"] == "INF090I01239"
        assert final_results[3]["benchmark_code"] == "NIFTY_SMALLCAP250_TRI"
        assert final_results[3]["benchmark_source"] == "explicit"
    
    def test_dedup_stats_feed_into_scoping(self, setup_resolvers):
        """Dedup stats should inform compute scope (400 schemes vs 5000 folios)"""
        dedup, benchmark = setup_resolvers
        
        # Simulate 1000 folios across 6 schemes (5 known + 1 completely new category)
        folios = []
        for i in range(1000):
            scheme_idx = i % 6
            scheme_codes = ["INF204K01VX3", "INF767K01EW8", "INF179K01BE2", 
                           "INF090I01239", "INF843K01AB1", "COMPLETELY_NEW_001"]
            # Use different AMC for the new one so heuristic doesn't match
            amcs = ["HDFC Mutual Fund", "PPFAS Mutual Fund", "HDFC Mutual Fund",
                    "SBI Mutual Fund", "ICICI Prudential MF", "Brand New AMC"]
            cats = ["Large Cap", "Flexi Cap", "Mid Cap", "Small Cap", "Large & Mid Cap", "International - US"]
            folios.append({
                "folio_id": f"FOL_{i:04d}",
                "scheme_code": scheme_codes[scheme_idx],
                "scheme_name": f"Fund {scheme_idx}",
                "amc": amcs[scheme_idx],
                "category": cats[scheme_idx],
            })
        
        results = dedup.resolve_folios_batch(folios)
        
        # Auto-register new schemes that need review
        for r in results:
            if r["needs_review"] and r["method"] == "new_scheme":
                folio = next(f for f in folios if f["folio_id"] == r["folio_id"])
                new_scheme = SchemeMaster(
                    scheme_code=folio["scheme_code"],
                    scheme_name=folio["scheme_name"],
                    amc=folio["amc"],
                    category=SchemeCategory(folio["category"]),
                )
                dedup.register_scheme(new_scheme)
        
        # Re-resolve to map the newly registered scheme
        results = dedup.resolve_folios_batch(folios)
        
        stats = dedup.get_dedup_stats()
        
        # Should have 5 known + 1 new = 6 unique schemes
        assert stats["unique_schemes"] == 6
        assert stats["total_folios_mapped"] == 1000
        # 1000 folios / 6 schemes = ~167 folios per scheme
        assert stats["avg_folios_per_scheme"] > 100
        
        # Compute engine only needs to score 6 schemes, not 1000 folios
        schemes_to_score = stats["unique_schemes"]
        folios_naive = stats["total_folios_mapped"]
        
        compute_savings = (folios_naive - schemes_to_score) / folios_naive * 100
        assert compute_savings > 99  # 99%+ compute reduction
    
    def test_new_scheme_gets_category_benchmark(self, setup_resolvers):
        """New scheme (no explicit benchmark) should get category fallback"""
        dedup, benchmark = setup_resolvers
        
        # Create a new scheme via folio resolution
        folio = {
            "folio_id": "NEW_FOLIO",
            "scheme_code": "BRAND_NEW_001",
            "scheme_name": "Brand New Large Cap Fund",
            "amc": "New AMC",
            "category": "Large Cap",
        }
        
        result = dedup.resolve_folios_batch([folio])[0]
        
        # Auto-register the new scheme
        if result["needs_review"]:
            new_scheme = create_scheme_master_from_folio(
                folio_scheme_code=folio["scheme_code"],
                folio_scheme_name=folio["scheme_name"],
                folio_amc=folio["amc"],
                folio_category=folio["category"],
            )
            dedup.register_scheme(new_scheme)
            result = dedup.resolve_folios_batch([folio])[0]
        
        # Now resolve benchmark for the new scheme
        scheme_master = dedup.get_scheme_master(result["scheme_code"])
        bm_result = benchmark.resolve(
            scheme_code=result["scheme_code"],
            scheme_name=scheme_master.scheme_name,
            category=scheme_master.category.value
        )
        
        # Should get category fallback (Large Cap -> Nifty 100 TRI)
        assert bm_result.source == "fallback"
        assert bm_result.benchmark_code == BenchmarkCode.NIFTY_100_TRI
        assert bm_result.confidence == 0.7
    
    def test_multiple_folios_same_scheme_share_benchmark(self, setup_resolvers):
        """Multiple folios mapping to same scheme should share same benchmark"""
        dedup, benchmark = setup_resolvers
        
        folios = [
            {"folio_id": "F1", "scheme_code": "INF204K01VX3", "scheme_name": "HDFC Top 100", "amc": "HDFC Mutual Fund", "category": "Large Cap"},
            {"folio_id": "F2", "scheme_code": "INF204K01VX3", "scheme_name": "HDFC Top 100 Fund Growth", "amc": "HDFC Mutual Fund", "category": "Large Cap"},
            {"folio_id": "F3", "scheme_code": None, "scheme_name": "HDFC Top 100 Fund Direct", "amc": "HDFC Mutual Fund", "category": "Large Cap"},
        ]
        
        results = dedup.resolve_folios_batch(folios)
        
        # All should map to same scheme
        scheme_codes = [r["scheme_code"] for r in results]
        assert len(set(scheme_codes)) == 1
        assert scheme_codes[0] == "INF204K01VX3"
        
        # Get benchmark once for the scheme
        scheme_master = dedup.get_scheme_master(scheme_codes[0])
        bm_result = benchmark.resolve(
            scheme_code=scheme_codes[0],
            scheme_name=scheme_master.scheme_name,
            category=scheme_master.category.value
        )
        
        # All folios share this benchmark
        assert bm_result.benchmark_code == BenchmarkCode.NIFTY_100_TRI
        assert bm_result.source == "explicit"
    
    def test_category_change_detection(self, setup_resolvers):
        """If folio category differs from scheme_master, flag for review"""
        dedup, benchmark = setup_resolvers
        
        # Folio claims Mid Cap but scheme is Large Cap
        folio = {
            "folio_id": "MISMATCH_FOLIO",
            "scheme_code": "INF204K01VX3",
            "scheme_name": "HDFC Top 100 Fund",
            "amc": "HDFC Mutual Fund",
            "category": "Mid Cap",  # Wrong!
        }
        
        result = dedup.resolve_folios_batch([folio])[0]
        
        # Should still resolve to correct scheme (exact code wins)
        assert result["scheme_code"] == "INF204K01VX3"
        assert result["method"] == "exact_code"
        
        # But benchmark resolver should use scheme_master's category, not folio's
        scheme_master = dedup.get_scheme_master(result["scheme_code"])
        bm_result = benchmark.resolve(
            scheme_code=result["scheme_code"],
            scheme_name=scheme_master.scheme_name,
            category=scheme_master.category.value  # Use master category, not folio
        )
        
        assert bm_result.benchmark_code == BenchmarkCode.NIFTY_100_TRI  # Large Cap benchmark
        assert bm_result.benchmark_code != BenchmarkCode.NIFTY_MIDCAP_150_TRI  # Not Mid Cap


if __name__ == "__main__":
    pytest.main([__file__, "-v"])