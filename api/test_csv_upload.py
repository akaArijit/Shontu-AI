"""CSV upload persistence tests (routes called directly with a fake cursor)."""

from __future__ import annotations

import asyncio
import io
from contextlib import contextmanager

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
