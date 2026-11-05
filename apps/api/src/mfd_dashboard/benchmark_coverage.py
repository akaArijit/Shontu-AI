"""Diagnostics for benchmark date coverage.

This module explains which local benchmark dates are still needed.  It does not
change any return, XIRR or comparison calculation; it only re-checks the dates
that the existing comparison logic would read from the local level series.
Missing dates are reported exactly and are never interpolated.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from mfd_dashboard.benchmark_data import load_benchmark_levels
from mfd_dashboard.db.models import (
    BenchmarkLevel,
    Folio,
    SchemeBenchmark,
    Transaction,
    UploadBatch,
)
from mfd_dashboard.ingest.values import normalize_header

DEFAULT_BENCHMARK = "Other / Unmapped"
VALID_GROSS_TYPES = {"purchase", "sip", "switch_in"}
VALID_OUTFLOW_TYPES = {"redemption", "switch_out"}


def _latest_batch(db: Session) -> UploadBatch | None:
    return db.scalars(
        select(UploadBatch).order_by(UploadBatch.id.desc()).limit(1)
    ).first()


def required_dates_for_flows(
    transactions: list[Transaction],
    valuation_date: date | None,
) -> tuple[set[date], str | None, date | None]:
    """Return the exact benchmark dates a folio comparison would need."""

    if valuation_date is None:
        return set(), None, None
    valid = [
        item
        for item in transactions
        if item.transaction_date is not None
        and item.amount is not None
        and Decimal(item.amount) != 0
        and item.transaction_type in VALID_GROSS_TYPES | VALID_OUTFLOW_TYPES
    ]
    if not valid:
        return set(), "no_transactions", None
    gross = [item for item in valid if item.transaction_type in VALID_GROSS_TYPES]
    outflows = [
        item for item in valid if item.transaction_type in VALID_OUTFLOW_TYPES
    ]
    first_date = min(
        (item.transaction_date for item in gross if item.transaction_date is not None),
        default=None,
    )
    is_lump_sum = (
        len(gross) == 1
        and gross[0].transaction_type == "purchase"
        and not outflows
    )
    if is_lump_sum and gross[0].transaction_date is not None:
        return (
            {gross[0].transaction_date, valuation_date},
            "point_to_point",
            first_date,
        )
    dates = {
        item.transaction_date
        for item in valid
        if item.transaction_date is not None
    }
    dates.add(valuation_date)
    return dates, "cash_flow_xirr", first_date


def _status_for(
    *,
    review_status: str,
    required_dates: set[date],
    available_dates: set[date],
    method: str | None,
) -> str:
    if review_status == "needs_mapping":
        return "needs_mapping"
    if review_status != "reviewed":
        return "needs_review"
    if method is None or not required_dates:
        return "no_transactions"
    if not available_dates:
        return "no_levels"
    if required_dates - available_dates:
        return "missing_dates"
    return "covered"


def build_benchmark_coverage(db: Session) -> dict[str, Any]:
    batch = _latest_batch(db)
    if batch is None:
        return {
            "summary": {
                "schemes_total": 0,
                "schemes_needs_mapping": 0,
                "schemes_needs_review": 0,
                "schemes_covered": 0,
                "schemes_missing_dates": 0,
                "schemes_no_levels": 0,
                "schemes_no_transactions": 0,
                "series_total": 0,
                "series_covered": 0,
                "series_missing_dates": 0,
                "series_no_required_dates": 0,
                "valuation_date": None,
                "valuation_date_missing_in": [],
                "first_transaction_missing_in": [],
            },
            "schemes": [],
            "series": [],
        }

    levels = load_benchmark_levels(db)
    level_display_names = {
        normalize_header(item.benchmark_name): item.benchmark_name
        for item in db.scalars(select(BenchmarkLevel))
    }
    mappings = {
        item.scheme_id: item
        for item in db.scalars(
            select(SchemeBenchmark).options(
                joinedload(SchemeBenchmark.scheme)
            )
        )
    }
    folios = list(
        db.scalars(
            select(Folio)
            .where(Folio.batch_id == batch.id)
            .options(joinedload(Folio.scheme))
        )
    )
    transactions = list(
        db.scalars(
            select(Transaction).where(Transaction.batch_id == batch.id)
        )
    )
    transactions_by_folio: dict[int, list[Transaction]] = defaultdict(list)
    for item in transactions:
        if item.folio_id is not None:
            transactions_by_folio[item.folio_id].append(item)

    folios_by_scheme: dict[int, list[Folio]] = defaultdict(list)
    for folio in folios:
        if folio.scheme_id is not None:
            folios_by_scheme[folio.scheme_id].append(folio)

    scheme_coverage: list[dict[str, Any]] = []
    series: dict[str, dict[str, Any]] = {}

    for scheme_id, scheme_folios in folios_by_scheme.items():
        scheme = scheme_folios[0].scheme
        mapping = mappings.get(scheme_id)
        benchmark_name = (
            mapping.benchmark_name
            if mapping is not None
            else DEFAULT_BENCHMARK
        )
        review_status = (
            "needs_mapping"
            if mapping is None or benchmark_name == DEFAULT_BENCHMARK
            else mapping.status
        )
        required: set[date] = set()
        methods: set[str] = set()
        first_dates: list[date] = []
        for folio in scheme_folios:
            dates, method, first_date = required_dates_for_flows(
                transactions_by_folio.get(folio.id, []),
                batch.report_date,
            )
            required.update(dates)
            if method:
                methods.add(method)
            if first_date:
                first_dates.append(first_date)

        benchmark_key = normalize_header(benchmark_name)
        available = set(levels.get(benchmark_key, {}))
        missing = sorted(required - available)
        method = (
            "point_to_point"
            if methods == {"point_to_point"}
            else ("cash_flow_xirr" if methods else None)
        )
        status = _status_for(
            review_status=review_status,
            required_dates=required,
            available_dates=available,
            method=method,
        )
        covered = status in {"covered", "no_transactions"}
        item = {
            "scheme_id": scheme_id,
            "scheme_name": scheme.name if scheme is not None else "Unknown scheme",
            "benchmark_name": benchmark_name,
            "review_status": review_status,
            "coverage_status": status,
            "comparison_method": method,
            "folio_count": len(scheme_folios),
            "valuation_date": (
                batch.report_date.isoformat() if batch.report_date else None
            ),
            "first_transaction_date": (
                min(first_dates).isoformat() if first_dates else None
            ),
            "required_dates": [value.isoformat() for value in sorted(required)],
            "required_date_count": len(required),
            "available_date_count": len(available),
            "missing_dates": [value.isoformat() for value in missing],
            "missing_date_count": len(missing),
            "covers_first_transaction": (
                min(first_dates) in available if first_dates else None
            ),
            "covers_valuation_date": (
                batch.report_date in available if required else None
            ),
            "covers_all_comparison_dates": (
                not missing if required and review_status == "reviewed" else None
            ),
            "is_complete": covered,
        }
        scheme_coverage.append(item)

        if review_status == "needs_mapping":
            continue
        row = series.setdefault(
            benchmark_key,
            {
                "benchmark_name": benchmark_name,
                "benchmark_key": benchmark_key,
                "required_dates": set(),
                "available_dates": available,
                "scheme_names": [],
                "folio_count": 0,
                "methods": set(),
                "first_dates": [],
                "needs_review_count": 0,
            },
        )
        row["required_dates"].update(required)
        row["available_dates"].update(available)
        row["scheme_names"].append(item["scheme_name"])
        row["folio_count"] += len(scheme_folios)
        row["methods"].update(methods)
        row["first_dates"].extend(first_dates)
        if review_status != "reviewed":
            row["needs_review_count"] += 1

    # Also show local level series that have no mapped folios yet.  This makes
    # an accidental extra series visible without claiming it is used.
    for key, available in levels.items():
        if key in series:
            continue
        series[key] = {
            "benchmark_name": level_display_names.get(key, key),
            "benchmark_key": key,
            "required_dates": set(),
            "available_dates": available,
            "scheme_names": [],
            "folio_count": 0,
            "methods": set(),
            "first_dates": [],
            "needs_review_count": 0,
        }

    series_rows: list[dict[str, Any]] = []
    for row in series.values():
        required = set(row["required_dates"])
        available = set(row["available_dates"])
        missing = sorted(required - available)
        if not required:
            status = "no_required_dates"
        elif not missing:
            status = "covered"
        elif not available:
            status = "no_levels"
        else:
            status = "missing_dates"
        first_dates = row["first_dates"]
        method = (
            "point_to_point"
            if row["methods"] == {"point_to_point"}
            else ("cash_flow_xirr" if row["methods"] else None)
        )
        series_rows.append(
            {
                "benchmark_name": row["benchmark_name"],
                "benchmark_key": row["benchmark_key"],
                "coverage_status": status,
                "comparison_method": method,
                "scheme_names": sorted(set(row["scheme_names"])),
                "scheme_count": len(set(row["scheme_names"])),
                "folio_count": row["folio_count"],
                "needs_review_count": row["needs_review_count"],
                "first_transaction_date": (
                    min(first_dates).isoformat() if first_dates else None
                ),
                "required_date_count": len(required),
                "available_date_count": len(available),
                "missing_date_count": len(missing),
                "missing_dates": [value.isoformat() for value in missing],
                "covers_first_transaction": (
                    all(item in available for item in first_dates)
                    if first_dates
                    else None
                ),
                "covers_valuation_date": (
                    batch.report_date in available if required else None
                ),
                "covers_all_comparison_dates": (
                    not missing if required else None
                ),
                "available_first_date": (
                    min(available).isoformat() if available else None
                ),
                "available_last_date": (
                    max(available).isoformat() if available else None
                ),
            }
        )

    series_rows.sort(
        key=lambda item: (
            item["coverage_status"] == "no_required_dates",
            item["coverage_status"] == "covered",
            item["benchmark_name"].casefold(),
        )
    )

    valuation_missing_in = [
        item["benchmark_name"]
        for item in series_rows
        if item["required_date_count"]
        and item["covers_valuation_date"] is False
    ]
    first_missing_in = [
        item["benchmark_name"]
        for item in series_rows
        if item["first_transaction_date"]
        and item["covers_first_transaction"] is False
    ]
    summary = {
        "schemes_total": len(scheme_coverage),
        "schemes_needs_mapping": sum(
            1 for item in scheme_coverage if item["coverage_status"] == "needs_mapping"
        ),
        "schemes_needs_review": sum(
            1 for item in scheme_coverage if item["coverage_status"] == "needs_review"
        ),
        "schemes_covered": sum(
            1 for item in scheme_coverage if item["coverage_status"] == "covered"
        ),
        "schemes_missing_dates": sum(
            1
            for item in scheme_coverage
            if item["coverage_status"] in {"missing_dates", "no_levels"}
        ),
        "schemes_no_levels": sum(
            1 for item in scheme_coverage if item["coverage_status"] == "no_levels"
        ),
        "schemes_no_transactions": sum(
            1
            for item in scheme_coverage
            if item["coverage_status"] == "no_transactions"
        ),
        "series_total": len(series_rows),
        "series_covered": sum(
            1 for item in series_rows if item["coverage_status"] == "covered"
        ),
        "series_missing_dates": sum(
            1
            for item in series_rows
            if item["coverage_status"] in {"missing_dates", "no_levels"}
        ),
        "series_no_required_dates": sum(
            1
            for item in series_rows
            if item["coverage_status"] == "no_required_dates"
        ),
        "valuation_date": (
            batch.report_date.isoformat() if batch.report_date else None
        ),
        "valuation_date_missing_in": valuation_missing_in,
        "first_transaction_missing_in": first_missing_in,
    }
    return {
        "summary": summary,
        "schemes": sorted(
            scheme_coverage,
            key=lambda item: (
                item["coverage_status"] == "covered",
                item["scheme_name"].casefold(),
            ),
        ),
        "series": series_rows,
    }
