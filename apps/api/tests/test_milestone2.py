from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mfd_dashboard.calculations import (
    DatedAmount,
    SignedCashFlow,
    calculate_folio_metrics,
    classify_transaction,
    simulate_benchmark,
)
from mfd_dashboard.ingest.config import column_aliases
from mfd_dashboard.ingest.service import build_preview

from .fixtures import (
    clients_xlsx,
    folios_xlsx,
    four_files,
    portfolio_csv,
    portfolio_xlsx,
    three_files,
    transactions_xlsx,
)


def review_mapping(client, scheme_name: str, benchmark_name: str) -> None:
    payload = client.get("/api/v1/benchmark-mappings").json()
    scheme = next(
        item for item in payload["mappings"] if item["scheme_name"] == scheme_name
    )
    response = client.patch(
        f"/api/v1/benchmark-mappings/{scheme['scheme_id']}",
        json={"benchmark_name": benchmark_name},
    )
    assert response.status_code == 200, response.text


def import_levels(client, rows: list[tuple[str, str, str]]) -> None:
    lines = ["benchmark_name,date,level"]
    lines.extend(f"{name},{level_date},{level}" for name, level_date, level in rows)
    response = client.post(
        "/api/v1/benchmarks/levels/import",
        files={
            "file": (
                "levels.csv",
                "\n".join(lines).encode("utf-8"),
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text


def tx(
    date_text: str,
    scheme: str,
    folio: str,
    client: str,
    txn_type: str,
    amount: str,
    *,
    code: str = "C001",
    source: str = "",
    target: str = "",
) -> tuple[object, ...]:
    return (
        date_text,
        scheme,
        folio,
        client,
        "REDACTED",
        txn_type,
        amount,
        "0",
        "0",
        txn_type,
        source,
        target,
        code,
        "",
        "",
        "",
    )


def preview_and_confirm(client, files):
    preview = client.post(
        "/api/v1/imports/preview",
        files={
            {
                "clients": "clients_file",
                "folios": "folios_file",
                "portfolio": "portfolio_file",
                "transactions": "transactions_file",
            }[kind]: (name, data, "application/octet-stream")
            for kind, (name, data) in files.items()
        },
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["can_confirm"] is True, payload["issues"]
    response = client.post(f"/api/v1/imports/{payload['import_id']}/confirm")
    assert response.status_code == 200, response.text
    return payload, client.get("/api/v1/dashboard").json()


def test_purchase_only_folio_metrics():
    metrics = calculate_folio_metrics(
        [
            DatedAmount(
                flow_date=date(2024, 1, 15),
                amount=Decimal("10000"),
                kind="purchase",
            )
        ],
        current_value=Decimal("12000"),
        valuation_date=date(2025, 1, 15),
    )

    assert metrics["gross_invested"] == Decimal("10000")
    assert metrics["net_invested"] == Decimal("10000")
    assert metrics["redemption_proceeds"] == Decimal("0")
    assert metrics["holding_period"] == 366
    assert metrics["absolute_return"] == Decimal("20.00")
    assert metrics["xirr"] == pytest.approx(19.94, abs=0.05)


def test_sip_folio_with_multiple_monthly_installments():
    metrics = calculate_folio_metrics(
        [
            DatedAmount(date(2025, 1, 15), Decimal("1000"), "sip"),
            DatedAmount(date(2025, 2, 15), Decimal("1000"), "sip"),
            DatedAmount(date(2025, 3, 15), Decimal("1000"), "sip"),
        ],
        current_value=Decimal("3300"),
        valuation_date=date(2025, 4, 15),
    )

    assert metrics["gross_invested"] == Decimal("3000")
    assert metrics["net_invested"] == Decimal("3000")
    assert metrics["first_investment_date"] == date(2025, 1, 15)
    assert metrics["holding_period"] == 90
    assert metrics["sip_count"] == 3
    assert metrics["xirr"] is not None
    assert metrics["xirr"] > 0


def test_redemption_folio_includes_proceeds_in_absolute_return():
    metrics = calculate_folio_metrics(
        [
            DatedAmount(date(2024, 1, 15), Decimal("10000"), "purchase"),
            DatedAmount(date(2025, 1, 15), Decimal("2000"), "redemption"),
        ],
        current_value=Decimal("10000"),
        valuation_date=date(2026, 1, 15),
    )

    assert metrics["gross_invested"] == Decimal("10000")
    assert metrics["redemption_proceeds"] == Decimal("2000")
    assert metrics["net_invested"] == Decimal("8000")
    assert metrics["absolute_return"] == Decimal("20.00")
    assert metrics["xirr"] is not None
    assert metrics["xirr"] > 0


def test_switch_out_and_switch_in_folio_are_paired():
    transactions = transactions_xlsx(
        [
            tx("01-01-2024", "Apex Bluechip Fund", "F001", "Alice Example", "PURCHASE", "10000"),
            tx(
                "01-06-2025",
                "Apex Bluechip Fund",
                "F001",
                "Alice Example",
                "SWITCH OUT",
                "1000",
                source="Apex Bluechip Fund",
                target="Apex Midcap Fund",
            ),
            tx(
                "01-06-2025",
                "Apex Midcap Fund",
                "F002",
                "Alice Example",
                "SWITCH IN",
                "1000",
                source="Apex Bluechip Fund",
                target="Apex Midcap Fund",
            ),
        ]
    )
    plan = build_preview(four_files(transactions=transactions))

    assert plan["can_confirm"] is True
    assert plan["counts"]["switch_pairs"] == 1
    assert plan["counts"]["switch_reviews"] == 0
    switch_rows = [
        item for item in plan["transactions"] if "SWITCH" in item["transaction_type_raw"]
    ]
    assert {item["switch_pair_key"] for item in switch_rows} == {"switch-1"}
    assert all(item["switch_review_status"] == "paired" for item in switch_rows)


def test_one_legged_switch_is_flagged_without_inventing_the_other_leg():
    transactions = transactions_xlsx(
        [
            tx(
                "01-06-2025",
                "Apex Bluechip Fund",
                "F001",
                "Alice Example",
                "SWITCH OUT",
                "1000",
                source="Apex Bluechip Fund",
                target="Apex Midcap Fund",
            ),
        ]
    )
    plan = build_preview(four_files(transactions=transactions))

    assert plan["counts"]["switch_pairs"] == 0
    assert plan["counts"]["switch_reviews"] == 1
    row = plan["transactions"][0]
    assert row["switch_pair_key"] is None
    assert row["switch_review_status"] == "unpaired"
    assert any(
        "Review the missing leg" in item["message"] for item in plan["issues"]
    )


def test_missing_transaction_date_is_reported_and_excluded(client):
    transactions = transactions_xlsx(
        [
            tx("", "Apex Bluechip Fund", "F001", "Alice Example", "PURCHASE", "10000"),
        ]
    )
    plan = build_preview(four_files(transactions=transactions))

    assert plan["transactions"][0]["transaction_date"] is None
    assert any(
        "Transaction date is missing" in item["message"] for item in plan["issues"]
    )


def test_missing_transaction_amount_is_reported_and_excluded():
    transactions = transactions_xlsx(
        [
            tx("15-01-2024", "Apex Bluechip Fund", "F001", "Alice Example", "PURCHASE", ""),
        ]
    )
    plan = build_preview(four_files(transactions=transactions))

    assert plan["transactions"][0]["amount"] is None
    assert any(
        "Transaction amount is blank" in item["message"] for item in plan["issues"]
    )


def test_unknown_transaction_type_is_flagged_and_excluded():
    transactions = transactions_xlsx(
        [
            tx("15-01-2024", "Apex Bluechip Fund", "F001", "Alice Example", "BONUS ISSUE", "1000"),
        ]
    )
    plan = build_preview(four_files(transactions=transactions))

    assert plan["transactions"][0]["transaction_type"] == "unknown"
    assert plan["counts"]["unknown_transactions"] == 1
    assert any(
        "Unknown transaction type" in item["message"] for item in plan["issues"]
    )


def test_transaction_folio_not_found_is_reported():
    transactions = transactions_xlsx(
        [
            tx("15-01-2024", "Apex Bluechip Fund", "F999", "Alice Example", "PURCHASE", "1000"),
        ]
    )
    plan = build_preview(four_files(transactions=transactions))

    assert plan["transactions"][0]["match_status"] == "folio_not_found"
    assert plan["counts"]["transactions_unmatched"] == 1
    assert any(
        "was not found in the Folios export" in item["message"]
        for item in plan["issues"]
    )


def test_scheme_name_mismatch_between_transactions_and_folios_is_reported():
    transactions = transactions_xlsx(
        [
            tx("15-01-2024", "Different Scheme Name", "F001", "Alice Example", "PURCHASE", "1000"),
        ]
    )
    plan = build_preview(four_files(transactions=transactions))

    assert plan["transactions"][0]["match_status"] == "scheme_mismatch"
    assert plan["counts"]["transactions_unmatched"] == 1
    assert any(
        "does not match the Folios scheme" in item["message"]
        for item in plan["issues"]
    )


def test_folio_aum_missing_keeps_invested_amount_but_marks_return_not_available(client):
    folios = folios_xlsx(
        [
            (
                "C001",
                "",
                "",
                "F001",
                "Apex Bluechip Fund",
                "100",
                "",
                "Single",
                "Alice Example",
                "",
            ),
            (
                "C001",
                "",
                "",
                "F002",
                "Apex Midcap Fund",
                "50",
                "5000",
                "Single",
                "Alice Example",
                "",
            ),
        ]
    )
    _, dashboard = preview_and_confirm(client, four_files(folios=folios))
    folio = next(
        item for item in dashboard["folios"] if item["folio_number"] == "F001"
    )

    assert folio["aum"] is None
    assert folio["gross_invested"] == 10000.0
    assert folio["absolute_return"] is None
    assert folio["xirr"] is None
    assert any("Folio AUM is not available" in note for note in folio["notes"])


def test_portfolio_current_value_missing_marks_reconciliation_not_available(client):
    portfolio = portfolio_xlsx(
        rows=[
            ("C001", "", "Alice Example", "0", "0", "", "0", "0", "0", "0", "0", "0"),
            ("C002", "", "Bob Example", "0", "0", "7000", "0", "0", "0", "0", "0", "0"),
        ],
        total_current=None,
    )
    preview, dashboard = preview_and_confirm(
        client, four_files(portfolio=portfolio)
    )
    alice = next(
        item for item in dashboard["clients"] if item["name"] == "Alice Example"
    )

    assert preview["can_confirm"] is True
    assert alice["current_value"] is None
    assert alice["reconciliation_status"] == "not_available"
    assert any(
        "client-level current value is missing" in item["message"]
        for item in dashboard["issues"]
    )


def test_folio_aum_total_mismatch_creates_reconciliation_warning(client):
    portfolio = portfolio_xlsx(
        rows=[
            ("C001", "", "Alice Example", "0", "0", "14000", "0", "0", "0", "0", "0", "0"),
            ("C002", "", "Bob Example", "0", "0", "7000", "0", "0", "0", "0", "0", "0"),
        ],
        total_current="21000",
    )
    _, dashboard = preview_and_confirm(
        client, four_files(portfolio=portfolio)
    )
    alice = next(
        item for item in dashboard["clients"] if item["name"] == "Alice Example"
    )

    assert alice["reconciliation_status"] == "mismatch"
    assert alice["difference"] == 1000.0
    assert dashboard["summary"]["reconciliation_warnings"] == 1
    assert any(
        "sum of folio AUM does not match" in item["message"]
        for item in dashboard["issues"]
    )


def test_benchmark_mapping_missing_shows_not_available(client):
    _, dashboard = preview_and_confirm(client, four_files())
    folio = next(
        item for item in dashboard["folios"] if item["folio_number"] == "F001"
    )

    assert folio["benchmark_status"] == "needs_review"
    assert folio["benchmark_comparison_status"] == "mapping_needs_review"
    assert folio["benchmark_xirr"] is None
    assert folio["benchmark_difference"] is None


def test_benchmark_level_data_missing_shows_not_available(client):
    _, dashboard = preview_and_confirm(client, four_files())
    review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI")
    dashboard = client.get("/api/v1/dashboard").json()
    folio = next(
        item for item in dashboard["folios"] if item["folio_number"] == "F001"
    )

    assert folio["benchmark_status"] == "reviewed"
    assert folio["benchmark_comparison_status"] == "levels_missing"
    assert folio["benchmark_return"] is None
    assert folio["benchmark_difference"] is None


def test_reviewed_mapping_and_local_levels_enable_benchmark_comparison(client):
    _, _dashboard = preview_and_confirm(client, four_files())
    review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI")
    review_mapping(client, "Apex Midcap Fund", "Nifty 50 TRI")
    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2024-01-15", "100"),
            ("Nifty 50 TRI", "2025-01-15", "110"),
            ("Nifty 50 TRI", "2025-06-15", "115"),
            ("Nifty 50 TRI", "2026-10-27", "130"),
        ],
    )
    dashboard = client.get("/api/v1/dashboard").json()
    folios = {item["folio_number"]: item for item in dashboard["folios"]}
    lump_sum = folios["F001"]
    sip = folios["F002"]

    assert lump_sum["benchmark_status"] == "reviewed"
    assert lump_sum["benchmark_comparison_status"] == "available"
    assert lump_sum["benchmark_comparison_method"] == "point_to_point"
    assert lump_sum["benchmark_return_type"] == "absolute"
    assert lump_sum["benchmark_return"] == pytest.approx(30.0)
    assert lump_sum["benchmark_difference"] == pytest.approx(
        lump_sum["absolute_return"] - lump_sum["benchmark_return"]
    )
    assert sip["benchmark_comparison_status"] == "available"
    assert sip["benchmark_comparison_method"] == "cash_flow_xirr"
    assert sip["benchmark_xirr"] is not None
    assert sip["benchmark_difference"] == pytest.approx(
        sip["xirr"] - sip["benchmark_xirr"]
    )
    assert dashboard["summary"]["benchmark_comparisons_available"] == 2
    assert dashboard["summary"]["benchmark_point_to_point"] == 1
    assert dashboard["summary"]["benchmark_cash_flow"] == 1


def test_local_benchmark_simulation_uses_same_dated_cash_flows():
    result = simulate_benchmark(
        [
            SignedCashFlow(date(2025, 1, 15), Decimal("-1000")),
            SignedCashFlow(date(2025, 7, 15), Decimal("500")),
        ],
        {
            date(2025, 1, 15): Decimal("100"),
            date(2025, 7, 15): Decimal("110"),
            date(2026, 1, 15): Decimal("120"),
        },
        date(2026, 1, 15),
    )

    assert result["status"] == "available"
    assert result["current_value"] > 0
    assert result["xirr"] is not None


def test_headerless_portfolio_csv_uses_fixed_layout_with_warning():
    files = three_files()
    files["portfolio"] = ("portfolio.csv", portfolio_csv())
    plan = build_preview(files)

    assert plan["can_confirm"] is True
    assert plan["detected_columns"]["portfolio"]["headerless"] is True
    assert any(
        "fixed 13-column" in item["message"] for item in plan["issues"]
    )
    assert plan["valuations"][0]["current_value"] == "15000"


def test_headerless_portfolio_csv_with_wrong_structure_is_blocked():
    rows = [
        ["Client A", "", "C001", "", "0", "0", "15000", "0", "0", "0", "0", "0", "0", "EXTRA"],
    ]
    files = three_files()
    files["portfolio"] = ("portfolio.csv", portfolio_csv(rows=rows))
    with pytest.raises(Exception) as error:
        build_preview(files)
    assert "more than 13 columns" in str(error.value)


def test_transaction_classification_variants():
    assert classify_transaction("SIP") == "sip"
    assert classify_transaction("SWITCH OUT") == "switch_out"
    assert classify_transaction("SWITCH IN") == "switch_in"
    assert classify_transaction("REDEMPTION") == "redemption"
    assert classify_transaction("PURCHASE") == "purchase"
    assert classify_transaction("SWITCH", source_scheme_name="A") == "switch_out"
    assert classify_transaction("SWITCH", target_scheme_name="B") == "switch_in"
    assert classify_transaction("SOMETHING ELSE") == "unknown"


def test_configured_alias_order_wins_over_lookalike_columns():
    """A file can contain both FUND NAME and SCHEME NAME or ACCOUNT NO and FOLIO NO."""

    assert column_aliases("transactions")["scheme_name"][0] == "SCHEME NAME"
    assert column_aliases("folios")["folio_number"][0] == "FOLIO NO"
