from __future__ import annotations

import time
from pathlib import Path

import pytest

from .fixtures import (
    clients_xlsx,
    folios_xlsx,
    four_files,
    transactions_xlsx,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_LEVELS = (
    PROJECT_ROOT / "samples" / "benchmark_levels" / "demo_benchmark_levels.csv"
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
        "",
        "",
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
    return payload


def review_mapping(client, scheme_name: str, benchmark_name: str):
    mappings = client.get("/api/v1/benchmark-mappings").json()["mappings"]
    scheme = next(
        item for item in mappings if item["scheme_name"] == scheme_name
    )
    response = client.patch(
        f"/api/v1/benchmark-mappings/{scheme['scheme_id']}",
        json={"benchmark_name": benchmark_name},
    )
    assert response.status_code == 200, response.text
    return response.json()


def approve_automatic_mappings(client) -> int:
    mappings = client.get("/api/v1/benchmark-mappings").json()["mappings"]
    approved = 0
    for item in mappings:
        if item["review_status"] != "needs_review":
            continue
        response = client.patch(
            f"/api/v1/benchmark-mappings/{item['scheme_id']}",
            json={"benchmark_name": item["benchmark_name"]},
        )
        assert response.status_code == 200, response.text
        approved += 1
    return approved


def import_demo_levels(client):
    response = client.post(
        "/api/v1/benchmarks/levels/import",
        files={
            "file": (
                DEMO_LEVELS.name,
                DEMO_LEVELS.read_bytes(),
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text


def load_ready_demo(client) -> dict:
    loaded = client.post("/api/v1/demo/load")
    assert loaded.status_code == 200, loaded.text
    assert approve_automatic_mappings(client) == 13
    import_demo_levels(client)
    return get_review(client)


def get_review(http_client, **params) -> dict:
    response = http_client.get("/api/v1/business-review", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_business_review_empty_state(client):
    payload = get_review(client)

    assert payload["meta"]["has_data"] is False
    assert payload["summary"]["folios"] == 0
    assert payload["summary"]["behind"] == 0
    assert payload["attention"]["folios"] == []
    assert payload["attention"]["matching"] == 0
    assert payload["attention"]["filter_options"] == {
        "benchmarks": [],
        "clients": [],
    }
    assert payload["data_quality"]["total_items"] == 0
    assert payload["data_quality"]["groups_with_issues"] == 0
    assert payload["concentration"]["total_folio_value"] == 0.0
    assert payload["concentration"]["by_benchmark"] == []
    assert payload["concentration"]["top_clients"] == []
    assert payload["concentration"]["top_schemes"] == []
    assert payload["review_status"]["mappings"]["schemes"] == 0
    assert payload["review_status"]["comparisons"]["available"] == 0
    assert payload["review_status"]["benchmark_data"]["series"] == 0

    filtered = get_review(client, performance="behind")
    assert filtered["attention"]["folios"] == []
    assert filtered["attention"]["matching"] == 0


def test_demo_business_review_summary_attention_and_filters(client):
    payload = load_ready_demo(client)

    assert payload["meta"]["has_data"] is True
    assert payload["summary"]["folios"] == 14
    assert payload["summary"]["behind"] == 10
    assert payload["summary"]["ahead"] == 2
    assert payload["summary"]["not_available"] == 1
    assert payload["summary"]["needs_review"] == 1
    assert payload["summary"]["comparisons_available"] == 12
    assert payload["summary"]["comparison_coverage"] == pytest.approx(85.7)
    assert payload["summary"]["clients"] == 11
    assert payload["summary"]["transactions"] == 20

    attention = get_review(
        client,
        performance="behind",
        sort="current_value",
        direction="desc",
    )
    rows = attention["attention"]["folios"]
    assert len(rows) == 10
    assert {row["performance"] for row in rows} == {"behind"}
    values = [row["aum"] for row in rows]
    assert all(value is not None for value in values)
    assert values == sorted(values, reverse=True)
    assert all(row["benchmark_difference"] < 0 for row in rows)

    all_rows = attention["attention"]["total_folios"]
    assert all_rows == 14

    benchmark_rows = get_review(client, benchmark="Nifty 50 TRI")["attention"][
        "folios"
    ]
    assert len(benchmark_rows) == 3
    assert {row["benchmark_name"] for row in benchmark_rows} == {
        "Nifty 50 TRI"
    }

    diya = next(
        item
        for item in attention["attention"]["filter_options"]["clients"]
        if item["name"] == "Diya Sharma"
    )
    client_rows = get_review(client, client=diya["key"])["attention"]["folios"]
    assert len(client_rows) == 2
    assert {row["client_name"] for row in client_rows} == {"Diya Sharma"}

    ahead = get_review(client, performance="ahead")["attention"]["folios"]
    assert len(ahead) == 2
    assert {row["performance"] for row in ahead} == {"ahead"}

    not_available = get_review(client, performance="not_available")["attention"][
        "folios"
    ]
    assert len(not_available) == 1
    assert not_available[0]["folio_number"] == "F010"

    needs_review = get_review(client, performance="needs_review")["attention"][
        "folios"
    ]
    assert len(needs_review) == 1
    assert needs_review[0]["folio_number"] == "F014"

    threshold = get_review(
        client,
        performance="all",
        min_current_value=100000,
        sort="current_value",
        direction="desc",
    )
    threshold_rows = threshold["attention"]["folios"]
    assert len(threshold_rows) == 7
    assert all(row["aum"] >= 100000 for row in threshold_rows)

    difference_asc = get_review(
        client,
        performance="behind",
        sort="difference",
        direction="asc",
    )["attention"]["folios"]
    differences = [row["benchmark_difference"] for row in difference_asc]
    assert differences == sorted(differences)

    xirr_desc = get_review(
        client,
        performance="all",
        sort="xirr",
        direction="desc",
    )["attention"]["folios"]
    xirr_values = [
        row["xirr"] for row in xirr_desc if row["xirr"] is not None
    ]
    assert xirr_values == sorted(xirr_values, reverse=True)
    assert xirr_desc[-1]["xirr"] is None

    by_client = get_review(
        client,
        performance="all",
        sort="client_name",
        direction="asc",
    )["attention"]["folios"]
    names = [row["client_name"].casefold() for row in by_client]
    assert names == sorted(names)


def test_demo_data_quality_lists(client):
    load_ready_demo(client)
    payload = get_review(client)
    quality = payload["data_quality"]
    counts = quality["counts"]

    assert counts == {
        "missing_current_value": 1,
        "missing_benchmark_mapping": 1,
        "mapping_needs_review": 0,
        "missing_benchmark_levels": 0,
        "unmatched_folios": 1,
        "unmatched_portfolio_rows": 2,
        "reconciliation_warnings": 3,
        "transaction_issues": 0,
    }
    assert quality["total_items"] == 8
    assert quality["groups_with_issues"] == 5

    missing_value = quality["missing_current_value"]
    assert len(missing_value) == 1
    assert missing_value[0]["folio_number"] == "F010"
    assert missing_value[0]["aum"] is None

    missing_mapping = quality["missing_benchmark_mapping"]
    assert len(missing_mapping) == 1
    assert missing_mapping[0]["folio_number"] == "F014"

    assert quality["mapping_needs_review"] == []
    assert quality["missing_benchmark_levels"] == []
    assert len(quality["unmatched_folios"]) == 1
    assert quality["unmatched_folios"][0]["folio_number"] == "F014"
    assert len(quality["unmatched_portfolio"]) == 2
    assert len(quality["reconciliation_warnings"]) == 3
    assert quality["transaction_issues"] == []


def test_missing_levels_and_mapping_review_lists(client):
    loaded = client.post("/api/v1/demo/load")
    assert loaded.status_code == 200, loaded.text

    mappings = client.get("/api/v1/benchmark-mappings").json()["mappings"]
    bluechip = next(
        item for item in mappings if item["scheme_name"] == "Apex Bluechip Fund"
    )
    review_mapping(client, "Apex Bluechip Fund", bluechip["benchmark_name"])

    payload = get_review(client)
    quality = payload["data_quality"]
    assert quality["counts"]["missing_benchmark_levels"] == 1
    assert len(quality["missing_benchmark_levels"]) == 1
    assert quality["missing_benchmark_levels"][0]["folio_number"] == "F001"
    assert quality["counts"]["mapping_needs_review"] == 12
    assert quality["counts"]["missing_benchmark_mapping"] == 1
    assert payload["summary"]["needs_review"] == 14
    assert payload["review_status"]["comparisons"]["available"] == 0


def test_demo_concentration_and_review_status(client):
    load_ready_demo(client)
    payload = get_review(client)
    concentration = payload["concentration"]

    assert concentration["total_folio_value"] == 1385000.0
    assert concentration["total_client_value"] == 1405000.0
    assert concentration["missing_folio_value_folios"] == 1
    assert concentration["clients_without_current_value"] == 1
    assert sum(item["value"] for item in concentration["by_benchmark"]) == (
        pytest.approx(1385000.0)
    )
    assert sum(item["value"] for item in concentration["top_schemes"]) == (
        pytest.approx(1385000.0)
    )
    assert sum(item["value"] for item in concentration["top_clients"]) == (
        pytest.approx(1405000.0)
    )
    assert concentration["top_clients"][0]["name"] == "Aarav Mehta"
    assert concentration["top_clients"][0]["value"] == 340000.0
    assert all(
        item["share"] > 0 for item in concentration["by_benchmark"]
    )

    review_status = payload["review_status"]
    assert review_status["mappings"] == {
        "schemes": 14,
        "reviewed": 13,
        "needs_review": 0,
        "unmapped": 1,
    }
    assert review_status["comparisons"] == {
        "available": 12,
        "needs_review": 1,
        "not_available": 1,
        "ahead": 2,
        "behind": 10,
        "in_line": 0,
        "coverage_percent": 85.7,
    }
    assert review_status["benchmark_data"]["series"] == 6
    assert review_status["benchmark_data"]["levels"] == 78
    assert review_status["coverage"]["clients"] == 11
    assert review_status["coverage"]["folios"] == 14
    assert review_status["coverage"]["portfolio_rows"] == 13
    assert review_status["coverage"]["transactions"] == 20
    assert review_status["coverage"]["xirr_available"] == 13
    assert review_status["coverage"]["xirr_missing"] == 1
    assert review_status["coverage"]["folio_value_available"] == 13
    assert review_status["coverage"]["folio_value_missing"] == 1


def test_business_review_handles_more_than_200_folios_quickly(client):
    clients = clients_xlsx(
        rows=[
            (
                f"C{index:03d}",
                "",
                "",
                f"Client {index:03d}",
                "01-01-2020",
                "500000",
                "REDACTED",
                "client@example.invalid",
                "REDACTED",
            )
            for index in range(1, 21)
        ]
    )
    folio_rows = []
    transaction_rows = []
    for index in range(1, 221):
        client_code = f"C{((index - 1) % 20) + 1:03d}"
        client_name = f"Client {((index - 1) % 20) + 1:03d}"
        folio_number = f"F{index:03d}"
        folio_rows.append(
            (
                client_code,
                "",
                "",
                folio_number,
                "Apex Bluechip Fund",
                "100",
                "12000",
                "Single",
                client_name,
                "REDACTED",
            )
        )
        transaction_rows.append(
            tx(
                "15-01-2024",
                "Apex Bluechip Fund",
                folio_number,
                client_name,
                "PURCHASE",
                "10000",
                code=client_code,
            )
        )

    preview_and_confirm(
        client,
        four_files(
            clients=clients,
            folios=folios_xlsx(rows=folio_rows),
            transactions=transactions_xlsx(rows=transaction_rows),
        ),
    )

    started = time.perf_counter()
    payload = get_review(client, performance="all", sort="current_value")
    elapsed = time.perf_counter() - started

    assert payload["summary"]["folios"] == 220
    assert payload["summary"]["needs_review"] == 220
    assert payload["attention"]["matching"] == 220
    assert len(payload["attention"]["filter_options"]["clients"]) == 20
    assert payload["data_quality"]["counts"]["mapping_needs_review"] == 220
    assert payload["concentration"]["total_folio_value"] == 2640000.0
    assert elapsed < 10.0
