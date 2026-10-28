#!/usr/bin/env python3
"""
Nightly Pipeline Runner

Orchestrates the complete fund monitoring pipeline:
1. Ingestion (mfapi NAV history, optional NSE benchmarks)
2. Resolution (benchmark mapping for every active scheme)
3. Feature Engineering (rolling returns, alpha, drawdown, vol, percentiles)
4. Rule Engine (alert generation)
5. Scoring Engine (0-100 fund health score)
6. Persistence (PostgreSQL)

Each stage is isolated: ingestion failures are recorded and the run continues
with the data already in the database. The run itself is logged in
`pipeline_run_log` so the API/dashboard can report freshness.

Usage:
    python scripts/run_nightly.py                     # full run
    python scripts/run_nightly.py --no-ingest         # recompute from DB only
    python scripts/run_nightly.py --dry-run           # compute, write nothing
    python scripts/run_nightly.py --steps features,rules,scoring
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.queries import DatabaseReader
from db.writer import DatabaseWriter, NullWriter
from features.feature_engineering import FeatureEngineeringPipeline
from resolution.benchmark_mapping import BenchmarkResolver
from rules.rule_engine import create_default_engine
from scoring.scoring_engine import create_default_scoring_engine

# Configure logging (file logging is best-effort; containers may be read-only)
LOG_DIR = Path(__file__).parent.parent / "logs"
_handlers = [logging.StreamHandler(sys.stdout)]
try:
    LOG_DIR.mkdir(exist_ok=True)
    _handlers.append(
        logging.FileHandler(LOG_DIR / f"pipeline_{date.today().isoformat()}.log")
    )
except OSError:  # pragma: no cover - environment dependent
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger(__name__)

STEPS = ("ingestion", "resolution", "features", "rules", "scoring", "persistence")


class PipelineRunner:
    """Orchestrates the complete nightly pipeline."""

    def __init__(
        self,
        as_of_date: Optional[date] = None,
        config_dir: Optional[Path] = None,
        reader=None,
        writer=None,
        fetcher=None,
        skip_ingest: bool = False,
        steps: Optional[Sequence[str]] = None,
    ):
        self.as_of_date = as_of_date or date.today()
        self.config_dir = config_dir or Path(__file__).parent.parent / "config"
        self.reader = reader or DatabaseReader()
        self.writer = writer or DatabaseWriter()
        self.fetcher = fetcher
        self.skip_ingest = skip_ingest
        self.steps = tuple(steps) if steps else STEPS

        self.stats = {
            "started_at": datetime.now(),
            "as_of_date": self.as_of_date,
            "schemes_processed": 0,
            "folios_processed": 0,
            "alerts_generated": 0,
            "scores_computed": 0,
            "nav_rows_ingested": 0,
            "feature_rows": 0,
            "ingestion_errors": 0,
            "errors": [],
        }

        # Components
        self.benchmark = BenchmarkResolver(
            explicit_mapping_path=self.config_dir / "explicit_benchmark_mappings.json"
        )
        self.features_engine = FeatureEngineeringPipeline()
        self.rules = create_default_engine()
        self.scoring = create_default_scoring_engine()

        # Working state
        self.schemes: list[dict] = []
        self.feature_dicts: list[dict] = []
        self.alerts: list[dict] = []
        self.scores: list[dict] = []

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def _enabled(self, step: str) -> bool:
        return step in self.steps

    def run(self) -> dict:
        logger.info(
            "Starting nightly pipeline for %s (steps: %s)",
            self.as_of_date,
            ", ".join(self.steps),
        )

        run_id = None
        try:
            run_id = self.writer.start_run(self.as_of_date)
        except Exception as exc:  # noqa: BLE001 - pipeline should still run
            logger.warning("Could not open pipeline run log: %s", exc)
            self.stats["errors"].append(f"run_log_start: {exc}")

        try:
            if self._enabled("ingestion"):
                logger.info("Step 1/6: Data Ingestion")
                self._run_ingestion()
            if self._enabled("resolution"):
                logger.info("Step 2/6: Resolution (Benchmark Mapping)")
                self._run_resolution()
            if self._enabled("features"):
                logger.info("Step 3/6: Feature Engineering")
                self._run_features()
            if self._enabled("rules"):
                logger.info("Step 4/6: Rule Engine (Alerts)")
                self._run_rules()
            if self._enabled("scoring"):
                logger.info("Step 5/6: Scoring Engine (0-100)")
                self._run_scoring()
            if self._enabled("persistence"):
                logger.info("Step 6/6: Persistence")
                self._run_persistence()

            status = "partial" if self.stats["ingestion_errors"] else "completed"
            self._finish(run_id, status)
            logger.info("Pipeline %s for %s", status, self.as_of_date)

        except Exception as exc:  # noqa: BLE001 - logged and re-raised for cron
            logger.exception("Pipeline failed")
            self.stats["error_message"] = str(exc)
            self.stats["errors"].append(str(exc))
            self._finish(run_id, "failed")
            raise

        return self.stats

    def _finish(self, run_id, status: str) -> None:
        self.stats["completed_at"] = datetime.now()
        self.stats["status"] = status
        try:
            self.writer.finish_run(
                run_id,
                status=status,
                schemes_processed=self.stats["schemes_processed"],
                folios_processed=self.stats["folios_processed"],
                alerts_generated=self.stats["alerts_generated"],
                scores_computed=self.stats["scores_computed"],
                error_message=self.stats.get("error_message"),
                metadata={
                    "nav_rows_ingested": self.stats["nav_rows_ingested"],
                    "feature_rows": self.stats["feature_rows"],
                    "ingestion_errors": self.stats["ingestion_errors"],
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not close pipeline run log: %s", exc)

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _load_schemes(self) -> list[dict]:
        if not self.schemes:
            self.schemes = list(self.reader.active_schemes())
        return self.schemes

    def _latest_nav_dates(self) -> dict:
        """Latest stored NAV date per scheme; empty when unavailable."""
        return self._reader_dates("latest_nav_dates")

    def _latest_benchmark_dates(self) -> dict:
        """Latest stored index date per benchmark; empty when unavailable."""
        return self._reader_dates("latest_benchmark_dates")

    def _reader_dates(self, method: str) -> dict:
        loader = getattr(self.reader, method, None)
        if loader is None:
            return {}
        try:
            return loader()
        except Exception as exc:  # noqa: BLE001 - fall back to a full fetch
            logger.warning("Could not load %s: %s", method, exc)
            return {}

    def _run_ingestion(self) -> None:
        """Fetch NAV history (and benchmarks when available) with error isolation."""
        schemes = self._load_schemes()
        if not schemes:
            logger.warning("No active schemes in scheme_master - skipping ingestion")
            return

        if self.skip_ingest or self.fetcher is None:
            logger.info("  Ingestion disabled (--no-ingest or no fetcher configured)")
            return

        nav_rows, errors = self.fetcher.fetch_nav(
            [s["scheme_code"] for s in schemes], since=self._latest_nav_dates()
        )
        self.stats["ingestion_errors"] += len(errors)
        self.stats["errors"].extend(errors)
        if nav_rows:
            written = self.writer.upsert_nav(nav_rows)
            self.stats["nav_rows_ingested"] = written
        logger.info(
            "  Ingested %d NAV rows (%d scheme errors)",
            self.stats["nav_rows_ingested"],
            len(errors),
        )

        try:
            benchmark_codes = self.reader.benchmark_codes()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load benchmark codes: %s", exc)
            benchmark_codes = []

        if not benchmark_codes:
            # First run: scheme_master has no mappings yet, so resolve them
            # in memory (the resolution step persists them afterwards).
            benchmark_codes = sorted(
                {
                    self.benchmark.resolve(
                        scheme["scheme_code"],
                        scheme["scheme_name"],
                        scheme.get("category") or "Unclassified",
                    ).benchmark_code.value
                    for scheme in schemes
                }
            )

        if benchmark_codes:
            from_date = self.as_of_date - timedelta(days=365 * 6)
            bench_rows, bench_errors = self.fetcher.fetch_benchmarks(
                benchmark_codes,
                from_date,
                self.as_of_date,
                since=self._latest_benchmark_dates(),
            )
            self.stats["ingestion_errors"] += len(bench_errors)
            self.stats["errors"].extend(bench_errors)
            if bench_rows:
                self.writer.upsert_benchmark_history(bench_rows)
                logger.info("  Ingested %d benchmark rows", len(bench_rows))

    def _run_resolution(self) -> None:
        """Resolve a benchmark for every active scheme and persist mappings."""
        schemes = self._load_schemes()
        if not schemes:
            logger.warning("No active schemes - skipping benchmark resolution")
            return

        benchmark_rows: dict[str, dict] = {}
        scheme_updates: list[dict] = []
        manual = 0

        for scheme in schemes:
            # Preserve explicit mappings supplied via CSV/manual overrides.
            if scheme.get("benchmark_index"):
                manual += 1
                continue

            mapping = self.benchmark.resolve(
                scheme["scheme_code"],
                scheme["scheme_name"],
                scheme.get("category") or "Unclassified",
            )
            code = mapping.benchmark_code.value
            benchmark_rows[code] = {
                "benchmark_code": code,
                "benchmark_name": mapping.benchmark_name,
                "category": scheme.get("category"),
            }
            scheme_updates.append(
                {"scheme_code": scheme["scheme_code"], "benchmark_index": code}
            )

        if benchmark_rows:
            self.writer.upsert_benchmarks(list(benchmark_rows.values()))
        if scheme_updates:
            self.writer.update_scheme_benchmarks(scheme_updates)
        logger.info(
            "  Mapped %d schemes to %d benchmarks (%d manual mappings kept)",
            len(scheme_updates),
            len(benchmark_rows),
            manual,
        )

    def _run_features(self) -> None:
        """Compute rolling metrics from stored NAV/benchmark history."""
        schemes = self._load_schemes()
        if not schemes:
            logger.warning("No active schemes - skipping feature engineering")
            return

        nav_rows = self.reader.nav_history(self.as_of_date)
        if not nav_rows:
            logger.warning("No NAV history in database - skipping feature engineering")
            return

        benchmark_rows = self.reader.benchmark_history(self.as_of_date)
        categories = {
            s["scheme_code"]: s.get("category") or "Unclassified" for s in schemes
        }

        self.features_engine.load_nav_history(nav_rows)
        self.features_engine.load_benchmark_history(benchmark_rows)
        self.features_engine.load_scheme_categories(categories)

        features = self.features_engine.compute_all_features(self.as_of_date)
        self.feature_dicts = []
        for feature in features:
            row = feature.to_dict()
            row["category"] = categories.get(feature.scheme_code, "Unclassified")
            row["scoring_config_version"] = self.scoring.config.version
            self.feature_dicts.append(row)

        self.stats["schemes_processed"] = len(self.feature_dicts)
        self.stats["feature_rows"] = len(self.feature_dicts)
        logger.info("  Computed features for %d schemes", len(self.feature_dicts))

    def _run_rules(self) -> None:
        """Evaluate alert rules against the computed features."""
        if not self.feature_dicts:
            logger.warning("No features available - skipping rule engine")
            return

        alerts = self.rules.evaluate_batch(self.feature_dicts, self.as_of_date)
        self.alerts = [a.to_dict() for a in alerts]
        self.stats["alerts_generated"] = len(self.alerts)
        logger.info("  Generated %d alerts", len(self.alerts))

    def _run_scoring(self) -> None:
        """Calculate 0-100 health scores."""
        if not self.feature_dicts:
            logger.warning("No features available - skipping scoring")
            return

        scores = self.scoring.calculate_batch(self.feature_dicts, self.as_of_date)
        self.scores = [s.to_dict() for s in scores]
        self.stats["scores_computed"] = len(self.scores)
        logger.info("  Computed %d scores", len(self.scores))

    def _run_persistence(self) -> None:
        """Write features, scores, alerts and close the run log."""
        if self.feature_dicts:
            self.writer.upsert_features(self.feature_dicts)
        if self.scores:
            self.writer.upsert_scores(self.scores)
        if self.alerts or self.feature_dicts:
            result = self.writer.sync_alerts(self.alerts, self.as_of_date)
            logger.info(
                "  Alerts: %d new, %d updated, %d auto-resolved",
                result.get("inserted", 0),
                result.get("updated", 0),
                result.get("resolved", 0),
            )

        try:
            self.stats["folios_processed"] = self.reader.folio_count()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not count folios: %s", exc)

        logger.info(
            "  Persisted %d feature rows and %d scores",
            len(self.feature_dicts),
            len(self.scores),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fund Monitoring Nightly Pipeline")
    parser.add_argument(
        "--date", type=str, help="As-of date (YYYY-MM-DD), default: today"
    )
    parser.add_argument("--config-dir", type=str, help="Config directory path")
    parser.add_argument(
        "--dry-run", action="store_true", help="Compute without persisting"
    )
    parser.add_argument(
        "--no-ingest", action="store_true", help="Skip network ingestion"
    )
    parser.add_argument(
        "--steps",
        type=str,
        help="Comma-separated steps to run (ingestion,resolution,features,rules,scoring,persistence)",
    )
    parser.add_argument("--limit", type=int, help="Limit schemes processed (debug)")

    args = parser.parse_args()

    as_of_date = None
    if args.date:
        try:
            as_of_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            logger.error("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)

    config_dir = Path(args.config_dir) if args.config_dir else None

    steps = None
    if args.steps:
        steps = [s.strip() for s in args.steps.split(",") if s.strip()]
        unknown = [s for s in steps if s not in STEPS]
        if unknown:
            logger.error("Unknown step(s): %s", ", ".join(unknown))
            sys.exit(1)

    fetcher = None
    if not args.no_ingest:
        from ingestion.market_fetcher import MarketDataFetcher

        fetcher = MarketDataFetcher()

    runner = PipelineRunner(
        as_of_date=as_of_date,
        config_dir=config_dir,
        writer=NullWriter() if args.dry_run else DatabaseWriter(),
        fetcher=fetcher,
        skip_ingest=args.no_ingest,
        steps=steps,
    )

    if args.limit:
        original_loader = runner._load_schemes

        def limited_loader():
            return original_loader()[: args.limit]

        runner._load_schemes = limited_loader

    if args.dry_run:
        logger.info("DRY RUN MODE - results will not be persisted")

    stats = runner.run()

    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("=" * 60)


if __name__ == "__main__":
    main()
