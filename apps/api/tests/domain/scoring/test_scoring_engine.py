"""
Tests for Scoring Engine
Run: python -m pytest test_scoring_engine.py -v
"""

import pytest
from datetime import date
from fund_engine.domain.scoring.scoring_engine import (
    ScoringEngine,
    ScoringConfig,
    ComponentConfig,
    ScoreComponent,
    FundScore,
    ScoreBreakdownItem,
    create_default_scoring_engine,
)


class TestScoringConfig:
    
    def test_default_config(self):
        config = ScoringConfig.default()
        
        assert config.version == "1.0"
        assert len(config.components) == 5
        assert config.penalty_per_month == 2.0
        assert config.penalty_cap == 20.0
        
        # Check weights sum to 1.0
        total_weight = sum(c.weight for c in config.components.values())
        assert abs(total_weight - 1.0) < 0.001
        
        # Check max points sum to 100
        total_points = sum(c.max_points for c in config.components.values())
        assert total_points == 100
    
    def test_config_serialization(self, tmp_path):
        config = ScoringConfig.default()
        path = tmp_path / "scoring_config.yaml"
        config.save(path)
        
        loaded = ScoringConfig.load(path)
        
        assert loaded.version == config.version
        assert loaded.penalty_per_month == config.penalty_per_month
        assert loaded.penalty_cap == config.penalty_cap
        assert set(loaded.components.keys()) == set(config.components.keys())


class TestScoringEngine:
    
    @pytest.fixture
    def engine(self):
        return create_default_scoring_engine()
    
    @pytest.fixture
    def good_fund_features(self):
        """Fund with strong performance"""
        return {
            "scheme_code": "GOOD_FUND",
            "alpha_1y": 0.06,
            "alpha_3y": 0.04,
            "category_percentile_1y": 90,
            "category_rank_1y": 5,
            "consecutive_underperf_months": 0,
            "max_drawdown_1y": 0.08,
            "volatility_1y": 0.14,
        }
    
    @pytest.fixture
    def average_fund_features(self):
        """Fund with average performance"""
        return {
            "scheme_code": "AVG_FUND",
            "alpha_1y": 0.01,
            "alpha_3y": 0.00,
            "category_percentile_1y": 50,
            "category_rank_1y": 50,
            "consecutive_underperf_months": 2,
            "max_drawdown_1y": 0.18,
            "volatility_1y": 0.20,
        }
    
    @pytest.fixture
    def poor_fund_features(self):
        """Fund with poor performance"""
        return {
            "scheme_code": "POOR_FUND",
            "alpha_1y": -0.08,
            "alpha_3y": -0.03,
            "category_percentile_1y": 20,
            "category_rank_1y": 90,
            "consecutive_underperf_months": 6,
            "max_drawdown_1y": 0.30,
            "volatility_1y": 0.30,
        }
    
    def test_good_fund_high_score(self, engine, good_fund_features):
        """Good fund should get high score"""
        score = engine.calculate(good_fund_features, "GOOD_FUND", date(2023, 12, 29))
        
        assert isinstance(score, FundScore)
        assert score.fund_health_score >= 75  # Should be high
        assert score.scheme_code == "GOOD_FUND"
        assert len(score.breakdown) == 5
        assert score.penalty == 0.0  # No underperformance streak
    
    def test_poor_fund_low_score(self, engine, poor_fund_features):
        """Poor fund should get low score"""
        score = engine.calculate(poor_fund_features, "POOR_FUND", date(2023, 12, 29))
        
        assert score.fund_health_score <= 40  # Should be low
        assert score.penalty > 0  # Should have penalty (6 months * 2 = 12, capped at 20)
        assert score.penalty == 12.0  # 6 * 2 = 12
    
    def test_average_fund_mid_score(self, engine, average_fund_features):
        """Average fund should get mid-range score"""
        score = engine.calculate(average_fund_features, "AVG_FUND", date(2023, 12, 29))
        
        assert 40 <= score.fund_health_score <= 70
        assert score.penalty == 4.0  # 2 months * 2 = 4
    
    def test_score_bounds(self, engine, poor_fund_features):
        """Score should be clamped to 0-100"""
        # Even with extreme penalty, score shouldn't go below 0
        extreme_features = poor_fund_features.copy()
        extreme_features["consecutive_underperf_months"] = 20  # 40 penalty, capped at 20
        
        score = engine.calculate(extreme_features, "EXTREME", date(2023, 12, 29))
        
        assert 0 <= score.fund_health_score <= 100
        assert score.penalty == 20.0  # Capped at penalty_cap
    
    def test_breakdown_structure(self, engine, good_fund_features):
        """Breakdown should have all 5 components with explainability"""
        score = engine.calculate(good_fund_features, "GOOD_FUND", date(2023, 12, 29))
        
        component_names = {b.component for b in score.breakdown}
        expected = {c.value for c in ScoreComponent}
        assert component_names == expected
        
        for b in score.breakdown:
            assert b.component in expected
            assert 0 <= b.points <= b.max_points
            assert b.reason  # Non-empty explanation
            assert b.raw_value is not None
    
    def test_benchmark_outperformance_scoring(self, engine):
        """Test alpha-based scoring"""
        # High alpha
        features = {"alpha_1y": 0.06, "category_percentile_1y": 50, "consecutive_underperf_months": 0,
                   "max_drawdown_1y": 0.15, "volatility_1y": 0.16}
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        bench_component = next(b for b in score.breakdown if b.component == "benchmark_outperformance")
        assert bench_component.points == 30  # Max for alpha > 5%
        
        # Negative alpha
        features["alpha_1y"] = -0.06
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        bench_component = next(b for b in score.breakdown if b.component == "benchmark_outperformance")
        assert bench_component.points == 0  # Min for alpha < -5%
    
    def test_category_ranking_scoring(self, engine):
        """Test percentile-based scoring"""
        # Top percentile
        features = {"alpha_1y": 0.0, "category_percentile_1y": 100, "category_rank_1y": 1,
                   "consecutive_underperf_months": 0, "max_drawdown_1y": 0.15, "volatility_1y": 0.16}
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        rank_component = next(b for b in score.breakdown if b.component == "category_ranking")
        assert rank_component.points == 20  # Max
        
        # Bottom percentile
        features["category_percentile_1y"] = 0
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        rank_component = next(b for b in score.breakdown if b.component == "category_ranking")
        assert rank_component.points == 0  # Min
        
        # Median
        features["category_percentile_1y"] = 50
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        rank_component = next(b for b in score.breakdown if b.component == "category_ranking")
        assert rank_component.points == 10  # Half
    
    def test_drawdown_scoring(self, engine):
        """Test drawdown-based scoring"""
        base = {"alpha_1y": 0.0, "category_percentile_1y": 50, "consecutive_underperf_months": 0,
                "volatility_1y": 0.16}
        
        # Low drawdown
        features = {**base, "max_drawdown_1y": 0.08}
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        dd_component = next(b for b in score.breakdown if b.component == "drawdown_control")
        assert dd_component.points == 15  # Max
        
        # High drawdown
        features["max_drawdown_1y"] = 0.28
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        dd_component = next(b for b in score.breakdown if b.component == "drawdown_control")
        assert dd_component.points == 0  # Min
    
    def test_volatility_scoring(self, engine):
        """Test volatility-based scoring"""
        base = {"alpha_1y": 0.0, "category_percentile_1y": 50, "consecutive_underperf_months": 0,
                "max_drawdown_1y": 0.15}
        
        # Low volatility
        features = {**base, "volatility_1y": 0.12}
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        vol_component = next(b for b in score.breakdown if b.component == "volatility_adjusted")
        assert vol_component.points == 15  # Max
        
        # High volatility
        features["volatility_1y"] = 0.30
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        vol_component = next(b for b in score.breakdown if b.component == "volatility_adjusted")
        assert vol_component.points == 0  # Min
    
    def test_consistency_scoring(self, engine):
        """Test consistency scoring based on streak"""
        base = {"alpha_1y": 0.0, "category_percentile_1y": 50,
                "max_drawdown_1y": 0.15, "volatility_1y": 0.16}
        
        # No streak
        features = {**base, "consecutive_underperf_months": 0}
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        cons_component = next(b for b in score.breakdown if b.component == "consistency_of_returns")
        assert cons_component.points == 20  # Max
        
        # 3 month streak
        features["consecutive_underperf_months"] = 3
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        cons_component = next(b for b in score.breakdown if b.component == "consistency_of_returns")
        # 36 month lookback, 3 months streak = 20 * (1 - 3/36) = 18.33
        assert abs(cons_component.points - 18.33) < 0.1
        
        # Max streak
        features["consecutive_underperf_months"] = 36
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        cons_component = next(b for b in score.breakdown if b.component == "consistency_of_returns")
        assert cons_component.points == 0  # Min
    
    def test_penalty_calculation(self, engine):
        """Penalty should be streak * penalty_per_month, capped"""
        base = {"alpha_1y": 0.0, "category_percentile_1y": 50,
                "max_drawdown_1y": 0.15, "volatility_1y": 0.16}
        
        # 5 month streak = 10 penalty
        features = {**base, "consecutive_underperf_months": 5}
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        assert score.penalty == 10.0
        
        # 15 month streak = 30 penalty, capped at 20
        features["consecutive_underperf_months"] = 15
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        assert score.penalty == 20.0
    
    def test_batch_calculation(self, engine, good_fund_features, poor_fund_features):
        """Batch calculation should work"""
        all_features = [good_fund_features, poor_fund_features]
        scores = engine.calculate_batch(all_features, date(2023, 12, 29))
        
        assert len(scores) == 2
        assert scores[0].fund_health_score > scores[1].fund_health_score
    
    def test_score_serialization(self, engine, good_fund_features):
        """FundScore should serialize to dict and JSON"""
        score = engine.calculate(good_fund_features, "GOOD_FUND", date(2023, 12, 29))
        
        d = score.to_dict()
        assert d["scheme_code"] == "GOOD_FUND"
        assert d["fund_health_score"] == score.fund_health_score
        assert len(d["breakdown"]) == 5
        assert "penalty" in d
        
        json_str = score.to_json()
        assert "GOOD_FUND" in json_str
        assert str(score.fund_health_score) in json_str


class TestScoreBreakdownItem:
    
    def test_breakdown_item(self):
        item = ScoreBreakdownItem(
            component="benchmark_outperformance",
            points=25.0,
            max_points=30,
            reason="Beat benchmark by 6.0%",
            raw_value=0.06
        )
        
        assert item.component == "benchmark_outperformance"
        assert item.points == 25.0
        assert item.max_points == 30
        assert item.reason == "Beat benchmark by 6.0%"
        assert item.raw_value == 0.06


class TestCustomConfig:
    
    def test_custom_weights(self):
        """Should support custom weight configurations"""
        config = ScoringConfig(
            version="2.0",
            effective_date=date(2024, 6, 1),
            components={
                ScoreComponent.BENCHMARK_OUTPERFORMANCE: ComponentConfig(0.40, 40),
                ScoreComponent.CATEGORY_RANKING: ComponentConfig(0.30, 30),
                ScoreComponent.CONSISTENCY_OF_RETURNS: ComponentConfig(0.15, 15),
                ScoreComponent.DRAWDOWN_CONTROL: ComponentConfig(0.10, 10),
                ScoreComponent.VOLATILITY_ADJUSTED: ComponentConfig(0.05, 5),
            },
            penalty_per_month=3.0,
            penalty_cap=30.0,
        )
        
        engine = ScoringEngine(config)
        
        features = {"alpha_1y": 0.0, "category_percentile_1y": 50,
                   "consecutive_underperf_months": 0, "max_drawdown_1y": 0.15,
                   "volatility_1y": 0.16}
        score = engine.calculate(features, "TEST", date(2023, 12, 29))
        
        # With alpha=0, benchmark_outperformance should give 10/40 = 25% of 40 = 10 points
        bench_component = next(b for b in score.breakdown if b.component == "benchmark_outperformance")
        assert bench_component.max_points == 40
        assert bench_component.points == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])