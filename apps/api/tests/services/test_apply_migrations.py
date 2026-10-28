"""Tests for the migration runner (no database required)."""

from __future__ import annotations

from pathlib import Path

from fund_engine.services.migrations import (
    MIGRATIONS_DIR,
    checksum,
    classify,
    migration_files,
)


def test_migration_files_are_ordered():
    names = [path.name for path in migration_files()]

    assert names == sorted(names)
    assert names[0].startswith("001")
    assert all(path.suffix == ".sql" for path in migration_files())
    assert all(path.parent == MIGRATIONS_DIR for path in migration_files())


def test_checksum_is_stable_and_content_sensitive(tmp_path: Path):
    path = tmp_path / "001_example.sql"
    path.write_text("SELECT 1;", encoding="utf-8")

    first = checksum(path)
    second = checksum(path)

    assert first == second
    assert len(first) == 64

    path.write_text("SELECT 2;", encoding="utf-8")
    assert checksum(path) != first


def test_classify_splits_pending_and_changed(tmp_path: Path):
    applied_file = tmp_path / "001_applied.sql"
    pending_file = tmp_path / "002_pending.sql"
    changed_file = tmp_path / "003_changed.sql"
    applied_file.write_text("SELECT 1;", encoding="utf-8")
    pending_file.write_text("SELECT 2;", encoding="utf-8")
    changed_file.write_text("SELECT 3;", encoding="utf-8")

    applied = {
        applied_file.name: checksum(applied_file),
        changed_file.name: checksum(pending_file),
    }

    pending, changed = classify(
        [applied_file, pending_file, changed_file], applied
    )

    assert pending == [pending_file]
    assert changed == [changed_file.name]


def test_classify_rejects_missing_checksum_match(tmp_path: Path):
    path = tmp_path / "001_example.sql"
    path.write_text("SELECT 1;", encoding="utf-8")

    pending, changed = classify([path], {path.name: "deadbeef"})

    assert pending == []
    assert changed == [path.name]
