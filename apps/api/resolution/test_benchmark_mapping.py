"""
Tests for Benchmark Mapping Service
Run: python -m pytest test_benchmark_mapping.py -v
"""

import pytest
from pathlib import Path
from benchmark_mapping import (
    BenchmarkResolver,
    BenchmarkCode,
    BenchmarkMapping,
    CATEGORY_FALLBACKS,
)


CONFIG_DIR = Path(__file__).parent.parent / "config"


class TestBenchmarkResolver:
    
    @pytest.fixture
    def resolver(self):
        return BenchmarkResolver(
            explicit_mapping_path=str(CONFIG_DIR / "explicit_benchmark_mappings.json")
        )
    
    def test_explicit_mapping_priority(self, resolver):
        """Explicit mappings should take priority over fallbacks"""
        result = resolver.resolve(
            scheme_code="INF204K01VX3",
            scheme_name="HDFC Top 100 Fund",
            category="Mid Cap"  # Wrong category - explicit should win
        )
        assert result.source == "explicit"
        assert result.confidence == 1.0
        assert result.benchmark_code == BenchmarkCode.NIFTY_100_TRI
    
    def test_category_fallback_large_cap(self, resolver):
        """Large Cap category falls back to Nifty 100 TRI"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_001",
            scheme_name="Unknown Large Cap Fund",
            category="Large Cap"
        )
        assert result.source == "fallback"
        assert result.confidence == 0.7
        assert result.benchmark_code == BenchmarkCode.NIFTY_100_TRI
    
    def test_category_fallback_flexi_cap(self, resolver):
        """Flexi Cap category falls back to Nifty 500 TRI"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_002",
            scheme_name="Unknown Flexi Cap Fund",
            category="Flexi Cap"
        )
        assert result.source == "fallback"
        assert result.benchmark_code == BenchmarkCode.NIFTY_500_TRI
    
    def test_category_fallback_mid_cap(self, resolver):
        """Mid Cap category falls back to Nifty Midcap 150 TRI"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_003",
            scheme_name="Unknown Mid Cap Fund",
            category="Mid Cap"
        )
        assert result.benchmark_code == BenchmarkCode.NIFTY_MIDCAP_150_TRI
    
    def test_category_fallback_small_cap(self, resolver):
        """Small Cap category falls back to Nifty Smallcap 250 TRI"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_004",
            scheme_name="Unknown Small Cap Fund",
            category="Small Cap"
        )
        assert result.benchmark_code == BenchmarkCode.NIFTY_SMALLCAP_250_TRI
    
    def test_category_fallback_elss(self, resolver):
        """ELSS category falls back to Nifty 500 TRI"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_005",
            scheme_name="Unknown ELSS Fund",
            category="ELSS"
        )
        assert result.benchmark_code == BenchmarkCode.NIFTY_500_TRI
    
    def test_category_fallback_hybrid_aggressive(self, resolver):
        """Hybrid Aggressive falls back to CRISIL Hybrid 35+65"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_006",
            scheme_name="Unknown Hybrid Fund",
            category="Hybrid Aggressive"
        )
        assert result.benchmark_code == BenchmarkCode.CRISIL_HYBRID_35_65
    
    def test_category_fallback_debt_short_duration(self, resolver):
        """Debt Short Duration falls back to CRISIL Short Term Bond"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_007",
            scheme_name="Unknown Debt Fund",
            category="Debt - Short Duration"
        )
        assert result.benchmark_code == BenchmarkCode.CRISIL_SHORT_TERM_BOND
    
    def test_category_fallback_international_us(self, resolver):
        """International US falls back to S&P 500 TRI"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_008",
            scheme_name="Unknown US Fund",
            category="International - US"
        )
        assert result.benchmark_code == BenchmarkCode.SP_500_TRI
    
    def test_category_case_insensitive(self, resolver):
        """Category matching should be case-insensitive"""
        result1 = resolver.resolve("S1", "Fund", "large cap")
        result2 = resolver.resolve("S2", "Fund", "LARGE CAP")
        result3 = resolver.resolve("S3", "Fund", "Large Cap")
        assert result1.benchmark_code == result2.benchmark_code == result3.benchmark_code
    
    def test_category_with_ampersand(self, resolver):
        """Category with & should match (Large & Mid Cap)"""
        result = resolver.resolve(
            scheme_code="S1",
            scheme_name="Fund",
            category="Large & Mid Cap"
        )
        assert result.benchmark_code == BenchmarkCode.NIFTY_LARGEMIDCAP_250_TRI
    
    def test_unknown_category_defaults_to_nifty500(self, resolver):
        """Unknown category should default to Nifty 500 TRI with low confidence"""
        result = resolver.resolve(
            scheme_code="UNKNOWN_SCHEME_999",
            scheme_name="Unknown Category Fund",
            category="Completely Unknown Category"
        )
        assert result.source == "default"
        assert result.confidence == 0.3
        assert result.benchmark_code == BenchmarkCode.NIFTY_500_TRI
    
    def test_batch_resolution(self, resolver):
        """Batch resolution should work for multiple schemes"""
        schemes = [
            {"scheme_code": "INF204K01VX3", "scheme_name": "HDFC Top 100", "category": "Large Cap"},
            {"scheme_code": "UNKNOWN_001", "scheme_name": "Flexi Fund", "category": "Flexi Cap"},
            {"scheme_code": "UNKNOWN_002", "scheme_name": "Mid Fund", "category": "Mid Cap"},
        ]
        results = resolver.resolve_batch(schemes)
        
        assert len(results) == 3
        assert results[0].source == "explicit"
        assert results[1].source == "fallback"
        assert results[2].source == "fallback"
        assert results[0].benchmark_code == BenchmarkCode.NIFTY_100_TRI
        assert results[1].benchmark_code == BenchmarkCode.NIFTY_500_TRI
        assert results[2].benchmark_code == BenchmarkCode.NIFTY_MIDCAP_150_TRI
    
    def test_get_unmapped_schemes(self, resolver):
        """Should identify schemes with no explicit or category mapping"""
        schemes = [
            {"scheme_code": "INF204K01VX3", "scheme_name": "Has Explicit", "category": "Large Cap"},
            {"scheme_code": "UNKNOWN_001", "scheme_name": "Has Fallback", "category": "Flexi Cap"},
            {"scheme_code": "TRULY_UNKNOWN", "scheme_name": "No Mapping", "category": "Unknown Category"},
        ]
        unmapped = resolver.get_unmapped_schemes(schemes)
        
        assert len(unmapped) == 1
        assert unmapped[0]["scheme_code"] == "TRULY_UNKNOWN"
    
    def test_add_explicit_mapping_at_runtime(self, resolver):
        """Should be able to add explicit mappings dynamically"""
        initial_count = resolver.explicit_count
        resolver.add_explicit_mapping("NEW_SCHEME_001", BenchmarkCode.NIFTY_50_TRI)
        assert resolver.explicit_count == initial_count + 1
        
        result = resolver.resolve("NEW_SCHEME_001", "New Fund", "Any Category")
        assert result.source == "explicit"
        assert result.benchmark_code == BenchmarkCode.NIFTY_50_TRI
    
    def test_export_explicit_mappings(self, resolver, tmp_path):
        """Should export explicit mappings to JSON"""
        export_path = tmp_path / "exported_mappings.json"
        resolver.export_explicit_mappings(export_path)
        
        assert export_path.exists()
        import json
        with open(export_path) as f:
            data = json.load(f)
        assert "INF204K01VX3" in data
        assert data["INF204K01VX3"] == "NIFTY100_TRI"


class TestCategoryFallbacks:
    """Test that all expected category fallbacks are defined"""
    
    def test_all_core_categories_covered(self):
        """Verify all core SEBI categories have fallbacks"""
        categories = {fb.category for fb in CATEGORY_FALLBACKS}
        
        required = {
            "Large Cap", "Large & Mid Cap", "Flexi Cap", "Multi Cap",
            "Mid Cap", "Small Cap", "ELSS", "Hybrid Aggressive",
            "Debt - Ultra Short Duration", "Debt - Short Duration",
            "International - US"
        }
        for req in required:
            assert req in categories, f"Missing fallback for: {req}"
    
    def test_no_duplicate_categories(self):
        """No duplicate category entries"""
        categories = [fb.category for fb in CATEGORY_FALLBACKS]
        assert len(categories) == len(set(categories))
    
    def test_all_benchmarks_valid(self):
        """All fallback benchmarks should be valid BenchmarkCode enums"""
        for fb in CATEGORY_FALLBACKS:
            assert isinstance(fb.benchmark, BenchmarkCode)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])