"""Milestone 7 feedback: scheme bulk mapping, keyword rules and import/export."""

from __future__ import annotations

import csv
import io
from io import BytesIO

from openpyxl import load_workbook

from .fixtures import (
    clients_xlsx,
    folios_xlsx,
    four_files,
    portfolio_xlsx,
    transactions_xlsx,
)


FILE_FIELDS = {
    "clients": "clients_file",
    "folios": "folios_file",
    "portfolio": "portfolio_file",
    "transactions": "transactions_file",
}


def load_demo(client) -> dict:
    response = client.post("/api/v1/demo/load?replace=true")
    assert response.status_code == 200, response.text
    return response.json()


def confirm_upload(client, files: dict[str, tuple[str, bytes]]) -> dict:
    preview = client.post(
        "/api/v1/imports/preview",
        files={
            FILE_FIELDS[kind]: (name, data, "application/octet-stream")
            for kind, (name, data) in files.items()
        },
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["can_confirm"] is True, payload["issues"]
    confirmed = client.post(f"/api/v1/imports/{payload['import_id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def mappings(client) -> dict:
    response = client.get("/api/v1/benchmark-mappings")
    assert response.status_code == 200, response.text
    return response.json()


def mapping_named(client, scheme_name: str) -> dict:
    return next(
        item
        for item in mappings(client)["mappings"]
        if item["scheme_name"] == scheme_name
    )


def csv_upload(content: bytes, name: str = "mapping.csv"):
    return {"file": (name, content, "text/csv")}


def xlsx_upload(content: bytes, name: str = "mapping.xlsx"):
    return {
        "file": (
            name,
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


def test_bulk_scheme_mapping_updates_every_related_folio_and_status_counts(client):
    load_demo(client)
    before = mappings(client)
    target = next(
        item
        for item in before["mappings"]
        if item["scheme_name"] == "Apex Unknown Sector Fund"
    )
    assert target["review_status"] == "needs_mapping"
    assert target["folio_count"] == 1
    assert before["status_summary"]["unmapped_folios"] == 1

    response = client.post(
        "/api/v1/benchmark-mappings/bulk",
        json={
            "scheme_ids": [target["scheme_id"]],
            "benchmark_name": "Nifty Smallcap 250 TRI",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["updated_schemes"] == 1
    assert payload["updated_folios"] == 1
    assert payload["previous_unmapped_folios"] == 1
    assert payload["unmapped_folios"] == 0
    assert payload["folios_moved_out_of_unmapped"] == 1
    assert payload["status_summary"]["total_schemes"] == 14
    assert payload["status_summary"]["mapped_schemes"] == 14
    assert payload["status_summary"]["unmapped_schemes"] == 0
    assert payload["status_summary"]["unmapped_folios"] == 0

    updated = mapping_named(client, "Apex Unknown Sector Fund")
    assert updated["benchmark_name"] == "Nifty Smallcap 250 TRI"
    assert updated["review_status"] == "reviewed"
    assert updated["source"] == "bulk"
    assert updated["folio_count"] == 1

    dashboard = client.get("/api/v1/dashboard").json()
    folios = [
        item
        for item in dashboard["folios"]
        if item["scheme_name"] == "Apex Unknown Sector Fund"
    ]
    assert len(folios) == 1
    assert all(item["benchmark_name"] == "Nifty Smallcap 250 TRI" for item in folios)
    assert all(item["benchmark_status"] == "reviewed" for item in folios)

    graph = client.get("/api/v1/benchmark-graph").json()
    unmapped = [item for item in graph["clusters"] if item["name"] == "Other / Unmapped"]
    assert all(
        folio["scheme_name"] != "Apex Unknown Sector Fund"
        for cluster in unmapped
        for folio in cluster["folios"]
    )


def test_full_nse_benchmark_master_is_selectable_without_local_levels(client):
    load_demo(client)
    before = mappings(client)
    options = before["available_benchmarks"]

    assert len(options) >= 119
    for expected in (
        "Nifty 50 TRI",
        "Nifty 500 TRI",
        "Nifty India Defence TRI",
        "Nifty MidSmallcap400 Momentum Quality 100 TRI",
    ):
        assert expected in options

    target = next(
        item
        for item in before["mappings"]
        if item["scheme_name"] == "Apex Unknown Sector Fund"
    )
    response = client.post(
        "/api/v1/benchmark-mappings/bulk",
        json={
            "scheme_ids": [target["scheme_id"]],
            "benchmark_name": "Nifty India Defence TRI",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["updated_schemes"] == 1
    assert mapping_named(client, "Apex Unknown Sector Fund")["benchmark_name"] == (
        "Nifty India Defence TRI"
    )

    graph = client.get("/api/v1/benchmark-graph").json()
    names = {cluster["name"] for cluster in graph["clusters"]}
    assert "Nifty India Defence TRI" in names
    # Nifty India Defence Equal Weight TRI is in master list only (no keyword rules)
    # so it should not appear in the graph unless explicitly mapped
    assert "Nifty India Defence Equal Weight TRI" not in names
    # With expanded keyword rules, more benchmarks appear due to auto-suggestions
    assert len(names) >= 10


def test_keyword_rule_previews_then_applies_at_scheme_level(client):
    load_demo(client)
    before = mappings(client)
    preview = client.post(
        "/api/v1/benchmark-mappings/keyword",
        json={
            "keyword": "Unknown",
            "benchmark_name": "Nifty Healthcare TRI",
            "apply": False,
        },
    )
    assert preview.status_code == 200, preview.text
    rule = preview.json()

    assert rule["apply"] is False
    assert rule["matched_scheme_count"] == 1
    assert rule["matched_folio_count"] == 1
    assert rule["matched_unmapped_scheme_count"] == 1
    assert rule["matched_unmapped_folio_count"] == 1
    assert rule["matched_schemes"][0]["scheme_name"] == "Apex Unknown Sector Fund"
    assert "contains 'Unknown'" in rule["rule"]
    assert rule["can_apply"] is True
    assert before["status_summary"]["unmapped_folios"] == 1

    applied = client.post(
        "/api/v1/benchmark-mappings/keyword",
        json={
            "keyword": "Unknown",
            "benchmark_name": "Nifty Healthcare TRI",
            "apply": True,
        },
    )
    assert applied.status_code == 200, applied.text
    payload = applied.json()
    assert payload["updated_schemes"] == 1
    assert payload["updated_folios"] == 1
    assert payload["folios_moved_out_of_unmapped"] == 1
    assert payload["unmapped_folios"] == 0
    assert mapping_named(client, "Apex Unknown Sector Fund")["benchmark_name"] == (
        "Nifty Healthcare TRI"
    )


def test_keyword_rule_preview_handles_no_match_and_empty_keyword(client):
    load_demo(client)
    no_match = client.post(
        "/api/v1/benchmark-mappings/keyword",
        json={
            "keyword": "No Such Scheme Keyword",
            "benchmark_name": "Nifty 50 TRI",
        },
    )
    assert no_match.status_code == 200
    assert no_match.json()["can_apply"] is False
    assert no_match.json()["matched_scheme_count"] == 0

    empty = client.post(
        "/api/v1/benchmark-mappings/keyword",
        json={"keyword": "   ", "benchmark_name": "Nifty 50 TRI"},
    )
    assert empty.status_code == 400
    assert "Enter a keyword" in empty.json()["detail"]

    apply_no_match = client.post(
        "/api/v1/benchmark-mappings/keyword",
        json={
            "keyword": "No Such Scheme Keyword",
            "benchmark_name": "Nifty 50 TRI",
            "apply": True,
        },
    )
    assert apply_no_match.status_code == 400
    assert "No scheme name contains" in apply_no_match.json()["detail"]


def test_accept_suggestions_reviews_only_visible_automatic_mappings(client):
    confirm_upload(client, four_files())
    before = mappings(client)
    assert before["status_summary"]["needs_review_schemes"] == 3
    assert before["status_summary"]["suggested_schemes"] == 3

    response = client.post("/api/v1/benchmark-mappings/accept-suggestions", json={})
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["accepted_schemes"] == 3
    assert payload["updated_schemes"] == 3
    assert payload["summary"]["reviewed"] == 3
    assert payload["summary"]["needs_review"] == 0
    after = mappings(client)
    assert all(
        item["review_status"] == "reviewed" for item in after["mappings"]
    )
    assert all(
        item["source"] == "accepted_suggestion" for item in after["mappings"]
    )


def test_mapping_export_then_import_updates_scheme_and_reports_validation(client):
    load_demo(client)
    export = client.get("/api/v1/benchmark-mappings/export?format=csv")
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    assert "scheme-benchmark-mappings-" in export.headers["content-disposition"]

    text = export.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    assert reader.fieldnames == [
        "scheme_id",
        "scheme_name",
        "normalized_scheme_name",
        "benchmark_name",
        "review_status",
        "folio_count",
        "source",
    ]
    assert len(rows) == 14
    unknown = next(
        row for row in rows if row["scheme_name"] == "Apex Unknown Sector Fund"
    )
    unknown["benchmark_name"] = "Nifty Smallcap 250 TRI"

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    edited = buffer.getvalue().encode("utf-8")

    preview = client.post(
        "/api/v1/benchmark-mappings/import/preview",
        files=csv_upload(edited),
    )
    assert preview.status_code == 200, preview.text
    validation = preview.json()
    assert validation["can_apply"] is True
    assert validation["error_count"] == 0
    assert validation["summary"]["schemes_to_update"] == 1
    assert validation["summary"]["folios_affected"] == 1
    assert validation["summary"]["unmapped_folios_affected"] == 1
    changed = next(
        item for item in validation["changes"] if item["action"] != "unchanged"
    )
    assert changed["action"] == "map"
    assert changed["scheme_name"] == "Apex Unknown Sector Fund"

    applied = client.post(
        "/api/v1/benchmark-mappings/import/apply",
        files=csv_upload(edited),
    )
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["applied"] is True
    assert result["updated_schemes"] == 1
    assert result["folios_moved_out_of_unmapped"] == 1
    assert mapping_named(client, "Apex Unknown Sector Fund")["benchmark_name"] == (
        "Nifty Smallcap 250 TRI"
    )


def test_mapping_export_xlsx_can_be_read_back_without_changes(client):
    load_demo(client)
    export = client.get("/api/v1/benchmark-mappings/export?format=xlsx")
    assert export.status_code == 200
    assert export.content[:2] == b"PK"
    workbook = load_workbook(BytesIO(export.content), read_only=True)
    sheet = workbook.active
    assert sheet.max_row == 15
    assert sheet.cell(1, 1).value == "scheme_id"

    preview = client.post(
        "/api/v1/benchmark-mappings/import/preview",
        files=xlsx_upload(export.content),
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["detected_format"] == "xlsx"
    assert payload["unchanged_count"] == 13
    assert payload["skipped_count"] == 1
    assert payload["can_apply"] is False
    assert payload["error_count"] == 1
    assert "did not contain any mapping changes" in payload["errors"][0]["message"]


def test_invalid_mapping_import_is_rejected_with_clear_errors_and_saves_nothing(client):
    load_demo(client)
    before = mapping_named(client, "Apex Unknown Sector Fund")
    invalid = "\n".join(
        [
            "scheme_id,scheme_name,benchmark_name",
            "999999,Missing Scheme,Nifty 50 TRI",
            f"{before['scheme_id']},Apex Unknown Sector Fund,Not A Real Benchmark",
        ]
    ).encode("utf-8")

    preview = client.post(
        "/api/v1/benchmark-mappings/import/preview",
        files=csv_upload(invalid),
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["can_apply"] is False
    assert payload["error_count"] == 2
    messages = " ".join(item["message"] for item in payload["errors"])
    assert "does not exist" in messages
    assert "not available locally" in messages

    applied = client.post(
        "/api/v1/benchmark-mappings/import/apply",
        files=csv_upload(invalid),
    )
    assert applied.status_code == 400
    assert "validation found 2 error" in applied.json()["detail"]

    after = mapping_named(client, "Apex Unknown Sector Fund")
    assert after["benchmark_name"] == before["benchmark_name"]
    assert after["review_status"] == "needs_mapping"


def test_invalid_mapping_file_headers_and_empty_file_are_rejected(client):
    load_demo(client)
    empty = client.post(
        "/api/v1/benchmark-mappings/import/preview",
        files=csv_upload(b""),
    )
    assert empty.status_code == 400
    assert "empty" in empty.json()["detail"]

    missing_headers = client.post(
        "/api/v1/benchmark-mappings/import/preview",
        files=csv_upload(b"scheme_name,review_status\nApex Bluechip Fund,reviewed\n"),
    )
    assert missing_headers.status_code == 400
    assert "Benchmark Name" in missing_headers.json()["detail"]


def _large_files() -> dict[str, tuple[str, bytes]]:
    schemes = [
        "Apex Blue Chip Advantage Fund",
        "Apex Bluechip Fund",
        "Apex Broad Market Fund",
        "Apex Flexi Cap Fund",
        "Apex Healthcare Fund",
        "Apex Large Cap Fund",
        "Apex Mid Cap 150 Index Fund",
        "Apex Midcap Opportunities Fund",
        "Apex PSU Equity Fund",
        "Apex Pharma Fund",
        "Apex Public Sector Fund",
        "Apex Small Cap 250 Index Fund",
        "Apex Small Cap Fund",
        "Apex Unknown Sector Fund",
    ]
    clients = []
    folios = []
    transactions = []
    portfolio = []
    for client_index in range(1, 21):
        code = f"S{client_index:03d}"
        name = f"Synthetic Client {client_index:03d}"
        clients.append(
            (
                code,
                "",
                "",
                name,
                "15-01-2024",
                "11000",
                "REDACTED",
                "synthetic@example.invalid",
                "REDACTED",
            )
        )
        for offset in range(11):
            folio_index = (client_index - 1) * 11 + offset + 1
            folio = f"L{folio_index:04d}"
            scheme = schemes[(folio_index - 1) % len(schemes)]
            folios.append(
                (code, "", "", folio, scheme, "100", "1000", "Single", name, "REDACTED")
            )
            transactions.append(
                (
                    "15-01-2024",
                    scheme,
                    folio,
                    name,
                    "",
                    "PURCHASE",
                    "1000",
                    "10",
                    "100",
                    "SYNTHETIC",
                    "",
                    "",
                    code,
                    "",
                    "",
                    "",
                )
            )
        portfolio.append(
            (
                code,
                "",
                name,
                "1100",
                "10000",
                "11000",
                "1000",
                "10.00",
                "8.00",
                "365",
                "0",
                "0",
            )
        )
    return {
        "clients": ("Client Details-27-10-2026.xlsx", clients_xlsx(rows=clients)),
        "folios": ("Folios-27-10-2026.xlsx", folios_xlsx(rows=folios)),
        "portfolio": (
            "PortfolioValuationReportMF-27-10-2026.xlsx",
            portfolio_xlsx(rows=portfolio, total_current="220000"),
        ),
        "transactions": (
            "Transaction Statement-27-10-2026.xlsx",
            transactions_xlsx(rows=transactions),
        ),
    }


def test_bulk_mapping_220_folios_keeps_graph_consistent(client):
    confirm_upload(client, _large_files())
    before = mappings(client)
    assert before["status_summary"]["total_schemes"] == 14
    assert before["status_summary"]["total_folios"] == 220
    assert before["status_summary"]["needs_review_schemes"] == 13
    assert before["status_summary"]["unmapped_schemes"] == 1
    assert before["status_summary"]["unmapped_folios"] == 15

    scheme_ids = [item["scheme_id"] for item in before["mappings"]]
    response = client.post(
        "/api/v1/benchmark-mappings/bulk",
        json={
            "scheme_ids": scheme_ids,
            "benchmark_name": "Nifty 50 TRI",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["updated_schemes"] == 14
    assert payload["updated_folios"] == 220
    assert payload["summary"]["reviewed"] == 14

    graph = client.get("/api/v1/benchmark-graph").json()
    assert graph["summary"]["folios"] == 220
    nifty = next(
        item for item in graph["clusters"] if item["name"] == "Nifty 50 TRI"
    )
    assert len(nifty["folios"]) == 220
    assert all(
        cluster["name"] != "Other / Unmapped" or not cluster["folios"]
        for cluster in graph["clusters"]
    )
