"""
Tests for Scheme Deduplication
Run: python -m pytest test_scheme_dedup.py -v
"""

import pytest
from datetime import date
from scheme_dedup import (
    SchemeDeduplicator,
    SchemeMaster,
    SchemeCategory,
    FolioMapping,
    create_scheme_master_from_folio,
)


class TestSchemeDeduplicator:
    
    @pytest.fixture
    def deduplicator(self):
        dedup = SchemeDeduplicator()
        
        # Pre-populate with some known schemes (simulating scheme_master)
        schemes = [
            SchemeMaster(
                scheme_code="INF204K01VX3",
                scheme_name="HDFC Top 100 Fund",
                amc="HDFC Mutual Fund",
                category=SchemeCategory.LARGE_CAP,
                expense_ratio=1.05,
                aum=25000,
                inception_date=date(2010, 1, 1),
            ),
            SchemeMaster(
                scheme_code="INF767K01EW8",
                scheme_name="Parag Parikh Flexi Cap Fund",
                amc="PPFAS Mutual Fund",
                category=SchemeCategory.FLEXI_CAP,
                expense_ratio=0.95,
                aum=18000,
                inception_date=date(2013, 5, 1),
            ),
            SchemeMaster(
                scheme_code="INF179K01BE2",
                scheme_name="HDFC Mid-Cap Opportunities Fund",
                amc="HDFC Mutual Fund",
                category=SchemeCategory.MID_CAP,
                expense_ratio=1.10,
                aum=15000,
                inception_date=date(2012, 3, 1),
            ),
            SchemeMaster(
                scheme_code="INF090I01239",
                scheme_name="SBI Small Cap Fund",
                amc="SBI Mutual Fund",
                category=SchemeCategory.SMALL_CAP,
                expense_ratio=1.15,
                aum=12000,
                inception_date=date(2015, 7, 1),
            ),
        ]
        dedup.register_schemes_bulk(schemes)
        return dedup
    
    def test_exact_code_match(self, deduplicator):
        """Folio with exact scheme_code should match with 1.0 confidence"""
        scheme_code, confidence, method = deduplicator.resolve_folio_scheme(
            folio_id="FOLIO_001",
            folio_scheme_code="INF204K01VX3",
            folio_scheme_name="HDFC Top 100 Fund",
            folio_amc="HDFC Mutual Fund",
            folio_category="Large Cap",
        )
        assert scheme_code == "INF204K01VX3"
        assert confidence == 1.0
        assert method == "exact_code"
    
    def test_exact_code_match_wrong_category(self, deduplicator):
        """Even with wrong category, exact scheme_code should win"""
        scheme_code, confidence, method = deduplicator.resolve_folio_scheme(
            folio_id="FOLIO_002",
            folio_scheme_code="INF204K01VX3",
            folio_scheme_name="HDFC Top 100 Fund",
            folio_amc="HDFC Mutual Fund",
            folio_category="Mid Cap",  # Wrong category
        )
        assert scheme_code == "INF204K01VX3"
        assert confidence == 1.0
        assert method == "exact_code"
    
    def test_fuzzy_name_amc_match(self, deduplicator):
        """Folio without scheme_code but matching name+AMC should fuzzy match"""
        scheme_code, confidence, method = deduplicator.resolve_folio_scheme(
            folio_id="FOLIO_003",
            folio_scheme_code=None,  # Missing code
            folio_scheme_name="HDFC Top 100 Fund - Growth",  # Slight variation
            folio_amc="HDFC Mutual Fund",
            folio_category="Large Cap",
        )
        assert scheme_code == "INF204K01VX3"
        assert confidence == 0.9
        assert method == "fuzzy_name_amc"
    
    def test_fuzzy_match_case_insensitive(self, deduplicator):
        """Fuzzy matching should be case insensitive"""
        scheme_code, confidence, method = deduplicator.resolve_folio_scheme(
            folio_id="FOLIO_004",
            folio_scheme_code=None,
            folio_scheme_name="hdfc top 100 fund",  # Lowercase
            folio_amc="hdfc mutual fund",
            folio_category="Large Cap",
        )
        assert scheme_code == "INF204K01VX3"
        assert confidence == 0.9
    
    def test_fuzzy_match_ignores_suffixes(self, deduplicator):
        """Should ignore common suffixes like Growth, Direct, Regular"""
        test_names = [
            "HDFC Top 100 Fund Growth",
            "HDFC Top 100 Fund Direct",
            "HDFC Top 100 Fund Regular Plan",
            "HDFC Top 100 Fund Direct Plan Growth Option",
        ]
        for name in test_names:
            scheme_code, confidence, method = deduplicator.resolve_folio_scheme(
                folio_id=f"FOLIO_{name[:10]}",
                folio_scheme_code=None,
                folio_scheme_name=name,
                folio_amc="HDFC Mutual Fund",
                folio_category="Large Cap",
            )
            assert scheme_code == "INF204K01VX3", f"Failed for: {name}"
            assert confidence == 0.9
    
    def test_category_amc_heuristic(self, deduplicator):
        """Unknown code/name but matching category+AMC should heuristic match"""
        scheme_code, confidence, method = deduplicator.resolve_folio_scheme(
            folio_id="FOLIO_005",
            folio_scheme_code="UNKNOWN_CODE",
            folio_scheme_name="Unknown HDFC Large Cap Fund",
            folio_amc="HDFC Mutual Fund",
            folio_category="Large Cap",
        )
        assert scheme_code == "INF204K01VX3"  # Only HDFC Large Cap in registry
        assert confidence == 0.7
        assert method == "category_amc_heuristic"
    
    def test_new_scheme_returns_empty(self, deduplicator):
        """Completely unknown scheme should return empty with new_scheme method"""
        scheme_code, confidence, method = deduplicator.resolve_folio_scheme(
            folio_id="FOLIO_006",
            folio_scheme_code="BRAND_NEW_001",
            folio_scheme_name="Brand New Fund",
            folio_amc="New AMC",
            folio_category="Flexi Cap",
        )
        assert scheme_code == ""
        assert confidence == 0.0
        assert method == "new_scheme"
    
    def test_batch_resolution(self, deduplicator):
        """Batch resolution should process multiple folios"""
        folios = [
            {"folio_id": "F1", "scheme_code": "INF204K01VX3", "scheme_name": "HDFC Top 100", "amc": "HDFC Mutual Fund", "category": "Large Cap"},
            {"folio_id": "F2", "scheme_code": None, "scheme_name": "Parag Parikh Flexi Cap Fund", "amc": "PPFAS Mutual Fund", "category": "Flexi Cap"},
            {"folio_id": "F3", "scheme_code": "UNKNOWN", "scheme_name": "Unknown Fund", "amc": "Unknown AMC", "category": "Mid Cap"},
        ]
        results = deduplicator.resolve_folios_batch(folios)
        
        assert len(results) == 3
        assert results[0]["scheme_code"] == "INF204K01VX3"
        assert results[0]["method"] == "exact_code"
        assert results[1]["scheme_code"] == "INF767K01EW8"
        assert results[1]["method"] == "fuzzy_name_amc"
        assert results[2]["method"] == "new_scheme"
        assert results[2]["needs_review"] == True
    
    def test_folio_mapping_tracking(self, deduplicator):
        """Resolved folios should be tracked in scheme_master"""
        deduplicator.resolve_folio_scheme("FOLIO_A", "INF204K01VX3", "HDFC Top 100", "HDFC Mutual Fund", "Large Cap")
        deduplicator.resolve_folio_scheme("FOLIO_B", "INF204K01VX3", "HDFC Top 100", "HDFC Mutual Fund", "Large Cap")
        deduplicator.resolve_folio_scheme("FOLIO_C", None, "HDFC Top 100 Fund Growth", "HDFC Mutual Fund", "Large Cap")
        
        scheme = deduplicator.get_scheme_master("INF204K01VX3")
        assert "FOLIO_A" in scheme.source_folio_codes
        assert "FOLIO_B" in scheme.source_folio_codes
        assert "FOLIO_C" in scheme.source_folio_codes
        assert len(scheme.source_folio_codes) == 3
    
    def test_get_schemes_by_category(self, deduplicator):
        """Should filter schemes by category"""
        large_cap = deduplicator.get_schemes_by_category(SchemeCategory.LARGE_CAP)
        flexi_cap = deduplicator.get_schemes_by_category(SchemeCategory.FLEXI_CAP)
        
        assert len(large_cap) == 1
        assert large_cap[0].scheme_code == "INF204K01VX3"
        assert len(flexi_cap) == 1
        assert flexi_cap[0].scheme_code == "INF767K01EW8"
    
    def test_dedup_stats(self, deduplicator):
        """Should compute deduplication statistics"""
        # Add some folio mappings
        deduplicator.resolve_folio_scheme("F1", "INF204K01VX3", "HDFC Top 100", "HDFC Mutual Fund", "Large Cap")
        deduplicator.resolve_folio_scheme("F2", "INF204K01VX3", "HDFC Top 100", "HDFC Mutual Fund", "Large Cap")
        deduplicator.resolve_folio_scheme("F3", "INF767K01EW8", "Parag Parikh Flexi Cap", "PPFAS Mutual Fund", "Flexi Cap")
        
        stats = deduplicator.get_dedup_stats()
        
        assert stats["total_folios_mapped"] == 3
        assert stats["unique_schemes"] == 4  # 4 pre-registered
        assert stats["avg_folios_per_scheme"] == 0.8  # 3/4
        assert stats["schemes_with_multiple_folios"] == 1  # HDFC Top 100 has 2
    
    def test_export_import_scheme_master(self, deduplicator, tmp_path):
        """Should export and import scheme master correctly"""
        export_path = tmp_path / "scheme_master.json"
        deduplicator.export_scheme_master(export_path)
        
        assert export_path.exists()
        
        # Create new deduplicator and import
        new_dedup = SchemeDeduplicator()
        count = new_dedup.load_scheme_master(export_path)
        
        assert count == 4
        assert new_dedup.get_scheme_master("INF204K01VX3") is not None
        assert new_dedup.get_scheme_master("INF204K01VX3").scheme_name == "HDFC Top 100 Fund"
    
    def test_create_scheme_master_from_folio(self):
        """Factory should create SchemeMaster from folio data"""
        scheme = create_scheme_master_from_folio(
            folio_scheme_code="NEW_001",
            folio_scheme_name="New Test Fund",
            folio_amc="Test AMC",
            folio_category="Large Cap",
            expense_ratio=1.2,
            aum=5000,
        )
        
        assert scheme.scheme_code == "NEW_001"
        assert scheme.scheme_name == "New Test Fund"
        assert scheme.amc == "Test AMC"
        assert scheme.category == SchemeCategory.LARGE_CAP
        assert scheme.expense_ratio == 1.2
        assert scheme.aum == 5000
    
    def test_create_scheme_master_unknown_category_defaults_flexi(self):
        """Unknown category should default to Flexi Cap"""
        scheme = create_scheme_master_from_folio(
            folio_scheme_code="NEW_002",
            folio_scheme_name="New Fund",
            folio_amc="Test AMC",
            folio_category="Unknown Category",
        )
        assert scheme.category == SchemeCategory.FLEXI_CAP


class TestSchemeMasterDataclass:
    """Test SchemeMaster dataclass behavior"""
    
    def test_scheme_master_immutable_fields(self):
        """SchemeMaster should be frozen (immutable)"""
        scheme = SchemeMaster(
            scheme_code="TEST001",
            scheme_name="Test Fund",
            amc="Test AMC",
            category=SchemeCategory.LARGE_CAP,
        )
        
        # Should not be able to modify frozen fields
        with pytest.raises(AttributeError):
            scheme.scheme_name = "Modified"
    
    def test_scheme_master_equality_all_fields(self):
        """Frozen dataclass compares all fields by default"""
        s1 = SchemeMaster("CODE1", "Fund A", "AMC A", SchemeCategory.LARGE_CAP)
        s2 = SchemeMaster("CODE1", "Fund A", "AMC A", SchemeCategory.LARGE_CAP)
        s3 = SchemeMaster("CODE1", "Fund B", "AMC A", SchemeCategory.LARGE_CAP)
        
        assert s1 == s2  # All fields same
        assert s1 != s3  # Different scheme_name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])