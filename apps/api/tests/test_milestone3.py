from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from openpyxl import Workbook

from mfd_dashboard.benchmark_data import parse_benchmark_levels

from .fixtures import (
    folios_xlsx,
    four_files,
    transactions_xlsx,
)


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


def mappings(client) -> dict:
    return client.get("/api/v1/benchmark-mappings").json()


def mapping_for(client, scheme_name: str) -> dict:
    return next(
        item
        for item in mappings(client)["mappings"]
        if item["scheme_name"] == scheme_name
    )


def review_mapping(client, scheme_name: str, benchmark_name: str):
    scheme = mapping_for(client, scheme_name)
    return client.patch(
        f"/api/v1/benchmark-mappings/{scheme['scheme_id']}",
        json={"benchmark_name": benchmark_name},
    )


def upload_levels(client, text: str, file_name: str = "levels.csv"):
    return client.post(
        "/api/v1/benchmarks/levels/import",
        files={"file": (file_name, text.encode("utf-8"), "text/csv")},
    )


def long_levels(rows: list[tuple[str, str, str]]) -> str:
    lines = ["benchmark_name,date,level"]
    lines.extend(f"{name},{level_date},{level}" for name, level_date, level in rows)
    return "\n".join(lines)


def import_levels(client, rows: list[tuple[str, str, str]]) -> None:
    response = upload_levels(client, long_levels(rows))
    assert response.status_code == 200, response.text


def folio_row(dashboard: dict, folio_number: str) -> dict:
    return next(
        item for item in dashboard["folios"] if item["folio_number"] == folio_number
    )


def test_mapping_update_marks_scheme_reviewed_and_removes_badge(client):
    _, dashboard = preview_and_confirm(client, four_files())
    before = mappings(client)
    scheme = next(
        item
        for item in before["mappings"]
        if item["scheme_name"] == "Apex Bluechip Fund"
    )
    assert scheme["review_status"] == "needs_review"
    assert before["summary"]["needs_review"] >= 1

    response = review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI")
    assert response.status_code == 200, response.text
    updated = response.json()["mapping"]
    assert updated["benchmark_name"] == "Nifty 50 TRI"
    assert updated["review_status"] == "reviewed"
    assert updated["source"] == "manual"

    after = mappings(client)
    assert after["summary"]["reviewed"] == before["summary"]["reviewed"] + 1
    assert after["summary"]["needs_review"] == before["summary"]["needs_review"] - 1
    dashboard = client.get("/api/v1/dashboard").json()
    assert folio_row(dashboard, "F001")["benchmark_status"] == "reviewed"


def test_mapping_update_rejects_unknown_benchmark_and_scheme(client):
    preview_and_confirm(client, four_files())
    scheme = mapping_for(client, "Apex Bluechip Fund")

    bad_name = client.patch(
        f"/api/v1/benchmark-mappings/{scheme['scheme_id']}",
        json={"benchmark_name": "Imaginary Index"},
    )
    missing = client.patch(
        "/api/v1/benchmark-mappings/999999",
        json={"benchmark_name": "Nifty 50 TRI"},
    )

    assert bad_name.status_code == 400
    assert "not available" in bad_name.json()["detail"].lower()
    assert missing.status_code == 404


def test_missing_benchmark_mapping_is_not_available(client):
    rows = [
        ("C001", "", "", "F001", "Apex Bluechip Fund", "100", "10000", "Single", "Alice Example", "REDACTED"),
        ("C001", "", "", "F002", "Apex Midcap Fund", "50", "5000", "Single", "Alice Example", "REDACTED"),
        ("C001", "", "", "F003", "Unclassified Strategy Fund", "10", "1000", "Single", "Alice Example", "REDACTED"),
        ("C999", "", "", "F900", "Apex Small Cap Fund", "10", "1000", "Single", "Unmatched Example", "REDACTED"),
    ]
    _, dashboard = preview_and_confirm(
        client, four_files(folios=folios_xlsx(rows=rows))
    )
    folio = folio_row(dashboard, "F003")

    assert folio["benchmark_name"] == "Other / Unmapped"
    assert folio["benchmark_status"] == "needs_review"
    assert folio["benchmark_comparison_status"] == "mapping_missing"
    assert folio["benchmark_return"] is None
    assert dashboard["summary"]["benchmark_mapping_missing"] == 1
    mapping = mapping_for(client, "Unclassified Strategy Fund")
    assert mapping["review_status"] == "needs_mapping"


def test_missing_benchmark_levels_keeps_comparison_unavailable(client):
    _, _dashboard = preview_and_confirm(client, four_files())
    assert review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI").status_code == 200
    dashboard = client.get("/api/v1/dashboard").json()
    folio = folio_row(dashboard, "F001")

    assert folio["benchmark_status"] == "reviewed"
    assert folio["benchmark_comparison_status"] == "levels_missing"
    assert folio["benchmark_return"] is None
    assert "No local benchmark levels" in folio["benchmark_comparison_note"]


def test_lump_sum_uses_point_to_point_benchmark_return(client):
    _, _dashboard = preview_and_confirm(client, four_files())
    assert review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI").status_code == 200
    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2024-01-15", "100"),
            ("Nifty 50 TRI", "2026-10-27", "130"),
        ],
    )
    dashboard = client.get("/api/v1/dashboard").json()
    folio = folio_row(dashboard, "F001")

    assert folio["benchmark_comparison_status"] == "available"
    assert folio["benchmark_comparison_method"] == "point_to_point"
    assert folio["benchmark_return_type"] == "absolute"
    assert folio["benchmark_return"] == pytest.approx(30.0)
    assert folio["benchmark_difference"] == pytest.approx(
        folio["absolute_return"] - 30.0
    )
    assert dashboard["summary"]["benchmark_point_to_point"] == 1


def test_sip_uses_same_dated_cash_flows_and_benchmark_xirr(client):
    _, _dashboard = preview_and_confirm(client, four_files())
    assert review_mapping(client, "Apex Midcap Fund", "Nifty 50 TRI").status_code == 200
    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2025-01-15", "110"),
            ("Nifty 50 TRI", "2025-06-15", "115"),
            ("Nifty 50 TRI", "2026-10-27", "130"),
        ],
    )
    dashboard = client.get("/api/v1/dashboard").json()
    folio = folio_row(dashboard, "F002")

    assert folio["benchmark_comparison_status"] == "available"
    assert folio["benchmark_comparison_method"] == "cash_flow_xirr"
    assert folio["benchmark_return_type"] == "xirr"
    assert folio["benchmark_xirr"] is not None
    assert folio["benchmark_return"] == pytest.approx(folio["benchmark_xirr"])
    assert folio["benchmark_difference"] == pytest.approx(
        folio["xirr"] - folio["benchmark_xirr"]
    )
    assert dashboard["summary"]["benchmark_cash_flow"] == 1


def test_switch_cash_flows_use_cash_flow_xirr_for_both_legs(client):
    transactions = transactions_xlsx(
        [
            tx("15-01-2024", "Apex Bluechip Fund", "F001", "Alice Example", "PURCHASE", "10000"),
            tx(
                "15-06-2025",
                "Apex Bluechip Fund",
                "F001",
                "Alice Example",
                "SWITCH OUT",
                "1000",
                source="Apex Bluechip Fund",
                target="Apex Midcap Fund",
            ),
            tx(
                "15-06-2025",
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
    preview, _dashboard = preview_and_confirm(
        client, four_files(transactions=transactions)
    )
    assert preview["counts"]["switch_pairs"] == 1
    assert review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI").status_code == 200
    assert review_mapping(client, "Apex Midcap Fund", "Nifty 50 TRI").status_code == 200
    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2024-01-15", "100"),
            ("Nifty 50 TRI", "2025-06-15", "115"),
            ("Nifty 50 TRI", "2026-10-27", "130"),
        ],
    )
    dashboard = client.get("/api/v1/dashboard").json()
    source_folio = folio_row(dashboard, "F001")
    target_folio = folio_row(dashboard, "F002")

    for folio in (source_folio, target_folio):
        assert folio["benchmark_comparison_status"] == "available"
        assert folio["benchmark_comparison_method"] == "cash_flow_xirr"
        assert folio["benchmark_return"] is not None
        assert folio["benchmark_difference"] == pytest.approx(
            folio["xirr"] - folio["benchmark_return"]
        )
    assert dashboard["summary"]["benchmark_cash_flow"] == 2


def test_benchmark_levels_not_covering_valuation_date_show_levels_missing(client):
    _, _dashboard = preview_and_confirm(client, four_files())
    assert review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI").status_code == 200
    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2024-01-15", "100"),
            ("Nifty 50 TRI", "2026-10-26", "130"),
        ],
    )
    dashboard = client.get("/api/v1/dashboard").json()
    folio = folio_row(dashboard, "F001")

    assert folio["benchmark_comparison_status"] == "levels_missing"
    assert folio["benchmark_return"] is None
    assert "valuation date" in folio["benchmark_comparison_note"]


def test_sip_missing_cash_flow_date_shows_levels_missing(client):
    _, _dashboard = preview_and_confirm(client, four_files())
    assert review_mapping(client, "Apex Midcap Fund", "Nifty 50 TRI").status_code == 200
    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2025-01-15", "110"),
            ("Nifty 50 TRI", "2026-10-27", "130"),
        ],
    )
    dashboard = client.get("/api/v1/dashboard").json()
    folio = folio_row(dashboard, "F002")

    assert folio["benchmark_comparison_status"] == "levels_missing"
    assert folio["benchmark_return"] is None
    assert "2025-06-15" in folio["benchmark_comparison_note"]


def test_invalid_benchmark_dates_and_levels_are_skipped_with_warnings(client):
    text = """benchmark_name,date,level
Nifty 50 TRI,,100
Nifty 50 TRI,not-a-date,100
Nifty 50 TRI,2026-10-27,not-a-level
,2026-10-27,100
Nifty 50 TRI,2026-10-27,125
"""
    response = upload_levels(client, text)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["imported"] == 1
    assert payload["skipped"] == 4
    assert len(payload["issues"]) == 4
    assert any(
        "date" in issue["message"].lower() for issue in payload["issues"]
    )
    levels = client.get("/api/v1/benchmarks/levels").json()
    assert levels["total_levels"] == 1


def test_import_with_no_valid_level_rows_is_rejected(client):
    response = upload_levels(
        client,
        "benchmark_name,date,level\nNifty 50 TRI,,100\nNifty 50 TRI,bad-date,100\n",
    )

    assert response.status_code == 400
    assert "No valid benchmark levels" in response.json()["detail"]


def test_wide_benchmark_level_layout_is_supported(client):
    text = """date,Nifty 50 TRI,Nifty Midcap 150 TRI
2024-01-15,100,100
2026-10-27,130,140
"""
    response = upload_levels(client, text)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["detected_format"] == "wide"
    assert payload["imported"] == 4
    levels = client.get("/api/v1/benchmarks/levels").json()
    assert levels["total_benchmarks"] == 2
    assert levels["total_levels"] == 4


def test_xlsx_benchmark_level_file_is_supported(client):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Benchmark Levels"
    worksheet.append(["benchmark_name", "date", "level"])
    worksheet.append(["Nifty 50 TRI", date(2026, 10, 27), 125])
    buffer = BytesIO()
    workbook.save(buffer)

    response = client.post(
        "/api/v1/benchmarks/levels/import",
        files={
            "file": (
                "levels.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["imported"] == 1
    assert payload["benchmarks"] == ["Nifty 50 TRI"]
    assert payload["first_date"] == "2026-10-27"


def test_benchmark_level_parser_reports_invalid_excel_serial_date():
    result = parse_benchmark_levels(
        b"benchmark_name,date,level\nNifty 50 TRI,999999999999,100\n",
        "levels.csv",
    )

    assert result.rows == []
    assert result.issues
    assert "date" in result.issues[0]["message"].lower()


def test_reviewed_mapping_is_preserved_when_snapshot_is_reimported(client):
    _, _dashboard = preview_and_confirm(client, four_files())
    assert review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI").status_code == 200

    _, _dashboard = preview_and_confirm(client, four_files())
    mapping = mapping_for(client, "Apex Bluechip Fund")

    assert mapping["benchmark_name"] == "Nifty 50 TRI"
    assert mapping["review_status"] == "reviewed"
    assert mapping["source"] == "manual"
