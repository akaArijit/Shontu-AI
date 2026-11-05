"""Read model for the current InvestWell snapshot."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from mfd_dashboard.benchmark_data import load_benchmark_levels
from mfd_dashboard.calculations import (
    DatedAmount,
    calculate_folio_metrics,
    point_to_point_return,
    simulate_benchmark,
)
from mfd_dashboard.db.models import (
    Client,
    Folio,
    ImportIssue,
    PortfolioValuation,
    Scheme,
    SchemeBenchmark,
    Transaction,
    UploadBatch,
)
from mfd_dashboard.ingest.values import normalize_header

ONE_RUPEE = Decimal("1.00")


def _number(value: Decimal | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _empty_dashboard() -> dict[str, Any]:
    return {
        "summary": {
            "clients": 0,
            "folios": 0,
            "portfolio_rows": 0,
            "total_folio_aum": None,
            "total_current_value": None,
            "total_purchase_value": None,
            "total_gross_invested": None,
            "total_net_invested": None,
            "unmatched_folio_aum": None,
            "unmatched_current_value": None,
            "needs_review": 0,
            "unmatched_folios": 0,
            "unmatched_portfolio_rows": 0,
            "transactions": 0,
            "transactions_unmatched": 0,
            "unknown_transactions": 0,
            "switch_reviews": 0,
            "missing_transaction_dates": 0,
            "missing_transaction_amounts": 0,
            "xirr_available": 0,
            "benchmark_comparisons_available": 0,
            "benchmark_levels_missing": 0,
            "benchmark_reviewed": 0,
            "benchmark_mapping_missing": 0,
            "benchmark_mapping_needs_review": 0,
            "benchmark_point_to_point": 0,
            "benchmark_cash_flow": 0,
            "reconciliation_warnings": 0,
            "partial_reconciliation": 0,
            "missing_folio_aum": 0,
            "missing_current_value": 0,
            "issues": 0,
            "errors": 0,
            "warnings": 0,
        },
        "clients": [],
        "folios": [],
        "unmatched_portfolio": [],
        "reconciliation": [],
        "total_reconciliation": None,
        "issues": [],
        "meta": {
            "has_data": False,
            "valuation_date": None,
            "benchmark_data": "Not available",
            "folio_value_source": "Folios AUM (as reported)",
            "client_value_source": "Portfolio Valuation CURRENT VALUE (as reported)",
            "return_source": "Not available",
            "folio_invested_amount": "Not available",
            "folio_absolute_return": "Not available",
            "folio_holding_period": "Not available",
            "folio_xirr": "Not available",
            "transaction_file_name": None,
            "batch": None,
        },
    }


def _latest_batch(db: Session) -> UploadBatch | None:
    return db.scalar(
        select(UploadBatch).order_by(UploadBatch.confirmed_at.desc()).limit(1)
    )


def _reconciliation_status(
    folio_count: int,
    folio_aum_total: Decimal | None,
    missing_aum: int,
    current_value: Decimal | None,
) -> str:
    if folio_count == 0:
        return "no_folios"
    if current_value is None:
        return "not_available"
    if missing_aum:
        return "partial"
    if folio_aum_total is not None and abs(folio_aum_total - current_value) <= ONE_RUPEE:
        return "matched"
    return "mismatch"


def get_dashboard(db: Session) -> dict[str, Any]:
    batch = _latest_batch(db)
    if batch is None:
        return _empty_dashboard()

    clients = db.scalars(select(Client).order_by(Client.name)).all()
    folios = db.scalars(
        select(Folio)
        .options(
            joinedload(Folio.client),
            joinedload(Folio.scheme).joinedload(Scheme.benchmark),
        )
        .order_by(Folio.folio_number, Folio.scheme_id)
    ).all()
    valuations = db.scalars(
        select(PortfolioValuation)
        .options(joinedload(PortfolioValuation.client))
        .order_by(PortfolioValuation.source_row)
    ).all()
    mappings = {
        item.scheme_id: item
        for item in db.scalars(select(SchemeBenchmark)).all()
    }
    transactions = db.scalars(
        select(Transaction)
        .where(Transaction.batch_id == batch.id)
        .order_by(Transaction.transaction_date, Transaction.id)
    ).all()
    benchmark_levels = load_benchmark_levels(db)
    issues = db.scalars(
        select(ImportIssue)
        .where(ImportIssue.batch_id == batch.id)
        .order_by(ImportIssue.severity.desc(), ImportIssue.id)
    ).all()

    folios_by_client: dict[int, list[Folio]] = defaultdict(list)
    for folio in folios:
        if folio.client_id is not None:
            folios_by_client[folio.client_id].append(folio)
    valuation_by_client = {
        item.client_id: item for item in valuations if item.client_id is not None
    }
    transactions_by_folio: dict[int, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        if transaction.folio_id is not None:
            transactions_by_folio[transaction.folio_id].append(transaction)

    client_rows: list[dict[str, Any]] = []
    reconciliation: list[dict[str, Any]] = []

    for client in clients:
        client_folios = folios_by_client.get(client.id, [])
        aum_values = [folio.aum for folio in client_folios if folio.aum is not None]
        folio_aum_total = (
            sum(aum_values, Decimal("0")) if aum_values else None
        )
        missing_aum = sum(1 for folio in client_folios if folio.aum is None)
        valuation = valuation_by_client.get(client.id)
        current_value = valuation.current_value if valuation else None
        status = _reconciliation_status(
            len(client_folios), folio_aum_total, missing_aum, current_value
        )
        difference = (
            folio_aum_total - current_value
            if folio_aum_total is not None and current_value is not None
            else None
        )

        notes: list[str] = []
        if not client_folios:
            notes.append("No folios were imported for this client.")
        if valuation is None:
            notes.append("No client-level valuation row was imported.")
        elif current_value is None:
            notes.append("Client current value is not available in the Portfolio Valuation export.")
        if missing_aum:
            notes.append(
                f"{missing_aum} folio AUM value(s) are missing, so reconciliation is partial."
            )
        if status == "mismatch":
            notes.append("Folio AUM total does not match the client-level current value.")

        row = {
            "id": client.id,
            "name": client.name,
            "iwell_code": client.iwell_code,
            "iwell_code_2": client.iwell_code_2,
            "app_code": client.app_code,
            "first_investment_date": (
                client.first_investment_date.isoformat()
                if client.first_investment_date
                else None
            ),
            "folio_count": len(client_folios),
            "folio_aum_total": _number(folio_aum_total),
            "folio_aum_missing_count": missing_aum,
            "current_value": _number(current_value),
            "purchase_value": _number(valuation.purchase_value if valuation else None),
            "gain": _number(valuation.gain if valuation else None),
            "absolute_return": _number(
                valuation.absolute_return if valuation else None
            ),
            "cagr": _number(valuation.cagr if valuation else None),
            "avg_holding_days": valuation.avg_holding_days if valuation else None,
            "valuation_date": (
                valuation.valuation_date.isoformat() if valuation else None
            ),
            "reconciliation_status": status,
            "difference": _number(difference),
            "match_status": "matched",
            "notes": notes,
        }
        client_rows.append(row)
        reconciliation.append(
            {
                "client_id": client.id,
                "client_name": client.name,
                "iwell_code": client.iwell_code,
                "folio_count": len(client_folios),
                "folio_aum_total": row["folio_aum_total"],
                "folio_aum_missing_count": missing_aum,
                "client_current_value": row["current_value"],
                "difference": row["difference"],
                "status": status,
            }
        )

    folio_rows: list[dict[str, Any]] = []
    for folio in folios:
        mapping = mappings.get(folio.scheme_id)
        scheme_name = folio.scheme.name if folio.scheme else "Not available"
        benchmark_name = (
            mapping.benchmark_name if mapping is not None else "Other / Unmapped"
        )
        benchmark_status = (
            mapping.status if mapping is not None else "needs_mapping"
        )
        client_name = (
            folio.client.name
            if folio.client
            else (folio.source_client_name or "Unmatched — needs review")
        )

        folio_transactions = transactions_by_folio.get(folio.id, [])
        dated_transactions = [
            DatedAmount(
                flow_date=item.transaction_date,
                amount=item.amount,
                kind=item.transaction_type,
            )
            for item in folio_transactions
        ]
        valuation_date = folio.value_date or batch.report_date
        metrics = calculate_folio_metrics(
            dated_transactions,
            current_value=folio.aum,
            valuation_date=valuation_date,
        )
        switch_review_count = sum(
            1
            for item in folio_transactions
            if item.transaction_type in {"switch_in", "switch_out"}
            and item.switch_pair_key is None
        )
        notes: list[str] = []
        if folio.match_status == "unmatched":
            notes.append("Client not matched — needs review.")
        elif folio.match_status == "name_fallback":
            notes.append("Matched by exact client name — needs review.")
        if folio.aum is None:
            notes.append("Folio AUM is not available in this file.")
        if not dated_transactions:
            notes.append("No matched transaction rows for this folio.")
        else:
            if metrics["missing_date_count"]:
                notes.append(
                    f"{metrics['missing_date_count']} transaction(s) have a missing or invalid date and were excluded."
                )
            if metrics["missing_amount_count"]:
                notes.append(
                    f"{metrics['missing_amount_count']} transaction(s) have a missing or invalid amount and were excluded."
                )
            if metrics["unknown_count"]:
                notes.append(
                    f"{metrics['unknown_count']} transaction(s) have an unknown type and were excluded."
                )
            if switch_review_count:
                notes.append(
                    f"{switch_review_count} switch leg(s) could not be confidently paired."
                )
            if metrics["gross_invested"] is None:
                notes.append(
                    "No valid purchase, SIP or switch-in amount is available."
                )
            if metrics["xirr"] is None and folio.aum is not None:
                notes.append("XIRR could not be calculated from the available cash flows.")

        benchmark_return = None
        benchmark_return_type = None
        benchmark_value = None
        benchmark_difference = None
        benchmark_note = None
        comparison_method = None
        folio_comparison_return = None
        benchmark_xirr = None
        benchmark_missing_dates: list[date] = []
        if benchmark_name in {"", "Other / Unmapped"}:
            benchmark_comparison_status = "mapping_missing"
            benchmark_note = "No reviewed benchmark mapping is available."
        elif benchmark_status != "reviewed":
            benchmark_comparison_status = "mapping_needs_review"
            benchmark_note = (
                "The benchmark mapping is automatic and needs review before a "
                "comparison can be shown."
            )
        elif not dated_transactions:
            benchmark_comparison_status = "no_transactions"
            benchmark_note = "No transaction cash flows are available for benchmark comparison."
        else:
            levels = benchmark_levels.get(normalize_header(benchmark_name), {})
            valid_flows = [
                item
                for item in dated_transactions
                if item.flow_date is not None
                and item.amount is not None
                and item.amount != 0
            ]
            gross_flows = [
                item
                for item in valid_flows
                if item.kind in {"purchase", "sip", "switch_in"}
            ]
            outflow_flows = [
                item
                for item in valid_flows
                if item.kind in {"redemption", "switch_out"}
            ]
            is_lump_sum = (
                len(gross_flows) == 1
                and gross_flows[0].kind == "purchase"
                and not outflow_flows
            )
            if not levels:
                required_dates = (
                    {gross_flows[0].flow_date, valuation_date}
                    if is_lump_sum
                    else {
                        item.flow_date
                        for item in valid_flows
                        if item.flow_date is not None
                    }
                    | {valuation_date}
                )
                benchmark_missing_dates = sorted(required_dates)
                benchmark_comparison_status = "levels_missing"
                benchmark_note = (
                    f"No local benchmark levels are imported for {benchmark_name}."
                )
            elif is_lump_sum:
                comparison_method = "point_to_point"
                benchmark_return_type = "absolute"
                folio_comparison_return = metrics["absolute_return"]
                result = point_to_point_return(
                    levels,
                    gross_flows[0].flow_date,
                    valuation_date,
                )
                benchmark_return = result.get("return")
                benchmark_note = result.get("message")
                benchmark_missing_dates = result.get("missing_dates", [])
                if result.get("status") != "available":
                    benchmark_comparison_status = "levels_missing"
                elif folio_comparison_return is None:
                    benchmark_comparison_status = "folio_return_unavailable"
                    benchmark_note = (
                        "The folio absolute return is unavailable, so a comparison "
                        "cannot be shown."
                    )
                else:
                    benchmark_comparison_status = "available"
                    benchmark_difference = (
                        folio_comparison_return - benchmark_return
                    )
            else:
                comparison_method = "cash_flow_xirr"
                benchmark_return_type = "xirr"
                folio_comparison_return = metrics["xirr"]
                result = simulate_benchmark(
                    metrics["cash_flows"], levels, valuation_date
                )
                benchmark_return = result.get("xirr")
                benchmark_value = result.get("current_value")
                benchmark_note = result.get("message")
                benchmark_xirr = benchmark_return
                benchmark_missing_dates = result.get("missing_dates", [])
                if result.get("status") != "available":
                    benchmark_comparison_status = "levels_missing"
                elif benchmark_return is None:
                    benchmark_comparison_status = "xirr_unavailable"
                    benchmark_note = (
                        "The benchmark XIRR could not be solved from the available "
                        "dates and levels."
                    )
                elif folio_comparison_return is None:
                    benchmark_comparison_status = "folio_return_unavailable"
                    benchmark_note = (
                        "The folio XIRR is unavailable, so a comparison cannot be "
                        "shown."
                    )
                else:
                    benchmark_comparison_status = "available"
                    benchmark_difference = (
                        folio_comparison_return - benchmark_return
                    )

        if benchmark_note and benchmark_comparison_status != "available":
            notes.append(benchmark_note)

        folio_rows.append(
            {
                "id": folio.id,
                "client_id": folio.client_id,
                "client_name": client_name,
                "client_iwell_code": (
                    folio.client.iwell_code
                    if folio.client
                    else folio.source_iwell_code
                ),
                "folio_number": folio.folio_number,
                "scheme_name": scheme_name,
                "folio_type": folio.folio_type or "Not available",
                "units": _number(folio.units),
                "aum": _number(folio.aum),
                "value_date": folio.value_date.isoformat() if folio.value_date else None,
                "benchmark_name": benchmark_name,
                "benchmark_status": benchmark_status,
                "match_status": folio.match_status,
                "match_note": folio.match_note,
                "invested_amount": _number(metrics["gross_invested"]),
                "gross_invested": _number(metrics["gross_invested"]),
                "net_invested": _number(metrics["net_invested"]),
                "redemption_proceeds": _number(metrics["redemption_proceeds"]),
                "switch_out_proceeds": _number(metrics["switch_out_proceeds"]),
                "absolute_return": _number(metrics["absolute_return"]),
                "holding_period": metrics["holding_period"],
                "first_investment_date": (
                    metrics["first_investment_date"].isoformat()
                    if metrics["first_investment_date"]
                    else None
                ),
                "xirr": metrics["xirr"],
                "benchmark_xirr": benchmark_xirr,
                "benchmark_return": (
                    float(benchmark_return) if benchmark_return is not None else None
                ),
                "benchmark_return_type": benchmark_return_type,
                "folio_comparison_return": (
                    float(folio_comparison_return)
                    if folio_comparison_return is not None
                    else None
                ),
                "benchmark_difference": (
                    float(benchmark_difference)
                    if benchmark_difference is not None
                    else None
                ),
                "benchmark_current_value": _number(benchmark_value),
                "benchmark_comparison_status": benchmark_comparison_status,
                "benchmark_comparison_method": comparison_method,
                "benchmark_comparison_note": benchmark_note,
                "benchmark_missing_dates": [
                    item.isoformat() for item in benchmark_missing_dates[:12]
                ],
                "benchmark_missing_date_count": len(benchmark_missing_dates),
                "transaction_count": metrics["transaction_count"],
                "switch_review_count": switch_review_count,
                "missing_date_count": metrics["missing_date_count"],
                "missing_amount_count": metrics["missing_amount_count"],
                "unknown_transaction_count": metrics["unknown_count"],
                "notes": notes,
            }
        )

    unmatched_portfolio = [
        {
            "id": item.id,
            "client_name": item.source_client_name or "Unmatched — needs review",
            "source_iwell_code": item.source_iwell_code,
            "current_value": _number(item.current_value),
            "purchase_value": _number(item.purchase_value),
            "gain": _number(item.gain),
            "absolute_return": _number(item.absolute_return),
            "cagr": _number(item.cagr),
            "valuation_date": item.valuation_date.isoformat(),
            "match_status": item.match_status,
            "match_note": item.match_note,
        }
        for item in valuations
        if item.client_id is None
    ]

    matched_folios = [folio for folio in folios if folio.client_id is not None]
    matched_valuations = [
        item for item in valuations if item.client_id is not None
    ]
    total_folio_aum_values = [
        folio.aum for folio in matched_folios if folio.aum is not None
    ]
    total_current_values = [
        item.current_value
        for item in matched_valuations
        if item.current_value is not None
    ]
    total_purchase_values = [
        item.purchase_value
        for item in matched_valuations
        if item.purchase_value is not None
    ]
    all_current_values = [
        item.current_value for item in valuations if item.current_value is not None
    ]
    unmatched_folio_aum_values = [
        folio.aum
        for folio in folios
        if folio.client_id is None and folio.aum is not None
    ]
    unmatched_current_values = [
        item.current_value
        for item in valuations
        if item.client_id is None and item.current_value is not None
    ]
    total_folio_aum = (
        sum(total_folio_aum_values, Decimal("0"))
        if total_folio_aum_values
        else None
    )
    matched_folio_rows = [
        row for row in folio_rows if row["client_id"] is not None
    ]
    gross_invested_values = [
        Decimal(str(row["gross_invested"]))
        for row in matched_folio_rows
        if row["gross_invested"] is not None
    ]
    net_invested_values = [
        Decimal(str(row["net_invested"]))
        for row in matched_folio_rows
        if row["net_invested"] is not None
    ]
    total_gross_invested = (
        sum(gross_invested_values, Decimal("0"))
        if gross_invested_values
        else None
    )
    total_net_invested = (
        sum(net_invested_values, Decimal("0")) if net_invested_values else None
    )
    total_current = (
        sum(total_current_values, Decimal("0")) if total_current_values else None
    )
    total_purchase = (
        sum(total_purchase_values, Decimal("0")) if total_purchase_values else None
    )
    total_all_current = (
        sum(all_current_values, Decimal("0")) if all_current_values else None
    )
    unmatched_folio_aum = (
        sum(unmatched_folio_aum_values, Decimal("0"))
        if unmatched_folio_aum_values
        else None
    )
    unmatched_current_value = (
        sum(unmatched_current_values, Decimal("0"))
        if unmatched_current_values
        else None
    )

    total_reconciliation = None
    if (
        batch.portfolio_total_current_value is not None
        and total_all_current is not None
        and all(item.current_value is not None for item in valuations)
    ):
        difference = total_all_current - batch.portfolio_total_current_value
        total_reconciliation = {
            "report_total": _number(batch.portfolio_total_current_value),
            "sum_of_client_rows": _number(total_all_current),
            "difference": _number(difference),
            "status": "matched"
            if abs(difference) <= ONE_RUPEE
            else "mismatch",
        }
    elif batch.portfolio_total_current_value is not None:
        total_reconciliation = {
            "report_total": _number(batch.portfolio_total_current_value),
            "sum_of_client_rows": _number(total_all_current),
            "difference": None,
            "status": "not_available",
        }

    status_counts = defaultdict(int)
    for item in client_rows:
        status_counts[item["reconciliation_status"]] += 1

    summary = {
        "clients": len(clients),
        "folios": len(folios),
        "portfolio_rows": len(valuations),
        "total_folio_aum": _number(total_folio_aum),
        "total_current_value": _number(total_current),
        "total_purchase_value": _number(total_purchase),
        "total_gross_invested": _number(total_gross_invested),
        "total_net_invested": _number(total_net_invested),
        "unmatched_folio_aum": _number(unmatched_folio_aum),
        "unmatched_current_value": _number(unmatched_current_value),
        "needs_review": sum(
            1 for item in mappings.values() if item.status == "needs_review"
        ),
        "benchmark_reviewed": sum(
            1 for item in mappings.values() if item.status == "reviewed"
        ),
        "benchmark_mapping_missing": sum(
            1
            for row in folio_rows
            if row["benchmark_comparison_status"] == "mapping_missing"
        ),
        "benchmark_mapping_needs_review": sum(
            1
            for row in folio_rows
            if row["benchmark_comparison_status"] == "mapping_needs_review"
        ),
        "benchmark_point_to_point": sum(
            1 for row in folio_rows if row["benchmark_comparison_method"] == "point_to_point"
        ),
        "benchmark_cash_flow": sum(
            1 for row in folio_rows if row["benchmark_comparison_method"] == "cash_flow_xirr"
        ),
        "unmatched_folios": sum(1 for item in folios if item.client_id is None),
        "unmatched_portfolio_rows": sum(
            1 for item in valuations if item.client_id is None
        ),
        "transactions": len(transactions),
        "transactions_unmatched": sum(
            1 for item in transactions if item.folio_id is None
        ),
        "unknown_transactions": sum(
            1 for item in transactions if item.transaction_type == "unknown"
        ),
        "switch_reviews": sum(
            1
            for item in transactions
            if item.transaction_type in {"switch_in", "switch_out"}
            and item.switch_pair_key is None
        ),
        "missing_transaction_dates": sum(
            1 for item in transactions if item.transaction_date is None
        ),
        "missing_transaction_amounts": sum(
            1 for item in transactions if item.amount is None
        ),
        "xirr_available": sum(
            1 for row in folio_rows if row["xirr"] is not None
        ),
        "benchmark_comparisons_available": sum(
            1
            for row in folio_rows
            if row["benchmark_comparison_status"] == "available"
        ),
        "benchmark_levels_missing": sum(
            1
            for row in folio_rows
            if row["benchmark_comparison_status"] == "levels_missing"
        ),
        "reconciliation_warnings": status_counts["mismatch"],
        "partial_reconciliation": status_counts["partial"],
        "missing_folio_aum": sum(1 for item in folios if item.aum is None),
        "missing_current_value": sum(
            1 for item in valuations if item.current_value is None
        ),
        "issues": len(issues),
        "errors": sum(1 for item in issues if item.severity == "error"),
        "warnings": sum(1 for item in issues if item.severity == "warning"),
    }

    issue_rows = [
        {
            "id": item.id,
            "file_type": item.file_type,
            "row_number": item.row_number,
            "field": item.field,
            "message": item.message,
            "severity": item.severity,
        }
        for item in issues
    ]

    return {
        "summary": summary,
        "clients": client_rows,
        "folios": folio_rows,
        "unmatched_portfolio": unmatched_portfolio,
        "reconciliation": reconciliation,
        "total_reconciliation": total_reconciliation,
        "issues": issue_rows,
        "meta": {
            "has_data": True,
            "valuation_date": batch.report_date.isoformat(),
            "benchmark_data": (
                f"Local SQLite levels for {len(benchmark_levels)} benchmark(s); "
                f"{summary['benchmark_reviewed']} reviewed mapping(s), "
                f"{summary['needs_review']} need review"
                if benchmark_levels
                else "Not available — no local benchmark levels"
            ),
            "folio_value_source": "Folios AUM (as reported)",
            "client_value_source": "Portfolio Valuation CURRENT VALUE (as reported)",
            "return_source": (
                "Calculated from the Transaction Statement"
                if batch.transaction_file_name
                else "Not available — no transaction statement"
            ),
            "folio_invested_amount": (
                "Transactions — gross purchases/SIP/switch-in"
                if batch.transaction_file_name
                else "Not available"
            ),
            "folio_absolute_return": (
                "Calculated from transactions and Folios AUM"
                if batch.transaction_file_name
                else "Not available"
            ),
            "folio_holding_period": (
                "First transaction date to valuation date"
                if batch.transaction_file_name
                else "Not available"
            ),
            "folio_xirr": (
                "Money-weighted XIRR from dated cash flows"
                if batch.transaction_file_name
                else "Not available"
            ),
            "transaction_file_name": batch.transaction_file_name,
            "batch": {
                "id": batch.id,
                "import_id": batch.import_id,
                "client_file_name": batch.client_file_name,
                "folios_file_name": batch.folios_file_name,
                "portfolio_file_name": batch.portfolio_file_name,
                "transaction_file_name": batch.transaction_file_name,
                "confirmed_at": batch.confirmed_at.isoformat(),
                "report_date": batch.report_date.isoformat(),
            },
        },
    }
