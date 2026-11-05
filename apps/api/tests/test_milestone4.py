from __future__ import annotations

import time

import pytest

from .fixtures import (
    clients_xlsx,
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


def mapping_for(client, scheme_name: str) -> dict:
    payload = client.get("/api/v1/benchmark-mappings").json()
    return next(
        item for item in payload["mappings"] if item["scheme_name"] == scheme_name
    )


def review_mapping(client, scheme_name: str, benchmark_name: str):
    scheme = mapping_for(client, scheme_name)
    response = client.patch(
        f"/api/v1/benchmark-mappings/{scheme['scheme_id']}",
        json={"benchmark_name": benchmark_name},
    )
    assert response.status_code == 200, response.text
    return response.json()


def import_levels(client, rows: list[tuple[str, str, str]]):
    lines = ["benchmark_name,date,level"]
    lines.extend(f"{name},{level_date},{level}" for name, level_date, level in rows)
    response = client.post(
        "/api/v1/benchmarks/levels/import",
        files={
            "file": (
                "levels.csv",
                ("\n".join(lines)).encode("utf-8"),
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text


def graph(client) -> dict:
    response = client.get("/api/v1/benchmark-graph")
    assert response.status_code == 200, response.text
    return response.json()


def cluster(graph_payload: dict, name: str) -> dict:
    return next(
        item for item in graph_payload["clusters"] if item["name"] == name
    )


def node(graph_payload: dict, folio_number: str) -> dict:
    return next(
        item
        for cluster_row in graph_payload["clusters"]
        for item in cluster_row["folios"]
        if item["folio_number"] == folio_number
    )


def test_graph_shows_configured_benchmarks_even_with_no_folios(client):
    payload = graph(client)

    # All configured keyword-rule benchmarks appear as empty nuclei
    # (default "Other / Unmapped" is excluded by default)
    assert payload["summary"]["benchmarks"] == 68
    assert payload["summary"]["folios"] == 0
    assert payload["meta"]["has_data"] is False
    assert "Nifty 50 TRI" in {item["name"] for item in payload["clusters"]}
    assert all(item["stats"]["folio_count"] == 0 for item in payload["clusters"])
    assert all(item["review_state"] == "no_folios" for item in payload["clusters"])


def test_demo_graph_creates_clusters_and_folio_connections(client):
    loaded = client.post("/api/v1/demo/load")
    assert loaded.status_code == 200, loaded.text

    payload = graph(client)

    assert payload["summary"]["folios"] == 14
    assert payload["meta"]["has_data"] is True
    assert node(payload, "F001")["benchmark_name"] == "Nifty 50 TRI"
    assert node(payload, "F013")["benchmark_name"] == "Nifty 50 TRI"
    assert node(payload, "F014")["benchmark_name"] == "Other / Unmapped"

    nifty_50 = cluster(payload, "Nifty 50 TRI")
    assert nifty_50["stats"]["folio_count"] == 3
    assert {item["folio_number"] for item in nifty_50["folios"]} == {
        "F001",
        "F007",
        "F013",
    }
    assert nifty_50["review_state"] == "needs_review"

    unmapped = cluster(payload, "Other / Unmapped")
    assert unmapped["review_state"] == "needs_mapping"
    assert node(payload, "F014")["performance"] == "needs_review"

    ids = [
        item["id"]
        for cluster_row in payload["clusters"]
        for item in cluster_row["folios"]
    ]
    assert len(ids) == len(set(ids))


def test_graph_green_red_grey_and_missing_aum_states(client):
    folios = folios_xlsx(
        rows=[
            ("C001", "", "", "F001", "Apex Bluechip Fund", "100", "15000", "Single", "Alice Example", "REDACTED"),
            ("C001", "", "", "F002", "Apex Midcap Fund", "50", "5000", "Single", "Alice Example", "REDACTED"),
            ("C001", "", "", "F003", "Apex Large Cap Fund", "10", "", "Single", "Alice Example", "REDACTED"),
        ]
    )
    transactions = transactions_xlsx(
        rows=[
            tx("15-01-2024", "Apex Bluechip Fund", "F001", "Alice Example", "PURCHASE", "10000"),
            tx("15-01-2024", "Apex Midcap Fund", "F002", "Alice Example", "PURCHASE", "10000"),
            tx("15-01-2024", "Apex Large Cap Fund", "F003", "Alice Example", "PURCHASE", "10000"),
        ]
    )
    preview_and_confirm(
        client, four_files(folios=folios, transactions=transactions)
    )
    for scheme_name in (
        "Apex Bluechip Fund",
        "Apex Midcap Fund",
        "Apex Large Cap Fund",
    ):
        review_mapping(client, scheme_name, "Nifty 50 TRI")
    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2024-01-15", "100"),
            ("Nifty 50 TRI", "2026-10-27", "120"),
        ],
    )

    payload = graph(client)
    nifty_50 = cluster(payload, "Nifty 50 TRI")
    assert nifty_50["stats"]["folio_count"] == 3
    assert nifty_50["stats"]["ahead"] == 1
    assert nifty_50["stats"]["behind"] == 1
    assert nifty_50["stats"]["not_available"] == 1
    assert nifty_50["stats"]["needs_review"] == 0
    assert nifty_50["stats"]["missing_folio_aum"] == 1
    assert nifty_50["stats"]["average_difference"] == pytest.approx(-20.0)
    assert nifty_50["review_state"] == "partial"

    assert node(payload, "F001")["performance"] == "ahead"
    assert node(payload, "F001")["benchmark_difference"] == pytest.approx(30.0)
    assert node(payload, "F002")["performance"] == "behind"
    assert node(payload, "F002")["benchmark_difference"] == pytest.approx(-70.0)
    assert node(payload, "F003")["performance"] == "not_available"
    assert node(payload, "F003")["benchmark_comparison_status"] == (
        "folio_return_unavailable"
    )
    assert node(payload, "F003")["aum"] is None
    assert payload["summary"]["ahead"] == 1
    assert payload["summary"]["behind"] == 1
    assert payload["summary"]["not_available"] == 1
    assert payload["summary"]["missing_folio_aum"] == 1


def test_graph_uses_amber_until_mapping_and_levels_are_ready(client):
    folios = folios_xlsx(
        rows=[
            ("C001", "", "", "F001", "Apex Bluechip Fund", "100", "15000", "Single", "Alice Example", "REDACTED"),
        ]
    )
    transactions = transactions_xlsx(
        rows=[
            tx("15-01-2024", "Apex Bluechip Fund", "F001", "Alice Example", "PURCHASE", "10000"),
        ]
    )
    preview_and_confirm(
        client, four_files(folios=folios, transactions=transactions)
    )

    before = node(graph(client), "F001")
    assert before["performance"] == "needs_review"
    assert before["benchmark_comparison_status"] == "mapping_needs_review"

    review_mapping(client, "Apex Bluechip Fund", "Nifty 50 TRI")
    after_review = node(graph(client), "F001")
    assert after_review["performance"] == "needs_review"
    assert after_review["benchmark_comparison_status"] == "levels_missing"

    import_levels(
        client,
        [
            ("Nifty 50 TRI", "2024-01-15", "100"),
            ("Nifty 50 TRI", "2026-10-27", "110"),
        ],
    )
    available = node(graph(client), "F001")
    assert available["performance"] == "ahead"
    assert available["benchmark_comparison_status"] == "available"
    assert available["benchmark_difference"] == pytest.approx(40.0)


def test_graph_handles_more_than_200_folios_quickly(client):
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
    payload = graph(client)
    elapsed = time.perf_counter() - started

    assert payload["summary"]["folios"] == 220
    assert payload["summary"]["needs_review"] == 220
    assert cluster(payload, "Nifty 50 TRI")["stats"]["folio_count"] == 220
    assert elapsed < 10.0
