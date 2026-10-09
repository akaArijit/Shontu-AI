"""
Feature Engineering Pipeline
Nightly batch: Rolling returns, Alpha, Drawdown, Volatility, Category Percentile
Compute once per unique scheme (~400), not per folio (~5000)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from enum import Enum
import numpy as np
import pandas as pd
from pathlib import Path
import json


class ReturnPeriod(str, Enum):
    """Standard return periods"""
    M1 = "1m"
    M3 = "3m"
    M6 = "6m"
    Y1 = "1y"
    Y3 = "3y"
    Y5 = "5y"


@dataclass
class RollingReturns:
    """Rolling returns for a scheme at a point in time"""
    scheme_code: str
    as_of_date: date
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_1y: Optional[float] = None
    return_3y: Optional[float] = None
    return_5y: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "scheme_code": self.scheme_code,
            "as_of_date": self.as_of_date.isoformat(),
            "return_1m": self.return_1m,
            "return_3m": self.return_3m,
            "return_6m": self.return_6m,
            "return_1y": self.return_1y,
            "return_3y": self.return_3y,
            "return_5y": self.return_5y,
        }


@dataclass
class SchemeFeatures:
    """Complete feature set for a scheme"""
    scheme_code: str
    as_of_date: date
    
    # Returns
    rolling_returns: Optional[RollingReturns] = None
    
    # Risk metrics
    alpha_1m: Optional[float] = None
    alpha_3m: Optional[float] = None
    alpha_6m: Optional[float] = None
    alpha_1y: Optional[float] = None
    alpha_3y: Optional[float] = None
    alpha_5y: Optional[float] = None
    
    max_drawdown_1y: Optional[float] = None
    max_drawdown_3y: Optional[float] = None
    
    volatility_1m: Optional[float] = None
    volatility_3m: Optional[float] = None
    volatility_1y: Optional[float] = None
    volatility_3y: Optional[float] = None
    
    # Category-relative
    category_percentile_1m: Optional[float] = None
    category_percentile_3m: Optional[float] = None
    category_percentile_1y: Optional[float] = None
    category_percentile_3y: Optional[float] = None
    
    category_rank_1m: Optional[int] = None
    category_rank_3m: Optional[int] = None
    category_rank_1y: Optional[int] = None
    category_rank_3y: Optional[int] = None
    
    # Streaks
    consecutive_underperf_months: int = 0
    consecutive_underperf_quarters: int = 0
    
    # Correlation
    correlation_to_benchmark_1y: Optional[float] = None
    correlation_to_benchmark_3y: Optional[float] = None
    
    def to_dict(self) -> dict:
        result = {
            "scheme_code": self.scheme_code,
            "as_of_date": self.as_of_date.isoformat(),
        }
        for key, value in self.__dict__.items():
            if key not in ("scheme_code", "as_of_date", "rolling_returns"):
                result[key] = value
        if self.rolling_returns:
            result.update(self.rolling_returns.to_dict())
        return result


class ReturnCalculator:
    """
    Calculate returns using appropriate method:
    - Simple return for periods < 1 year
    - CAGR for periods >= 1 year
    """
    
    @staticmethod
    def simple_return(start_nav: float, end_nav: float) -> float:
        """Simple return: (end - start) / start"""
        if start_nav <= 0:
            return None
        return (end_nav - start_nav) / start_nav
    
    @staticmethod
    def cagr(start_nav: float, end_nav: float, years: float) -> float:
        """Compound Annual Growth Rate"""
        if start_nav <= 0 or end_nav <= 0 or years <= 0:
            return None
        return (end_nav / start_nav) ** (1 / years) - 1
    
    @classmethod
    def calculate_return(cls, start_nav: float, end_nav: float, days: int) -> float:
        """Auto-select method based on period"""
        if days < 365:
            return cls.simple_return(start_nav, end_nav)
        else:
            years = days / 365.25
            return cls.cagr(start_nav, end_nav, years)


class RollingReturnsCalculator:
    """
    Calculate rolling returns for all standard periods.
    Uses business-day aligned windows (not calendar days).
    """
    
    # Period definitions in trading days (approx)
    PERIOD_DAYS = {
        ReturnPeriod.M1: 21,
        ReturnPeriod.M3: 63,
        ReturnPeriod.M6: 126,
        ReturnPeriod.Y1: 252,
        ReturnPeriod.Y3: 756,
        ReturnPeriod.Y5: 1260,
    }
    
    def __init__(self, nav_series: pd.Series):
        """
        Args:
            nav_series: pd.Series with DatetimeIndex, values = NAV
        """
        self.nav = nav_series.sort_index()
    
    def calculate_all(self, as_of_date: date) -> RollingReturns:
        """Calculate all rolling returns as of a date"""
        as_of_ts = pd.Timestamp(as_of_date)
        
        # Get NAV as of date (or latest before)
        nav_as_of = self._get_nav_as_of(as_of_ts)
        if nav_as_of is None:
            return RollingReturns(scheme_code="", as_of_date=as_of_date)
        
        returns = {}
        for period, days in self.PERIOD_DAYS.items():
            start_date = as_of_ts - pd.Timedelta(days=days)
            nav_start = self._get_nav_as_of(start_date)
            
            if nav_start is not None:
                returns[period.value] = ReturnCalculator.calculate_return(
                    nav_start, nav_as_of, days
                )
            else:
                returns[period.value] = None
        
        return RollingReturns(
            scheme_code="",  # Set by caller
            as_of_date=as_of_date,
            return_1m=returns.get("1m"),
            return_3m=returns.get("3m"),
            return_6m=returns.get("6m"),
            return_1y=returns.get("1y"),
            return_3y=returns.get("3y"),
            return_5y=returns.get("5y"),
        )
    
    def _get_nav_as_of(self, target_date: pd.Timestamp) -> Optional[float]:
        """Get NAV on or before target date"""
        # Find last available NAV on or before target_date
        mask = self.nav.index <= target_date
        if not mask.any():
            return None
        return self.nav[mask].iloc[-1]


class AlphaCalculator:
    """Calculate alpha (fund return - benchmark return)"""
    
    @staticmethod
    def calculate(fund_return: float, benchmark_return: float) -> float:
        """Alpha = fund return - benchmark return"""
        if fund_return is None or benchmark_return is None:
            return None
        return round(fund_return - benchmark_return, 6)
    
    @classmethod
    def calculate_all_periods(cls, fund_returns: RollingReturns, 
                               benchmark_returns: RollingReturns) -> dict:
        """Calculate alpha for all matching periods"""
        alphas = {}
        for period in ReturnPeriod:
            fund_ret = getattr(fund_returns, f"return_{period.value}")
            bench_ret = getattr(benchmark_returns, f"return_{period.value}")
            alphas[f"alpha_{period.value}"] = cls.calculate(fund_ret, bench_ret)
        return alphas


class DrawdownCalculator:
    """Calculate maximum drawdown over rolling windows"""
    
    @staticmethod
    def max_drawdown(nav_series: pd.Series) -> float:
        """
        Maximum peak-to-trough decline.
        Returns as positive percentage (e.g., 0.15 = 15% drawdown)
        """
        if len(nav_series) < 2:
            return None
        
        # Running maximum (peak)
        running_max = nav_series.expanding().max()
        # Drawdown from peak
        drawdown = (nav_series - running_max) / running_max
        # Maximum drawdown (most negative)
        max_dd = drawdown.min()
        
        return abs(max_dd) if max_dd is not None else None
    
    @classmethod
    def rolling_max_drawdown(cls, nav_series: pd.Series, window_days: int) -> float:
        """Max drawdown over trailing window"""
        if len(nav_series) < window_days:
            # Use all available data
            return cls.max_drawdown(nav_series)
        
        window_data = nav_series.tail(window_days)
        return cls.max_drawdown(window_data)


class VolatilityCalculator:
    """Calculate rolling volatility (annualized standard deviation of returns)"""
    
    TRADING_DAYS_PER_YEAR = 252
    
    @staticmethod
    def daily_returns(nav_series: pd.Series) -> pd.Series:
        """Calculate daily returns"""
        return nav_series.pct_change().dropna()
    
    @classmethod
    def annualized_volatility(cls, nav_series: pd.Series, window_days: int) -> float:
        """Annualized volatility over trailing window"""
        returns = cls.daily_returns(nav_series)
        
        if len(returns) < window_days:
            # Use all available
            window_returns = returns
        else:
            window_returns = returns.tail(window_days)
        
        if len(window_returns) < 2:
            return None
        
        daily_vol = window_returns.std()
        annual_vol = daily_vol * np.sqrt(cls.TRADING_DAYS_PER_YEAR)
        
        return float(annual_vol) if not np.isnan(annual_vol) else None
    
    @classmethod
    def calculate_all_periods(cls, nav_series: pd.Series) -> dict:
        """Calculate volatility for standard periods"""
        periods = {
            "volatility_1m": 21,
            "volatility_3m": 63,
            "volatility_1y": 252,
            "volatility_3y": 756,
        }
        
        result = {}
        for key, days in periods.items():
            result[key] = cls.annualized_volatility(nav_series, days)
        
        return result


class PercentileRankCalculator:
    """Calculate category-relative percentile ranks"""
    
    @staticmethod
    def percentile_rank(value: float, peer_values: list[float]) -> float:
        """
        Percentile rank: percentage of peers with lower value.
        0 = worst, 100 = best
        """
        if value is None or not peer_values:
            return None
        
        peer_values = [v for v in peer_values if v is not None]
        if not peer_values:
            return None
        
        # Count peers with lower return
        lower_count = sum(1 for v in peer_values if v < value)
        return (lower_count / len(peer_values)) * 100
    
    @staticmethod
    def rank(value: float, peer_values: list[float], ascending: bool = False) -> int:
        """
        Rank within category (1 = best by default).
        ascending=False means higher return = better rank
        """
        if value is None or not peer_values:
            return None
        
        peer_values = [v for v in peer_values if v is not None]
        if not peer_values:
            return None
        
        # Add the value to peer list and sort
        all_values = peer_values + [value]
        sorted_values = sorted(all_values, reverse=not ascending)
        
        # Rank is 1-based index - find the rank of our specific value
        # (if duplicate values exist, find the first occurrence in sorted list)
        for i, v in enumerate(sorted_values):
            if abs(v - value) < 1e-9:
                return i + 1
        return len(sorted_values)
    
    @classmethod
    def calculate_category_ranks(cls, 
                                  scheme_returns: dict[str, float],
                                  category_scheme_codes: list[str]) -> dict[str, dict]:
        """
        Calculate percentile and rank for each scheme in category.
        
        Args:
            scheme_returns: {scheme_code: return_value}
            category_scheme_codes: list of scheme codes in same category
            
        Returns:
            {scheme_code: {"percentile": float, "rank": int}}
        """
        # Get peer returns (excluding self for percentile calc)
        peer_returns = {k: v for k, v in scheme_returns.items() 
                       if k in category_scheme_codes}
        
        results = {}
        for scheme_code in category_scheme_codes:
            value = scheme_returns.get(scheme_code)
            peer_values = [v for k, v in peer_returns.items() if k != scheme_code]
            
            results[scheme_code] = {
                "percentile": cls.percentile_rank(value, peer_values),
                "rank": cls.rank(value, peer_values, ascending=False),
            }
        
        return results


class ConsecutiveUnderperformanceCalculator:
    """Track consecutive periods of underperformance"""
    
    @staticmethod
    def calculate_monthly_streak(fund_returns: pd.Series, 
                                  benchmark_returns: pd.Series) -> int:
        """
        Count consecutive months where fund return < benchmark return.
        Both series should be monthly returns aligned by date (oldest first).
        """
        if len(fund_returns) != len(benchmark_returns) or len(fund_returns) == 0:
            return 0
        
        streak = 0
        # Iterate from most recent to oldest
        for f_ret, b_ret in zip(reversed(fund_returns), reversed(benchmark_returns)):
            if f_ret < b_ret:
                streak += 1
            else:
                break
        
        return streak
    
    @staticmethod
    def calculate_from_alphas(alphas: dict[str, float]) -> int:
        """
        Calculate streak from pre-computed alphas.
        Assumes keys are ordered chronologically (oldest first).
        """
        streak = 0
        for period in ["1m", "3m", "6m", "1y", "3y", "5y"]:
            key = f"alpha_{period}"
            if key in alphas and alphas[key] is not None:
                if alphas[key] < 0:
                    streak += 1
                else:
                    break
            else:
                break
        return streak


class CorrelationCalculator:
    """Calculate rolling correlation to benchmark"""
    
    @staticmethod
    def rolling_correlation(fund_nav: pd.Series, benchmark_nav: pd.Series, 
                            window_days: int) -> float:
        """Rolling correlation of daily returns"""
        fund_rets = fund_nav.pct_change().dropna()
        bench_rets = benchmark_nav.pct_change().dropna()
        
        # Align indices
        common_idx = fund_rets.index.intersection(bench_rets.index)
        if len(common_idx) < window_days:
            return None
        
        fund_aligned = fund_rets.loc[common_idx].tail(window_days)
        bench_aligned = bench_rets.loc[common_idx].tail(window_days)
        
        if len(fund_aligned) < 10:
            return None
        
        # Check for constant series (zero variance)
        if fund_aligned.std() == 0 or bench_aligned.std() == 0:
            return None
        
        corr = fund_aligned.corr(bench_aligned)
        return float(corr) if not np.isnan(corr) else None


class FeatureEngineeringPipeline:
    """
    Main pipeline: computes all features for all schemes nightly.
    Input: nav_history (scheme_code, nav_date, nav_value) + benchmark_history
    Output: fund_rolling_returns, fund_features
    """
    
    def __init__(self):
        self.scheme_navs: dict[str, pd.Series] = {}
        self.benchmark_navs: dict[str, pd.Series] = {}
        self.scheme_categories: dict[str, str] = {}
    
    def load_nav_history(self, nav_records: list[dict]) -> None:
        """
        Load NAV history from database records.
        
        Args:
            nav_records: [{"scheme_code", "nav_date", "nav_value"}, ...]
        """
        df = pd.DataFrame(nav_records)
        if df.empty:
            return
        
        df["nav_date"] = pd.to_datetime(df["nav_date"])
        
        for scheme_code, group in df.groupby("scheme_code"):
            series = group.set_index("nav_date")["nav_value"].sort_index()
            self.scheme_navs[scheme_code] = series
    
    def load_benchmark_history(self, benchmark_records: list[dict]) -> None:
        """Load benchmark index history"""
        df = pd.DataFrame(benchmark_records)
        if df.empty:
            return
        
        df["index_date"] = pd.to_datetime(df["index_date"])
        
        for bench_code, group in df.groupby("benchmark_code"):
            series = group.set_index("index_date")["index_value"].sort_index()
            self.benchmark_navs[bench_code] = series
    
    def load_scheme_categories(self, scheme_categories: dict[str, str]) -> None:
        """Load scheme_code -> category mapping"""
        self.scheme_categories = scheme_categories
    
    def compute_all_features(self, as_of_date: date) -> list[SchemeFeatures]:
        """Compute features for all schemes as of a date"""
        all_features = []
        
        # Group schemes by category for percentile calculation
        category_to_schemes = {}
        for scheme_code, category in self.scheme_categories.items():
            if scheme_code in self.scheme_navs:
                category_to_schemes.setdefault(category, []).append(scheme_code)
        
        for scheme_code, nav_series in self.scheme_navs.items():
            try:
                features = self._compute_scheme_features(
                    scheme_code, nav_series, as_of_date, category_to_schemes
                )
                all_features.append(features)
            except Exception as e:
                # Log error in production, continue with other schemes
                print(f"Error computing features for {scheme_code}: {e}")
                continue
        
        return all_features
    
    def _compute_scheme_features(self, scheme_code: str, nav_series: pd.Series,
                                  as_of_date: date, category_to_schemes: dict) -> SchemeFeatures:
        """Compute all features for a single scheme"""
        
        # 1. Rolling returns
        returns_calc = RollingReturnsCalculator(nav_series)
        rolling_returns = returns_calc.calculate_all(as_of_date)
        rolling_returns.scheme_code = scheme_code
        
        # 2. Benchmark returns (if available)
        category = self.scheme_categories.get(scheme_code)
        benchmark_code = self._get_benchmark_for_category(category)
        benchmark_series = self.benchmark_navs.get(benchmark_code)
        
        benchmark_returns = None
        if benchmark_series is not None:
            bench_calc = RollingReturnsCalculator(benchmark_series)
            benchmark_returns = bench_calc.calculate_all(as_of_date)
        
        # 3. Alpha
        alphas = {}
        if benchmark_returns:
            alphas = AlphaCalculator.calculate_all_periods(rolling_returns, benchmark_returns)
        
        # 4. Drawdown
        drawdown_1y = DrawdownCalculator.rolling_max_drawdown(nav_series, 252)
        drawdown_3y = DrawdownCalculator.rolling_max_drawdown(nav_series, 756)
        
        # 5. Volatility
        volatility = VolatilityCalculator.calculate_all_periods(nav_series)
        
        # 6. Category percentile & rank
        category_schemes = category_to_schemes.get(category, [])
        percentiles = {}
        ranks = {}
        
        for period in ReturnPeriod:
            # Collect returns for all schemes in category
            period_returns = {}
            for sc in category_schemes:
                if sc in self.scheme_navs:
                    r_calc = RollingReturnsCalculator(self.scheme_navs[sc])
                    r = r_calc.calculate_all(as_of_date)
                    period_returns[sc] = getattr(r, f"return_{period.value}")
            
            cat_results = PercentileRankCalculator.calculate_category_ranks(
                period_returns, category_schemes
            )
            
            if scheme_code in cat_results:
                percentiles[f"category_percentile_{period.value}"] = cat_results[scheme_code]["percentile"]
                ranks[f"category_rank_{period.value}"] = cat_results[scheme_code]["rank"]
        
        # 7. Consecutive underperformance
        consec_months = 0
        if benchmark_returns:
            consec_months = ConsecutiveUnderperformanceCalculator.calculate_from_alphas(alphas)
        
        # 8. Correlation to benchmark
        corr_1y = None
        corr_3y = None
        if benchmark_series is not None:
            corr_1y = CorrelationCalculator.rolling_correlation(nav_series, benchmark_series, 252)
            corr_3y = CorrelationCalculator.rolling_correlation(nav_series, benchmark_series, 756)
        
        # Build features object
        features = SchemeFeatures(
            scheme_code=scheme_code,
            as_of_date=as_of_date,
            rolling_returns=rolling_returns,
            alpha_1m=alphas.get("alpha_1m"),
            alpha_3m=alphas.get("alpha_3m"),
            alpha_6m=alphas.get("alpha_6m"),
            alpha_1y=alphas.get("alpha_1y"),
            alpha_3y=alphas.get("alpha_3y"),
            alpha_5y=alphas.get("alpha_5y"),
            max_drawdown_1y=drawdown_1y,
            max_drawdown_3y=drawdown_3y,
            volatility_1m=volatility.get("volatility_1m"),
            volatility_3m=volatility.get("volatility_3m"),
            volatility_1y=volatility.get("volatility_1y"),
            volatility_3y=volatility.get("volatility_3y"),
            category_percentile_1m=percentiles.get("category_percentile_1m"),
            category_percentile_3m=percentiles.get("category_percentile_3m"),
            category_percentile_1y=percentiles.get("category_percentile_1y"),
            category_percentile_3y=percentiles.get("category_percentile_3y"),
            category_rank_1m=ranks.get("category_rank_1m"),
            category_rank_3m=ranks.get("category_rank_3m"),
            category_rank_1y=ranks.get("category_rank_1y"),
            category_rank_3y=ranks.get("category_rank_3y"),
            consecutive_underperf_months=consec_months,
            correlation_to_benchmark_1y=corr_1y,
            correlation_to_benchmark_3y=corr_3y,
        )
        
        return features
    
    def _get_benchmark_for_category(self, category: str) -> str:
        """Map category to benchmark code (simplified)"""
        mapping = {
            "Large Cap": "NIFTY100_TRI",
            "Large & Mid Cap": "NIFTY_LARGEMIDCAP250_TRI",
            "Flexi Cap": "NIFTY500_TRI",
            "Multi Cap": "NIFTY500_TRI",
            "Mid Cap": "NIFTY_MIDCAP150_TRI",
            "Small Cap": "NIFTY_SMALLCAP250_TRI",
            "ELSS": "NIFTY500_TRI",
            "Hybrid Aggressive": "CRISIL_HYBRID_35_65",
            "Debt - Ultra Short Duration": "CRISIL_SHORT_TERM_BOND",
            "Debt - Short Duration": "CRISIL_SHORT_TERM_BOND",
            "International - US": "SP500_TRI",
        }
        return mapping.get(category, "NIFTY500_TRI")
    
    def export_features(self, features: list[SchemeFeatures], path: str | Path) -> None:
        """Export features to JSON for debugging/loading"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [f.to_dict() for f in features]
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)


# Convenience function for testing
def create_sample_nav_series(start_date: date, days: int, 
                             start_nav: float = 100, 
                             daily_return: float = 0.0005) -> pd.Series:
    """Create a sample NAV series for testing"""
    dates = pd.date_range(start=start_date, periods=days, freq="B")  # Business days
    navs = [start_nav]
    for _ in range(1, days):
        navs.append(navs[-1] * (1 + daily_return + np.random.normal(0, 0.01)))
    return pd.Series(navs, index=dates)