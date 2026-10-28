"""
Scoring Engine — 0-100 Fund Health Score with Explainable Breakdown
Weighted, additive, fully explainable. No black box.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date
from enum import Enum
from pathlib import Path
import yaml
import json


class ScoreComponent(str, Enum):
    """Score components from architecture doc Section 11"""
    BENCHMARK_OUTPERFORMANCE = "benchmark_outperformance"
    CATEGORY_RANKING = "category_ranking"
    CONSISTENCY_OF_RETURNS = "consistency_of_returns"
    DRAWDOWN_CONTROL = "drawdown_control"
    VOLATILITY_ADJUSTED = "volatility_adjusted"


@dataclass
class ComponentConfig:
    """Configuration for a score component"""
    weight: float
    max_points: int
    # Scaling function parameters
    scale_type: str = "linear"  # linear, percentile, threshold
    scale_params: dict = field(default_factory=dict)


@dataclass
class ScoringConfig:
    """Complete scoring configuration (versioned)"""
    version: str
    effective_date: date
    components: dict[ScoreComponent, ComponentConfig]
    penalty_per_month: float = 2.0  # Points deducted per consecutive underperf month
    penalty_cap: float = 20.0  # Max penalty
    
    @classmethod
    def default(cls) -> "ScoringConfig":
        return cls(
            version="1.0",
            effective_date=date(2024, 1, 1),
            components={
                ScoreComponent.BENCHMARK_OUTPERFORMANCE: ComponentConfig(
                    weight=0.30, max_points=30,
                    scale_type="alpha_threshold",
                    scale_params={"alpha_1y_thresholds": [[0.05, 30], [0.02, 20], [0.0, 10], [-0.02, 5], [-0.05, 0]]}
                ),
                ScoreComponent.CATEGORY_RANKING: ComponentConfig(
                    weight=0.20, max_points=20,
                    scale_type="percentile_linear",
                    scale_params={}
                ),
                ScoreComponent.CONSISTENCY_OF_RETURNS: ComponentConfig(
                    weight=0.20, max_points=20,
                    scale_type="positive_months_ratio",
                    scale_params={"lookback_months": 36}
                ),
                ScoreComponent.DRAWDOWN_CONTROL: ComponentConfig(
                    weight=0.15, max_points=15,
                    scale_type="inverse_threshold",
                    scale_params={"max_dd_thresholds": [[0.10, 15], [0.15, 10], [0.20, 5], [0.25, 0]]}
                ),
                ScoreComponent.VOLATILITY_ADJUSTED: ComponentConfig(
                    weight=0.15, max_points=15,
                    scale_type="inverse_threshold",
                    scale_params={"vol_thresholds": [[0.15, 15], [0.18, 10], [0.22, 5], [0.25, 0]]}
                ),
            },
            penalty_per_month=2.0,
            penalty_cap=20.0,
        )
    
    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "effective_date": self.effective_date.isoformat(),
            "components": {
                k.value: {
                    "weight": v.weight,
                    "max_points": v.max_points,
                    "scale_type": v.scale_type,
                    "scale_params": v.scale_params,
                } for k, v in self.components.items()
            },
            "penalty_per_month": self.penalty_per_month,
            "penalty_cap": self.penalty_cap,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ScoringConfig":
        components = {}
        for k, v in data["components"].items():
            components[ScoreComponent(k)] = ComponentConfig(**v)
        return cls(
            version=data["version"],
            effective_date=date.fromisoformat(data["effective_date"]),
            components=components,
            penalty_per_month=data.get("penalty_per_month", 2.0),
            penalty_cap=data.get("penalty_cap", 20.0),
        )
    
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def load(cls, path: str | Path) -> "ScoringConfig":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


@dataclass
class ScoreBreakdownItem:
    """Single component breakdown for explainability"""
    component: str
    points: float
    max_points: int
    reason: str
    raw_value: Optional[float] = None


@dataclass
class FundScore:
    """Complete fund health score with breakdown"""
    scheme_code: str
    as_of_date: date
    fund_health_score: int  # 0-100
    category_rank: Optional[int] = None
    category_percentile: Optional[float] = None
    breakdown: list[ScoreBreakdownItem] = field(default_factory=list)
    penalty: float = 0.0
    scoring_config_version: str = ""
    
    def to_dict(self) -> dict:
        return {
            "scheme_code": self.scheme_code,
            "as_of_date": self.as_of_date.isoformat(),
            "fund_health_score": self.fund_health_score,
            "category_rank": self.category_rank,
            "category_percentile": self.category_percentile,
            "breakdown": [
                {
                    "component": b.component,
                    "points": round(b.points, 1),
                    "max_points": b.max_points,
                    "reason": b.reason,
                    "raw_value": b.raw_value,
                } for b in self.breakdown
            ],
            "penalty": round(self.penalty, 1),
            "scoring_config_version": self.scoring_config_version,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class ScoringEngine:
    """
    Calculates 0-100 Fund Health Score with full explainability.
    Weights and thresholds live in ScoringConfig (versioned).
    """
    
    def __init__(self, config: ScoringConfig = None):
        self.config = config or ScoringConfig.default()
    
    def calculate(self, features: dict, scheme_code: str, as_of_date: date) -> FundScore:
        """
        Calculate fund health score for a scheme.
        
        Args:
            features: Dict from SchemeFeatures.to_dict()
            scheme_code: Scheme identifier
            as_of_date: Score date
            
        Returns:
            FundScore with breakdown
        """
        breakdown = []
        total_points = 0.0
        
        # 1. Benchmark Outperformance
        points, reason, raw = self._score_benchmark_outperformance(features)
        max_pts = self.config.components[ScoreComponent.BENCHMARK_OUTPERFORMANCE].max_points
        breakdown.append(ScoreBreakdownItem(
            component=ScoreComponent.BENCHMARK_OUTPERFORMANCE.value,
            points=points, max_points=max_pts, reason=reason, raw_value=raw
        ))
        total_points += points
        
        # 2. Category Ranking
        points, reason, raw = self._score_category_ranking(features)
        max_pts = self.config.components[ScoreComponent.CATEGORY_RANKING].max_points
        breakdown.append(ScoreBreakdownItem(
            component=ScoreComponent.CATEGORY_RANKING.value,
            points=points, max_points=max_pts, reason=reason, raw_value=raw
        ))
        total_points += points
        
        # 3. Consistency of Returns
        points, reason, raw = self._score_consistency(features)
        max_pts = self.config.components[ScoreComponent.CONSISTENCY_OF_RETURNS].max_points
        breakdown.append(ScoreBreakdownItem(
            component=ScoreComponent.CONSISTENCY_OF_RETURNS.value,
            points=points, max_points=max_pts, reason=reason, raw_value=raw
        ))
        total_points += points
        
        # 4. Drawdown Control
        points, reason, raw = self._score_drawdown_control(features)
        max_pts = self.config.components[ScoreComponent.DRAWDOWN_CONTROL].max_points
        breakdown.append(ScoreBreakdownItem(
            component=ScoreComponent.DRAWDOWN_CONTROL.value,
            points=points, max_points=max_pts, reason=reason, raw_value=raw
        ))
        total_points += points
        
        # 5. Volatility Adjusted
        points, reason, raw = self._score_volatility(features)
        max_pts = self.config.components[ScoreComponent.VOLATILITY_ADJUSTED].max_points
        breakdown.append(ScoreBreakdownItem(
            component=ScoreComponent.VOLATILITY_ADJUSTED.value,
            points=points, max_points=max_pts, reason=reason, raw_value=raw
        ))
        total_points += points
        
        # Penalty for consecutive underperformance
        penalty = self._calculate_penalty(features)
        
        # Final score
        final_score = max(0, min(100, round(total_points - penalty)))
        
        return FundScore(
            scheme_code=scheme_code,
            as_of_date=as_of_date,
            fund_health_score=final_score,
            category_rank=features.get("category_rank_1y"),
            category_percentile=features.get("category_percentile_1y"),
            breakdown=breakdown,
            penalty=penalty,
            scoring_config_version=self.config.version,
        )
    
    def calculate_batch(self, all_features: list[dict], as_of_date: date) -> list[FundScore]:
        """Calculate scores for multiple schemes"""
        return [self.calculate(f, f.get("scheme_code", ""), as_of_date) for f in all_features]
    
    def _score_benchmark_outperformance(self, features: dict) -> tuple[float, str, float]:
        """Score based on alpha vs benchmark"""
        alpha_1y = features.get("alpha_1y")
        alpha_3y = features.get("alpha_3y")
        
        if alpha_1y is None:
            return 0.0, "No 1Y alpha data", None
        
        # Use thresholds from config
        thresholds = self.config.components[ScoreComponent.BENCHMARK_OUTPERFORMANCE].scale_params.get(
            "alpha_1y_thresholds", [(0.05, 30), (0.02, 20), (0.0, 10), (-0.02, 5), (-0.05, 0)]
        )
        
        points = 0
        for threshold, pts in thresholds:
            if alpha_1y >= threshold:
                points = pts
                break
        
        if alpha_1y >= 0.05:
            reason = f"Beat benchmark by {alpha_1y:.1%} over 1Y"
        elif alpha_1y >= 0:
            reason = f"Matched benchmark ({alpha_1y:.1%} alpha over 1Y)"
        else:
            reason = f"Underperformed benchmark by {abs(alpha_1y):.1%} over 1Y"
        
        return points, reason, alpha_1y
    
    def _score_category_ranking(self, features: dict) -> tuple[float, str, float]:
        """Score based on category percentile rank"""
        percentile = features.get("category_percentile_1y")
        rank = features.get("category_rank_1y")
        
        if percentile is None:
            return 0.0, "No category ranking data", None
        
        # Linear: 100th percentile = 20 pts, 0th percentile = 0 pts
        points = (percentile / 100) * 20
        
        if rank:
            reason = f"Ranked #{rank} in category ({percentile:.0f}th percentile)"
        else:
            reason = f"{percentile:.0f}th percentile in category"
        
        return round(points, 1), reason, percentile
    
    def _score_consistency(self, features: dict) -> tuple[float, str, float]:
        """Score based on consistency of positive returns"""
        # Use consecutive underperformance streak (inverted)
        # Also consider alpha consistency if available
        streak = features.get("consecutive_underperf_months", 0)
        
        # Lower streak = better consistency
        # 0 months = 20 pts, 12+ months = 0 pts
        max_streak = self.config.components[ScoreComponent.CONSISTENCY_OF_RETURNS].scale_params.get(
            "lookback_months", 36
        )
        points = max(0, 20 * (1 - streak / max_streak))
        
        if streak == 0:
            reason = "No consecutive underperformance months"
        elif streak <= 3:
            reason = f"{streak} consecutive underperformance month(s)"
        else:
            reason = f"{streak} consecutive underperformance months (concerning)"
        
        return round(points, 1), reason, float(streak)
    
    def _score_drawdown_control(self, features: dict) -> tuple[float, str, float]:
        """Score based on max drawdown (lower is better)"""
        dd = features.get("max_drawdown_1y")
        
        if dd is None:
            return 0.0, "No drawdown data", None
        
        thresholds = self.config.components[ScoreComponent.DRAWDOWN_CONTROL].scale_params.get(
            "max_dd_thresholds", [(0.10, 15), (0.15, 10), (0.20, 5), (0.25, 0)]
        )
        
        points = 0
        for threshold, pts in thresholds:
            if dd <= threshold:
                points = pts
                break
        
        if dd <= 0.10:
            reason = f"Excellent drawdown control ({dd:.1%} max DD)"
        elif dd <= 0.15:
            reason = f"Good drawdown control ({dd:.1%} max DD)"
        elif dd <= 0.20:
            reason = f"Moderate drawdown ({dd:.1%} max DD)"
        elif dd <= 0.25:
            reason = f"High drawdown ({dd:.1%} max DD)"
        else:
            reason = f"Severe drawdown ({dd:.1%} max DD)"
        
        return points, reason, dd
    
    def _score_volatility(self, features: dict) -> tuple[float, str, float]:
        """Score based on volatility (lower is better, within reason)"""
        vol = features.get("volatility_1y")
        
        if vol is None:
            return 0.0, "No volatility data", None
        
        thresholds = self.config.components[ScoreComponent.VOLATILITY_ADJUSTED].scale_params.get(
            "vol_thresholds", [(0.15, 15), (0.18, 10), (0.22, 5), (0.25, 0)]
        )
        
        points = 0
        for threshold, pts in thresholds:
            if vol <= threshold:
                points = pts
                break
        
        if vol <= 0.15:
            reason = f"Low volatility ({vol:.1%} annualized)"
        elif vol <= 0.18:
            reason = f"Moderate volatility ({vol:.1%} annualized)"
        elif vol <= 0.22:
            reason = f"Elevated volatility ({vol:.1%} annualized)"
        elif vol <= 0.25:
            reason = f"High volatility ({vol:.1%} annualized)"
        else:
            reason = f"Very high volatility ({vol:.1%} annualized)"
        
        return points, reason, vol
    
    def _calculate_penalty(self, features: dict) -> float:
        """Calculate penalty for persistent underperformance"""
        streak = features.get("consecutive_underperf_months", 0)
        penalty = streak * self.config.penalty_per_month
        return min(penalty, self.config.penalty_cap)


def create_default_scoring_engine() -> ScoringEngine:
    return ScoringEngine(ScoringConfig.default())