"""NSE Total Return Index fetcher tests (no network)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from ingestion.fetchers import NseIndicesFetcher


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _row(day: str, value: str) -> dict:
    return {
        "RequestNumber": "TRI1",
        "Index Name": "Nifty 100",
        "Date": day,
        "TotalReturnsIndex": value,
        "NTR_Value": "1",
    }


def test_fetch_index_history_parses_and_sorts_points(monkeypatch):
    payload = [
        _row("03 Oct 2026", "23000.50"),
        _row("01 Oct 2026", "22800.10"),
        _row("02 Oct 2026", "22,900.25"),
    ]
    requests: list[dict] = []

    def fake_post(url, **kwargs):
        requests.append({"url": url, "kwargs": kwargs})
        return FakeResponse(payload)

    fetcher = NseIndicesFetcher()
    monkeypatch.setattr(fetcher, "_post_with_retry", fake_post)

    records = fetcher.fetch_index_history(
        "NIFTY100_TRI", date(2026, 10, 1), date(2026, 10, 3)
    )

    assert [r.index_date for r in records] == [
        date(2026, 10, 1),
        date(2026, 10, 2),
        date(2026, 10, 3),
    ]
    assert [r.index_value for r in records] == [22800.10, 22900.25, 23000.50]
    assert all(r.benchmark_code == "NIFTY100_TRI" for r in records)

    sent = requests[0]
    assert sent["url"].endswith("getTotalReturnIndexString")
    cinfo = json.loads(sent["kwargs"]["json"]["cinfo"])
    assert cinfo["name"] == "NIFTY 100"
    assert cinfo["startDate"] == "10/01/2026"
    assert cinfo["endDate"] == "10/03/2026"


def test_fetch_index_history_chunks_ranges_over_one_year(monkeypatch):
    calls: list[str] = []

    def fake_post(url, **kwargs):
        cinfo = json.loads(kwargs["json"]["cinfo"])
        calls.append(cinfo["endDate"])
        return FakeResponse([])

    fetcher = NseIndicesFetcher()
    fetcher.CHUNK_DAYS = 330
    monkeypatch.setattr(fetcher, "_post_with_retry", fake_post)

    fetcher.fetch_index_history("NIFTY50_TRI", date(2025, 1, 1), date(2026, 10, 1))

    # 638 days -> 330 + 308, so two windows
    assert len(calls) == 2
    assert calls[0] == "11/27/2025"
    assert calls[1] == "10/01/2026"


def test_fetch_index_history_accepts_legacy_d_envelope(monkeypatch):
    payload = {"d": json.dumps([_row("01 Oct 2026", "100")])}

    fetcher = NseIndicesFetcher()
    monkeypatch.setattr(
        fetcher, "_post_with_retry", lambda *a, **k: FakeResponse(payload)
    )

    records = fetcher.fetch_index_history(
        "NIFTY50_TRI", date(2026, 10, 1), date(2026, 10, 2)
    )

    assert len(records) == 1
    assert records[0].index_value == 100.0


def test_unsupported_benchmark_raises_not_implemented():
    fetcher = NseIndicesFetcher()

    with pytest.raises(NotImplementedError):
        fetcher.fetch_index_history(
            "CRISIL_HYBRID_35_65", date(2026, 1, 1), date(2026, 2, 1)
        )


def test_unparseable_rows_are_skipped(monkeypatch):
    payload = [
        _row("01 Oct 2026", "100"),
        {"Date": "not a date", "TotalReturnsIndex": "200"},
        {"Date": "02 Oct 2026", "TotalReturnsIndex": "-"},
    ]

    fetcher = NseIndicesFetcher()
    monkeypatch.setattr(
        fetcher, "_post_with_retry", lambda *a, **k: FakeResponse(payload)
    )

    records = fetcher.fetch_index_history(
        "NIFTY50_TRI", date(2026, 10, 1), date(2026, 10, 2)
    )

    assert [r.index_value for r in records] == [100.0]


def test_non_json_payload_raises_ingestion_error(monkeypatch):
    from ingestion.fetchers import IngestionError

    fetcher = NseIndicesFetcher()
    monkeypatch.setattr(
        fetcher, "_post_with_retry", lambda *a, **k: FakeResponse(ValueError("bad"))
    )

    with pytest.raises(IngestionError):
        fetcher.fetch_index_history("NIFTY50_TRI", date(2026, 10, 1), date(2026, 10, 2))


def test_fetch_latest_indices_skips_failures(monkeypatch):
    fetcher = NseIndicesFetcher()

    def fake_history(code, start, end):
        if code == "NIFTY50_TRI":
            from ingestion.fetchers import BenchmarkRecord, DataSource

            return [
                BenchmarkRecord(
                    benchmark_code=code,
                    index_date=date(2026, 10, 1),
                    index_value=1.0,
                    source=DataSource.NSE_INDICES,
                ),
                BenchmarkRecord(
                    benchmark_code=code,
                    index_date=date(2026, 10, 2),
                    index_value=2.0,
                    source=DataSource.NSE_INDICES,
                ),
            ]
        raise NotImplementedError(code)

    monkeypatch.setattr(fetcher, "fetch_index_history", fake_history)

    records = fetcher.fetch_latest_indices()

    assert len(records) == 1
    assert records[0].index_date == date(2026, 10, 2)
