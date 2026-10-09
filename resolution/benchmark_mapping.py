"""
Benchmark Mapping Service
Two-tier resolution:
1. Explicit mapping table — AMC-declared benchmark per scheme (from factsheets/SID)
2. Category fallback rule — default benchmark by SEBI category
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import json
from pathlib import Path


class BenchmarkCode(str, Enum):
    """Standard benchmark index codes"""
    NIFTY_100_TRI = "NIFTY100_TRI"
    NIFTY_LARGEMIDCAP_250_TRI = "NIFTY_LARGEMIDCAP250_TRI"
    NIFTY_500_TRI = "NIFTY500_TRI"
    NIFTY_MIDCAP_150_TRI = "NIFTY_MIDCAP150_TRI"
    NIFTY_SMALLCAP_250_TRI = "NIFTY_SMALLCAP250_TRI"
    CRISIL_HYBRID_35_65 = "CRISIL_HYBRID_35_65"
    CRISIL_SHORT_TERM_BOND = "CRISIL_SHORT_TERM_BOND"
    NIFTY_50_TRI = "NIFTY50_TRI"
    SP_500_TRI = "SP500_TRI"
    NIFTY_INDIA_CONSUMPTION_TRI = "NIFTY_INDIA_CONSUMPTION_TRI"
    NIFTY_INFRASTRUCTURE_TRI = "NIFTY_INFRASTRUCTURE_TRI"
    NIFTY_PHARMA_TRI = "NIFTY_PHARMA_TRI"
    NIFTY_BANK_TRI = "NIFTY_BANK_TRI"
    NIFTY_IT_TRI = "NIFTY_IT_TRI"


@dataclass(frozen=True)
class CategoryFallback:
    """Category → default benchmark mapping"""
    category: str
    benchmark: BenchmarkCode
    benchmark_name: str


# Tier 2: Category Fallback Rules (from architecture doc Section 4)
CATEGORY_FALLBACKS: list[CategoryFallback] = [
    CategoryFallback("Large Cap", BenchmarkCode.NIFTY_100_TRI, "Nifty 100 TRI"),
    CategoryFallback("Large & Mid Cap", BenchmarkCode.NIFTY_LARGEMIDCAP_250_TRI, "Nifty LargeMidcap 250 TRI"),
    CategoryFallback("Flexi Cap", BenchmarkCode.NIFTY_500_TRI, "Nifty 500 TRI"),
    CategoryFallback("Multi Cap", BenchmarkCode.NIFTY_500_TRI, "Nifty 500 TRI"),
    CategoryFallback("Mid Cap", BenchmarkCode.NIFTY_MIDCAP_150_TRI, "Nifty Midcap 150 TRI"),
    CategoryFallback("Small Cap", BenchmarkCode.NIFTY_SMALLCAP_250_TRI, "Nifty Smallcap 250 TRI"),
    CategoryFallback("ELSS", BenchmarkCode.NIFTY_500_TRI, "Nifty 500 TRI"),
    CategoryFallback("Sectoral - Consumption", BenchmarkCode.NIFTY_INDIA_CONSUMPTION_TRI, "Nifty India Consumption TRI"),
    CategoryFallback("Sectoral - Infrastructure", BenchmarkCode.NIFTY_INFRASTRUCTURE_TRI, "Nifty Infrastructure TRI"),
    CategoryFallback("Sectoral - Pharma", BenchmarkCode.NIFTY_PHARMA_TRI, "Nifty Pharma TRI"),
    CategoryFallback("Sectoral - Banking", BenchmarkCode.NIFTY_BANK_TRI, "Nifty Bank TRI"),
    CategoryFallback("Sectoral - IT", BenchmarkCode.NIFTY_IT_TRI, "Nifty IT TRI"),
    CategoryFallback("Thematic", BenchmarkCode.NIFTY_500_TRI, "Nifty 500 TRI"),
    CategoryFallback("Hybrid Aggressive", BenchmarkCode.CRISIL_HYBRID_35_65, "CRISIL Hybrid 35+65"),
    CategoryFallback("Hybrid Conservative", BenchmarkCode.CRISIL_SHORT_TERM_BOND, "CRISIL Short Term Bond Index"),
    CategoryFallback("Debt - Ultra Short Duration", BenchmarkCode.CRISIL_SHORT_TERM_BOND, "CRISIL Short Term Bond Index"),
    CategoryFallback("Debt - Short Duration", BenchmarkCode.CRISIL_SHORT_TERM_BOND, "CRISIL Short Term Bond Index"),
    CategoryFallback("Debt - Medium Duration", BenchmarkCode.CRISIL_SHORT_TERM_BOND, "CRISIL Short Term Bond Index"),
    CategoryFallback("International - US", BenchmarkCode.SP_500_TRI, "S&P 500 TRI"),
    CategoryFallback("International - Global", BenchmarkCode.NIFTY_500_TRI, "Nifty 500 TRI"),
]


@dataclass
class BenchmarkMapping:
    """Resolved benchmark for a scheme"""
    scheme_code: str
    scheme_name: str
    category: str
    benchmark_code: BenchmarkCode
    benchmark_name: str
    source: str  # "explicit" | "fallback"
    confidence: float  # 1.0 for explicit, 0.7 for fallback


class BenchmarkResolver:
    """
    Resolves scheme_code → benchmark_index using two-tier strategy:
    1. Explicit mapping (authoritative, from AMC factsheets/SID)
    2. Category fallback (rule-based dictionary)
    """
    
    def __init__(
        self,
        explicit_mappings: Optional[dict[str, BenchmarkCode]] = None,
        explicit_mapping_path: Optional[str | Path] = None,
    ):
        """
        Args:
            explicit_mappings: Dict of scheme_code → BenchmarkCode (loaded from DB/config)
            explicit_mapping_path: Path to JSON file with explicit mappings
        """
        self._explicit: dict[str, BenchmarkCode] = {}
        
        if explicit_mappings:
            self._explicit.update(explicit_mappings)
        
        if explicit_mapping_path:
            self.load_explicit_mappings(explicit_mapping_path)
        
        # Build category → fallback lookup (normalized keys)
        self._fallback_by_category: dict[str, CategoryFallback] = {}
        for fb in CATEGORY_FALLBACKS:
            key = self._normalize_category(fb.category)
            self._fallback_by_category[key] = fb
    
    def load_explicit_mappings(self, path: str | Path) -> int:
        """Load explicit mappings from JSON file. Returns count loaded."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Explicit mapping file not found: {path}")
        
        with open(path) as f:
            data = json.load(f)
        
        count = 0
        for scheme_code, benchmark_str in data.items():
            try:
                benchmark_code = BenchmarkCode(benchmark_str)
                self._explicit[scheme_code] = benchmark_code
                count += 1
            except ValueError:
                # Log warning in production
                pass
        return count
    
    def add_explicit_mapping(self, scheme_code: str, benchmark: BenchmarkCode) -> None:
        """Add or update an explicit mapping (e.g., from new factsheet ingestion)"""
        self._explicit[scheme_code] = benchmark
    
    def resolve(self, scheme_code: str, scheme_name: str, category: str) -> BenchmarkMapping:
        """
        Resolve benchmark for a scheme.
        
        Args:
            scheme_code: AMFI scheme code / ISIN
            scheme_name: Scheme name (for logging/debugging)
            category: SEBI category (e.g., "Large Cap", "Flexi Cap")
            
        Returns:
            BenchmarkMapping with benchmark_code, benchmark_name, source, confidence
        """
        # Tier 1: Explicit mapping
        if scheme_code in self._explicit:
            bm = self._explicit[scheme_code]
            return BenchmarkMapping(
                scheme_code=scheme_code,
                scheme_name=scheme_name,
                category=category,
                benchmark_code=bm,
                benchmark_name=bm.value,
                source="explicit",
                confidence=1.0,
            )
        
        # Tier 2: Category fallback
        normalized = self._normalize_category(category)
        fallback = self._fallback_by_category.get(normalized)
        
        if fallback:
            return BenchmarkMapping(
                scheme_code=scheme_code,
                scheme_name=scheme_name,
                category=category,
                benchmark_code=fallback.benchmark,
                benchmark_name=fallback.benchmark_name,
                source="fallback",
                confidence=0.7,
            )
        
        # No mapping found — return default with low confidence
        return BenchmarkMapping(
            scheme_code=scheme_code,
            scheme_name=scheme_name,
            category=category,
            benchmark_code=BenchmarkCode.NIFTY_500_TRI,
            benchmark_name="Nifty 500 TRI (default)",
            source="default",
            confidence=0.3,
        )
    
    def resolve_batch(
        self, 
        schemes: list[dict[str, str]]  # [{"scheme_code", "scheme_name", "category"}, ...]
    ) -> list[BenchmarkMapping]:
        """Resolve benchmarks for multiple schemes at once"""
        return [self.resolve(s["scheme_code"], s["scheme_name"], s["category"]) for s in schemes]
    
    def get_unmapped_schemes(self, schemes: list[dict[str, str]]) -> list[dict[str, str]]:
        """Return schemes that would fall back to default (no explicit, no category match)"""
        unmapped = []
        for s in schemes:
            result = self.resolve(s["scheme_code"], s["scheme_name"], s["category"])
            if result.source == "default":
                unmapped.append(s)
        return unmapped
    
    @staticmethod
    def _normalize_category(category: str) -> str:
        """Normalize category string for lookup"""
        return category.strip().lower().replace("&", "and").replace("-", " ").replace("/", " ")
    
    def export_explicit_mappings(self, path: str | Path) -> None:
        """Export current explicit mappings to JSON file"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.value for k, v in self._explicit.items()}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    @property
    def explicit_count(self) -> int:
        return len(self._explicit)
    
    @property
    def fallback_categories(self) -> list[str]:
        return list(self._fallback_by_category.keys())