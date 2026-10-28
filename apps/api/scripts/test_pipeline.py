"""End-to-end pipeline test with in-memory reader/writer doubles."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from scripts.run_nightly import PipelineRunner

AS_OF = date(2026, 10, 27)


class FakeReader:
    def __init__(self, schemes, nav_rows, benchmark_rows, folio_count=7):
        self.schemes = schemes
        self.nav_rows = nav_rows
        self.benchmark_rows = benchmark_rows
        self._folio_count = folio_count
        self.fail_nav = False

    def active_schemes(self):
        return list(self.schemes)

    def nav_history(self, as_of_date=None):
        if self.fail_nav:
            raise RuntimeError("nav_history unavailable")
        return list(self.nav_rows)

    def benchmark_history(self, as_of_date=None):
        return list(self.benchmark_rows)

    def benchmark_codes(self):
        return sorted({row["benchmark_code"] for row in self.benchmark_rows})

    def folio_count(self):
        return self._folio_count


class FakeWriter:
    def __init__(self):
        self.run_id = None
        self.status = None
        self.finish_kwargs = {}
        self.schemes = []
        self.benchmarks = []
        self.scheme_benchmarks = []
        self.benchmark_history = []
        self.features = []
        self.scores = []
        self.alerts = []

    def start_run(self, as_of_date):
        self.run_id = "run-1"
        return self.run_id

    def finish_run(self, run_id, status, **kwargs):
        self.status = status
        self.finish_kwargs = kwargs

    def upsert_benchmarks(self, rows):
        self.benchmarks.extend(rows)
        return len(rows)

    def upsert_schemes(self, rows):
        self.schemes.extend(rows)
        return len(rows)

    def update_scheme_benchmarks(self, rows):
        self.scheme_benchmarks.extend(rows)
        return len(rows)

    def upsert_nav(self, rows):
        return len(rows)

    def upsert_benchmark_history(self, rows):
        self.benchmark_history.extend(rows)
        return len(rows)

    def upsert_features(self, rows):
        self.features.extend(rows)
        return len(rows)

    def upsert_scores(self, rows):
        self.scores.extend(rows)
        return len(rows)

    def sync_alerts(self, alerts, as_of_date):
        self.alerts.extend(alerts)
        return {"inserted": len(alerts), "updated": 0, "resolved": 2}


def _nav_rows(scheme_code, drift, amplitude=0.02):
    dates = pd.bdate_range(end=AS_OF, periods=900)
    rows = []
    for index, timestamp in enumerate(dates):
        value = 100 * (1 + drift) ** index
        value *= 1 + amplitude * math.sin(index / 7)
        rows.append(
            {
                "scheme_code": scheme_code,
                "nav_date": timestamp.date(),
                "nav_value": round(value, 4),
            }
        )
    return rows


def _benchmark_rows(benchmark_code, drift=0.0004):
    dates = pd.bdate_range(end=AS_OF, periods=900)
    return [
        {
            "benchmark_code": benchmark_code,
            "index_date": timestamp.date(),
            "index_value": round(1000 * (1 + drift) ** index, 4),
        }
        for index, timestamp in enumerate(dates)
    ]


SCHEMES = [
    {
        "scheme_code": "100001",
        "scheme_name": "Alpha Large Cap Fund",
        "amc": "Alpha AMC",
        "category": "Large Cap",
        "benchmark_index": None,
    },
    {
        "scheme_code": "100002",
        "scheme_name": "Beta Large Cap Fund",
        "amc": "Beta AMC",
        "category": "Large Cap",
        "benchmark_index": None,
    },
    {
        "scheme_code": "100003",
        "scheme_name": "Gamma Flexi Cap Fund",
        "amc": "Gamma AMC",
        "category": "Flexi Cap",
        "benchmark_index": None,
    },
]


def _all_nav_rows():
    rows = []
    rows += _nav_rows("100001", drift=0.0008)
    rows += _nav_rows("100002", drift=0.0001, amplitude=0.05)
    rows += _nav_rows("100003", drift=0.0005, amplitude=0.03)
    return rows


def _all_benchmark_rows():
    return _benchmark_rows("NIFTY100_TRI") + _benchmark_rows("NIFTY500_TRI")


def _build_runner(folio_count=7):
    reader = FakeReader(
        SCHEMES, _all_nav_rows(), _all_benchmark_rows(), folio_count=folio_count
    )
    writer = FakeWriter()
    runner = PipelineRunner(
        as_of_date=AS_OF,
        reader=reader,
        writer=writer,
        fetcher=None,
        skip_ingest=True,
    )
    return runner, reader, writer


def test_pipeline_computes_and_persists_all_stages():
    runner, _, writer = _build_runner(folio_count=7)

    stats = runner.run()

    assert stats["status"] == "completed"
    assert writer.status == "completed"
    assert stats["scores_computed"] == 3
    assert len(writer.features) == 3
    assert len(writer.scores) == 3

    # Benchmark resolution persisted both the master rows and scheme pointers.
    assert {row["benchmark_code"] for row in writer.benchmarks} == {
        "NIFTY100_TRI",
        "NIFTY500_TRI",
    }
    assert {row["scheme_code"] for row in writer.scheme_benchmarks} == {
        "100001",
        "100002",
        "100003",
    }

    # Enriched feature rows carry category for the rule engine and DB write.
    assert all(row["category"] for row in writer.features)
    assert all("return_1y" in row for row in writer.features)

    # Scores are valid 0-100 values with a breakdown.
    assert all(0 <= row["fund_health_score"] <= 100 for row in writer.scores)
    assert all(isinstance(row["breakdown"], list) for row in writer.scores)

    assert stats["alerts_generated"] == len(writer.alerts)
    assert writer.finish_kwargs["scores_computed"] == 3
    assert writer.finish_kwargs["folios_processed"] == 7


def test_pipeline_without_nav_history_produces_no_scores():
    runner, reader, writer = _build_runner()
    reader.nav_rows = []

    stats = runner.run()

    assert stats["status"] == "completed"
    assert stats["scores_computed"] == 0
    assert writer.scores == []
    assert writer.features == []


def test_pipeline_marks_run_failed_on_step_exception():
    runner, reader, writer = _build_runner()
    reader.fail_nav = True

    with pytest.raises(RuntimeError):
        runner.run()

    assert writer.status == "failed"
    assert "nav_history unavailable" in writer.finish_kwargs["error_message"]


class FakeIngestionFetcher:
    """Stands in for MarketDataFetcher; records what the runner asked for."""

    def __init__(self, nav_rows, benchmark_rows=None, bench_errors=None):
        self.nav_rows = nav_rows
        self.benchmark_rows = benchmark_rows or []
        self.bench_errors = bench_errors or []
        self.nav_calls = []
        self.benchmark_calls = []

    def fetch_nav(self, scheme_codes, since=None):
        self.nav_calls.append({"codes": list(scheme_codes), "since": since})
        return list(self.nav_rows), []

    def fetch_benchmarks(self, benchmark_codes, from_date, to_date, since=None):
        self.benchmark_calls.append(
            {
                "codes": list(benchmark_codes),
                "from_date": from_date,
                "to_date": to_date,
                "since": since,
            }
        )
        return list(self.benchmark_rows), list(self.bench_errors)


class DatedFakeReader(FakeReader):
    """Reader that reports stored dates so incremental fetches can be asserted."""

    def latest_nav_dates(self):
        return {"100001": AS_OF - timedelta(days=5)}

    def latest_benchmark_dates(self):
        return {"NIFTY100_TRI": AS_OF - timedelta(days=5)}


def _build_ingesting_runner(reader=None, fetcher=None):
    benchmark_rows = _all_benchmark_rows()
    reader = reader or FakeReader(SCHEMES, _all_nav_rows(), benchmark_rows)
    writer = FakeWriter()
    fetcher = fetcher or FakeIngestionFetcher(
        _all_nav_rows(), [{**row, "source": "nse"} for row in benchmark_rows]
    )
    runner = PipelineRunner(
        as_of_date=AS_OF,
        reader=reader,
        writer=writer,
        fetcher=fetcher,
        skip_ingest=False,
    )
    return runner, reader, writer, fetcher


def test_first_run_resolves_benchmarks_before_fetching():
    """Fresh DB: benchmark_codes() is empty, so the runner resolves in memory."""
    fresh_reader = FakeReader(SCHEMES, _all_nav_rows(), [])
    runner, _, writer, fetcher = _build_ingesting_runner(reader=fresh_reader)

    stats = runner.run()

    assert stats["status"] == "completed"
    assert stats["ingestion_errors"] == 0
    assert [call["codes"] for call in fetcher.benchmark_calls] == [
        ["NIFTY100_TRI", "NIFTY500_TRI"]
    ]
    assert stats["nav_rows_ingested"] == 3 * 900
    assert len(writer.benchmark_history) == len(fetcher.benchmark_rows)
    # Resolution still persists the mappings it used for the fetch.
    assert {row["benchmark_code"] for row in writer.benchmarks} == {
        "NIFTY100_TRI",
        "NIFTY500_TRI",
    }


def test_ingestion_fetches_resolved_benchmarks_alongside_manual_mappings():
    """Fresh CSV with partial manual mappings: fetch manual + newly resolved."""
    schemes = [
        {**SCHEMES[0], "benchmark_index": "CRISIL_HYBRID_35_65"},
        {**SCHEMES[1], "benchmark_index": None},
        {**SCHEMES[2], "benchmark_index": None},
    ]
    reader = FakeReader(
        schemes, _all_nav_rows(), _benchmark_rows("CRISIL_HYBRID_35_65")
    )
    runner, _, _, fetcher = _build_ingesting_runner(reader=reader)

    runner.run()

    assert fetcher.benchmark_calls[0]["codes"] == [
        "CRISIL_HYBRID_35_65",
        "NIFTY100_TRI",
        "NIFTY500_TRI",
    ]


def test_ingestion_passes_stored_dates_for_incremental_fetch():
    dated_reader = DatedFakeReader(SCHEMES, _all_nav_rows(), [])
    runner, _, _, fetcher = _build_ingesting_runner(reader=dated_reader)

    runner.run()

    assert fetcher.nav_calls[0]["since"] == {"100001": AS_OF - timedelta(days=5)}
    assert fetcher.benchmark_calls[0]["since"] == {
        "NIFTY100_TRI": AS_OF - timedelta(days=5)
    }
    assert fetcher.benchmark_calls[0]["to_date"] == AS_OF


def test_benchmark_fetch_errors_mark_run_partial():
    runner, _, writer, fetcher = _build_ingesting_runner()
    fetcher.bench_errors = ["NIFTY100_TRI: rate limited"]

    stats = runner.run()

    assert stats["status"] == "partial"
    assert "NIFTY100_TRI: rate limited" in stats["errors"]
    assert stats["ingestion_errors"] == 1
    assert writer.status == "partial"
