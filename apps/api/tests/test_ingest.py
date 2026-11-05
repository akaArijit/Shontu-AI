from __future__ import annotations

from decimal import Decimal

from mfd_dashboard.ingest.service import build_preview
from mfd_dashboard.ingest.values import (
    clean_code,
    is_sensitive_header,
    normalize_code,
    parse_decimal,
)

from .fixtures import (
    _workbook_bytes,
    clients_xlsx,
    folios_xlsx,
    portfolio_xlsx,
    three_files,
)


def test_preview_matches_clients_and_marks_unmatched():
    plan = build_preview(three_files())

    assert plan["can_confirm"] is True
    assert plan["report_date"] == "2026-10-27"
    assert plan["counts"]["clients_imported"] == 2
    assert plan["counts"]["folios_imported"] == 3
    assert plan["counts"]["portfolio_imported"] == 3
    assert plan["counts"]["portfolio_rows"] == 3
    assert plan["counts"]["needs_review"] == 3
    assert plan["counts"]["unmatched_folios"] == 1
    assert plan["counts"]["unmatched_portfolio_rows"] == 1

    statuses = {item["folio_number"]: item["match_status"] for item in plan["folios"]}
    assert statuses["F001"] == "matched"
    assert statuses["F900"] == "unmatched"
    assert all(item["benchmark_status"] == "needs_review" for item in plan["schemes"])

    reconciliation = {item["client_name"]: item for item in plan["reconciliation"]}
    assert reconciliation["Alice Example"]["status"] == "matched"
    assert reconciliation["Alice Example"]["difference"] == "0"
    assert reconciliation["Bob Example"]["status"] == "no_folios"


def test_name_fallback_is_used_only_when_exact_and_unique():
    files = three_files(
        clients=clients_xlsx(
            [("C001", "", "", "Alice Example", "01-01-2020", "15000", "", "", "")]
        ),
        folios=folios_xlsx(
            [
                (
                    "",
                    "",
                    "",
                    "F001",
                    "Apex Bluechip Fund",
                    "100",
                    "10000",
                    "Single",
                    "Alice Example",
                    "",
                )
            ]
        ),
    )
    plan = build_preview(files)
    assert plan["folios"][0]["match_status"] == "name_fallback"
    assert any("exact client name" in item["message"] for item in plan["issues"])


def test_client_codes_remain_text_and_leading_apostrophe_is_trimmed():
    files = three_files(
        clients=clients_xlsx(
            [("'00123", "", "", "Alice Example", "01-01-2020", "", "", "", "")]
        ),
        folios=folios_xlsx(
            [
                (
                    "00123",
                    "",
                    "",
                    "F001",
                    "Apex Bluechip Fund",
                    "100",
                    "10000",
                    "Single",
                    "Alice Example",
                    "",
                )
            ]
        ),
    )
    plan = build_preview(files)
    assert plan["clients"][0]["iwell_code"] == "00123"
    assert plan["folios"][0]["match_status"] == "matched"
    assert normalize_code(" '00123 ") == "00123"


def test_incomplete_folio_and_malformed_numbers_are_reported_not_guessed():
    files = three_files(
        folios=folios_xlsx(
            [
                (
                    "C001",
                    "",
                    "",
                    "F001",
                    "Apex Bluechip Fund",
                    "100",
                    "not-a-number",
                    "Single",
                    "Alice Example",
                    "",
                ),
                (
                    "C001",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "Single",
                    "Alice Example",
                    "",
                ),
            ]
        ),
        portfolio=portfolio_xlsx(
            rows=[
                (
                    "C001",
                    "",
                    "Alice Example",
                    "0",
                    "0",
                    "15000",
                    "0",
                    "0",
                    "0",
                    "0",
                    "bad",
                    "0",
                )
            ],
            total_current="15000",
        ),
    )
    plan = build_preview(files)
    assert plan["counts"]["folios_imported"] == 1
    assert plan["counts"]["folios_skipped"] == 1
    assert plan["folios"][0]["aum"] is None
    assert plan["valuations"][0]["one_day_change"] is None
    messages = " ".join(item["message"] for item in plan["issues"])
    assert "could not be read as a number" in messages
    assert "Incomplete folio row skipped" in messages


def test_missing_required_column_blocks_confirmation():
    folios_without_scheme = _workbook_bytes(
        [
            ["IWELL CODE", "FOLIO NO", "AUM"],
            ["C001", "F001", "10000"],
        ],
        "Folios",
    )
    plan = build_preview(three_files(folios=folios_without_scheme))
    assert plan["can_confirm"] is False
    assert plan["counts"]["errors"] >= 1
    assert any("SCHEME NAME" in item["message"] for item in plan["issues"])


def test_missing_report_date_blocks_confirmation():
    plan = build_preview(three_files(portfolio=portfolio_xlsx(report_date=None)))
    assert plan["can_confirm"] is False
    assert any("report date was not found" in item["message"] for item in plan["issues"])


def test_all_rows_unmatched_blocks_confirmation():
    files = three_files(
        clients=clients_xlsx(
            [("C001", "", "", "Alice Example", "01-01-2020", "", "", "", "")]
        ),
        folios=folios_xlsx(
            [
                (
                    "C999",
                    "",
                    "",
                    "F900",
                    "Apex Small Cap Fund",
                    "10",
                    "1000",
                    "Single",
                    "Other Client",
                    "",
                )
            ]
        ),
        portfolio=portfolio_xlsx(
            rows=[
                (
                    "C900",
                    "",
                    "Other Client",
                    "0",
                    "2000",
                    "2000",
                    "0",
                    "0",
                    "0",
                    "0",
                    "0",
                    "0",
                )
            ],
            total_current="2000",
        ),
    )
    plan = build_preview(files)
    assert plan["can_confirm"] is False
    assert any(
        item["severity"] == "error" and "No client rows could be matched" in item["message"]
        for item in plan["issues"]
    )


def test_total_row_is_skipped_and_duplicate_client_valuation_is_reported():
    portfolio = portfolio_xlsx(
        rows=[
            ("C001", "", "Alice Example", "0", "0", "15000", "0", "0", "0", "0", "0", "0"),
            ("C002", "", "Bob Example", "0", "0", "7000", "0", "0", "0", "0", "0", "0"),
            ("C001", "", "Alice Example", "0", "0", "15000", "0", "0", "0", "0", "0", "0"),
        ],
        total_current="22000",
    )
    plan = build_preview(three_files(portfolio=portfolio))
    assert plan["counts"]["portfolio_rows"] == 3
    assert plan["counts"]["portfolio_imported"] == 2
    assert all(item["source_client_name"] != "Total" for item in plan["valuations"])
    assert any("Duplicate client valuation" in item["message"] for item in plan["issues"])


def test_value_helpers_are_strict_and_privacy_aware():
    assert clean_code(" '00123 ") == "00123"
    assert clean_code(123.0) == "123"
    assert parse_decimal("₹ 1,23,456.78") == Decimal("123456.78")
    assert parse_decimal("(1,000)") == Decimal("-1000")
    assert parse_decimal("n/a") is None
    assert parse_decimal("12.5%") == Decimal("12.5")
    assert is_sensitive_header("PAN Number") is True
    assert is_sensitive_header("Mobile No") is True
    assert is_sensitive_header("IWELL CODE") is False
    assert is_sensitive_header("CLIENT NAME") is False
