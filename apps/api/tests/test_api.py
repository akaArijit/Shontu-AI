from __future__ import annotations

from sqlalchemy import inspect

from mfd_dashboard.db.base import Base
from mfd_dashboard.db.session import engine

from .fixtures import portfolio_xlsx, three_files


def _upload(client, files: dict[str, tuple[str, bytes]]):
    field_names = {
        "clients": "clients_file",
        "folios": "folios_file",
        "portfolio": "portfolio_file",
    }
    return client.post(
        "/api/v1/imports/preview",
        files={
            field_names[kind]: (
                name,
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            for kind, (name, data) in files.items()
        },
    )


def test_health_and_empty_dashboard(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["meta"]["has_data"] is False
    assert payload["summary"]["folios"] == 0
    assert payload["folios"] == []


def test_preview_confirm_and_dashboard(client):
    preview_response = _upload(client, three_files())
    assert preview_response.status_code == 200
    preview = preview_response.json()

    assert preview["can_confirm"] is True
    assert preview["report_date"] == "2026-10-27"
    assert preview["counts"]["clients_imported"] == 2
    assert preview["counts"]["folios_imported"] == 3
    assert preview["counts"]["needs_review"] == 3
    assert preview["counts"]["unmatched_folios"] == 1
    assert preview["counts"]["unmatched_portfolio_rows"] == 1
    assert "PAN" in preview["detected_columns"]["clients"]["ignored_sensitive_columns"]
    assert "Email" in preview["detected_columns"]["clients"]["ignored_sensitive_columns"]

    confirm_response = client.post(
        f"/api/v1/imports/{preview['import_id']}/confirm"
    )
    assert confirm_response.status_code == 200
    confirmed = confirm_response.json()
    assert confirmed["imported"]["clients"] == 2
    assert confirmed["imported"]["folios"] == 3
    assert confirmed["imported"]["needs_review"] == 3
    assert confirmed["unmatched"]["folios"] == 1

    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["meta"]["has_data"] is True
    assert dashboard["meta"]["valuation_date"] == "2026-10-27"
    assert dashboard["summary"]["clients"] == 2
    assert dashboard["summary"]["folios"] == 3
    assert dashboard["summary"]["needs_review"] == 3
    assert dashboard["summary"]["unmatched_folios"] == 1
    assert dashboard["summary"]["unmatched_portfolio_rows"] == 1
    assert dashboard["summary"]["total_folio_aum"] == 15000.0
    assert dashboard["summary"]["unmatched_folio_aum"] == 1000.0
    assert dashboard["summary"]["total_current_value"] == 22000.0
    assert dashboard["summary"]["unmatched_current_value"] == 2000.0
    assert dashboard["summary"]["reconciliation_warnings"] == 0

    alice = next(item for item in dashboard["clients"] if item["name"] == "Alice Example")
    assert alice["current_value"] == 15000.0
    assert alice["folio_aum_total"] == 15000.0
    assert alice["absolute_return"] == 25.0
    assert alice["cagr"] == 12.0
    assert alice["reconciliation_status"] == "matched"

    folio = next(item for item in dashboard["folios"] if item["folio_number"] == "F001")
    assert folio["benchmark_status"] == "needs_review"
    assert folio["benchmark_name"]
    assert folio["invested_amount"] is None
    assert folio["absolute_return"] is None
    assert folio["holding_period"] is None
    assert folio["value_date"] == "2026-10-27"

    unmatched = next(item for item in dashboard["folios"] if item["folio_number"] == "F900")
    assert unmatched["match_status"] == "unmatched"
    assert "Unmatched" in unmatched["client_name"]


def test_mismatch_creates_reconciliation_warning(client):
    files = three_files(
        portfolio=portfolio_xlsx(
            rows=[
                ("C001", "", "Alice Example", "0", "0", "14000", "0", "0", "0", "0", "0", "0"),
                ("C002", "", "Bob Example", "0", "0", "7000", "0", "0", "0", "0", "0", "0"),
            ],
            total_current="21000",
        )
    )
    preview = _upload(client, files).json()
    confirm = client.post(f"/api/v1/imports/{preview['import_id']}/confirm")
    assert confirm.status_code == 200

    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["summary"]["reconciliation_warnings"] == 1
    alice = next(item for item in dashboard["clients"] if item["name"] == "Alice Example")
    assert alice["reconciliation_status"] == "mismatch"
    assert alice["difference"] == 1000.0
    assert any(
        item["status"] == "mismatch" for item in dashboard["reconciliation"]
    )


def test_confirm_twice_returns_conflict_and_invalid_file_is_rejected(client):
    files = three_files()
    preview = _upload(client, files).json()
    first = client.post(f"/api/v1/imports/{preview['import_id']}/confirm")
    assert first.status_code == 200
    second = client.post(f"/api/v1/imports/{preview['import_id']}/confirm")
    assert second.status_code == 409

    bad = client.post(
        "/api/v1/imports/preview",
        files={
            "clients_file": ("clients.csv", b"a,b", "text/csv"),
            "folios_file": ("folios.xlsx", files["folios"][1], "application/octet-stream"),
            "portfolio_file": (
                "portfolio.xlsx",
                files["portfolio"][1],
                "application/octet-stream",
            ),
        },
    )
    assert bad.status_code == 200
    bad_payload = bad.json()
    assert bad_payload["can_confirm"] is False
    assert bad_payload["counts"]["errors"] >= 1


def test_database_has_no_pan_or_contact_columns():
    tables = Base.metadata.tables
    column_names = {
        column.name
        for table in tables.values()
        for column in table.columns
    }
    for forbidden in ("pan", "aadhaar", "aadhar", "email", "mobile", "phone"):
        assert forbidden not in column_names

    all_columns = {
        table_name: {column["name"] for column in inspect(engine).get_columns(table_name)}
        for table_name in tables
    }
    assert "pan" not in all_columns["clients"]
    assert "email" not in all_columns["clients"]
    assert "mobile" not in all_columns["clients"]


def test_demo_data_loads_expected_snapshot(client):
    response = client.post("/api/v1/demo/load?replace=true")
    assert response.status_code == 200
    result = response.json()
    assert result["imported"]["clients"] == 11
    assert result["imported"]["folios"] == 14
    assert result["imported"]["portfolio_rows"] == 13
    assert result["imported"]["transactions"] == 20
    assert result["imported"]["switch_pairs"] == 1
    assert result["imported"]["needs_review"] == 14
    assert result["reconciliation_warnings"] == 1

    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["summary"]["clients"] == 11
    assert dashboard["summary"]["folios"] == 14
    assert dashboard["summary"]["portfolio_rows"] == 13
    assert dashboard["summary"]["needs_review"] == 14
    assert dashboard["summary"]["unmatched_folios"] == 1
    assert dashboard["summary"]["unmatched_portfolio_rows"] == 2
    assert dashboard["summary"]["reconciliation_warnings"] == 1
    assert dashboard["summary"]["partial_reconciliation"] == 1
    assert dashboard["summary"]["missing_folio_aum"] == 1
    assert dashboard["summary"]["total_folio_aum"] == 1365000.0
    assert dashboard["summary"]["unmatched_folio_aum"] == 20000.0
    assert dashboard["summary"]["total_current_value"] == 1405000.0
    assert dashboard["summary"]["unmatched_current_value"] == 95000.0
    assert dashboard["summary"]["transactions"] == 20
    assert dashboard["summary"]["switch_reviews"] == 0
    assert dashboard["summary"]["benchmark_comparisons_available"] == 0
    assert dashboard["meta"]["valuation_date"] == "2026-10-27"
    assert dashboard["meta"]["transaction_file_name"] == "demo_transactions.xlsx"

    for folio in dashboard["folios"]:
        assert folio["gross_invested"] is not None
        assert folio["holding_period"] is not None
        if folio["aum"] is None:
            assert folio["absolute_return"] is None
            assert folio["xirr"] is None
        else:
            assert folio["absolute_return"] is not None
            assert folio["xirr"] is not None
        assert folio["benchmark_status"] in {"needs_review", "needs_mapping"}
        assert folio["benchmark_xirr"] is None
