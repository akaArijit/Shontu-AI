"""Benchmark seeding script tests (no network, no database)."""

from __future__ import annotations

import sys
from datetime import date
from types import SimpleNamespace

from fund_engine.ingestion.fetchers import BenchmarkRecord, DataSource
from fund_engine.services import benchmarks as seed_benchmarks


class FakeReader:
    def __init__(self, codes=(), schemes=()):
        self._codes = list(codes)
        self._schemes = list(schemes)

    def benchmark_codes(self):
        return list(self._codes)

    def active_schemes(self):
        return list(self._schemes)


class StubResolver:
    def resolve(self, scheme_code, scheme_name, category):
        return SimpleNamespace(
            benchmark_code=SimpleNamespace(value=f"BENCH_{category.replace(' ', '_')}")
        )


def test_resolve_prefers_explicit_codes():
    reader = FakeReader(codes=["STORED"])
    codes = seed_benchmarks.resolve_benchmark_codes(
        reader, StubResolver(), [" z ", "A", ""]
    )
    assert codes == ["A", "z"]


def test_resolve_uses_stored_mappings():
    reader = FakeReader(codes=["NIFTY500_TRI", "NIFTY100_TRI"])
    assert seed_benchmarks.resolve_benchmark_codes(reader, StubResolver()) == [
        "NIFTY100_TRI",
        "NIFTY500_TRI",
    ]


def test_resolve_falls_back_to_resolver():
    reader = FakeReader(
        schemes=[
            {"scheme_code": "1", "scheme_name": "A", "category": "Large Cap"},
            {"scheme_code": "2", "scheme_name": "B", "category": "Mid Cap"},
            {"scheme_code": "3", "scheme_name": "C", "category": "Large Cap"},
        ]
    )
    assert seed_benchmarks.resolve_benchmark_codes(reader, StubResolver()) == [
        "BENCH_Large_Cap",
        "BENCH_Mid_Cap",
    ]


class FakeWriter:
    def __init__(self):
        self.benchmarks = []
        self.history = []

    def upsert_benchmarks(self, rows):
        self.benchmarks.extend(rows)
        return len(rows)

    def upsert_benchmark_history(self, rows):
        self.history.extend(rows)
        return len(rows)


class FakeFetcher:
    def __init__(self, *args, **kwargs):
        self.CHUNK_DAYS = 330
        self.calls = []

    def fetch_index_history(self, code, start, end):
        self.calls.append((code, start, end))
        if code == "UNSUPPORTED":
            raise NotImplementedError(code)
        return [
            BenchmarkRecord(
                benchmark_code=code,
                index_date=date(2026, 10, 1),
                index_value=100.0,
                source=DataSource.NSE_INDICES,
            ),
            BenchmarkRecord(
                benchmark_code=code,
                index_date=date(2026, 10, 2),
                index_value=101.0,
                source=DataSource.NSE_INDICES,
            ),
        ]


def test_main_backfills_history_without_network(monkeypatch):
    reader = FakeReader(codes=["NIFTY100_TRI", "UNSUPPORTED"])
    writer = FakeWriter()
    fetcher = FakeFetcher()

    monkeypatch.setattr(seed_benchmarks, "DatabaseReader", lambda: reader)
    monkeypatch.setattr(seed_benchmarks, "DatabaseWriter", lambda: writer)
    monkeypatch.setattr(seed_benchmarks, "NseIndicesFetcher", lambda **kwargs: fetcher)
    monkeypatch.setattr(
        sys,
        "argv",
        ["seed_benchmarks.py", "--from-date", "2026-10-01", "--to-date", "2026-10-02"],
    )

    assert seed_benchmarks.main() == 0

    assert {row["benchmark_code"] for row in writer.benchmarks} == {
        "NIFTY100_TRI",
        "UNSUPPORTED",
    }
    assert len(writer.history) == 2
    assert all(row["source"] == "nse" for row in writer.history)
    assert fetcher.calls[0][1] == date(2026, 10, 1)
    assert fetcher.calls[0][2] == date(2026, 10, 2)


def test_main_fails_when_no_codes(monkeypatch):
    monkeypatch.setattr(seed_benchmarks, "DatabaseReader", lambda: FakeReader())
    monkeypatch.setattr(seed_benchmarks, "DatabaseWriter", lambda: FakeWriter())
    monkeypatch.setattr(sys, "argv", ["seed_benchmarks.py"])

    assert seed_benchmarks.main() == 2
