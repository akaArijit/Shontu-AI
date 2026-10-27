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


def _build_runner(folio_count=7):
    schemes = [
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

    nav_rows = []
    nav_rows += _nav_rows("100001", drift=0.0008)
    nav_rows += _nav_rows("100002", drift=0.0001, amplitude=0.05)
    nav_rows += _nav_rows("100003", drift=0.0005, amplitude=0.03)

    benchmark_rows = _benchmark_rows("NIFTY100_TRI") + _benchmark_rows("NIFTY500_TRI")

    reader = FakeReader(schemes, nav_rows, benchmark_rows, folio_count=folio_count)
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
