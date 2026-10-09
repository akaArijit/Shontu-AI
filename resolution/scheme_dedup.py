"""
Scheme Deduplication & Master Registry
Core architectural principle: 5000 folios → ~400 unique schemes
Every folio becomes a foreign key lookup against pre-computed scheme data.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date
from enum import Enum
import re
from pathlib import Path
import json


class SchemeCategory(str, Enum):
    """SEBI mutual fund categories"""
    LARGE_CAP = "Large Cap"
    LARGE_AND_MID_CAP = "Large & Mid Cap"
    FLEXI_CAP = "Flexi Cap"
    MULTI_CAP = "Multi Cap"
    MID_CAP = "Mid Cap"
    SMALL_CAP = "Small Cap"
    ELSS = "ELSS"
    SECTORAL_CONSUMPTION = "Sectoral - Consumption"
    SECTORAL_INFRASTRUCTURE = "Sectoral - Infrastructure"
    SECTORAL_PHARMA = "Sectoral - Pharma"
    SECTORAL_BANKING = "Sectoral - Banking"
    SECTORAL_IT = "Sectoral - IT"
    THEMATIC = "Thematic"
    HYBRID_AGGRESSIVE = "Hybrid Aggressive"
    HYBRID_CONSERVATIVE = "Hybrid Conservative"
    DEBT_ULTRA_SHORT = "Debt - Ultra Short Duration"
    DEBT_SHORT = "Debt - Short Duration"
    DEBT_MEDIUM = "Debt - Medium Duration"
    INTERNATIONAL_US = "International - US"
    INTERNATIONAL_GLOBAL = "International - Global"


@dataclass(frozen=True)
class SchemeMaster:
    """Deduplicated scheme registry entry (one per unique scheme)"""
    scheme_code: str          # AMFI code / ISIN - PRIMARY KEY
    scheme_name: str
    amc: str
    category: SchemeCategory
    sub_category: Optional[str] = None
    benchmark_index: Optional[str] = None  # FK to benchmark_master
    fund_manager: Optional[str] = None
    expense_ratio: Optional[float] = None
    aum: Optional[float] = None           # in crores
    inception_date: Optional[date] = None
    last_updated: Optional[date] = None
    is_active: bool = True
    # Deduplication metadata
    source_folio_codes: list[str] = field(default_factory=list)  # folio codes that map to this scheme
    dedup_confidence: float = 1.0        # 1.0 = exact match, <1.0 = fuzzy matched


@dataclass
class FolioMapping:
    """Client folio → scheme_code mapping (thin, no duplicated computation)"""
    folio_id: str
    client_id: str
    scheme_code: str          # FK to scheme_master
    units: float
    invested_value: float
    current_value: float
    purchase_date: Optional[date] = None


class SchemeDeduplicator:
    """
    Resolves 5000+ folios to ~400 unique schemes.
    
    Strategy:
    1. Exact match on scheme_code (AMFI/ISIN) - highest confidence
    2. Fuzzy match on scheme_name + AMC - for data entry variations
    3. Category + AMC heuristic - for completely unknown codes
    """
    
    def __init__(self):
        self._master: dict[str, SchemeMaster] = {}           # scheme_code → SchemeMaster
        self._name_amc_index: dict[str, str] = {}            # normalized_name|amc → scheme_code
        self._folio_to_scheme: dict[str, str] = {}           # folio_id → scheme_code
    
    def register_scheme(self, scheme: SchemeMaster) -> str:
        """Register a scheme in the master registry. Returns scheme_code."""
        self._master[scheme.scheme_code] = scheme
        # Build fuzzy lookup index
        key = self._normalize_name_amc(scheme.scheme_name, scheme.amc)
        self._name_amc_index[key] = scheme.scheme_code
        return scheme.scheme_code
    
    def register_schemes_bulk(self, schemes: list[SchemeMaster]) -> int:
        """Bulk register schemes. Returns count registered."""
        for s in schemes:
            self.register_scheme(s)
        return len(schemes)
    
    def resolve_folio_scheme(
        self,
        folio_id: str,
        folio_scheme_code: Optional[str],
        folio_scheme_name: str,
        folio_amc: str,
        folio_category: Optional[str] = None,
    ) -> tuple[str, float, str]:
        """
        Resolve a folio's scheme to a master scheme_code.
        
        Returns: (scheme_code, confidence, method)
        method: "exact_code" | "fuzzy_name_amc" | "category_amc_heuristic" | "new_scheme"
        """
        # 1. Exact scheme_code match (AMFI/ISIN)
        if folio_scheme_code and folio_scheme_code in self._master:
            self._folio_to_scheme[folio_id] = folio_scheme_code
            self._master[folio_scheme_code].source_folio_codes.append(folio_id)
            return folio_scheme_code, 1.0, "exact_code"
        
        # 2. Fuzzy match on normalized name + AMC
        key = self._normalize_name_amc(folio_scheme_name, folio_amc)
        if key in self._name_amc_index:
            scheme_code = self._name_amc_index[key]
            self._folio_to_scheme[folio_id] = scheme_code
            self._master[scheme_code].source_folio_codes.append(folio_id)
            return scheme_code, 0.9, "fuzzy_name_amc"
        
        # 3. Category + AMC heuristic (try to find similar scheme in same AMC/category)
        if folio_category:
            heuristic_match = self._find_by_category_amc(folio_category, folio_amc)
            if heuristic_match:
                self._folio_to_scheme[folio_id] = heuristic_match
                self._master[heuristic_match].source_folio_codes.append(folio_id)
                return heuristic_match, 0.7, "category_amc_heuristic"
        
        # 4. No match - this is a new scheme not in master yet
        # Caller should create SchemeMaster and register it
        return "", 0.0, "new_scheme"
    
    def resolve_folios_batch(
        self,
        folios: list[dict],  # [{"folio_id", "scheme_code", "scheme_name", "amc", "category", ...}, ...]
    ) -> list[dict]:
        """
        Resolve multiple folios at once.
        Returns list of {folio_id, scheme_code, confidence, method, needs_review}
        """
        results = []
        for f in folios:
            scheme_code, confidence, method = self.resolve_folio_scheme(
                folio_id=f["folio_id"],
                folio_scheme_code=f.get("scheme_code"),
                folio_scheme_name=f["scheme_name"],
                folio_amc=f["amc"],
                folio_category=f.get("category"),
            )
            results.append({
                "folio_id": f["folio_id"],
                "scheme_code": scheme_code,
                "confidence": confidence,
                "method": method,
                "needs_review": confidence < 0.9 or method == "new_scheme",
            })
        return results
    
    def get_scheme_master(self, scheme_code: str) -> Optional[SchemeMaster]:
        """Get scheme master by code"""
        return self._master.get(scheme_code)
    
    def get_folio_scheme(self, folio_id: str) -> Optional[str]:
        """Get resolved scheme_code for a folio"""
        return self._folio_to_scheme.get(folio_id)
    
    def get_all_schemes(self) -> list[SchemeMaster]:
        """Get all registered schemes"""
        return list(self._master.values())
    
    def get_schemes_by_category(self, category: SchemeCategory) -> list[SchemeMaster]:
        """Get all schemes in a category"""
        return [s for s in self._master.values() if s.category == category]
    
    def get_dedup_stats(self) -> dict:
        """Get deduplication statistics"""
        total_folios = len(self._folio_to_scheme)
        unique_schemes = len(self._master)
        avg_folios_per_scheme = total_folios / unique_schemes if unique_schemes > 0 else 0
        
        method_counts: dict[str, int] = {}
        confidence_sum = 0.0
        for folio_id, scheme_code in self._folio_to_scheme.items():
            # We'd need to track method per folio - simplified here
            pass
        
        return {
            "total_folios_mapped": total_folios,
            "unique_schemes": unique_schemes,
            "avg_folios_per_scheme": round(avg_folios_per_scheme, 1),
            "schemes_with_multiple_folios": sum(
                1 for s in self._master.values() if len(s.source_folio_codes) > 1
            ),
        }
    
    def export_scheme_master(self, path: str | Path) -> None:
        """Export scheme master to JSON for persistence/debugging"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for s in self._master.values():
            data.append({
                "scheme_code": s.scheme_code,
                "scheme_name": s.scheme_name,
                "amc": s.amc,
                "category": s.category.value,
                "sub_category": s.sub_category,
                "benchmark_index": s.benchmark_index,
                "fund_manager": s.fund_manager,
                "expense_ratio": s.expense_ratio,
                "aum": s.aum,
                "inception_date": s.inception_date.isoformat() if s.inception_date else None,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
                "is_active": s.is_active,
                "source_folio_codes": s.source_folio_codes,
                "dedup_confidence": s.dedup_confidence,
            })
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def load_scheme_master(self, path: str | Path) -> int:
        """Load scheme master from JSON"""
        path = Path(path)
        if not path.exists():
            return 0
        
        with open(path) as f:
            data = json.load(f)
        
        count = 0
        for item in data:
            scheme = SchemeMaster(
                scheme_code=item["scheme_code"],
                scheme_name=item["scheme_name"],
                amc=item["amc"],
                category=SchemeCategory(item["category"]),
                sub_category=item.get("sub_category"),
                benchmark_index=item.get("benchmark_index"),
                fund_manager=item.get("fund_manager"),
                expense_ratio=item.get("expense_ratio"),
                aum=item.get("aum"),
                inception_date=date.fromisoformat(item["inception_date"]) if item.get("inception_date") else None,
                last_updated=date.fromisoformat(item["last_updated"]) if item.get("last_updated") else None,
                is_active=item.get("is_active", True),
                source_folio_codes=item.get("source_folio_codes", []),
                dedup_confidence=item.get("dedup_confidence", 1.0),
            )
            self.register_scheme(scheme)
            count += 1
        return count
    
    @staticmethod
    def _normalize_name_amc(name: str, amc: str) -> str:
        """Normalize scheme name + AMC for fuzzy matching"""
        # Remove common suffixes/prefixes, lowercase, remove special chars
        name_clean = re.sub(r'\b(Growth|Dividend|Direct|Regular|Plan|Option)\b', '', name, flags=re.IGNORECASE)
        name_clean = re.sub(r'[^\w\s]', '', name_clean).strip().lower()
        name_clean = re.sub(r'\s+', ' ', name_clean)
        amc_clean = re.sub(r'[^\w\s]', '', amc).strip().lower()
        return f"{name_clean}|{amc_clean}"
    
    def _find_by_category_amc(self, category: str, amc: str) -> Optional[str]:
        """Find scheme by category + AMC heuristic"""
        try:
            cat_enum = SchemeCategory(category)
        except ValueError:
            return None
        
        amc_clean = amc.strip().lower()
        for scheme in self._master.values():
            if scheme.category == cat_enum and amc_clean in scheme.amc.lower():
                return scheme.scheme_code
        return None


def create_scheme_master_from_folio(
    folio_scheme_code: str,
    folio_scheme_name: str,
    folio_amc: str,
    folio_category: str,
    **kwargs
) -> SchemeMaster:
    """Factory to create SchemeMaster from folio data"""
    try:
        category = SchemeCategory(folio_category)
    except ValueError:
        category = SchemeCategory.FLEXI_CAP  # Default fallback
    
    return SchemeMaster(
        scheme_code=folio_scheme_code or folio_scheme_name.replace(" ", "_").upper()[:20],
        scheme_name=folio_scheme_name,
        amc=folio_amc,
        category=category,
        **kwargs
    )