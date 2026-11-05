"""Milestone 7: large real-file imports, diagnostics and date coverage."""

from __future__ import annotations

import csv
import io
import json
import time

from mfd_dashboard.core.paths import PREVIEWS_DIR, UPLOADS_DIR
from mfd_dashboard.ingest.service import build_preview

from .fixtures import (
    CLIENT_HEADERS,
    TRANSACTION_HEADERS,
    _workbook_bytes,
    clients_xlsx,
    four_files,
    folios_xlsx,
    portfolio_xlsx,
    three_files,
    transactions_xlsx,
)


FILE_FIELDS = {
    "clients": "clients_file",
    "folios": "folios_file",
    "portfolio": "portfolio_file",
    "transactions": "transactions_file",
}


def upload_preview(client, files: dict[str, tuple[str, bytes]]):
    return client.post(
        "/api/v1/imports/preview",
        files={
            FILE_FIELDS[kind]: (name, data, "application/octet-stream")
            for kind, (name, data) in files.items()
        },
    )


def preview_and_confirm(client, files: dict[str, tuple[str, bytes]]):
    preview = upload_preview(client, files)
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["can_confirm"] is True, payload["issues"]
    confirmed = client.post(f"/api/v1/imports/{payload['import_id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    return payload, confirmed.json()


def csv_bytes(headers: list[str], rows) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def mapping_for(client, scheme_name: str) -> dict:
    payload = client.get("/api/v1/benchmark-mappings").json()
    return next(
        item for item in payload["mappings"] if item["scheme_name"] == scheme_name
    )


def review_mapping(client, scheme_name: str, benchmark_name: str) -> dict:
    scheme = mapping_for(client, scheme_name)
    response = client.patch(
        f"/api/v1/benchmark-mappings/{scheme['scheme_id']}",
        json={"benchmark_name": benchmark_name},
    )
    assert response.status_code == 200, response.text
    return response.json()


def import_levels(client, rows: list[tuple[str, str, str]]) -> None:
    lines = ["benchmark_name,date,level"]
    lines.extend(f"{name},{day},{level}" for name, day, level in rows)
    response = client.post(
        "/api/v1/benchmarks/levels/import",
        files={
            "file": (
                "benchmark-levels.csv",
                "\n".join(lines).encode("utf-8"),
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text


def folio_row(dashboard: dict, folio_number: str) -> dict:
    return next(
        item for item in dashboard["folios"] if item["folio_number"] == folio_number
    )


def test_public_preview_is_compact_but_full_plan_is_kept(client):
    preview_response = upload_preview(client, four_files())
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()

    assert preview["preview_rows_omitted"] is True
    assert "clients" not in preview
    assert "folios" not in preview
    assert "transactions" not in preview
    assert preview["file_reports"]["transactions"]["supplied"] is True
    assert preview["counts"]["transactions_imported"] == 3

    stored = json.loads(
        (PREVIEWS_DIR / f"{preview['import_id']}.json").read_text(encoding="utf-8")
    )
    assert len(stored["clients"]) == 2
    assert len(stored["folios"]) == 3
    assert len(stored["transactions"]) == 3

    confirmed = client.post(f"/api/v1/imports/{preview['import_id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["imported"]["transactions"] == 3

    # Temporary upload folders are removed after the request.
    assert list(UPLOADS_DIR.glob("mfd-upload-*")) == []


def test_blank_total_and_duplicate_rows_are_skipped_and_reported():
    blank_client = ("", "", "", "", "", "", "", "", "")
    clients = clients_xlsx(
        rows=[
            ("C001", "", "", "Alice Example", "01-01-2020", "15000", "", "", ""),
            blank_client,
            ("", "", "", "Total", "", "", "", "", ""),
            ("C001", "", "", "Alice Example", "01-01-2020", "15000", "", "", ""),
        ]
    )
    folios = folios_xlsx(
        rows=[
            ("C001", "", "", "F001", "Apex Bluechip Fund", "100", "15000", "Single", "Alice Example", ""),
            ("", "", "", "", "", "", "", "", "", ""),
            ("", "", "", "", "Total", "", "", "", "", ""),
            ("C001", "", "", "F001", "Apex Bluechip Fund", "100", "15000", "Single", "Alice Example", ""),
        ]
    )
    portfolio_row = (
        "C001",
        "",
        "Alice Example",
        "150",
        "12000",
        "15000",
        "3000",
        "25.00",
        "12.00",
        "1000",
        "10",
        "0",
    )
    portfolio = portfolio_xlsx(
        rows=[portfolio_row, portfolio_row],
        total_current="15000",
    )
    transaction_row = (
        "15-01-2024",
        "Apex Bluechip Fund",
        "F001",
        "Alice Example",
        "",
        "PURCHASE",
        "10000",
        "100",
        "100",
        "LUMPSUM PURCHASE",
        "",
        "",
        "C001",
        "",
        "",
        "",
    )
    transactions = transactions_xlsx(
        rows=[
            transaction_row,
            ("",) * 16,
            ("", "", "", "Total", "", "", "", "", "", "", "", "", "", "", "", ""),
            transaction_row,
        ]
    )

    plan = build_preview(
        four_files(
            clients=clients,
            folios=folios,
            portfolio=portfolio,
            transactions=transactions,
        )
    )

    assert plan["can_confirm"] is True
    assert plan["counts"]["clients_imported"] == 1
    assert plan["counts"]["folios_imported"] == 1
    assert plan["counts"]["transactions_imported"] == 1
    assert plan["counts"]["portfolio_imported"] == 1
    assert plan["counts"]["blank_rows"] == 3
    assert plan["counts"]["total_rows"] == 4
    assert plan["counts"]["duplicate_rows"] == 4

    assert plan["file_reports"]["clients"]["rows_read"] == 4
    assert plan["file_reports"]["clients"]["blank_rows"] == 1
    assert plan["file_reports"]["clients"]["total_rows"] == 1
    assert plan["file_reports"]["clients"]["duplicate_rows"] == 1
    assert plan["file_reports"]["clients"]["skipped_rows"] == 3
    assert plan["file_reports"]["transactions"]["skipped_rows"] == 3
    assert any(
        "Duplicate" in issue["message"] for issue in plan["issues"]
    )


def test_missing_files_bad_formats_oversize_and_missing_headers(client, monkeypatch):
    missing = client.post(
        "/api/v1/imports/preview",
        files={
            "folios_file": ("Folios.xlsx", folios_xlsx(), "application/octet-stream"),
        },
    )
    assert missing.status_code == 422
    assert "Client Details file is missing" in missing.json()["detail"]

    wrong_type = upload_preview(
        client,
        {
            "clients": ("Client Details.txt", b"IWELL CODE,NAME\nC001,Alice\n"),
            "folios": ("Folios.xlsx", folios_xlsx()),
            "portfolio": ("Portfolio.xlsx", portfolio_xlsx()),
        },
    )
    assert wrong_type.status_code == 400
    assert "must be an .xlsx or .csv" in wrong_type.json()["detail"]

    bad_workbook = upload_preview(
        client,
        {
            "clients": ("Client Details.xlsx", b"not a workbook"),
            "folios": ("Folios.xlsx", folios_xlsx()),
            "portfolio": ("Portfolio.xlsx", portfolio_xlsx()),
        },
    )
    assert bad_workbook.status_code == 400
    assert "could not be read as an XLSX" in bad_workbook.json()["detail"]

    from mfd_dashboard.api import routes

    monkeypatch.setattr(routes, "MAX_FILE_SIZE", 512)
    oversized = upload_preview(client, four_files())
    monkeypatch.setattr(routes, "MAX_FILE_SIZE", 25 * 1024 * 1024)
    assert oversized.status_code == 413
    assert "larger than 25 MB" in oversized.json()["detail"]
    assert list(UPLOADS_DIR.glob("mfd-upload-*")) == []

    missing_header = build_preview(
        four_files(
            clients=_workbook_bytes(
                [["IWELL CODE", "PAN"], ["C001", "REDACTED"]],
                "Client Details",
            )
        )
    )
    assert missing_header["can_confirm"] is False
    assert any(
        issue["field"] == "name" and "not found" in issue["message"]
        for issue in missing_header["issues"]
    )

    missing_report_date = build_preview(
        four_files(portfolio=portfolio_xlsx(report_date=None))
    )
    assert missing_report_date["can_confirm"] is False
    assert any(
        "report date was not found" in issue["message"]
        for issue in missing_report_date["issues"]
    )

    mixed_dates = four_files()
    mixed_dates = {
        kind: (
            {
                "clients": "Client Details-27-10-2026.xlsx",
                "folios": "Folios-27-10-2026.xlsx",
                "portfolio": "PortfolioValuationReportMF-26-10-2026.xlsx",
                "transactions": "Transaction Statement-27-10-2026.xlsx",
            }[kind],
            data,
        )
        for kind, (_, data) in mixed_dates.items()
    }
    run_check = build_preview(mixed_dates)["export_run"]
    assert run_check["status"] == "review"
    assert "2026-10-26" in run_check["message"]
    assert "same InvestWell export run" in run_check["message"]


def test_invalid_dates_and_amounts_are_explained_and_not_used():
    bad_rows = [
        (
            "not-a-date",
            "Apex Bluechip Fund",
            "F001",
            "Alice Example",
            "",
            "PURCHASE",
            "10000",
            "100",
            "100",
            "BAD DATE",
            "",
            "",
            "C001",
            "",
            "",
            "",
        ),
        (
            "15-01-2024",
            "Apex Bluechip Fund",
            "F001",
            "Alice Example",
            "",
            "PURCHASE",
            "not-a-number",
            "100",
            "100",
            "BAD AMOUNT",
            "",
            "",
            "C001",
            "",
            "",
            "",
        ),
    ]
    plan = build_preview(four_files(transactions=transactions_xlsx(rows=bad_rows)))

    assert plan["can_confirm"] is True
    assert plan["counts"]["invalid_date_rows"] == 1
    assert plan["counts"]["invalid_number_rows"] == 1
    assert plan["file_reports"]["transactions"]["invalid_date_rows"] == 1
    assert plan["file_reports"]["transactions"]["invalid_number_rows"] == 1
    messages = " ".join(issue["message"] for issue in plan["issues"])
    assert "Transaction date is missing or could not be read" in messages
    assert "TOTAL AMOUNT could not be read as a number" in messages
    assert "not-a-number" not in messages


def test_unmatched_clients_and_transactions_are_reported():
    transaction_rows = [
        (
            "15-01-2024",
            "Apex Bluechip Fund",
            "F001",
            "Alice Example",
            "",
            "PURCHASE",
            "10000",
            "100",
            "100",
            "VALID",
            "",
            "",
            "C001",
            "",
            "",
            "",
        ),
        (
            "15-01-2024",
            "Unknown Fund",
            "F999",
            "Missing Person",
            "",
            "PURCHASE",
            "5000",
            "50",
            "100",
            "UNMATCHED",
            "",
            "",
            "C999",
            "",
            "",
            "",
        ),
    ]
    plan = build_preview(
        four_files(transactions=transactions_xlsx(rows=transaction_rows))
    )

    assert plan["can_confirm"] is True
    assert plan["counts"]["unmatched_folios"] == 1
    assert plan["counts"]["unmatched_portfolio_rows"] == 1
    assert plan["counts"]["transactions_unmatched"] == 1
    assert plan["client_matching"]["status"] == "review"
    assert plan["client_matching"]["transactions"]["unmatched"] == 1
    assert "unmatched" in plan["client_matching"]["message"]
    assert any(
        issue["severity"] == "warning"
        and "was not found in the Folios export" in issue["message"]
        for issue in plan["issues"]
    )

    all_unmatched = build_preview(
        three_files(
            clients=clients_xlsx(
                rows=[
                    (
                        "C001",
                        "",
                        "",
                        "Alice Example",
                        "01-01-2020",
                        "15000",
                        "",
                        "",
                        "",
                    )
                ]
            ),
            folios=folios_xlsx(
                rows=[
                    (
                        "C999",
                        "",
                        "",
                        "F900",
                        "Apex Small Cap Fund",
                        "10",
                        "1000",
                        "Single",
                        "Other Person",
                        "",
                    )
                ]
            ),
            portfolio=portfolio_xlsx(
                rows=[
                    (
                        "C900",
                        "",
                        "Other Person",
                        "10",
                        "2000",
                        "2000",
                        "0",
                        "0",
                        "0",
                        "0",
                        "0",
                        "0",
                    )
                ]
            ),
        )
    )
    assert all_unmatched["can_confirm"] is False
    assert all_unmatched["client_matching"]["status"] == "review"
    assert any(
        issue["severity"] == "error"
        and "No client rows could be matched" in issue["message"]
        for issue in all_unmatched["issues"]
    )


def test_preview_issue_lists_are_capped_but_counts_are_complete(client):
    rows = [
        (
            "not-a-date",
            "Apex Midcap Fund",
            "F002",
            "Alice Example",
            "",
            "SIP",
            "1000",
            str(index + 1),
            "100",
            f"BAD DATE {index}",
            "",
            "",
            "C001",
            "",
            "",
            "",
        )
        for index in range(210)
    ]
    response = upload_preview(
        client,
        four_files(transactions=transactions_xlsx(rows=rows)),
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["issue_count"] > 200
    assert payload["preview_issues_truncated"] is True
    assert len(payload["issues"]) == 201
    assert "Showing the first 200" in payload["issues"][-1]["message"]
    assert payload["file_reports"]["transactions"]["invalid_date_rows"] == 210
    assert payload["counts"]["invalid_date_rows"] == 210


def test_benchmark_coverage_reports_exact_missing_dates_and_then_updates(client):
    _, _dashboard = preview_and_confirm(client, four_files())

    initial = client.get("/api/v1/benchmarks/coverage").json()
    assert initial["summary"]["schemes_total"] == 3
    assert initial["summary"]["schemes_needs_review"] == 3
    initial_mapping = mapping_for(client, "Apex Bluechip Fund")
    assert initial_mapping["coverage_status"] == "needs_review"

    review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI")
    review_mapping(client, "Apex Midcap Fund", "Nifty 50 TRI")

    no_levels = client.get("/api/v1/benchmarks/coverage").json()
    assert no_levels["summary"]["schemes_no_levels"] >= 1
    series = next(
        item for item in no_levels["series"] if item["benchmark_name"] == "Nifty 50 TRI"
    )
    assert series["coverage_status"] == "no_levels"
    assert series["missing_date_count"] == series["required_date_count"]
    dashboard = client.get("/api/v1/dashboard").json()
    bluechip = folio_row(dashboard, "F001")
    assert bluechip["benchmark_comparison_status"] == "levels_missing"
    assert bluechip["benchmark_missing_date_count"] == 2
    assert bluechip["benchmark_missing_dates"] == ["2024-01-15", "2026-10-27"]

    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2024-01-15", "100"),
            ("Nifty 50 TRI", "2026-10-27", "130"),
        ],
    )
    partial = client.get("/api/v1/benchmarks/coverage").json()
    series = next(
        item for item in partial["series"] if item["benchmark_name"] == "Nifty 50 TRI"
    )
    assert series["coverage_status"] == "missing_dates"
    assert series["covers_valuation_date"] is True
    assert series["covers_first_transaction"] is False
    assert series["covers_all_comparison_dates"] is False
    assert series["missing_dates"] == ["2025-01-15", "2025-06-15"]
    assert partial["summary"]["valuation_date_missing_in"] == []
    assert partial["summary"]["first_transaction_missing_in"] == ["Nifty 50 TRI"]

    midcap_mapping = mapping_for(client, "Apex Midcap Fund")
    assert midcap_mapping["coverage_status"] == "missing_dates"
    assert midcap_mapping["coverage_missing_dates"] == [
        "2025-01-15",
        "2025-06-15",
    ]
    assert midcap_mapping["covers_first_transaction"] is False
    assert midcap_mapping["covers_valuation_date"] is True

    dashboard = client.get("/api/v1/dashboard").json()
    midcap = folio_row(dashboard, "F002")
    assert midcap["benchmark_comparison_status"] == "levels_missing"
    assert midcap["benchmark_missing_dates"] == ["2025-01-15", "2025-06-15"]
    assert midcap["benchmark_missing_date_count"] == 2

    graph = client.get("/api/v1/benchmark-graph").json()
    node = next(
        item
        for cluster in graph["clusters"]
        for item in cluster["folios"]
        if item["folio_number"] == "F002"
    )
    assert node["benchmark_missing_dates"] == ["2025-01-15", "2025-06-15"]
    assert node["benchmark_comparison_status"] == "levels_missing"
    assert node["performance"] == "needs_review"

    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2025-01-15", "110"),
            ("Nifty 50 TRI", "2025-06-15", "120"),
        ],
    )
    covered = client.get("/api/v1/benchmarks/coverage").json()
    series = next(
        item for item in covered["series"] if item["benchmark_name"] == "Nifty 50 TRI"
    )
    assert series["coverage_status"] == "covered"
    assert series["missing_dates"] == []
    assert series["covers_all_comparison_dates"] is True
    dashboard = client.get("/api/v1/dashboard").json()
    assert folio_row(dashboard, "F002")["benchmark_comparison_status"] == "available"
    assert mapping_for(client, "Apex Midcap Fund")["coverage_status"] == "covered"


def test_large_import_5000_folios_and_10000_transactions(client):
    client_rows = [
        (
            f"C{index:03d}",
            "",
            "",
            f"Client {index:03d}",
            "01-01-2020",
            "50000",
            "REDACTED",
            "client@example.invalid",
            "REDACTED",
        )
        for index in range(1, 101)
    ]
    folio_rows = []
    transaction_rows = []
    for index in range(1, 5001):
        client_index = ((index - 1) % 100) + 1
        client_code = f"C{client_index:03d}"
        client_name = f"Client {client_index:03d}"
        folio_number = f"F{index:05d}"
        folio_rows.append(
            (
                client_code,
                "",
                "",
                folio_number,
                "Apex Bluechip Fund",
                "100",
                "100",
                "Single",
                client_name,
                "REDACTED",
            )
        )
        for day in ("15-01-2024", "15-06-2024"):
            transaction_rows.append(
                (
                    day,
                    "Apex Bluechip Fund",
                    folio_number,
                    client_name,
                    "",
                    "PURCHASE",
                    "1000",
                    "10",
                    "100",
                    "LARGE IMPORT",
                    "",
                    "",
                    client_code,
                    "",
                    "",
                    "",
                )
            )

    portfolio_rows = [
        (
            f"C{index:03d}",
            "",
            f"Client {index:03d}",
            "500",
            "4000",
            "5000",
            "1000",
            "25.00",
            "12.00",
            "900",
            "0",
            "0",
        )
        for index in range(1, 101)
    ]
    files = four_files(
        clients=csv_bytes(CLIENT_HEADERS, client_rows),
        folios=csv_bytes(
            [
                "IWELL CODE",
                "IWELLCODE2",
                "APP CODE",
                "FOLIO NO",
                "SCHEME NAME",
                "UNITS",
                "AUM",
                "FOLIO TYPE",
                "CLIENT NAME",
                "PAN",
            ],
            folio_rows,
        ),
        portfolio=portfolio_xlsx(
            rows=portfolio_rows,
            total_current="500000",
        ),
        transactions=csv_bytes(TRANSACTION_HEADERS, transaction_rows),
    )
    # Use explicit filenames with the same export date.
    files = {
        kind: (
            {
                "clients": "Client Details-27-10-2026.csv",
                "folios": "Folios-27-10-2026.csv",
                "portfolio": "PortfolioValuationReportMF-27-10-2026.xlsx",
                "transactions": "Transaction Statement-27-10-2026.csv",
            }[kind],
            data,
        )
        for kind, (_, data) in files.items()
    }

    started = time.perf_counter()
    preview_response = upload_preview(client, files)
    preview_elapsed = time.perf_counter() - started
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["can_confirm"] is True, preview["issues"][:5]
    assert preview["counts"]["clients_imported"] == 100
    assert preview["counts"]["folios_imported"] == 5000
    assert preview["counts"]["transactions_imported"] == 10000
    assert preview["counts"]["portfolio_imported"] == 100
    assert preview["export_run"]["status"] == "consistent"
    assert preview_elapsed < 60

    started = time.perf_counter()
    confirmed = client.post(f"/api/v1/imports/{preview['import_id']}/confirm")
    confirm_elapsed = time.perf_counter() - started
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["imported"]["folios"] == 5000
    assert confirmed.json()["imported"]["transactions"] == 10000
    assert confirm_elapsed < 60

    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["summary"]["clients"] == 100
    assert dashboard["summary"]["folios"] == 5000
    assert dashboard["summary"]["transactions"] == 10000
