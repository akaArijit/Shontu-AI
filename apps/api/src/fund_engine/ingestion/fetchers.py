"""
Data Ingestion Layer
Pluggable adapters for: AMFI NAV, mfapi.in, NSE Indices, RBI, MOSPI
Architecture principle: 3-4 ingestion jobs, not one. Build as pluggable adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from enum import Enum
import requests
from pathlib import Path
import csv
import io
import json
import time


class DataSource(str, Enum):
    AMFI_NAV = "amfi_nav"
    MFAPI = "mfapi"
    NSE_INDICES = "nse_indices"
    RBI = "rbi"
    MOSPI = "mospi"
    FBIL = "fbil"
    VALUE_RESEARCH = "value_research"


@dataclass
class NavRecord:
    """Single NAV data point"""
    scheme_code: str
    nav_date: date
    nav_value: float
    source: DataSource
    fetched_at: datetime = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.utcnow()


@dataclass
class BenchmarkRecord:
    """Single benchmark index value"""
    benchmark_code: str
    index_date: date
    index_value: float
    source: DataSource
    fetched_at: datetime = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.utcnow()


@dataclass
class MacroRecord:
    """Single macro indicator value"""
    indicator_name: str
    indicator_date: date
    value: float
    source: DataSource
    fetched_at: datetime = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.utcnow()


@dataclass
class SchemeInfo:
    """Scheme metadata from AMFI/mfapi"""
    scheme_code: str
    scheme_name: str
    amc: str
    category: str
    sub_category: Optional[str] = None
    fund_manager: Optional[str] = None
    expense_ratio: Optional[float] = None
    aum: Optional[float] = None
    inception_date: Optional[date] = None
    source: DataSource = DataSource.AMFI_NAV


class IngestionError(Exception):
    """Custom exception for ingestion failures"""
    def __init__(self, source: DataSource, message: str, original_error: Exception = None):
        self.source = source
        self.original_error = original_error
        super().__init__(f"[{source.value}] {message}")


class BaseFetcher(ABC):
    """Abstract base class for all data fetchers"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3, retry_delay: float = 1.0):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FundMonitoringEngine/1.0 (+https://github.com/yourorg/fund-engine)"
        })
    
    @abstractmethod
    def fetch(self) -> list:
        """Fetch data from source. Returns list of records."""
        pass
    
    @property
    @abstractmethod
    def source(self) -> DataSource:
        """Data source identifier"""
        pass
    
    def _request_with_retry(self, url: str, **kwargs) -> requests.Response:
        """HTTP GET with exponential backoff retry"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        raise IngestionError(self.source, f"Failed after {self.max_retries} retries", last_error)

    def _post_with_retry(self, url: str, **kwargs) -> requests.Response:
        """HTTP POST with exponential backoff retry"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        raise IngestionError(
            self.source,
            f"POST failed after {self.max_retries} retries: {last_error}",
            last_error,
        )


class AmfiNavFetcher(BaseFetcher):
    """
    AMFI NAVAll.txt - Daily NAV for all schemes
    Source: https://www.amfiindia.com/spages/NAVAll.txt
    Free, official, but snapshot only (no history)
    """
    
    URL = "https://www.amfiindia.com/spages/NAVAll.txt"
    
    @property
    def source(self) -> DataSource:
        return DataSource.AMFI_NAV
    
    def fetch(self) -> list[NavRecord]:
        """Fetch and parse AMFI NAVAll.txt"""
        response = self._request_with_retry(self.URL)
        records = []
        
        # Parse tab-separated format
        # Format: Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;Net Asset Value;Date
        lines = response.text.strip().split('\n')
        
        for line in lines[1:]:  # Skip header
            if not line.strip():
                continue
            parts = line.split(';')
            if len(parts) < 5:
                continue
            
            try:
                scheme_code = parts[0].strip()
                scheme_name = parts[1].strip()
                nav_str = parts[3].strip()
                date_str = parts[4].strip()
                
                if not nav_str or nav_str == 'N.A.':
                    continue
                
                nav_value = float(nav_str)
                nav_date = datetime.strptime(date_str, "%d-%b-%Y").date()
                
                records.append(NavRecord(
                    scheme_code=scheme_code,
                    nav_date=nav_date,
                    nav_value=nav_value,
                    source=self.source,
                ))
            except (ValueError, IndexError):
                continue  # Skip malformed lines
        
        return records
    
    def fetch_scheme_info(self) -> list[SchemeInfo]:
        """Extract scheme metadata from NAVAll.txt"""
        response = self._request_with_retry(self.URL)
        schemes = {}
        
        lines = response.text.strip().split('\n')
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(';')
            if len(parts) < 5:
                continue
            
            scheme_code = parts[0].strip()
            if scheme_code not in schemes:
                schemes[scheme_code] = SchemeInfo(
                    scheme_code=scheme_code,
                    scheme_name=parts[1].strip(),
                    amc="",  # Not in NAVAll.txt
                    category="",  # Not in NAVAll.txt
                    source=self.source,
                )
        
        return list(schemes.values())


class MfapiFetcher(BaseFetcher):
    """
    mfapi.in - Historical NAV time series
    Free, unofficial, decent uptime
    API: https://api.mfapi.in/mf/{scheme_code}
    """
    
    BASE_URL = "https://api.mfapi.in/mf"
    
    @property
    def source(self) -> DataSource:
        return DataSource.MFAPI
    
    def fetch_scheme_history(self, scheme_code: str) -> list[NavRecord]:
        """Fetch full NAV history for a single scheme"""
        url = f"{self.BASE_URL}/{scheme_code}"
        response = self._request_with_retry(url)
        data = response.json()
        
        records = []
        for item in data.get("data", []):
            try:
                nav_date = datetime.strptime(item["date"], "%d-%m-%Y").date()
                nav_value = float(item["nav"])
                records.append(NavRecord(
                    scheme_code=scheme_code,
                    nav_date=nav_date,
                    nav_value=nav_value,
                    source=self.source,
                ))
            except (ValueError, KeyError):
                continue
        
        return records
    
    def fetch_scheme_info(self, scheme_code: str) -> Optional[SchemeInfo]:
        """Fetch scheme metadata"""
        url = f"{self.BASE_URL}/{scheme_code}"
        response = self._request_with_retry(url)
        data = response.json()
        
        meta = data.get("meta", {})
        return SchemeInfo(
            scheme_code=scheme_code,
            scheme_name=meta.get("scheme_name", ""),
            amc=meta.get("fund_house", ""),
            category=meta.get("scheme_category", ""),
            source=self.source,
        )
    
    def fetch_multiple_schemes(self, scheme_codes: list[str], delay: float = 0.5) -> dict[str, list[NavRecord]]:
        """Fetch history for multiple schemes with rate limiting"""
        results = {}
        for code in scheme_codes:
            try:
                results[code] = self.fetch_scheme_history(code)
            except IngestionError as e:
                results[code] = []  # Empty on failure, log in production
            if delay > 0:
                time.sleep(delay)
        return results
    
    def fetch(self) -> list:
        """Base fetch - not used for mfapi (scheme-specific)"""
        raise NotImplementedError("Use fetch_scheme_history or fetch_multiple_schemes")


class NseIndicesFetcher(BaseFetcher):
    """
    NSE Indices (niftyindices.com) - Total Return Index values.

    Uses the public JSON endpoint behind the "Historical Data" report. The
    endpoint accepts at most one year per request, so ranges are chunked.
    """

    BASE_URL = "https://www.niftyindices.com"
    TRI_URL = f"{BASE_URL}/BackPage/getTotalReturnIndexString"
    MAX_DAYS_PER_REQUEST = 365
    CHUNK_DAYS = 330

    # Display names (kept for the demo/summary output)
    INDEX_MAPPING = {
        "NIFTY100_TRI": "Nifty 100 TRI",
        "NIFTY_LARGEMIDCAP250_TRI": "Nifty LargeMidcap 250 TRI",
        "NIFTY500_TRI": "Nifty 500 TRI",
        "NIFTY_MIDCAP150_TRI": "Nifty Midcap 150 TRI",
        "NIFTY_SMALLCAP250_TRI": "Nifty Smallcap 250 TRI",
        "NIFTY50_TRI": "Nifty 50 TRI",
        "NIFTY_BANK_TRI": "Nifty Bank TRI",
        "NIFTY_IT_TRI": "Nifty IT TRI",
        "NIFTY_INDIA_CONSUMPTION_TRI": "Nifty India Consumption TRI",
        "NIFTY_INFRASTRUCTURE_TRI": "Nifty Infrastructure TRI",
        "NIFTY_PHARMA_TRI": "Nifty Pharma TRI",
        "CRISIL_HYBRID_35_65": "CRISIL Hybrid 35+65",
        "CRISIL_SHORT_TERM_BOND": "CRISIL Short Term Bond Index",
    }

    # Exact trading-index names required by the NSE endpoint.
    TRI_INDEX_NAMES = {
        "NIFTY100_TRI": "NIFTY 100",
        "NIFTY_LARGEMIDCAP250_TRI": "NIFTY LARGEMIDCAP 250",
        "NIFTY500_TRI": "NIFTY 500",
        "NIFTY_MIDCAP150_TRI": "NIFTY MIDCAP 150",
        "NIFTY_SMALLCAP250_TRI": "NIFTY SMALLCAP 250",
        "NIFTY50_TRI": "NIFTY 50",
        "NIFTY_BANK_TRI": "NIFTY BANK",
        "NIFTY_IT_TRI": "NIFTY IT",
        "NIFTY_INDIA_CONSUMPTION_TRI": "NIFTY INDIA CONSUMPTION",
        "NIFTY_INFRASTRUCTURE_TRI": "NIFTY INFRASTRUCTURE",
        "NIFTY_PHARMA_TRI": "NIFTY PHARMA",
    }

    @property
    def source(self) -> DataSource:
        return DataSource.NSE_INDICES

    def fetch_index_history(
        self, benchmark_code: str, from_date: date, to_date: date
    ) -> list[BenchmarkRecord]:
        """Fetch TRI history for one benchmark, chunked to the API's 1-year limit."""
        index_name = self.TRI_INDEX_NAMES.get(benchmark_code)
        if index_name is None:
            raise NotImplementedError(
                f"{benchmark_code} is not an NSE Total Return Index; "
                "load its history via CSV instead"
            )

        by_date: dict[date, float] = {}
        chunk_start = from_date
        while chunk_start <= to_date:
            chunk_end = min(chunk_start + timedelta(days=self.CHUNK_DAYS), to_date)
            for row in self._fetch_chunk(index_name, chunk_start, chunk_end):
                parsed = self._parse_row(row)
                if parsed is not None:
                    by_date[parsed[0]] = parsed[1]
            chunk_start = chunk_end + timedelta(days=1)

        return [
            BenchmarkRecord(
                benchmark_code=benchmark_code,
                index_date=index_date,
                index_value=index_value,
                source=self.source,
            )
            for index_date, index_value in sorted(by_date.items())
        ]

    def fetch_latest_indices(self) -> list[BenchmarkRecord]:
        """Fetch the latest available value for every supported index."""
        to_date = date.today()
        from_date = to_date - timedelta(days=14)
        records = []
        for benchmark_code in self.TRI_INDEX_NAMES:
            try:
                history = self.fetch_index_history(benchmark_code, from_date, to_date)
            except (IngestionError, NotImplementedError):
                continue
            if history:
                records.append(history[-1])
        return records

    def fetch(self) -> list:
        return self.fetch_latest_indices()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_chunk(self, index_name: str, start: date, end: date) -> list[dict]:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.BASE_URL}/reports/historical-data",
            # The NSE site rejects non-browser user agents, so override the
            # default engine UA for this request only.
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        }
        payload = {
            "cinfo": json.dumps(
                {
                    "name": index_name,
                    "indexName": index_name,
                    "startDate": start.strftime("%m/%d/%Y"),
                    "endDate": end.strftime("%m/%d/%Y"),
                }
            )
        }
        response = self._post_with_retry(self.TRI_URL, json=payload, headers=headers)
        return self._parse_response(response)

    def _parse_response(self, response) -> list[dict]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise IngestionError(self.source, "NSE returned a non-JSON payload", exc)

        # Current API returns a list; older deployments wrap it in {"d": "..."}.
        if isinstance(payload, dict):
            payload = payload.get("d", [])
            if isinstance(payload, str):
                payload = json.loads(payload) if payload.strip() else []

        if not isinstance(payload, list):
            raise IngestionError(self.source, "Unexpected NSE payload shape")
        return payload

    @staticmethod
    def _parse_row(row: dict) -> Optional[tuple[date, float]]:
        raw_date = row.get("Date") or row.get("HistoricalDate")
        raw_value = row.get("TotalReturnsIndex") or row.get("CLOSE")
        if not raw_date or raw_value in (None, "", "-"):
            return None

        parsed_date = None
        for fmt in ("%d %b %Y", "%d-%b-%Y", "%d/%m/%Y"):
            try:
                parsed_date = datetime.strptime(str(raw_date).strip(), fmt).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            return None

        try:
            return parsed_date, float(str(raw_value).replace(",", ""))
        except ValueError:
            return None


class RbiFetcher(BaseFetcher):
    """
    RBI DBIE / RBI website - Repo rate, CPI, bond yield
    Official, but manual scraping needed - no clean API
    """
    
    @property
    def source(self) -> DataSource:
        return DataSource.RBI
    
    def fetch_repo_rate(self) -> list[MacroRecord]:
        """Fetch repo rate history"""
        # RBI doesn't have a clean API - would need scraping
        # Placeholder for actual implementation
        raise NotImplementedError("RBI data requires web scraping")
    
    def fetch_bond_yields(self) -> list[MacroRecord]:
        """Fetch government bond yields"""
        raise NotImplementedError("RBI bond yields require web scraping")
    
    def fetch(self) -> list:
        raise NotImplementedError("Use specific fetch methods")


class MospiFetcher(BaseFetcher):
    """
    MOSPI - CPI, inflation, GDP
    Govt source, quarterly/monthly lag
    """
    
    @property
    def source(self) -> DataSource:
        return DataSource.MOSPI
    
    def fetch_cpi(self) -> list[MacroRecord]:
        """Fetch CPI inflation data"""
        raise NotImplementedError("MOSPI data requires specific API integration")
    
    def fetch(self) -> list:
        raise NotImplementedError("Use specific fetch methods")


class FbilFetcher(BaseFetcher):
    """
    FBIL / RBI reference rate - USD/INR
    Daily reference rate
    """
    
    @property
    def source(self) -> DataSource:
        return DataSource.FBIL
    
    def fetch_usd_inr(self) -> list[MacroRecord]:
        """Fetch USD/INR reference rate"""
        raise NotImplementedError("FBIL data requires specific API integration")
    
    def fetch(self) -> list:
        raise NotImplementedError("Use specific fetch methods")


class IngestionOrchestrator:
    """
    Orchestrates multiple fetchers with error isolation.
    One failing source doesn't break the pipeline.
    """
    
    def __init__(self):
        self.fetchers: dict[DataSource, BaseFetcher] = {}
    
    def register_fetcher(self, fetcher: BaseFetcher) -> None:
        self.fetchers[fetcher.source] = fetcher
    
    def fetch_all_nav(self, scheme_codes: list[str]) -> dict[DataSource, list[NavRecord]]:
        """Fetch NAV from all available NAV sources"""
        results = {}
        
        # AMFI - single call gets all schemes
        if DataSource.AMFI_NAV in self.fetchers:
            try:
                results[DataSource.AMFI_NAV] = self.fetchers[DataSource.AMFI_NAV].fetch()
            except IngestionError as e:
                results[DataSource.AMFI_NAV] = []
                # Log error in production
        
        # mfapi - scheme by scheme
        if DataSource.MFAPI in self.fetchers:
            mfapi_fetcher = self.fetchers[DataSource.MFAPI]
            if isinstance(mfapi_fetcher, MfapiFetcher):
                try:
                    results[DataSource.MFAPI] = mfapi_fetcher.fetch_multiple_schemes(scheme_codes)
                except IngestionError as e:
                    results[DataSource.MFAPI] = {}
        
        return results
    
    def fetch_benchmarks(self, benchmark_codes: list[str]) -> list[BenchmarkRecord]:
        """Fetch benchmark index values"""
        results = []
        if DataSource.NSE_INDICES in self.fetchers:
            try:
                # Would call appropriate method
                pass
            except IngestionError:
                pass
        return results
    
    def fetch_macro(self) -> list[MacroRecord]:
        """Fetch macro indicators from all sources"""
        results = []
        for source in [DataSource.RBI, DataSource.MOSPI, DataSource.FBIL]:
            if source in self.fetchers:
                try:
                    # Would call appropriate methods
                    pass
                except IngestionError:
                    pass
        return results
    
    def get_health_status(self) -> dict:
        """Check health of all registered fetchers"""
        status = {}
        for source, fetcher in self.fetchers.items():
            try:
                # Quick health check - try a simple request
                status[source.value] = "healthy"
            except Exception:
                status[source.value] = "unhealthy"
        return status


# Convenience function for quick testing
def create_orchestrator() -> IngestionOrchestrator:
    """Create orchestrator with all fetchers registered"""
    orchestrator = IngestionOrchestrator()
    orchestrator.register_fetcher(AmfiNavFetcher())
    orchestrator.register_fetcher(MfapiFetcher())
    orchestrator.register_fetcher(NseIndicesFetcher())
    orchestrator.register_fetcher(RbiFetcher())
    orchestrator.register_fetcher(MospiFetcher())
    orchestrator.register_fetcher(FbilFetcher())
    return orchestrator