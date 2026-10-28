"""
Tests for Data Ingestion Layer
Run: python -m pytest test_fetchers.py -v
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
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
    BenchmarkRecord,
    MacroRecord,
    SchemeInfo,
    IngestionError,
)


class TestAmfiNavFetcher:
    
    @pytest.fixture
    def fetcher(self):
        return AmfiNavFetcher(timeout=5, max_retries=3)
    
    @pytest.fixture
    def sample_amfi_response(self):
        """Sample AMFI NAVAll.txt response"""
        return """Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;Net Asset Value;Date
123456;HDFC Top 100 Fund - Growth;INF123456789;123.456;01-Jan-2024
789012;Parag Parikh Flexi Cap Fund - Direct;INF987654321;456.789;01-Jan-2024
345678;SBI Small Cap Fund - Regular;INF456789123;78.901;01-Jan-2024
INVALID_LINE_WITHOUT_ENOUGH_FIELDS
999999;Test Fund;INF999999999;N.A.;01-Jan-2024"""
    
    def test_parse_amfi_response(self, fetcher, sample_amfi_response):
        """Test parsing of AMFI NAVAll.txt format"""
        with patch.object(fetcher, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.text = sample_amfi_response
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response
            
            records = fetcher.fetch()
            
            assert len(records) == 3  # 3 valid, 1 invalid line, 1 N.A.
            
            # Check first record
            r1 = records[0]
            assert r1.scheme_code == "123456"
            assert r1.nav_value == 123.456
            assert r1.nav_date == date(2024, 1, 1)
            assert r1.source == DataSource.AMFI_NAV
            
            # Check second record
            r2 = records[1]
            assert r2.scheme_code == "789012"
            assert r2.nav_value == 456.789
            
            # Check third record
            r3 = records[2]
            assert r3.scheme_code == "345678"
            assert r3.nav_value == 78.901
    
    def test_parse_scheme_info(self, fetcher, sample_amfi_response):
        """Test scheme metadata extraction"""
        with patch.object(fetcher, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.text = sample_amfi_response
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response
            
            schemes = fetcher.fetch_scheme_info()
            
            # Should get 4 schemes (the N.A. line still has a valid scheme code/name)
            assert len(schemes) == 4
            assert schemes[0].scheme_code == "123456"
            assert schemes[0].scheme_name == "HDFC Top 100 Fund - Growth"
            assert schemes[0].source == DataSource.AMFI_NAV
    
    def test_skips_na_values(self, fetcher):
        """Should skip NAV values marked as N.A."""
        response_text = """Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;Net Asset Value;Date
111111;Valid Fund;INF111111111;100.00;01-Jan-2024
222222;Invalid Fund;INF222222222;N.A.;01-Jan-2024"""
        
        with patch.object(fetcher, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.text = response_text
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response
            
            records = fetcher.fetch()
            assert len(records) == 1
            assert records[0].scheme_code == "111111"
    
    def test_retry_on_failure(self, fetcher):
        """Should retry on network failure"""
        call_count = 0
        
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise requests.RequestException("Network error")
            # Third call succeeds
            return Mock(text="Scheme Code;Scheme Name;ISIN;Net Asset Value;Date\n111;Fund;INF111;100;01-Jan-2024", raise_for_status=Mock())
        
        with patch.object(fetcher.session, 'get', side_effect=side_effect):
            records = fetcher.fetch()
            assert call_count == 3
            assert len(records) == 1
    
    def test_raises_ingestion_error_after_max_retries(self, fetcher):
        """Should raise IngestionError after max retries"""
        with patch.object(fetcher.session, 'get', side_effect=requests.RequestException("Persistent error")):
            with pytest.raises(IngestionError) as exc_info:
                fetcher.fetch()
            
            assert exc_info.value.source == DataSource.AMFI_NAV


class TestMfapiFetcher:
    
    @pytest.fixture
    def fetcher(self):
        return MfapiFetcher(timeout=5, max_retries=1)
    
    @pytest.fixture
    def sample_mfapi_response(self):
        """Sample mfapi.in response"""
        return {
            "meta": {
                "fund_house": "HDFC Mutual Fund",
                "scheme_type": "Open Ended",
                "scheme_category": "Equity - Large Cap",
                "scheme_name": "HDFC Top 100 Fund - Growth",
                "scheme_code": 123456
            },
            "data": [
                {"date": "01-01-2024", "nav": "123.456"},
                {"date": "31-12-2023", "nav": "122.111"},
                {"date": "30-12-2023", "nav": "121.999"},
            ]
        }
    
    def test_fetch_scheme_history(self, fetcher, sample_mfapi_response):
        """Test fetching NAV history for a scheme"""
        with patch.object(fetcher, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = sample_mfapi_response
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response
            
            records = fetcher.fetch_scheme_history("123456")
            
            assert len(records) == 3
            assert records[0].scheme_code == "123456"
            assert records[0].nav_date == date(2024, 1, 1)
            assert records[0].nav_value == 123.456
            assert records[0].source == DataSource.MFAPI
    
    def test_fetch_scheme_info(self, fetcher, sample_mfapi_response):
        """Test fetching scheme metadata"""
        with patch.object(fetcher, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = sample_mfapi_response
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response
            
            info = fetcher.fetch_scheme_info("123456")
            
            assert info.scheme_code == "123456"
            assert info.scheme_name == "HDFC Top 100 Fund - Growth"
            assert info.amc == "HDFC Mutual Fund"
            assert info.category == "Equity - Large Cap"
            assert info.source == DataSource.MFAPI
    
    def test_fetch_multiple_schemes(self, fetcher, sample_mfapi_response):
        """Test fetching multiple schemes with rate limiting"""
        with patch.object(fetcher, 'fetch_scheme_history') as mock_fetch:
            mock_fetch.return_value = [
                NavRecord("123", date(2024, 1, 1), 100, DataSource.MFAPI),
                NavRecord("123", date(2023, 12, 31), 99, DataSource.MFAPI),
            ]
            
            results = fetcher.fetch_multiple_schemes(["123", "456", "789"], delay=0)
            
            assert len(results) == 3
            assert "123" in results
            assert "456" in results
            assert "789" in results
            assert mock_fetch.call_count == 3
    
    def test_handles_malformed_data(self, fetcher):
        """Should handle malformed data gracefully"""
        bad_response = {
            "meta": {"scheme_name": "Test", "fund_house": "Test AMC", "scheme_category": "Test"},
            "data": [
                {"date": "01-01-2024", "nav": "100"},
                {"date": "invalid-date", "nav": "101"},  # Bad date
                {"date": "02-01-2024"},  # Missing nav
                {"nav": "102"},  # Missing date
            ]
        }
        
        with patch.object(fetcher, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = bad_response
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response
            
            records = fetcher.fetch_scheme_history("123")
            # Only first record is valid
            assert len(records) == 1


class TestIngestionOrchestrator:
    
    @pytest.fixture
    def orchestrator(self):
        return IngestionOrchestrator()
    
    def test_register_fetcher(self, orchestrator):
        """Should register fetchers by source"""
        fetcher = AmfiNavFetcher()
        orchestrator.register_fetcher(fetcher)
        
        assert DataSource.AMFI_NAV in orchestrator.fetchers
        assert orchestrator.fetchers[DataSource.AMFI_NAV] == fetcher
    
    def test_fetch_all_nav_isolates_errors(self, orchestrator):
        """One failing source shouldn't break others"""
        # Mock AMFI success
        amfi_fetcher = Mock(spec=AmfiNavFetcher)
        amfi_fetcher.source = DataSource.AMFI_NAV
        amfi_fetcher.fetch.return_value = [
            NavRecord("123", date(2024, 1, 1), 100, DataSource.AMFI_NAV)
        ]
        
        # Mock mfapi failure
        mfapi_fetcher = Mock(spec=MfapiFetcher)
        mfapi_fetcher.source = DataSource.MFAPI
        mfapi_fetcher.fetch_multiple_schemes.side_effect = IngestionError(DataSource.MFAPI, "API down")
        
        orchestrator.register_fetcher(amfi_fetcher)
        orchestrator.register_fetcher(mfapi_fetcher)
        
        results = orchestrator.fetch_all_nav(["123", "456"])
        
        # AMFI should succeed
        assert DataSource.AMFI_NAV in results
        assert len(results[DataSource.AMFI_NAV]) == 1
        
        # mfapi should return empty dict on failure
        assert DataSource.MFAPI in results
        assert results[DataSource.MFAPI] == {}
    
    def test_health_status(self, orchestrator):
        """Should report health of all fetchers"""
        amfi_fetcher = Mock(spec=AmfiNavFetcher)
        amfi_fetcher.source = DataSource.AMFI_NAV
        
        mfapi_fetcher = Mock(spec=MfapiFetcher)
        mfapi_fetcher.source = DataSource.MFAPI
        
        orchestrator.register_fetcher(amfi_fetcher)
        orchestrator.register_fetcher(mfapi_fetcher)
        
        status = orchestrator.get_health_status()
        
        assert "amfi_nav" in status
        assert "mfapi" in status


class TestDataClasses:
    
    def test_nav_record_creation(self):
        """Test NavRecord dataclass"""
        record = NavRecord(
            scheme_code="123",
            nav_date=date(2024, 1, 1),
            nav_value=100.5,
            source=DataSource.AMFI_NAV,
        )
        
        assert record.scheme_code == "123"
        assert record.nav_value == 100.5
        assert record.source == DataSource.AMFI_NAV
        assert record.fetched_at is not None
    
    def test_benchmark_record_creation(self):
        """Test BenchmarkRecord dataclass"""
        record = BenchmarkRecord(
            benchmark_code="NIFTY50_TRI",
            index_date=date(2024, 1, 1),
            index_value=25000.0,
            source=DataSource.NSE_INDICES,
        )
        
        assert record.benchmark_code == "NIFTY50_TRI"
        assert record.index_value == 25000.0
    
    def test_macro_record_creation(self):
        """Test MacroRecord dataclass"""
        record = MacroRecord(
            indicator_name="REPO_RATE",
            indicator_date=date(2024, 1, 1),
            value=6.5,
            source=DataSource.RBI,
        )
        
        assert record.indicator_name == "REPO_RATE"
        assert record.value == 6.5
    
    def test_scheme_info_creation(self):
        """Test SchemeInfo dataclass"""
        info = SchemeInfo(
            scheme_code="123",
            scheme_name="Test Fund",
            amc="Test AMC",
            category="Large Cap",
            expense_ratio=1.05,
            aum=10000,
        )
        
        assert info.expense_ratio == 1.05
        assert info.aum == 10000


class TestIngestionError:
    
    def test_ingestion_error_wraps_original(self):
        """Should wrap original error"""
        original = ValueError("Original error")
        error = IngestionError(DataSource.AMFI_NAV, "Failed to fetch", original)
        
        assert error.source == DataSource.AMFI_NAV
        assert error.original_error == original
        assert "amfi_nav" in str(error).lower()
        assert "Failed to fetch" in str(error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])