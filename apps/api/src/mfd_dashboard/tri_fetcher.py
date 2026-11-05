"""NSE Total Return Index (TRI) data fetcher.

Fetches historical TRI data from niftyindices.com for benchmarks that are
actually used by mapped schemes. Data is stored locally in SQLite and never
sent outside the application.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class TriFetchError(Exception):
    """Raised when TRI data fetch fails."""
    pass


class NseTriFetcher:
    """
    Fetches Total Return Index (TRI) data from NSE India (niftyindices.com).

    Uses the public JSON endpoint behind the "Historical Data" report.
    The endpoint accepts at most ~1 year per request, so ranges are chunked.
    """

    BASE_URL = "https://www.niftyindices.com"
    TRI_URL = f"https://www.niftyindices.com/BackPage/getTotalReturnIndexString"
    CHUNK_DAYS = 330  # NSE limit is ~1 year per request; 330 days is safe

    # Maps our benchmark names (as stored in benchmark_master.yaml) to NSE index names
    # These are the exact index names expected by the NSE TRI endpoint
    NSE_INDEX_NAMES: dict[str, str] = {
        "Nifty 50 TRI": "NIFTY 50",
        "Nifty 100 TRI": "NIFTY 100",
        "Nifty 200 TRI": "NIFTY 200",
        "Nifty 500 TRI": "NIFTY 500",
        "Nifty Midcap 50 TRI": "NIFTY MIDCAP 50",
        "Nifty Midcap 100 TRI": "NIFTY MIDCAP 100",
        "Nifty Midcap 150 TRI": "NIFTY MIDCAP 150",
        "Nifty Midcap Select TRI": "NIFTY MIDCAP SELECT",
        "Nifty Smallcap 50 TRI": "NIFTY SMALLCAP 50",
        "Nifty Smallcap 100 TRI": "NIFTY SMALLCAP 100",
        "Nifty Smallcap 250 TRI": "NIFTY SMALLCAP 250",
        "Nifty Smallcap 500 TRI": "NIFTY SMALLCAP 500",
        "Nifty Microcap 250 TRI": "NIFTY MICROCAP 250",
        "Nifty LargeMidcap 250 TRI": "NIFTY LARGEMIDCAP 250",
        "Nifty MidSmallcap 400 TRI": "NIFTY MIDSMLCAP 400",
        "Nifty Total Market TRI": "NIFTY TOTAL MARKET",
        "Nifty Next 50 TRI": "NIFTY NEXT 50",
        "Nifty Next 100 TRI": "NIFTY NEXT 100",
        "Nifty Bank TRI": "NIFTY BANK",
        "Nifty IT TRI": "NIFTY IT",
        "Nifty Pharma TRI": "NIFTY PHARMA",
        "Nifty Auto TRI": "NIFTY AUTO",
        "Nifty FMCG TRI": "NIFTY FMCG",
        "Nifty Metal TRI": "NIFTY METAL",
        "Nifty PSU TRI": "NIFTY PSU",
        "Nifty Private Bank TRI": "NIFTY PRIVATE BANK",
        "Nifty PSU Bank TRI": "NIFTY PSU BANK",
        "Nifty Financial Services TRI": "NIFTY FINANCIAL SERVICES",
        "Nifty Healthcare TRI": "NIFTY HEALTHCARE",
        "Nifty Media TRI": "NIFTY MEDIA",
        "Nifty Realty TRI": "NIFTY REALTY",
        "Nifty Infrastructure TRI": "NIFTY INFRASTRUCTURE",
        "Nifty Energy TRI": "NIFTY ENERGY",
        "Nifty Commodities TRI": "NIFTY COMMODITIES",
        "Nifty Consumption TRI": "NIFTY CONSUMPTION",
        "Nifty MNC TRI": "NIFTY MNC",
        "Nifty India Defence TRI": "NIFTY INDIA DEFENCE",
        "Nifty India Manufacturing TRI": "NIFTY INDIA MANUFACTURING",
        "Nifty India Tourism TRI": "NIFTY INDIA TOURISM",
        "Nifty Capital Goods TRI": "NIFTY CAPITAL GOODS",
        "Nifty Services Sector TRI": "NIFTY SERVICES SECTOR",
        "Nifty ESG TRI": "NIFTY ESG",
        "Nifty 100 Equal Weight TRI": "NIFTY 100 EQUAL WEIGHT",
        "Nifty 50 Equal Weight TRI": "NIFTY 50 EQUAL WEIGHT",
        "Nifty 500 Equal Weight TRI": "NIFTY 500 EQUAL WEIGHT",
        "Nifty 50 Value 20 TRI": "NIFTY 50 VALUE 20",
        "Nifty Alpha 50 TRI": "NIFTY ALPHA 50",
        "Nifty High Beta 50 TRI": "NIFTY HIGH BETA 50",
        "Nifty Low Volatility 50 TRI": "NIFTY LOW VOLATILITY 50",
        "Nifty 100 Low Volatility 30 TRI": "NIFTY 100 LOW VOLATILITY 30",
        "Nifty 100 Quality 30 TRI": "NIFTY 100 QUALITY 30",
        "Nifty 200 TRI": "NIFTY 200",
        "Nifty Dividend Opportunities 50 TRI": "NIFTY DIVIDEND OPPORTUNITIES 50",
        "Nifty High Dividend Yield 15 TRI": "NIFTY HIGH DIVIDEND YIELD 15",
        "Nifty Growth Sectors 15 TRI": "NIFTY GROWTH SECTORS 15",
        "Nifty Alpha Low-Volatility 30 TRI": "NIFTY ALPHA LOW VOLATILITY 30",
        "Nifty Alpha Quality Low-Volatility 30 TRI": "NIFTY ALPHA QUALITY LOW VOLATILITY 30",
        "Nifty Alpha Quality Value Low-Volatility 30 TRI": "NIFTY ALPHA QUALITY VALUE LOW VOLATILITY 30",
        "Nifty Quality Low-Volatility 30 TRI": "NIFTY QUALITY LOW VOLATILITY 30",
        "Nifty 100 Low Volatility 30 TRI": "NIFTY 100 LOW VOLATILITY 30",
        "Nifty 100 Quality 30 TRI": "NIFTY 100 QUALITY 30",
        "Nifty 50 Arbitrage TRI": "NIFTY 50 ARBITRAGE",
        "CRISIL Hybrid 35+65 TRI": "CRISIL HYBRID 35+65",
        "CRISIL Short Term Bond TRI": "CRISIL SHORT TERM BOND INDEX",
        "CRISIL Liquid Fund TRI": "CRISIL LIQUID FUND INDEX",
    }

    def __init__(
        self,
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.niftyindices.com/reports/historical-data",
            "Content-Type": "application/json; charset=utf-8",
        })

    def get_supported_benchmarks(self) -> list[str]:
        """Return list of benchmark names that have NSE TRI support."""
        return list(self.NSE_INDEX_NAMES.keys())

    def get_nse_index_name(self, benchmark_name: str) -> Optional[str]:
        """Get the NSE index name for a benchmark."""
        return self.NSE_INDEX_NAMES.get(benchmark_name)

    def is_supported(self, benchmark_name: str) -> bool:
        """Check if a benchmark has NSE TRI support."""
        return benchmark_name in self.NSE_INDEX_NAMES

    def fetch_tri_history(
        self,
        benchmark_name: str,
        from_date: date,
        to_date: date,
    ) -> list[tuple[date, float]]:
        """
        Fetch TRI history for a benchmark, chunked to the API's limit.

        Returns list of (date, value) tuples sorted by date.
        """
        nse_name = self.get_nse_index_name(benchmark_name)
        if nse_name is None:
            raise TriFetchError(
                f"No NSE TRI support for benchmark: {benchmark_name}"
            )

        logger.info(
            "Fetching TRI for %s (%s) from %s to %s",
            benchmark_name,
            nse_name,
            from_date,
            to_date,
        )

        by_date: dict[date, float] = {}
        chunk_start = from_date

        while chunk_start <= to_date:
            chunk_end = min(chunk_start + timedelta(days=self.CHUNK_DAYS), to_date)
            chunk_data = self._fetch_chunk(nse_name, chunk_start, chunk_end)
            for row in chunk_data:
                parsed = self._parse_row(row)
                if parsed is not None:
                    by_date[parsed[0]] = parsed[1]
            chunk_start = chunk_end + timedelta(days=1)
            # Be nice to NSE servers
            time.sleep(0.5)

        if not by_date:
            return []

        # Return sorted by date
        return sorted(by_date.items())

    def fetch_tri_history_bulk(
        self,
        benchmark_names: list[str],
        from_date: date,
        to_date: date,
    ) -> dict[str, list[tuple[date, float]]]:
        """
        Fetch TRI history for multiple benchmarks.

        Returns a dict mapping benchmark_name -> list of (date, value) tuples.
        """
        results: dict[str, list[tuple[date, float]]] = {}

        for name in benchmark_names:
            if not self.is_supported(name):
                logger.warning("Skipping unsupported benchmark: %s", name)
                continue
            try:
                data = self.fetch_tri_history(name, from_date, to_date)
                results[name] = data
            except TriFetchError as e:
                logger.error("Failed to fetch TRI for %s: %s", name, e)
                continue

        return results

    def _fetch_chunk(self, index_name: str, start: date, end: date) -> list[dict]:
        """Fetch a single chunk of TRI data from NSE."""
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.niftyindices.com/reports/historical-data",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
        }
        payload = {
            "cinfo": json.dumps({
                "name": index_name,
                "indexName": index_name,
                "startDate": start.strftime("%m/%d/%Y"),
                "endDate": end.strftime("%m/%d/%Y"),
            })
        }

        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.TRI_URL,
                    json=payload,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return self._parse_response(response)
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise TriFetchError(f"NSE request failed: {e}") from e

        raise TriFetchError("Max retries exceeded")

    @staticmethod
    def _parse_response(response) -> list[dict]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise TriFetchError("NSE returned non-JSON payload") from exc

        # Current API returns a list; older deployments wrap it in {"d": "..."}
        if isinstance(payload, dict):
            payload = payload.get("d", [])
            if isinstance(payload, str):
                payload = json.loads(payload) if payload.strip() else []

        if not isinstance(payload, list):
            raise TriFetchError("Unexpected NSE payload shape")
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


def fetch_tri_for_benchmarks(
    benchmark_names: list[str],
    from_date: date,
    to_date: date,
) -> dict[str, list[tuple[date, float]]]:
    """
    Fetch TRI history for multiple benchmarks.

    Returns a dict mapping benchmark_name -> list of (date, value) tuples.
    """
    fetcher = NseTriFetcher()
    results: dict[str, list[tuple[date, float]]] = {}

    for name in benchmark_names:
        if not fetcher.is_supported(name):
            logger.warning("Skipping unsupported benchmark: %s", name)
            continue
        try:
            data = fetcher.fetch_tri_history(name, from_date, to_date)
            results[name] = data
        except TriFetchError as e:
            logger.error("Failed to fetch TRI for %s: %s", name, e)
            continue

    return results