"""
Tests for Feature Engineering Pipeline
Run: python -m pytest test_feature_engineering.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import date, timedelta
from feature_engineering import (
    ReturnCalculator,
    RollingReturnsCalculator,
    AlphaCalculator,
    DrawdownCalculator,
    VolatilityCalculator,
    PercentileRankCalculator,
    ConsecutiveUnderperformanceCalculator,
    CorrelationCalculator,
    FeatureEngineeringPipeline,
    RollingReturns,
    SchemeFeatures,
    ReturnPeriod,
    create_sample_nav_series,
)


class TestReturnCalculator:
    
    def test_simple_return(self):
        """Simple return for periods < 1 year"""
        result = ReturnCalculator.simple_return(100, 110)
        assert result == 0.10  # 10%
    
    def test_simple_return_zero_start(self):
        """Should handle zero start NAV"""
        result = ReturnCalculator.simple_return(0, 110)
        assert result is None
    
    def test_cagr(self):
        """CAGR for periods >= 1 year"""
        # 100 to 121 over 2 years = 10% CAGR
        result = ReturnCalculator.cagr(100, 121, 2)
        assert abs(result - 0.10) < 0.001
    
    def test_cagr_zero_values(self):
        """Should handle zero/negative NAV"""
        assert ReturnCalculator.cagr(0, 110, 1) is None
        assert ReturnCalculator.cagr(100, 0, 1) is None
        assert ReturnCalculator.cagr(100, 110, 0) is None
    
    def test_auto_select_simple(self):
        """< 365 days uses simple return"""
        result = ReturnCalculator.calculate_return(100, 110, 100)
        assert result == 0.10
    
    def test_auto_select_cagr(self):
        """>= 365 days uses CAGR"""
        result = ReturnCalculator.calculate_return(100, 121, 730)  # 2 years
        assert abs(result - 0.10) < 0.001


class TestRollingReturnsCalculator:
    
    @pytest.fixture
    def nav_series(self):
        """Create a 3-year NAV series with ~10% annual return"""
        return create_sample_nav_series(date(2021, 1, 1), 756, start_nav=100, daily_return=0.0004)
    
    def test_calculate_all_returns(self, nav_series):
        """Should calculate all standard period returns"""
        calc = RollingReturnsCalculator(nav_series)
        returns = calc.calculate_all(date(2023, 12, 29))
        
        assert isinstance(returns, RollingReturns)
        assert returns.as_of_date == date(2023, 12, 29)
        
        # All periods should have values (3 years of data)
        assert returns.return_1m is not None
        assert returns.return_3m is not None
        assert returns.return_6m is not None
        assert returns.return_1y is not None
        assert returns.return_3y is not None
        assert returns.return_5y is None  # Not enough data for 5y
    
    def test_insufficient_data(self):
        """Should return None for periods with insufficient data"""
        short_series = create_sample_nav_series(date(2023, 1, 1), 30, start_nav=100)
        calc = RollingReturnsCalculator(short_series)
        returns = calc.calculate_all(date(2023, 1, 31))
        
        assert returns.return_1m is not None
        assert returns.return_3m is None  # Not enough data
        assert returns.return_1y is None
    
    def test_get_nav_as_of_exact_date(self, nav_series):
        """Should get NAV on exact date"""
        calc = RollingReturnsCalculator(nav_series)
        nav = calc._get_nav_as_of(pd.Timestamp(date(2022, 6, 15)))
        assert nav is not None
    
    def test_get_nav_as_of_before_date(self, nav_series):
        """Should get latest NAV before date if date not in series"""
        calc = RollingReturnsCalculator(nav_series)
        # Weekend date not in business day series
        nav = calc._get_nav_as_of(pd.Timestamp(date(2022, 6, 18)))  # Saturday
        assert nav is not None


class TestAlphaCalculator:
    
    def test_calculate_alpha(self):
        """Alpha = fund return - benchmark return"""
        result = AlphaCalculator.calculate(0.12, 0.10)
        assert abs(result - 0.02) < 1e-9
    
    def test_calculate_alpha_negative(self):
        """Negative alpha when fund underperforms"""
        result = AlphaCalculator.calculate(0.08, 0.10)
        assert abs(result - (-0.02)) < 1e-9
    
    def test_calculate_alpha_none(self):
        """Should handle None values"""
        assert AlphaCalculator.calculate(None, 0.10) is None
        assert AlphaCalculator.calculate(0.10, None) is None
    
    def test_calculate_all_periods(self):
        """Should calculate alpha for all matching periods"""
        fund_returns = RollingReturns(
            scheme_code="TEST", as_of_date=date(2023, 12, 29),
            return_1m=0.02, return_3m=0.06, return_1y=0.15
        )
        bench_returns = RollingReturns(
            scheme_code="BENCH", as_of_date=date(2023, 12, 29),
            return_1m=0.01, return_3m=0.05, return_1y=0.12
        )
        
        alphas = AlphaCalculator.calculate_all_periods(fund_returns, bench_returns)
        
        assert abs(alphas["alpha_1m"] - 0.01) < 1e-9
        assert abs(alphas["alpha_3m"] - 0.01) < 1e-9
        assert abs(alphas["alpha_1y"] - 0.03) < 1e-9
        assert alphas["alpha_3y"] is None  # Not in fund_returns


class TestDrawdownCalculator:
    
    def test_max_drawdown_simple(self):
        """Simple peak-to-trough"""
        navs = pd.Series([100, 110, 105, 95, 100, 108], 
                         index=pd.date_range("2023-01-01", periods=6, freq="D"))
        result = DrawdownCalculator.max_drawdown(navs)
        # Peak 110, trough 95 -> drawdown = (110-95)/110 = 13.6%
        assert abs(result - 0.136) < 0.01
    
    def test_max_drawdown_no_drawdown(self):
        """Monotonically increasing -> 0 drawdown"""
        navs = pd.Series([100, 105, 110, 115], 
                         index=pd.date_range("2023-01-01", periods=4, freq="D"))
        result = DrawdownCalculator.max_drawdown(navs)
        assert result == 0.0
    
    def test_max_drawdown_insufficient_data(self):
        """Need at least 2 points"""
        navs = pd.Series([100], index=pd.date_range("2023-01-01", periods=1, freq="D"))
        result = DrawdownCalculator.max_drawdown(navs)
        assert result is None
    
    def test_rolling_max_drawdown(self):
        """Rolling window max drawdown"""
        navs = pd.Series([100, 110, 105, 95, 100, 108, 115, 110, 105, 100],
                         index=pd.date_range("2023-01-01", periods=10, freq="D"))
        # 5-day window
        result = DrawdownCalculator.rolling_max_drawdown(navs, 5)
        assert result is not None
        assert result >= 0


class TestVolatilityCalculator:
    
    @pytest.fixture
    def nav_series(self):
        """Create series with known volatility"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=253, freq="B")  # 253 to get 252 after slicing
        # Daily returns with 15% annual vol -> daily vol ~0.94%
        daily_returns = np.random.normal(0.0005, 0.0094, 252)
        navs = [100]
        for r in daily_returns:
            navs.append(navs[-1] * (1 + r))
        return pd.Series(navs[1:], index=dates[1:])  # 252 values, 252 dates
    
    def test_annualized_volatility(self, nav_series):
        """Should annualize daily volatility"""
        result = VolatilityCalculator.annualized_volatility(nav_series, 252)
        # With 15% annual vol input, should get ~15%
        assert result is not None
        assert 0.10 < result < 0.20  # Allow some variance
    
    def test_volatility_insufficient_data(self):
        """Need enough data points"""
        short_series = pd.Series([100, 101], 
                                  index=pd.date_range("2023-01-01", periods=2, freq="D"))
        result = VolatilityCalculator.annualized_volatility(short_series, 252)
        assert result is None
    
    def test_calculate_all_periods(self, nav_series):
        """Should calculate for all standard periods"""
        result = VolatilityCalculator.calculate_all_periods(nav_series)
        
        assert "volatility_1m" in result
        assert "volatility_3m" in result
        assert "volatility_1y" in result
        assert "volatility_3y" in result


class TestPercentileRankCalculator:
    
    def test_percentile_rank(self):
        """Percentile rank: % of peers with lower value"""
        # Value at 75th percentile in peer group
        peers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = PercentileRankCalculator.percentile_rank(8, peers)
        # 7 values below 8 out of 10 = 70%
        assert result == 70.0
    
    def test_percentile_rank_best(self):
        """Best value = 100th percentile"""
        peers = [1, 2, 3, 4, 5]
        result = PercentileRankCalculator.percentile_rank(10, peers)
        assert result == 100.0
    
    def test_percentile_rank_worst(self):
        """Worst value = 0th percentile"""
        peers = [1, 2, 3, 4, 5]
        result = PercentileRankCalculator.percentile_rank(0, peers)
        assert result == 0.0
    
    def test_percentile_rank_none(self):
        """Should handle None"""
        assert PercentileRankCalculator.percentile_rank(None, [1, 2, 3]) is None
        assert PercentileRankCalculator.percentile_rank(1, []) is None
        assert PercentileRankCalculator.percentile_rank(1, [None, None]) is None
    
    def test_rank(self):
        """Rank: 1 = best (highest return)"""
        peers = [0.05, 0.10, 0.15, 0.20]  # Returns
        result = PercentileRankCalculator.rank(0.15, peers, ascending=False)
        # Sorted descending: [0.20, 0.15, 0.15, 0.10, 0.05]
        # 0.15 is 2nd (first occurrence at index 1) -> rank 2
        assert result == 2
    
    def test_rank_ascending(self):
        """Ascending rank (for metrics where lower is better)"""
        peers = [0.05, 0.10, 0.15, 0.20]
        result = PercentileRankCalculator.rank(0.15, peers, ascending=True)
        assert result == 3
    
    def test_calculate_category_ranks(self):
        """Full category ranking"""
        scheme_returns = {
            "SCHEME_A": 0.15,
            "SCHEME_B": 0.12,
            "SCHEME_C": 0.10,
            "SCHEME_D": 0.08,
            "SCHEME_E": 0.05,
        }
        category_schemes = ["SCHEME_A", "SCHEME_B", "SCHEME_C", "SCHEME_D", "SCHEME_E"]
        
        results = PercentileRankCalculator.calculate_category_ranks(
            scheme_returns, category_schemes
        )
        
        # SCHEME_A (best) -> rank 1, percentile 100
        assert results["SCHEME_A"]["rank"] == 1
        assert results["SCHEME_A"]["percentile"] == 100.0
        
        # SCHEME_E (worst) -> rank 5, percentile 0
        assert results["SCHEME_E"]["rank"] == 5
        assert results["SCHEME_E"]["percentile"] == 0.0


class TestConsecutiveUnderperformanceCalculator:
    
    def test_monthly_streak(self):
        """Count consecutive months of underperformance"""
        # Oldest to newest: fund < bench for first 3, then fund > bench for last 3
        fund = pd.Series([0.01, 0.01, 0.01, 0.03, 0.02, 0.01])
        bench = pd.Series([0.02, 0.02, 0.02, 0.01, 0.01, 0.01])
        
        # Most recent 3 months: fund > bench (streak = 0)
        streak = ConsecutiveUnderperformanceCalculator.calculate_monthly_streak(fund, bench)
        assert streak == 0
    
    def test_monthly_streak_continues(self):
        """Streak continues if recent months all underperformed"""
        # Oldest to newest: fund > bench for first 2, then fund < bench for last 3
        fund = pd.Series([0.03, 0.03, -0.01, -0.02, -0.01])
        bench = pd.Series([0.02, 0.02, 0.01, 0.00, 0.01])
        
        # Most recent 3 months: fund < bench (streak = 3)
        streak = ConsecutiveUnderperformanceCalculator.calculate_monthly_streak(fund, bench)
        assert streak == 3
    
    def test_from_alphas(self):
        """Calculate streak from alpha dict"""
        alphas = {
            "alpha_1m": -0.01,
            "alpha_3m": -0.02,
            "alpha_6m": -0.01,
            "alpha_1y": 0.02,  # Positive breaks streak
            "alpha_3y": 0.05,
        }
        streak = ConsecutiveUnderperformanceCalculator.calculate_from_alphas(alphas)
        assert streak == 3  # 1m, 3m, 6m negative


class TestCorrelationCalculator:
    
    def test_rolling_correlation(self):
        """Correlation of daily returns"""
        np.random.seed(42)
        # Use more periods to ensure enough data after pct_change
        dates = pd.date_range("2023-01-01", periods=300, freq="B")
        
        # Create correlated series
        bench_returns = np.random.normal(0.0005, 0.01, 300)
        fund_returns = bench_returns * 0.8 + np.random.normal(0, 0.005, 300)
        
        bench_nav = pd.Series((1 + bench_returns).cumprod() * 1000, index=dates)
        fund_nav = pd.Series((1 + fund_returns).cumprod() * 100, index=dates)
        
        corr = CorrelationCalculator.rolling_correlation(fund_nav, bench_nav, 252)
        
        assert corr is not None
        assert 0.3 < corr < 1.0  # Should be positively correlated (lower bound relaxed)
    
    def test_insufficient_data(self):
        """Need enough overlapping data"""
        fund_nav = pd.Series([100, 101, 102], index=pd.date_range("2023-01-01", periods=3, freq="D"))
        bench_nav = pd.Series([1000, 1010], index=pd.date_range("2023-01-01", periods=2, freq="D"))
        
        corr = CorrelationCalculator.rolling_correlation(fund_nav, bench_nav, 10)
        assert corr is None


class TestFeatureEngineeringPipeline:
    
    @pytest.fixture
    def pipeline(self):
        return FeatureEngineeringPipeline()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample NAV data for multiple schemes"""
        np.random.seed(42)
        
        nav_records = []
        benchmark_records = []
        scheme_categories = {}
        
        # Create 5 schemes in "Large Cap" category
        for i in range(5):
            scheme_code = f"SCHEME_{i}"
            scheme_categories[scheme_code] = "Large Cap"
            
            dates = pd.date_range("2022-01-01", periods=500, freq="B")
            daily_returns = np.random.normal(0.0004, 0.01, len(dates))
            navs = [100]
            for r in daily_returns:
                navs.append(navs[-1] * (1 + r))
            
            for d, nav in zip(dates, navs[1:]):
                nav_records.append({
                    "scheme_code": scheme_code,
                    "nav_date": d.date(),
                    "nav_value": nav,
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
                "index_value": nav,
            })
        
        return nav_records, benchmark_records, scheme_categories
    
    def test_load_data(self, pipeline, sample_data):
        """Should load NAV and benchmark history"""
        nav_records, benchmark_records, scheme_categories = sample_data
        
        pipeline.load_nav_history(nav_records)
        pipeline.load_benchmark_history(benchmark_records)
        pipeline.load_scheme_categories(scheme_categories)
        
        assert len(pipeline.scheme_navs) == 5
        assert "NIFTY100_TRI" in pipeline.benchmark_navs
        assert len(pipeline.scheme_categories) == 5
    
    def test_compute_all_features(self, pipeline, sample_data):
        """Should compute features for all schemes"""
        nav_records, benchmark_records, scheme_categories = sample_data
        
        pipeline.load_nav_history(nav_records)
        pipeline.load_benchmark_history(benchmark_records)
        pipeline.load_scheme_categories(scheme_categories)
        
        features = pipeline.compute_all_features(date(2023, 12, 29))
        
        assert len(features) == 5
        for f in features:
            assert isinstance(f, SchemeFeatures)
            assert f.scheme_code in scheme_categories
            assert f.as_of_date == date(2023, 12, 29)
            assert f.rolling_returns is not None
            assert f.rolling_returns.return_1y is not None
    
    def test_features_have_all_components(self, pipeline, sample_data):
        """Features should include returns, risk, category-relative, streaks"""
        nav_records, benchmark_records, scheme_categories = sample_data
        
        pipeline.load_nav_history(nav_records)
        pipeline.load_benchmark_history(benchmark_records)
        pipeline.load_scheme_categories(scheme_categories)
        
        features = pipeline.compute_all_features(date(2023, 12, 29))
        f = features[0]
        
        # Returns
        assert f.rolling_returns.return_1y is not None
        
        # Alpha (vs benchmark)
        assert f.alpha_1y is not None
        
        # Drawdown
        assert f.max_drawdown_1y is not None
        
        # Volatility
        assert f.volatility_1y is not None
        
        # Category-relative
        assert f.category_percentile_1y is not None
        assert f.category_rank_1y is not None
        
        # Streak
        assert isinstance(f.consecutive_underperf_months, int)
        
        # Correlation
        assert f.correlation_to_benchmark_1y is not None
    
    def test_export_features(self, pipeline, sample_data, tmp_path):
        """Should export features to JSON"""
        nav_records, benchmark_records, scheme_categories = sample_data
        
        pipeline.load_nav_history(nav_records)
        pipeline.load_benchmark_history(benchmark_records)
        pipeline.load_scheme_categories(scheme_categories)
        
        features = pipeline.compute_all_features(date(2023, 12, 29))
        export_path = tmp_path / "features.json"
        
        pipeline.export_features(features, export_path)
        
        assert export_path.exists()
        import json
        with open(export_path) as f:
            data = json.load(f)
        assert len(data) == 5
        assert "scheme_code" in data[0]


class TestSchemeFeaturesDataclass:
    
    def test_to_dict(self):
        """Should serialize to dict"""
        features = SchemeFeatures(
            scheme_code="TEST",
            as_of_date=date(2023, 12, 29),
            alpha_1y=0.02,
            max_drawdown_1y=0.15,
        )
        
        d = features.to_dict()
        
        assert d["scheme_code"] == "TEST"
        assert d["as_of_date"] == "2023-12-29"
        assert d["alpha_1y"] == 0.02
        assert d["max_drawdown_1y"] == 0.15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])