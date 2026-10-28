"""
Tests for Rule Engine
Run: python -m pytest test_rule_engine.py -v
"""

import pytest
from datetime import date
from fund_engine.domain.rules.rule_engine import (
    RuleEngine,
    AlertRule,
    Alert,
    AlertType,
    AlertSeverity,
    DEFAULT_RULES,
    create_default_engine,
)


class TestAlertRule:
    
    def test_alert_rule_creation(self):
        rule = AlertRule(
            id="test_rule",
            alert_type=AlertType.UNDERPERFORM_3M,
            condition="alpha_1y < -0.02",
            severity=AlertSeverity.HIGH,
            description="Test rule",
        )
        assert rule.id == "test_rule"
        assert rule.alert_type == AlertType.UNDERPERFORM_3M
        assert rule.severity == AlertSeverity.HIGH
        assert rule.enabled is True
    
    def test_category_override(self):
        rule = AlertRule(
            id="test",
            alert_type=AlertType.BENCHMARK_DEVIATION,
            condition="abs(alpha_1y) > 0.05",
            severity=AlertSeverity.LOW,
            category_overrides={
                "Small Cap": {"condition": "abs(alpha_1y) > 0.10", "severity": "medium"},
            }
        )
        assert "Small Cap" in rule.category_overrides


class TestRuleEngine:
    
    @pytest.fixture
    def engine(self):
        return create_default_engine()
    
    @pytest.fixture
    def sample_features_good(self):
        """Scheme with good performance - should trigger few/no alerts"""
        return {
            "scheme_code": "GOOD_FUND",
            "category": "Large Cap",
            "alpha_1y": 0.03,
            "alpha_3m": 0.01,
            "category_percentile_1y": 85,
            "category_percentile_3m": 80,
            "category_rank_1y": 5,
            "category_rank_3m": 8,
            "max_drawdown_1y": 0.12,
            "volatility_1y": 0.16,
            "consecutive_underperf_months": 0,
            "correlation_to_benchmark_1y": 0.85,
        }
    
    @pytest.fixture
    def sample_features_bad(self):
        """Scheme with poor performance - should trigger multiple alerts"""
        return {
            "scheme_code": "BAD_FUND",
            "category": "Large Cap",
            "alpha_1y": -0.08,
            "alpha_3m": -0.03,
            "category_percentile_1y": 30,
            "category_percentile_3m": 25,
            "category_rank_1y": 85,
            "category_rank_3m": 50,
            "max_drawdown_1y": 0.25,
            "volatility_1y": 0.30,
            "consecutive_underperf_months": 6,  # Need >=6 for UNDERPERFORM_6M
            "correlation_to_benchmark_1y": 0.60,
        }
    
    @pytest.fixture
    def sample_features_smallcap(self):
        """Small cap fund - tests category overrides"""
        return {
            "scheme_code": "SMALL_FUND",
            "category": "Small Cap",
            "alpha_1y": -0.08,  # Would trigger benchmark_deviation for Large Cap
            "alpha_3m": -0.03,
            "category_percentile_1y": 30,
            "category_rank_1y": 85,
            "max_drawdown_1y": 0.25,
            "volatility_1y": 0.30,
            "consecutive_underperf_months": 5,
        }
    
    def test_good_fund_few_alerts(self, engine, sample_features_good):
        """Good fund should trigger minimal alerts"""
        alerts = engine.evaluate(sample_features_good, "GOOD_FUND", date(2023, 12, 29))
        
        # Should not trigger underperformance, rank decline, high drawdown, etc.
        alert_types = [a.alert_type for a in alerts]
        assert AlertType.UNDERPERFORM_3M not in alert_types
        assert AlertType.UNDERPERFORM_6M not in alert_types
        assert AlertType.BELOW_TOP50_CATEGORY not in alert_types
        assert AlertType.RANK_DECLINE not in alert_types
        assert AlertType.HIGH_DRAWDOWN not in alert_types
        assert AlertType.HIGH_VOLATILITY not in alert_types
        assert AlertType.CONSECUTIVE_UNDERPERF not in alert_types
    
    def test_bad_fund_many_alerts(self, engine, sample_features_bad):
        """Bad fund should trigger multiple alerts"""
        alerts = engine.evaluate(sample_features_bad, "BAD_FUND", date(2023, 12, 29))
        
        alert_types = {a.alert_type for a in alerts}
        
        # Should trigger these
        assert AlertType.UNDERPERFORM_3M in alert_types
        assert AlertType.UNDERPERFORM_6M in alert_types
        assert AlertType.BELOW_TOP25_CATEGORY in alert_types
        assert AlertType.BELOW_TOP50_CATEGORY in alert_types
        assert AlertType.RANK_DECLINE in alert_types  # rank went from 50 to 85
        assert AlertType.BENCHMARK_DEVIATION in alert_types  # alpha_1y = -0.08
        assert AlertType.HIGH_DRAWDOWN in alert_types  # 25% > 20%
        assert AlertType.HIGH_VOLATILITY in alert_types  # 30% > 25%
        assert AlertType.CONSECUTIVE_UNDERPERF in alert_types  # 5 months
    
    def test_severity_levels(self, engine, sample_features_bad):
        """Alerts should have correct severity"""
        alerts = engine.evaluate(sample_features_bad, "BAD_FUND", date(2023, 12, 29))
        
        severity_map = {a.alert_type: a.severity for a in alerts}
        
        assert severity_map[AlertType.UNDERPERFORM_3M] == AlertSeverity.MEDIUM
        assert severity_map[AlertType.UNDERPERFORM_6M] == AlertSeverity.HIGH
        assert severity_map[AlertType.BELOW_TOP25_CATEGORY] == AlertSeverity.MEDIUM
        assert severity_map[AlertType.BELOW_TOP50_CATEGORY] == AlertSeverity.HIGH
        assert severity_map[AlertType.RANK_DECLINE] == AlertSeverity.MEDIUM
        assert severity_map[AlertType.BENCHMARK_DEVIATION] == AlertSeverity.LOW
        assert severity_map[AlertType.HIGH_DRAWDOWN] == AlertSeverity.MEDIUM
        assert severity_map[AlertType.HIGH_VOLATILITY] == AlertSeverity.LOW
        assert severity_map[AlertType.CONSECUTIVE_UNDERPERF] == AlertSeverity.MEDIUM
    
    def test_category_override_small_cap(self, engine, sample_features_smallcap):
        """Small Cap should use overridden threshold for benchmark_deviation"""
        alerts = engine.evaluate(sample_features_smallcap, "SMALL_FUND", date(2023, 12, 29))
        
        alert_types = {a.alert_type for a in alerts}
        
        # For Small Cap, benchmark_deviation threshold is 10% not 5%
        # alpha_1y = -0.08 (8%) < 10% threshold, so should NOT trigger
        assert AlertType.BENCHMARK_DEVIATION not in alert_types
    
    def test_category_override_mid_cap(self, engine):
        """Mid Cap should use 8% threshold"""
        features = {
            "scheme_code": "MID_FUND",
            "category": "Mid Cap",
            "alpha_1y": -0.07,  # 7% - below 8% threshold
            "category_percentile_1y": 50,
            "category_rank_1y": 50,
            "max_drawdown_1y": 0.15,
            "volatility_1y": 0.20,
            "consecutive_underperf_months": 0,
        }
        alerts = engine.evaluate(features, "MID_FUND", date(2023, 12, 29))
        alert_types = {a.alert_type for a in alerts}
        assert AlertType.BENCHMARK_DEVIATION not in alert_types
        
        # Now test above threshold
        features["alpha_1y"] = -0.09  # 9% - above 8% threshold
        alerts = engine.evaluate(features, "MID_FUND", date(2023, 12, 29))
        alert_types = {a.alert_type for a in alerts}
        assert AlertType.BENCHMARK_DEVIATION in alert_types
    
    def test_batch_evaluation(self, engine, sample_features_good, sample_features_bad):
        """Batch evaluation should process multiple schemes"""
        all_features = [sample_features_good, sample_features_bad]
        alerts = engine.evaluate_batch(all_features, date(2023, 12, 29))
        
        # Should have alerts from bad fund, none from good fund
        scheme_alerts = {}
        for a in alerts:
            scheme_alerts.setdefault(a.scheme_code, []).append(a)
        
        assert len(scheme_alerts.get("GOOD_FUND", [])) == 0
        assert len(scheme_alerts.get("BAD_FUND", [])) > 0
    
    def test_disabled_rule(self, engine):
        """Disabled rules should not trigger"""
        engine.add_rule(AlertRule(
            id="disabled_test",
            alert_type=AlertType.NAV_JUMP,
            condition="True",  # Always true
            severity=AlertSeverity.HIGH,
            enabled=False,
        ))
        
        features = {"scheme_code": "TEST", "category": "Large Cap"}
        alerts = engine.evaluate(features, "TEST", date(2023, 12, 29))
        
        alert_types = {a.alert_type for a in alerts}
        assert AlertType.NAV_JUMP not in alert_types
    
    def test_alert_details(self, engine, sample_features_bad):
        """Alert should include relevant feature values in details"""
        alerts = engine.evaluate(sample_features_bad, "BAD_FUND", date(2023, 12, 29))
        
        for alert in alerts:
            assert "rule_id" in alert.details
            assert "condition" in alert.details
            assert "feature_values" in alert.details
            # Feature values should include those referenced in condition
            assert len(alert.details["feature_values"]) > 0
    
    def test_alert_to_dict(self):
        """Alert serialization"""
        alert = Alert(
            alert_id="test_123",
            scheme_code="TEST",
            alert_type=AlertType.UNDERPERFORM_3M,
            severity=AlertSeverity.MEDIUM,
            triggered_on=date(2023, 12, 29),
            details={"rule_id": "underperform_3m", "test": "value"},
        )
        
        d = alert.to_dict()
        
        assert d["alert_id"] == "test_123"
        assert d["scheme_code"] == "TEST"
        assert d["alert_type"] == "underperform_3m"
        assert d["severity"] == "medium"
        assert d["triggered_on"] == "2023-12-29"
        assert d["resolved_on"] is None
        assert d["details"]["test"] == "value"


class TestYAMLConfig:
    
    @pytest.fixture
    def engine(self):
        return RuleEngine()
    
    def test_load_from_yaml(self, engine, tmp_path):
        """Should load rules from YAML file"""
        yaml_content = """
alert_rules:
  - id: yaml_rule_1
    alert_type: underperform_3m
    condition: "consecutive_underperf_months >= 3"
    severity: medium
    description: "From YAML"
    enabled: true
  - id: yaml_rule_2
    alert_type: high_drawdown
    condition: "max_drawdown_1y > 0.20"
    severity: high
    description: "High drawdown"
"""
        yaml_path = tmp_path / "rules.yaml"
        yaml_path.write_text(yaml_content)
        
        count = engine.load_from_yaml(yaml_path)
        
        assert count == 2
        assert len(engine.rules) == 2
        assert engine.rules[0].id == "yaml_rule_1"
        assert engine.rules[1].severity == AlertSeverity.HIGH
    
    def test_export_to_yaml(self, engine, tmp_path):
        """Should export rules to YAML"""
        yaml_path = tmp_path / "exported_rules.yaml"
        engine.export_to_yaml(yaml_path)
        
        assert yaml_path.exists()
        
        import yaml
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
        
        assert "alert_rules" in config
        assert len(config["alert_rules"]) == len(engine.rules)


class TestDefaultRules:
    
    def test_default_rules_exist(self):
        """All default rules should be defined"""
        assert len(DEFAULT_RULES) == 9
        
        rule_ids = {r.id for r in DEFAULT_RULES}
        expected = {
            "underperform_3m", "underperform_6m", "below_top25_category",
            "below_top50_category", "rank_decline", "benchmark_deviation",
            "high_drawdown", "high_volatility", "consecutive_underperf",
        }
        assert rule_ids == expected
    
    def test_default_rules_have_categories(self):
        """Each rule should have proper alert_type"""
        for rule in DEFAULT_RULES:
            assert isinstance(rule.alert_type, AlertType)
            assert isinstance(rule.severity, AlertSeverity)
            assert rule.condition
            assert rule.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])