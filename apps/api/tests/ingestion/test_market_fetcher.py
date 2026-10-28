"""Tests for the MarketDataFetcher adapter (no network calls)."""

from __future__ import annotations

from datetime import date

from fund_engine.ingestion.fetchers import DataSource, NavRecord
from fund_engine.ingestion.market_fetcher import MarketDataFetcher


class FakeMfapi:
    def __init__(self, records, fail=False):
        self.records = records
        self.fail = fail
        self.calls = []

    def fetch_scheme_history(self, scheme_code):
        self.calls.append(scheme_code)
        if self.fail:
            raise RuntimeError("upstream timeout")
        return self.records


def _record(nav_date):
    return NavRecord(
        scheme_code="100001",
        nav_date=nav_date,
        nav_value=42.5,
        source=DataSource.MFAPI,
    )


def test_fetch_nav_returns_rows_for_all_schemes():
    fetcher = MarketDataFetcher()
    fetcher.mfapi = FakeMfapi([_record(date(2026, 1, 2)), _record(date(2026, 1, 3))])

    rows, errors = fetcher.fetch_nav(["100001"])

    assert errors == []
    assert [row["nav_date"] for row in rows] == [date(2026, 1, 2), date(2026, 1, 3)]
    assert all(row["source"] == "mfapi" for row in rows)


def test_fetch_nav_filters_points_already_stored():
    fetcher = MarketDataFetcher()
    fetcher.mfapi = FakeMfapi([_record(date(2026, 1, 2)), _record(date(2026, 1, 5))])

    rows, _ = fetcher.fetch_nav(["100001"], since={"100001": date(2026, 1, 2)})

    assert [row["nav_date"] for row in rows] == [date(2026, 1, 5)]


def test_fetch_nav_isolates_per_scheme_failures():
    fetcher = MarketDataFetcher()
    fetcher.mfapi = FakeMfapi([_record(date(2026, 1, 2))], fail=True)

    rows, errors = fetcher.fetch_nav(["100001", "100002"])

    assert rows == []
    assert len(errors) == 2
    assert "100001" in errors[0]
