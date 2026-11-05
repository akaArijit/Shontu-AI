"""Read-only benchmark cluster graph for the dashboard.

Milestone 4 renders the graph from the same folio calculations and benchmark
comparison results that power the folio table.  This module therefore only
groups existing rows into benchmark clusters and derives display counts; it
does not add or change any return, XIRR or benchmark calculation.

Milestone 8B adds cluster-level TRI return calculation based on average
holding days of folios in each benchmark cluster.
"""

from __future__ import annotations

from statistics import fmean
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from mfd_dashboard.benchmark_data import (
    benchmark_level_summaries,
    load_benchmark_levels,
)
from mfd_dashboard.benchmark_mappings import (
    DEFAULT_BENCHMARK,
    available_benchmark_names,
)
from mfd_dashboard.dashboard import get_dashboard
from mfd_dashboard.ingest.values import normalize_header

NEEDS_REVIEW_STATUSES = {
    "mapping_missing",
    "mapping_needs_review",
    "levels_missing",
}


def _average(values: list[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return round(fmean(present), 4) if present else None


def _performance(row: dict[str, Any]) -> str:
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


def _cluster_review_state(
    *,
    benchmark_name: str,
    folios: list[dict[str, Any]],
    available: int,
    not_available: int,
) -> str:
    if not folios:
        return "no_folios"
    if benchmark_name == DEFAULT_BENCHMARK:
        return "needs_mapping"
    statuses = {item["benchmark_comparison_status"] for item in folios}
    if "mapping_missing" in statuses or "mapping_needs_review" in statuses:
        return "needs_review"
    if "levels_missing" in statuses:
        return "levels_missing"
    if available and not_available:
        return "partial"
    if available:
        return "ready"
    return "no_comparison"


def _calculate_tri_return(
    levels: dict[date, float],
    from_date: date,
    to_date: date,
) -> float | None:
    """
    Calculate TRI return for a benchmark over a date range.

    Returns the percentage return from the TRI level at from_date to to_date.
    Returns None if levels are not available for the required dates.
    """
    # Find the closest available level on or before from_date
    from_level = None
    from_level_date = None
    for d, v in sorted(levels.items()):
        if d <= from_date:
            from_level = v
            from_level_date = d
        else:
            break

    # Find the closest available level on or before to_date (which is typically today/valuation_date)
    to_level = None
    for d, v in sorted(levels.items()):
        if d <= to_date:
            to_level = v
        else:
            break

    if from_level is None or to_level is None or from_level == 0:
        return None

    return round(((to_level - from_level) / from_level) * 100, 2)


def _folio_node(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"folio:{row['id']}",
        "folio_id": row["id"],
        "client_id": row["client_id"],
        "client_name": row["client_name"],
        "folio_number": row["folio_number"],
        "scheme_name": row["scheme_name"],
        "benchmark_name": row["benchmark_name"],
        "benchmark_status": row["benchmark_status"],
        "aum": row["aum"],
        "invested_amount": row["invested_amount"],
        "gross_invested": row["gross_invested"],
        "holding_period": row["holding_period"],
        "first_investment_date": row["first_investment_date"],
        "value_date": row["value_date"],
        "absolute_return": row["absolute_return"],
        "xirr": row["xirr"],
        "benchmark_return": row["benchmark_return"],
        "benchmark_return_type": row["benchmark_return_type"],
        "benchmark_xirr": row["benchmark_xirr"],
        "folio_comparison_return": row["folio_comparison_return"],
        "benchmark_difference": row["benchmark_difference"],
        "benchmark_comparison_status": row["benchmark_comparison_status"],
        "benchmark_comparison_method": row["benchmark_comparison_method"],
        "benchmark_comparison_note": row["benchmark_comparison_note"],
        "benchmark_missing_dates": row.get("benchmark_missing_dates", []),
        "benchmark_missing_date_count": row.get(
            "benchmark_missing_date_count", 0
        ),
        "performance": _performance(row),
    }


def get_benchmark_graph(db: Session) -> dict[str, Any]:
    """Return benchmark nuclei and their connected folio nodes."""

    dashboard = get_dashboard(db)
    folio_rows = dashboard["folios"]
    level_counts = {
        normalize_header(item["benchmark_name"]): item["level_count"]
        for item in benchmark_level_summaries(db)
    }

    # Load all benchmark levels for TRI return calculation
    all_levels = load_benchmark_levels(db)
    valuation_date = dashboard["meta"]["valuation_date"]
    val_date = date.fromisoformat(valuation_date) if valuation_date else date.today()

    # The master catalogue is only a dropdown option list.  Drawing every
    # catalogue name would fill the graph with empty nuclei, so the graph keeps
    # only configured rules, imported level series and existing mappings.
    names = available_benchmark_names(db, include_master=False)
    if any(row["benchmark_name"] == DEFAULT_BENCHMARK for row in folio_rows):
        names.append(DEFAULT_BENCHMARK)

    clusters_by_key: dict[str, dict[str, Any]] = {}
    for name in names:
        key = normalize_header(name)
        if not key or key in clusters_by_key:
            continue
        clusters_by_key[key] = {
            "id": f"benchmark:{key}",
            "name": name,
            "normalized_name": key,
            "level_count": level_counts.get(key, 0),
            "folios": [],
        }

    for row in folio_rows:
        key = normalize_header(row["benchmark_name"])
        cluster = clusters_by_key.get(key)
        if cluster is None:
            # A reviewed mapping can reference a local benchmark whose levels
            # have not been uploaded yet.  Keep the folio visible in its own
            # benchmark nucleus rather than dropping it from the graph.
            cluster = {
                "id": f"benchmark:{key}",
                "name": row["benchmark_name"],
                "normalized_name": key,
                "level_count": level_counts.get(key, 0),
                "folios": [],
            }
            clusters_by_key[key] = cluster
        cluster["folios"].append(_folio_node(row))

    clusters: list[dict[str, Any]] = []
    for cluster in clusters_by_key.values():
        folios = cluster["folios"]
        ahead = sum(1 for item in folios if item["performance"] == "ahead")
        behind = sum(1 for item in folios if item["performance"] == "behind")
        in_line = sum(1 for item in folios if item["performance"] == "in_line")
        needs_review = sum(
            1 for item in folios if item["performance"] == "needs_review"
        )
        not_available = sum(
            1 for item in folios if item["performance"] == "not_available"
        ) + needs_review
        available = ahead + behind + in_line
        comparison_rows = [
            item
            for item in folios
            if item["benchmark_comparison_status"] == "available"
        ]

        # Calculate average holding days for this cluster
        holding_days = [
            item["holding_period"]
            for item in folios
            if item.get("holding_period") is not None
        ]
        avg_holding_days = int(fmean(holding_days)) if holding_days else None

        # Calculate cluster-level TRI return
        tri_return = None
        tri_return_note = None
        if avg_holding_days is not None:
            cluster_key = normalize_header(cluster["name"])
            levels = all_levels.get(cluster_key, {})
            if levels:
                from_date = val_date - timedelta(days=avg_holding_days)
                tri_return = _calculate_tri_return(levels, from_date, val_date)
                if tri_return is None:
                    tri_return_note = (
                        f"Benchmark TRI data unavailable for the last {avg_holding_days} days"
                    )
            else:
                tri_return_note = "No benchmark TRI data available"

        # Calculate average folio return for comparison
        avg_folio_return = _average(
            [item["folio_comparison_return"] for item in comparison_rows]
        )
        avg_benchmark_return = _average(
            [item["benchmark_return"] for item in comparison_rows]
        )

        cluster["stats"] = {
            "folio_count": len(folios),
            "ahead": ahead,
            "behind": behind,
            "in_line": in_line,
            "available": available,
            "not_available": not_available,
            "needs_review": needs_review,
            "missing_folio_aum": sum(1 for item in folios if item["aum"] is None),
            "average_difference": _average(
                [item["benchmark_difference"] for item in comparison_rows]
            ),
            "average_folio_return": avg_folio_return,
            "average_benchmark_return": avg_benchmark_return,
            # Cluster-level TRI return fields
            "avg_holding_days": avg_holding_days,
            "benchmark_tri_return": tri_return,
            "benchmark_tri_return_note": tri_return_note,
            "benchmark_return_difference": (
                round(float(avg_folio_return) - float(tri_return), 2)
                if tri_return is not None and avg_folio_return is not None
                else None
            ),
        }
        cluster["review_state"] = _cluster_review_state(
            benchmark_name=cluster["name"],
            folios=folios,
            available=available,
            not_available=not_available,
        )
        clusters.append(cluster)

    # Clusters with folios lead the graph; empty benchmark nuclei remain
    # visible afterwards so new benchmark data can be reviewed in context.
    clusters.sort(
        key=lambda item: (
            item["stats"]["folio_count"] == 0,
            -item["stats"]["folio_count"],
            item["name"].casefold(),
        )
    )

    all_folios = [item for cluster in clusters for item in cluster["folios"]]
    summary = {
        "benchmarks": len(clusters),
        "folios": len(all_folios),
        "ahead": sum(1 for item in all_folios if item["performance"] == "ahead"),
        "behind": sum(1 for item in all_folios if item["performance"] == "behind"),
        "in_line": sum(1 for item in all_folios if item["performance"] == "in_line"),
        "needs_review": sum(
            1 for item in all_folios if item["performance"] == "needs_review"
        ),
        "not_available": sum(
            1 for item in all_folios if item["performance"] == "not_available"
        ),
        "missing_folio_aum": sum(1 for item in all_folios if item["aum"] is None),
    }

    return {
        "summary": summary,
        "clusters": clusters,
        "meta": {
            "has_data": dashboard["meta"]["has_data"],
            "valuation_date": dashboard["meta"]["valuation_date"],
            "benchmark_data": dashboard["meta"]["benchmark_data"],
            "source": (
                "Existing folio calculations and benchmark comparison results"
            ),
        },
    }