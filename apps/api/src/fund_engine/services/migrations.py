"""Apply SQL migrations in order and record them in ``schema_migrations``.

The runner is idempotent: files already recorded with the same checksum are
skipped, so it is safe to run on every deploy. Modified migration files are
rejected - add a new numbered migration instead.

Usage (from ``apps/api``)::

    python -m fund_engine.services.migrations              # apply pending
    python -m fund_engine.services.migrations --dry-run    # list pending
    python -m fund_engine.services.migrations --baseline   # mark all applied
                                                           # (existing DB)

The thin wrapper at ``scripts/apply_migrations.py`` accepts the same arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Iterable

from fund_engine.core.paths import MIGRATIONS_DIR
from fund_engine.core.settings import database_url

TRACKING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

LOCK_KEY = "fund_engine_schema_migrations"


def migration_files() -> list[Path]:
    """Return migration files in lexicographic (numeric prefix) order."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No migrations found in {MIGRATIONS_DIR}")
    return files


def checksum(path: Path) -> str:
    """SHA-256 of a migration file, used to detect edits after apply."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(
    files: Iterable[Path], applied: dict[str, str]
) -> tuple[list[Path], list[str]]:
    """Split files into pending migrations and already-applied files that changed."""
    pending: list[Path] = []
    changed: list[str] = []
    for path in files:
        digest = checksum(path)
        if path.name not in applied:
            pending.append(path)
        elif applied[path.name] != digest:
            changed.append(path.name)
    return pending, changed


def apply_migrations(
    conn,
    files: list[Path],
    *,
    baseline: bool = False,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Apply (or plan) migrations on an open psycopg2 connection."""
    with conn.cursor() as cur:
        cur.execute(TRACKING_TABLE_SQL)
        cur.execute("SELECT pg_advisory_lock(hashtext(%s))", (LOCK_KEY,))
    conn.commit()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT filename, checksum FROM schema_migrations")
            applied = dict(cur.fetchall())

        pending, changed = classify(files, applied)
        if changed:
            raise RuntimeError(
                "Already-applied migration files were modified: "
                + ", ".join(changed)
                + ". Add a new migration instead."
            )

        if baseline:
            with conn.cursor() as cur:
                for path in pending:
                    cur.execute(
                        "INSERT INTO schema_migrations (filename, checksum) "
                        "VALUES (%s, %s) ON CONFLICT (filename) DO NOTHING",
                        (path.name, checksum(path)),
                    )
            conn.commit()
            return {"baseline": [path.name for path in pending], "applied": []}

        if dry_run:
            return {"pending": [path.name for path in pending], "applied": []}

        applied_now: list[str] = []
        for path in pending:
            sql = path.read_text(encoding="utf-8")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                        (path.name, checksum(path)),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            applied_now.append(path.name)

        return {"pending": [], "applied": applied_now}
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (LOCK_KEY,))
            conn.commit()
        except Exception:
            conn.rollback()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=database_url(),
        help="Postgres URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List pending migrations without applying"
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Mark all pending files as applied (for a manually created schema)",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2

    files = migration_files()
    try:
        import psycopg2
    except ImportError:
        print("error: psycopg2 is not installed (pip install psycopg2-binary)", file=sys.stderr)
        return 2

    conn = psycopg2.connect(args.database_url)
    try:
        result = apply_migrations(
            conn, files, baseline=args.baseline, dry_run=args.dry_run
        )
    finally:
        conn.close()

    if args.baseline:
        print(f"Baseline complete. Marked {len(result['baseline'])} file(s) as applied.")
        for name in result["baseline"]:
            print(f"  = {name}")
    elif args.dry_run:
        if result["pending"]:
            print("Pending migrations:")
            for name in result["pending"]:
                print(f"  + {name}")
        else:
            print("No pending migrations.")
    elif result["applied"]:
        print(f"Applied {len(result['applied'])} migration(s):")
        for name in result["applied"]:
            print(f"  + {name}")
    else:
        print("No pending migrations.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
