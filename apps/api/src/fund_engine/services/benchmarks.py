#!/usr/bin/env python3
"""
Backfill benchmark (Total Return Index) history from niftyindices.com.

The nightly pipeline fetches benchmarks incrementally, but a fresh deployment
needs a one-off backfill before alpha/correlation metrics can be computed.

Usage:
    python -m fund_engine.services.benchmarks                    # 6 years
    python -m fund_engine.services.benchmarks --years 3
    python -m fund_engine.services.benchmarks --codes NIFTY100_TRI,NIFTY500_TRI
    python -m fund_engine.services.benchmarks --dry-run

The thin wrapper at ``scripts/seed_benchmarks.py`` accepts the same arguments.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from fund_engine.core.logging import configure_logging
from fund_engine.core.paths import CONFIG_DIR
from fund_engine.db.queries import DatabaseReader
from fund_engine.db.writer import DatabaseWriter, NullWriter
from fund_engine.domain.resolution.benchmark_mapping import BenchmarkResolver
from fund_engine.ingestion.fetchers import NseIndicesFetcher

logger = logging.getLogger(__name__)

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

    configure_logging()

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

    resolver = BenchmarkResolver(
        explicit_mapping_path=CONFIG_DIR / "explicit_benchmark_mappings.json"
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
