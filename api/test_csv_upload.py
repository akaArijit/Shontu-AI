"""CSV upload persistence tests (routes called directly with a fake cursor)."""

from __future__ import annotations

import asyncio
import io
from contextlib import contextmanager

import pytest
from fastapi import UploadFile

from api.routes import csv_upload


class FakeCursor:
    def __init__(self, existing_codes=()):
        self.existing_codes = set(existing_codes)
        self.executed: list[tuple[str, dict]] = []
        self.executed_many: list[tuple[str, list[dict]]] = []
        self._rows = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "SELECT scheme_code FROM scheme_master" in sql:
            self._rows = [{"scheme_code": code} for code in self.existing_codes]

    def executemany(self, sql, rows):
        self.executed_many.append((sql, list(rows)))

    def fetchall(self):
        return self._rows


def _fake_cursor_ctx(cursor, calls):
    @contextmanager
    def _ctx():
        calls.append(cursor)
        yield cursor

    return _ctx


def _upload(content: str, name: str = "schemes.csv") -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(content.encode("utf-8")))


SCHEME_CSV = """scheme_code,scheme_name,amc,category,benchmark_index,is_active
100001,Alpha Large Cap Fund,Alpha AMC,Large Cap,NIFTY100_TRI,true
100002,Beta Large Cap Fund,Beta AMC,Large Cap,,true
"""


def test_upload_persists_new_schemes_and_skips_existing(monkeypatch):
    cursor = FakeCursor(existing_codes={"100002"})
    calls = []
    monkeypatch.setattr(csv_upload, "get_cursor", _fake_cursor_ctx(cursor, calls))

    response = asyncio.run(
        csv_upload.upload_scheme_master_csv(
            _upload(SCHEME_CSV), dry_run=False, overwrite=False
        )
    )

    assert response.persisted_rows == 1
    assert response.skipped_rows == 1
    assert "1 persisted" in response.message

    written = {
        row["scheme_code"]
        for sql, rows in cursor.executed_many
        if "INSERT INTO scheme_master" in sql
        for row in rows
    }
    assert written == {"100001"}
    assert any("INSERT INTO benchmark_master" in sql for sql, _ in cursor.executed_many)
    assert any("INSERT INTO scheme_master" in sql for sql, _ in cursor.executed_many)


def test_upload_dry_run_never_touches_the_database(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("database must not be used for a dry run")

    monkeypatch.setattr(csv_upload, "get_cursor", _explode)

    response = asyncio.run(
        csv_upload.upload_scheme_master_csv(
            _upload(SCHEME_CSV), dry_run=True, overwrite=False
        )
    )

    assert response.valid_rows == 2
    assert response.persisted_rows == 0


def test_upload_rejects_invalid_rows_without_writing(monkeypatch):
    cursor = FakeCursor()
    calls = []
    monkeypatch.setattr(csv_upload, "get_cursor", _fake_cursor_ctx(cursor, calls))

    bad_csv = """scheme_code,scheme_name,amc,category
100003,Gamma Fund,Gamma AMC,Not A Category
"""
    response = asyncio.run(
        csv_upload.upload_scheme_master_csv(
            _upload(bad_csv), dry_run=False, overwrite=False
        )
    )

    assert response.valid_rows == 0
    assert response.invalid_rows == 1
    assert calls == []  # nothing to persist -> no connection opened


def test_benchmark_mapping_upload_applies_known_schemes(monkeypatch):
    cursor = FakeCursor(existing_codes={"100001"})
    calls = []
    monkeypatch.setattr(csv_upload, "get_cursor", _fake_cursor_ctx(cursor, calls))

    mapping_csv = """scheme_code,benchmark_code
100001,NIFTY500_TRI
999999,NIFTY100_TRI
"""
    response = asyncio.run(
        csv_upload.upload_benchmark_mappings_csv(_upload(mapping_csv), dry_run=False)
    )

    assert response["persisted_rows"] == 1
    assert response["skipped_rows"] == 1

    updates = [
        row
        for sql, rows in cursor.executed_many
        if "UPDATE scheme_master" in sql
        for row in rows
    ]
    assert updates == [{"scheme_code": "100001", "benchmark_index": "NIFTY500_TRI"}]


BENCHMARK_HISTORY_CSV = """benchmark_code,index_date,index_value
NIFTY100_TRI,2026-09-30,22000.5
NIFTY100_TRI,2026-10-01,"22,100.25"
NIFTY500_TRI,01-10-2026,18000
NIFTY100_TRI,2026-10-01,99999
"""


def test_benchmark_history_upload_dedupes_and_persists(monkeypatch):
    cursor = FakeCursor()
    calls = []
    monkeypatch.setattr(csv_upload, "get_cursor", _fake_cursor_ctx(cursor, calls))

    response = asyncio.run(
        csv_upload.upload_benchmark_history_csv(
            _upload(BENCHMARK_HISTORY_CSV, "history.csv"), dry_run=False
        )
    )

    assert response["valid_rows"] == 3
    assert response["duplicate_rows"] == 1
    assert response["persisted_rows"] == 3
    assert response["benchmarks"] == ["NIFTY100_TRI", "NIFTY500_TRI"]

    # Benchmark master placeholders must exist before history (FK).
    benchmark_sql = [
        (sql, rows)
        for sql, rows in cursor.executed_many
        if "INSERT INTO benchmark_master" in sql
    ]
    assert len(benchmark_sql) == 1
    assert {row["benchmark_code"] for row in benchmark_sql[0][1]} == {
        "NIFTY100_TRI",
        "NIFTY500_TRI",
    }

    history_rows = [
        row
        for sql, rows in cursor.executed_many
        if "INSERT INTO benchmark_history" in sql
        for row in rows
    ]
    assert len(history_rows) == 3
    # Later duplicate wins and dates are normalised to date objects
    duplicate = [
        row
        for row in history_rows
        if row["benchmark_code"] == "NIFTY100_TRI"
        and row["index_date"].isoformat() == "2026-10-01"
    ]
    assert duplicate[0]["index_value"] == 99999.0
    assert all(row["source"] == "csv" for row in history_rows)


def test_benchmark_history_upload_rejects_bad_rows(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("invalid rows must not touch the database")

    monkeypatch.setattr(csv_upload, "get_cursor", _explode)

    bad_csv = """benchmark_code,index_date,index_value
NIFTY100_TRI,not-a-date,100
NIFTY100_TRI,2026-10-01,not-a-number
,2026-10-01,100
NIFTY100_TRI,2026-10-01,-5
"""
    response = asyncio.run(
        csv_upload.upload_benchmark_history_csv(
            _upload(bad_csv, "bad.csv"), dry_run=False
        )
    )

    assert response["valid_rows"] == 0
    assert response["invalid_rows"] == 4
    assert response["persisted_rows"] == 0
    assert response["success"] is False


def test_benchmark_history_upload_dry_run(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("dry run must not open a connection")

    monkeypatch.setattr(csv_upload, "get_cursor", _explode)

    response = asyncio.run(
        csv_upload.upload_benchmark_history_csv(
            _upload(BENCHMARK_HISTORY_CSV, "history.csv"), dry_run=True
        )
    )

    assert response["valid_rows"] == 3
    assert response["persisted_rows"] == 0
    assert response["success"] is True


def test_scheme_upload_accepts_excel_bom_and_uppercase_extension(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("dry run must not open a connection")

    monkeypatch.setattr(csv_upload, "get_cursor", _explode)

    response = asyncio.run(
        csv_upload.upload_scheme_master_csv(
            _upload("\ufeff" + SCHEME_CSV, "SCHEMES.CSV"), dry_run=True, overwrite=False
        )
    )

    assert response.valid_rows == 2
    assert response.invalid_rows == 0


def test_benchmark_history_accepts_excel_bom(monkeypatch):
    monkeypatch.setattr(csv_upload, "get_cursor", lambda *a, **k: None)

    response = asyncio.run(
        csv_upload.upload_benchmark_history_csv(
            _upload("\ufeff" + BENCHMARK_HISTORY_CSV, "history.CSV"), dry_run=True
        )
    )

    assert response["valid_rows"] == 3
    assert response["success"] is True


def test_non_csv_upload_is_rejected():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            csv_upload.upload_benchmark_history_csv(
                _upload("a,b\n1,2", "history.txt"), dry_run=True
            )
        )

    assert exc_info.value.status_code == 400
