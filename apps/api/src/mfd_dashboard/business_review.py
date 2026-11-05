"""Read-only Business Review aggregation.

Milestone 5 turns the existing dashboard rows, benchmark comparison results,
local mappings and imported data into a practical review view.  This module
does not calculate returns, XIRR or benchmark comparisons.  It only groups,
filters and sorts values that already exist in the dashboard read model.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from mfd_dashboard.benchmark_data import benchmark_level_summaries
from mfd_dashboard.benchmark_mappings import list_benchmark_mappings
from mfd_dashboard.dashboard import get_dashboard

PERFORMANCE_VALUES = {
    "ahead",
    "behind",
    "in_line",
    "not_available",
    "needs_review",
}
PERFORMANCE_FILTERS = {"all", *PERFORMANCE_VALUES}
SORT_FIELDS = {"current_value", "difference", "xirr", "client_name"}
DIRECTIONS = {"asc", "desc"}
NEEDS_REVIEW_STATUSES = {
    "mapping_missing",
    "mapping_needs_review",
    "levels_missing",
}


def _performance(row: dict[str, Any]) -> str:
    """Use the same state rules as the benchmark graph and folio table."""

    status = row["benchmark_comparison_status"]
    if status in NEEDS_REVIEW_STATUSES:
        return "needs_review"
    if status != "available" or row["benchmark_difference"] is None:
        return "not_available"
    if row["benchmark_difference"] > 0:
        return "ahead"
    if row["benchmark_difference"] < 0:
        return "behind"
    return "in_line"


def _client_key(row: dict[str, Any]) -> str:
    if row["client_id"] is None:
        return "unmatched"
    return str(row["client_id"])


def _client_options(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _client_key(row)
        item = grouped.get(key)
        if item is None:
            grouped[key] = {
                "key": key,
                "name": (
                    "Unmatched client"
                    if row["client_id"] is None
                    else row["client_name"]
                ),
                "count": 1,
            }
        else:
            item["count"] += 1
    return sorted(
        grouped.values(),
        key=lambda item: (item["name"].casefold(), item["key"]),
    )


def _benchmark_options(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["benchmark_name"]] += 1
    return [
        {"name": name, "count": count}
        for name, count in sorted(
            counts.items(), key=lambda item: item[0].casefold()
        )
    ]


def _sort_folios(
    rows: list[dict[str, Any]], sort: str, direction: str
) -> list[dict[str, Any]]:
    reverse = direction == "desc"
    if sort == "client_name":
        return sorted(
            rows,
            key=lambda row: (
                row["client_name"].casefold(),
                row["folio_number"].casefold(),
            ),
            reverse=reverse,
        )

    field = {
        "current_value": "aum",
        "difference": "benchmark_difference",
        "xirr": "xirr",
    }[sort]
    present = [row for row in rows if row[field] is not None]
    missing = [row for row in rows if row[field] is None]
    present.sort(
        key=lambda row: (
            row[field],
            row["client_name"].casefold(),
            row["folio_number"].casefold(),
        ),
        reverse=reverse,
    )
    # A missing value is a data gap, not a zero.  Keep those rows visible at the
    # end regardless of the chosen direction.
    return present + missing


def _quality_item(row: dict[str, Any], note: str) -> dict[str, Any]:
    return {
        "folio_id": row["id"],
        "client_id": row["client_id"],
        "client_name": row["client_name"],
        "folio_number": row["folio_number"],
        "scheme_name": row["scheme_name"],
        "benchmark_name": row["benchmark_name"],
        "aum": row["aum"],
        "performance": row["performance"],
        "match_status": row["match_status"],
        "benchmark_comparison_status": row["benchmark_comparison_status"],
        "note": note or row["benchmark_comparison_note"] or "",
    }


def _transaction_issue(row: dict[str, Any]) -> dict[str, Any] | None:
    missing_dates = row["missing_date_count"]
    missing_amounts = row["missing_amount_count"]
    unknown = row["unknown_transaction_count"]
    if not (missing_dates or missing_amounts or unknown):
        return None

    parts: list[str] = []
    if missing_dates:
        parts.append(f"{missing_dates} missing date")
    if missing_amounts:
        parts.append(f"{missing_amounts} missing amount")
    if unknown:
        parts.append(f"{unknown} unknown type")
    return {
        "folio_id": row["id"],
        "client_name": row["client_name"],
        "folio_number": row["folio_number"],
        "scheme_name": row["scheme_name"],
        "missing_date_count": missing_dates,
        "missing_amount_count": missing_amounts,
        "unknown_transaction_count": unknown,
        "summary": " · ".join(parts),
    }


def _data_quality(
    dashboard: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    missing_current_value = [
        _quality_item(
            row,
            "Current value is missing from the Folios export.",
        )
        for row in rows
        if row["aum"] is None
    ]
    missing_benchmark_mapping = [
        _quality_item(row, "No benchmark mapping is available for this scheme.")
        for row in rows
        if row["benchmark_comparison_status"] == "mapping_missing"
    ]
    mapping_needs_review = [
        _quality_item(row, "The automatic benchmark mapping needs local review.")
        for row in rows
        if row["benchmark_comparison_status"] == "mapping_needs_review"
    ]
    missing_benchmark_levels = [
        _quality_item(
            row,
            row["benchmark_comparison_note"]
            or "Local benchmark levels are missing for the required dates.",
        )
        for row in rows
        if row["benchmark_comparison_status"] == "levels_missing"
    ]
    unmatched_folios = [
        _quality_item(
            row,
            row["match_note"] or "Client not matched — needs review.",
        )
        for row in rows
        if row["client_id"] is None
    ]
    reconciliation_warnings = [
        row for row in dashboard["reconciliation"] if row["status"] != "matched"
    ]
    transaction_issues = [
        issue
        for issue in (_transaction_issue(row) for row in rows)
        if issue is not None
    ]

    counts = {
        "missing_current_value": len(missing_current_value),
        "missing_benchmark_mapping": len(missing_benchmark_mapping),
        "mapping_needs_review": len(mapping_needs_review),
        "missing_benchmark_levels": len(missing_benchmark_levels),
        "unmatched_folios": len(unmatched_folios),
        "unmatched_portfolio_rows": len(dashboard["unmatched_portfolio"]),
        "reconciliation_warnings": len(reconciliation_warnings),
        "transaction_issues": len(transaction_issues),
    }
    groups_with_issues = sum(1 for count in counts.values() if count > 0)
    return {
        "missing_current_value": missing_current_value,
        "missing_benchmark_mapping": missing_benchmark_mapping,
        "mapping_needs_review": mapping_needs_review,
        "missing_benchmark_levels": missing_benchmark_levels,
        "unmatched_folios": unmatched_folios,
        "unmatched_portfolio": dashboard["unmatched_portfolio"],
        "reconciliation_warnings": reconciliation_warnings,
        "transaction_issues": transaction_issues,
        "counts": counts,
        "total_items": sum(counts.values()),
        "groups_with_issues": groups_with_issues,
    }


def _concentration(
    dashboard: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    benchmark_values: dict[str, dict[str, Any]] = {}
    scheme_values: dict[str, dict[str, Any]] = {}
    total_folio_value = 0.0
    missing_value_folios = 0

    for row in rows:
        if row["aum"] is None:
            missing_value_folios += 1
            continue
        value = float(row["aum"])
        total_folio_value += value

        benchmark_name = row["benchmark_name"]
        benchmark_item = benchmark_values.setdefault(
            benchmark_name,
            {"name": benchmark_name, "value": 0.0, "folio_count": 0},
        )
        benchmark_item["value"] += value
        benchmark_item["folio_count"] += 1

        scheme_name = row["scheme_name"]
        scheme_item = scheme_values.setdefault(
            scheme_name,
            {"name": scheme_name, "value": 0.0, "folio_count": 0},
        )
        scheme_item["value"] += value
        scheme_item["folio_count"] += 1

    total_folio_value = round(total_folio_value, 2)
    by_benchmark = []
    for item in benchmark_values.values():
        by_benchmark.append(
            {
                **item,
                "value": round(item["value"], 2),
                "share": (
                    round(item["value"] / total_folio_value * 100, 2)
                    if total_folio_value
                    else 0.0
                ),
            }
        )
    by_benchmark.sort(
        key=lambda item: (-item["value"], item["name"].casefold())
    )

    top_schemes = []
    for item in scheme_values.values():
        top_schemes.append(
            {
                **item,
                "value": round(item["value"], 2),
                "share": (
                    round(item["value"] / total_folio_value * 100, 2)
                    if total_folio_value
                    else 0.0
                ),
            }
        )
    top_schemes.sort(
        key=lambda item: (-item["value"], item["name"].casefold())
    )

    client_values = [
        row
        for row in dashboard["clients"]
        if row["current_value"] is not None
    ]
    total_client_value = round(
        sum(float(row["current_value"]) for row in client_values), 2
    )
    top_clients = [
        {
            "client_id": row["id"],
            "name": row["name"],
            "value": round(float(row["current_value"]), 2),
            "folio_count": row["folio_count"],
            "share": (
                round(float(row["current_value"]) / total_client_value * 100, 2)
                if total_client_value
                else 0.0
            ),
        }
        for row in client_values
    ]
    top_clients.sort(
        key=lambda item: (-item["value"], item["name"].casefold())
    )

    return {
        "total_folio_value": total_folio_value,
        "total_client_value": total_client_value,
        "missing_folio_value_folios": missing_value_folios,
        "clients_without_current_value": sum(
            1
            for row in dashboard["clients"]
            if row["current_value"] is None
        ),
        "by_benchmark": by_benchmark,
        "top_clients": top_clients,
        "top_schemes": top_schemes,
    }


def _review_status(
    dashboard: dict[str, Any],
    rows: list[dict[str, Any]],
    mappings: dict[str, Any],
    level_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    folio_count = len(rows)
    performance_counts = {
        state: sum(1 for row in rows if row["performance"] == state)
        for state in PERFORMANCE_VALUES
    }
    comparisons_available = sum(
        1
        for row in rows
        if row["benchmark_comparison_status"] == "available"
    )
    mapping_summary = mappings["summary"]
    levels = sum(item["level_count"] for item in level_summaries)

    return {
        "mappings": mapping_summary,
        "comparisons": {
            "available": comparisons_available,
            "needs_review": performance_counts["needs_review"],
            "not_available": performance_counts["not_available"],
            "ahead": performance_counts["ahead"],
            "behind": performance_counts["behind"],
            "in_line": performance_counts["in_line"],
            "coverage_percent": (
                round(comparisons_available / folio_count * 100, 1)
                if folio_count
                else 0.0
            ),
        },
        "benchmark_data": {
            "series": len(level_summaries),
            "levels": levels,
            "series_names": [
                item["benchmark_name"] for item in level_summaries
            ],
        },
        "coverage": {
            "clients": dashboard["summary"]["clients"],
            "folios": folio_count,
            "portfolio_rows": dashboard["summary"]["portfolio_rows"],
            "transactions": dashboard["summary"]["transactions"],
            "xirr_available": dashboard["summary"]["xirr_available"],
            "xirr_missing": max(
                0, folio_count - dashboard["summary"]["xirr_available"]
            ),
            "folio_value_available": max(
                0, folio_count - dashboard["summary"]["missing_folio_aum"]
            ),
            "folio_value_missing": dashboard["summary"]["missing_folio_aum"],
            "transactions_unmatched": dashboard["summary"][
                "transactions_unmatched"
            ],
            "unknown_transactions": dashboard["summary"][
                "unknown_transactions"
            ],
            "missing_transaction_dates": dashboard["summary"][
                "missing_transaction_dates"
            ],
            "missing_transaction_amounts": dashboard["summary"][
                "missing_transaction_amounts"
            ],
        },
    }


def get_business_review(
    db: Session,
    *,
    performance: str = "all",
    benchmark: str = "all",
    client: str = "all",
    min_current_value: float | None = None,
    sort: str = "current_value",
    direction: str = "desc",
) -> dict[str, Any]:
    """Return the Business Review read model with server-side filters/sorts."""

    if performance not in PERFORMANCE_FILTERS:
        raise ValueError(f"Unknown performance filter: {performance}")
    if sort not in SORT_FIELDS:
        raise ValueError(f"Unknown sort field: {sort}")
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown sort direction: {direction}")
    if min_current_value is not None and min_current_value < 0:
        raise ValueError("Minimum current value cannot be negative.")

    dashboard = get_dashboard(db)
    rows = [
        {**row, "performance": _performance(row)}
        for row in dashboard["folios"]
    ]
    mappings = list_benchmark_mappings(db)
    level_summaries = benchmark_level_summaries(db)

    filter_options = {
        "benchmarks": _benchmark_options(rows),
        "clients": _client_options(rows),
    }

    filtered = rows
    if performance != "all":
        filtered = [
            row for row in filtered if row["performance"] == performance
        ]
    if benchmark != "all":
        filtered = [
            row for row in filtered if row["benchmark_name"] == benchmark
        ]
    if client != "all":
        if client == "unmatched":
            filtered = [
                row for row in filtered if row["client_id"] is None
            ]
        else:
            filtered = [
                row for row in filtered if _client_key(row) == client
            ]
    if min_current_value is not None:
        filtered = [
            row
            for row in filtered
            if row["aum"] is not None
            and row["aum"] >= min_current_value
        ]

    filtered = _sort_folios(filtered, sort, direction)
    data_quality = _data_quality(dashboard, rows)
    concentration = _concentration(dashboard, rows)
    review_status = _review_status(
        dashboard,
        rows,
        mappings,
        level_summaries,
    )
    behind_value = sum(
        float(row["aum"])
        for row in rows
        if row["performance"] == "behind" and row["aum"] is not None
    )
    performance_counts = {
        state: sum(1 for row in rows if row["performance"] == state)
        for state in PERFORMANCE_VALUES
    }

    return {
        "summary": {
            "clients": dashboard["summary"]["clients"],
            "folios": len(rows),
            "transactions": dashboard["summary"]["transactions"],
            "ahead": performance_counts["ahead"],
            "behind": performance_counts["behind"],
            "in_line": performance_counts["in_line"],
            "not_available": performance_counts["not_available"],
            "needs_review": performance_counts["needs_review"],
            "underperforming_value": (
                round(behind_value, 2) if behind_value else None
            ),
            "data_quality_items": data_quality["total_items"],
            "data_quality_groups": data_quality["groups_with_issues"],
            "comparisons_available": review_status["comparisons"][
                "available"
            ],
            "comparison_coverage": review_status["comparisons"][
                "coverage_percent"
            ],
        },
        "attention": {
            "folios": filtered,
            "total_folios": len(rows),
            "matching": len(filtered),
            "filter_options": filter_options,
            "applied_filters": {
                "performance": performance,
                "benchmark": benchmark,
                "client": client,
                "min_current_value": min_current_value,
                "sort": sort,
                "direction": direction,
            },
        },
        "data_quality": data_quality,
        "concentration": concentration,
        "review_status": review_status,
        "meta": {
            "has_data": dashboard["meta"]["has_data"],
            "valuation_date": dashboard["meta"]["valuation_date"],
            "benchmark_data": dashboard["meta"]["benchmark_data"],
            "source": (
                "Existing dashboard calculations, benchmark comparisons "
                "and local mappings"
            ),
        },
    }
