"""
Rule Engine — YAML-config deterministic alert rules
No ML — pure config-driven thresholds evaluated nightly per scheme
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import date
from pathlib import Path
import yaml


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertType(str, Enum):
    UNDERPERFORM_3M = "underperform_3m"
    UNDERPERFORM_6M = "underperform_6m"
    UNDERPERFORM_1Y = "underperform_1y"
    BELOW_TOP25_CATEGORY = "below_top25_category"
    BELOW_TOP50_CATEGORY = "below_top50_category"
    RANK_DECLINE = "rank_decline"
    BENCHMARK_DEVIATION = "benchmark_deviation"
    HIGH_DRAWDOWN = "high_drawdown"
    HIGH_VOLATILITY = "high_volatility"
    CONSECUTIVE_UNDERPERF = "consecutive_underperf"
    STALE_NAV = "stale_nav"
    NAV_JUMP = "nav_jump"
    AUM_DROP = "aum_drop"


@dataclass
class AlertRule:
    """Single alert rule definition"""
    id: str
    alert_type: AlertType
    condition: str  # Python expression evaluated against scheme features
    severity: AlertSeverity
    description: str = ""
    enabled: bool = True
    # Per-category overrides (optional)
    category_overrides: dict[str, dict] = field(default_factory=dict)


@dataclass
class Alert:
    """Triggered alert"""
    alert_id: str  # UUID or sequential
    scheme_code: str
    alert_type: AlertType
    severity: AlertSeverity
    triggered_on: date
    resolved_on: Optional[date] = None
    details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "scheme_code": self.scheme_code,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "triggered_on": self.triggered_on.isoformat(),
            "resolved_on": self.resolved_on.isoformat() if self.resolved_on else None,
            "details": self.details,
        }


class RuleEngine:
    """
    Evaluates alert rules against scheme features.
    Rules are defined in YAML config for easy tuning without code changes.
    """
    
    def __init__(self, rules: list[AlertRule] = None):
        self.rules = rules or []
        self._alert_counter = 0
    
    def add_rule(self, rule: AlertRule) -> None:
        self.rules.append(rule)
    
    def load_from_yaml(self, path: str | Path) -> int:
        """Load rules from YAML file. Returns count loaded."""
        path = Path(path)
        with open(path) as f:
            config = yaml.safe_load(f)
        
        count = 0
        for rule_data in config.get("alert_rules", []):
            rule = AlertRule(
                id=rule_data["id"],
                alert_type=AlertType(rule_data["alert_type"]),
                condition=rule_data["condition"],
                severity=AlertSeverity(rule_data["severity"]),
                description=rule_data.get("description", ""),
                enabled=rule_data.get("enabled", True),
                category_overrides=rule_data.get("category_overrides", {}),
            )
            self.add_rule(rule)
            count += 1
        return count
    
    def evaluate(self, scheme_features: dict, scheme_code: str, 
                 as_of_date: date) -> list[Alert]:
        """
        Evaluate all enabled rules against a scheme's features.
        
        Args:
            scheme_features: Dict of feature_name -> value (from SchemeFeatures.to_dict())
            scheme_code: Scheme identifier
            as_of_date: Evaluation date
            
        Returns:
            List of triggered Alert objects
        """
        alerts = []
        
        # Get category for potential overrides
        category = scheme_features.get("category", "")
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # Check category-specific override
            condition = rule.condition
            severity = rule.severity
            if category in rule.category_overrides:
                override = rule.category_overrides[category]
                condition = override.get("condition", condition)
                severity = AlertSeverity(override.get("severity", severity.value))
            
            # Evaluate condition
            try:
                triggered = self._eval_condition(condition, scheme_features)
            except Exception as e:
                # Log error in production, skip rule
                print(f"Error evaluating rule {rule.id} for {scheme_code}: {e}")
                continue
            
            if triggered:
                self._alert_counter += 1
                alert = Alert(
                    alert_id=f"{rule.id}_{scheme_code}_{as_of_date.isoformat()}_{self._alert_counter}",
                    scheme_code=scheme_code,
                    alert_type=rule.alert_type,
                    severity=severity,
                    triggered_on=as_of_date,
                    details={
                        "rule_id": rule.id,
                        "condition": condition,
                        "feature_values": self._extract_relevant_features(condition, scheme_features),
                    }
                )
                alerts.append(alert)
        
        return alerts
    
    def evaluate_batch(self, all_features: list[dict], as_of_date: date) -> list[Alert]:
        """Evaluate rules against all schemes"""
        all_alerts = []
        for features in all_features:
            scheme_code = features.get("scheme_code", "")
            alerts = self.evaluate(features, scheme_code, as_of_date)
            all_alerts.extend(alerts)
        return all_alerts
    
    def _eval_condition(self, condition: str, features: dict) -> bool:
        """Safely evaluate a condition expression"""
        # Create a safe evaluation context
        context = {k: v for k, v in features.items() if v is not None}
        
        # Add helper functions
        context["abs"] = abs
        context["min"] = min
        context["max"] = max
        
        # Evaluate
        return bool(eval(condition, {"__builtins__": {}}, context))
    
    def _extract_relevant_features(self, condition: str, features: dict) -> dict:
        """Extract feature values referenced in condition for alert details"""
        # Simple extraction - in production, parse AST for accuracy
        relevant = {}
        for key, value in features.items():
            if key in condition and value is not None:
                relevant[key] = value
        return relevant
    
    def export_to_yaml(self, path: str | Path) -> None:
        """Export current rules to YAML"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        config = {"alert_rules": []}
        for rule in self.rules:
            config["alert_rules"].append({
                "id": rule.id,
                "alert_type": rule.alert_type.value,
                "condition": rule.condition,
                "severity": rule.severity.value,
                "description": rule.description,
                "enabled": rule.enabled,
                "category_overrides": rule.category_overrides,
            })
        
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


# Default rules from architecture doc Section 6
DEFAULT_RULES = [
    AlertRule(
        id="underperform_3m",
        alert_type=AlertType.UNDERPERFORM_3M,
        condition="consecutive_underperf_months >= 3",
        severity=AlertSeverity.MEDIUM,
        description="Fund underperformed benchmark for 3+ consecutive months",
    ),
    AlertRule(
        id="underperform_6m",
        alert_type=AlertType.UNDERPERFORM_6M,
        condition="consecutive_underperf_months >= 6",
        severity=AlertSeverity.HIGH,
        description="Fund underperformed benchmark for 6+ consecutive months",
    ),
    AlertRule(
        id="below_top25_category",
        alert_type=AlertType.BELOW_TOP25_CATEGORY,
        condition="category_percentile_1y is not None and category_percentile_1y < 75",
        severity=AlertSeverity.MEDIUM,
        description="Fund ranked below top 25% in category over 1Y",
    ),
    AlertRule(
        id="below_top50_category",
        alert_type=AlertType.BELOW_TOP50_CATEGORY,
        condition="category_percentile_1y is not None and category_percentile_1y < 50",
        severity=AlertSeverity.HIGH,
        description="Fund ranked below top 50% in category over 1Y",
    ),
    AlertRule(
        id="rank_decline",
        alert_type=AlertType.RANK_DECLINE,
        condition="category_rank_1y is not None and category_rank_3m is not None and (category_rank_1y - category_rank_3m) > 10",
        severity=AlertSeverity.MEDIUM,
        description="Category rank declined by more than 10 positions in 3 months",
    ),
    AlertRule(
        id="benchmark_deviation",
        alert_type=AlertType.BENCHMARK_DEVIATION,
        condition="alpha_1y is not None and abs(alpha_1y) > 0.05",
        severity=AlertSeverity.LOW,
        description="1Y alpha deviation exceeds 5% (positive or negative)",
        category_overrides={
            "Small Cap": {"condition": "alpha_1y is not None and abs(alpha_1y) > 0.10", "severity": "low"},
            "Mid Cap": {"condition": "alpha_1y is not None and abs(alpha_1y) > 0.08", "severity": "low"},
        },
    ),
    AlertRule(
        id="high_drawdown",
        alert_type=AlertType.HIGH_DRAWDOWN,
        condition="max_drawdown_1y is not None and max_drawdown_1y > 0.20",
        severity=AlertSeverity.MEDIUM,
        description="1Y max drawdown exceeds 20%",
    ),
    AlertRule(
        id="high_volatility",
        alert_type=AlertType.HIGH_VOLATILITY,
        condition="volatility_1y is not None and volatility_1y > 0.25",
        severity=AlertSeverity.LOW,
        description="1Y annualized volatility exceeds 25%",
    ),
    AlertRule(
        id="consecutive_underperf",
        alert_type=AlertType.CONSECUTIVE_UNDERPERF,
        condition="consecutive_underperf_months >= 4",
        severity=AlertSeverity.MEDIUM,
        description="4+ consecutive months of benchmark underperformance",
    ),
]


def create_default_engine() -> RuleEngine:
    """Create RuleEngine with default rules"""
    engine = RuleEngine()
    for rule in DEFAULT_RULES:
        engine.add_rule(rule)
    return engine