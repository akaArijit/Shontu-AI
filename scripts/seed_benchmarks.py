#!/usr/bin/env python3
"""
Backfill benchmark (Total Return Index) history from niftyindices.com.

The nightly pipeline fetches benchmarks incrementally, but a fresh deployment
needs a one-off backfill before alpha/correlation metrics can be computed.

Usage:
    python scripts/seed_benchmarks.py                    # 6 years, all mapped codes
    python scripts/seed_benchmarks.py --years 3
    python scripts/seed_benchmarks.py --codes NIFTY100_TRI,NIFTY500_TRI
    python scripts/seed_benchmarks.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.queries import DatabaseReader
from db.writer import DatabaseWriter, NullWriter
from ingestion.fetchers import NseIndicesFetcher
from resolution.benchmark_mapping import BenchmarkResolver

logger = logging.getLogger("seed_benchmarks")

DEFAULT_CHUNK_DAYS = NseIndicesFetcher.CHUNK_DAYS
BENCHMARK_NAMES = dict(NseIndicesFetcher.INDEX_MAPPING)


def resolve_benchmark_codes(
    reader: DatabaseReader,
    resolver: BenchmarkResolver,
    explicit: Optional[Iterable[str]] = None,
) -> list[str]:
    """Choose benchmarks to backfill: explicit > stored mappings > resolver.

    Database errors are treated as "no data" so ``--codes`` still works on a
    machine without database access.
    """
    if explicit:
        return sorted({code.strip() for code in explicit if code and code.strip()})

    try:
        stored = reader.benchmark_codes()
    except Exception as exc:  # noqa: BLE001 - allow offline runs with --codes
        logger.warning("Could not read stored benchmark codes: %s", exc)
        stored = []
    if stored:
        return sorted(stored)

    try:
        schemes = reader.active_schemes()
    except Exception as exc:  # noqa: BLE001 - allow offline runs with --codes
        logger.warning("Could not read active schemes: %s", exc)
        return []

    return sorted(
        {
            resolver.resolve(
                scheme["scheme_code"],
                scheme["scheme_name"],
                scheme.get("category") or "Unclassified",
            ).benchmark_code.value
            for scheme in schemes
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill NSE TRI benchmark history")
    parser.add_argument("--years", type=int, default=6)
    parser.add_argument("--from-date", type=str)
    parser.add_argument("--to-date", type=str)
    parser.add_argument("--codes", type=str, help="Comma-separated benchmark codes")
    parser.add_argument("--chunk-days", type=int, default=DEFAULT_CHUNK_DAYS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    to_date = (
        datetime.strptime(args.to_date, "%Y-%m-%d").date()
        if args.to_date
        else date.today()
    )
    from_date = (
        datetime.strptime(args.from_date, "%Y-%m-%d").date()
        if args.from_date
        else to_date - timedelta(days=365 * args.years)
    )

    config_dir = Path(__file__).parent.parent / "config"
    resolver = BenchmarkResolver(
        explicit_mapping_path=config_dir / "explicit_benchmark_mappings.json"
    )
    reader = DatabaseReader()
    writer = NullWriter() if args.dry_run else DatabaseWriter()

    codes = resolve_benchmark_codes(
        reader,
        resolver,
        [code for code in (args.codes or "").split(",") if code.strip()] or None,
    )
    if not codes:
        logger.error(
            "No benchmark codes found. Upload a scheme master first or pass --codes."
        )
        return 2

    fetcher = NseIndicesFetcher(timeout=60, max_retries=3)
    fetcher.CHUNK_DAYS = args.chunk_days

    logger.info("Backfilling %s -> %s for %d benchmarks", from_date, to_date, len(codes))

    if not args.dry_run:
        writer.upsert_benchmarks(
            [
                {
                    "benchmark_code": code,
                    "benchmark_name": BENCHMARK_NAMES.get(code, code),
                    "category": None,
                }
                for code in codes
            ]
        )

    total_rows = 0
    succeeded = 0
    failed = 0
    for code in codes:
        try:
            records = fetcher.fetch_index_history(code, from_date, to_date)
        except NotImplementedError as exc:
            logger.warning("Skipping %s: %s", code, exc)
            failed += 1
            continue
        except Exception as exc:  # noqa: BLE001 - continue with other benchmarks
            logger.error("Failed to fetch %s: %s", code, exc)
            failed += 1
            continue

        if not records:
            logger.warning("No data returned for %s", code)
            failed += 1
            continue

        rows = [
            {
                "benchmark_code": record.benchmark_code,
                "index_date": record.index_date,
                "index_value": record.index_value,
                "source": "nse",
            }
            for record in records
        ]
        total_rows += writer.upsert_benchmark_history(rows)
        succeeded += 1
        logger.info(
            "  %s: %d points (%s -> %s)",
            code,
            len(records),
            records[0].index_date,
            records[-1].index_date,
        )

    logger.info(
        "Done: %d benchmarks, %d rows%s (%d failed)",
        succeeded,
        total_rows,
        " (dry run)" if args.dry_run else "",
        failed,
    )
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
