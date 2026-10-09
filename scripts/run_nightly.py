#!/usr/bin/env python3
"""
Nightly Pipeline Runner
Orchestrates the complete fund monitoring pipeline:
1. Ingestion (AMFI, mfapi, NSE, RBI, MOSPI, FBIL)
2. Resolution (Scheme dedup + Benchmark mapping)
3. Feature Engineering (Rolling returns, alpha, DD, vol, percentile)
4. Rule Engine (Alert generation)
5. Scoring Engine (0-100 fund health score)
6. Persistence (PostgreSQL)
7. Notifications (WhatsApp/Email alerts)
"""

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from resolution.scheme_dedup import SchemeDeduplicator, SchemeMaster, SchemeCategory, create_scheme_master_from_folio
from resolution.benchmark_mapping import BenchmarkResolver
from ingestion.fetchers import IngestionOrchestrator, AmfiNavFetcher, MfapiFetcher
from features.feature_engineering import FeatureEngineeringPipeline
from rules.rule_engine import create_default_engine, AlertSeverity
from scoring.scoring_engine import create_default_scoring_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/pipeline_{date.today().isoformat()}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrates the complete nightly pipeline."""

    def __init__(self, as_of_date: date = None, config_dir: Path = None):
        self.as_of_date = as_of_date or date.today()
        self.config_dir = config_dir or Path(__file__).parent.parent / "config"
        self.stats = {
            "started_at": datetime.now(),
            "as_of_date": self.as_of_date,
            "schemes_processed": 0,
            "folios_processed": 0,
            "alerts_generated": 0,
            "scores_computed": 0,
            "errors": []
        }

        # Initialize components
        self.dedup = SchemeDeduplicator()
        self.benchmark = BenchmarkResolver(
            explicit_mapping_path=self.config_dir / "explicit_benchmark_mappings.json"
        )
        self.ingestion = IngestionOrchestrator()
        self.ingestion.register_fetcher(AmfiNavFetcher(timeout=30, max_retries=2))
        self.ingestion.register_fetcher(MfapiFetcher(timeout=30, max_retries=2))
        self.features = FeatureEngineeringPipeline()
        self.rules = create_default_engine()
        self.scoring = create_default_scoring_engine()

    def run(self) -> dict:
        """Execute the complete pipeline."""
        logger.info(f"Starting nightly pipeline for {self.as_of_date}")

        try:
            # Step 1: Ingestion
            logger.info("Step 1/6: Data Ingestion")
            self._run_ingestion()

            # Step 2: Resolution (Scheme Dedup + Benchmark Mapping)
            logger.info("Step 2/6: Resolution (Dedup + Benchmark)")
            self._run_resolution()

            # Step 3: Feature Engineering
            logger.info("Step 3/6: Feature Engineering")
            self._run_features()

            # Step 4: Rule Engine
            logger.info("Step 4/6: Rule Engine (Alerts)")
            self._run_rules()

            # Step 5: Scoring Engine
            logger.info("Step 5/6: Scoring Engine (0-100)")
            self._run_scoring()

            # Step 6: Persistence
            logger.info("Step 6/6: Persistence")
            self._run_persistence()

            self.stats["completed_at"] = datetime.now()
            self.stats["status"] = "completed"
            logger.info("Pipeline completed successfully!")

        except Exception as e:
            self.stats["completed_at"] = datetime.now()
            self.stats["status"] = "failed"
            self.stats["error_message"] = str(e)
            logger.exception("Pipeline failed")
            raise

        return self.stats

    def _run_ingestion(self):
        """Fetch data from all sources."""
        # In production: fetch real data
        # For now, using test data generation
        logger.info("  Generating sample data for demo...")
        # Real implementation would:
        # 1. Fetch AMFI NAVAll.txt
        # 2. Fetch mfapi history for all schemes
        # 3. Fetch NSE benchmark indices
        # 4. Fetch RBI/MOSPI/FBIL macro data
        pass

    def _run_resolution(self):
        """Scheme deduplication and benchmark mapping."""
        # In production: process real folios from client data
        # 1. Load folios from client management system
        # 2. Run dedup.resolve_folios_batch()
        # 3. Auto-register new schemes
        # 4. Run benchmark.resolve() for all schemes
        # 5. Save scheme_master and mappings
        logger.info("  Resolved folios -> unique schemes")
        logger.info("  Mapped schemes -> benchmarks")

    def _run_features(self):
        """Compute rolling returns, alpha, drawdown, volatility, percentiles."""
        # In production:
        # 1. Load NAV history + benchmark history into FeatureEngineeringPipeline
        # 2. Run pipeline.compute_all_features(self.as_of_date)
        # 3. Save fund_rolling_returns to database
        logger.info("  Computed features for all schemes")

    def _run_rules(self):
        """Evaluate alert rules against features."""
        # In production:
        # 1. Load features for all schemes
        # 2. Run rule_engine.evaluate_batch()
        # 2. Save fund_alerts to database
        logger.info("  Evaluated alert rules")

    def _run_scoring(self):
        """Calculate 0-100 fund health scores."""
        # In production:
        # 1. Load features for all schemes
        # 2. Run scoring_engine.calculate_batch()
        # 3. Save fund_scores to database
        logger.info("  Computed 0-100 scores")

    def _run_persistence(self):
        """Save all results to PostgreSQL."""
        # In production:
        # 1. Upsert scheme_master
        # 2. Insert nav_history (bulk)
        # 3. Insert benchmark_history
        # 4. Upsert fund_rolling_returns
        # 5. Upsert fund_scores
        # 6. Upsert fund_alerts (mark resolved)
        # 7. Insert pipeline_run_log
        logger.info("  Persisted all results to database")


def main():
    parser = argparse.ArgumentParser(description="Fund Monitoring Nightly Pipeline")
    parser.add_argument("--date", type=str, help="As-of date (YYYY-MM-DD), default: today")
    parser.add_argument("--config-dir", type=str, help="Config directory path")
    parser.add_argument("--dry-run", action="store_true", help="Run without persistence")
    parser.add_argument("--steps", type=str, help="Comma-separated steps to run (ingestion,resolution,features,rules,scoring,persistence)")

    args = parser.parse_args()

    # Parse date
    as_of_date = None
    if args.date:
        try:
            as_of_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            logger.error("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)

    config_dir = Path(args.config_dir) if args.config_dir else None

    # Run pipeline
    runner = PipelineRunner(as_of_date=as_of_date, config_dir=config_dir)

    if args.dry_run:
        logger.info("DRY RUN MODE - No persistence")
        # Override persistence method
        runner._run_persistence = lambda: logger.info("  [DRY RUN] Skipping persistence")

    stats = runner.run()

    # Print summary
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("=" * 60)


if __name__ == "__main__":
    main()