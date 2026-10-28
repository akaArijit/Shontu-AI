"""Contract tests for the FastAPI application factory and health endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fund_engine.api.main import create_app


def test_health_endpoint_is_available():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "mfd-fund-monitoring-api",
        "version": "1.0.0",
    }


def test_root_metadata_endpoint():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "operational"
    assert payload["docs"] == "/docs"


def test_openapi_exposes_versioned_mfd_routes():
    paths = create_app().openapi()["paths"]

    assert "/health" in paths
    assert "/api/v1/mfd/scores" in paths
    assert "/api/v1/mfd/alerts" in paths


def test_cors_preflight_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://fund-engine.vercel.app")
    monkeypatch.delenv("ALLOWED_ORIGIN_REGEX", raising=False)
    client = TestClient(create_app())

    response = client.options(
        "/api/v1/mfd/scores",
        headers={
            "Origin": "https://fund-engine.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://fund-engine.vercel.app"
    )


def test_cors_preflight_allows_preview_regex(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    monkeypatch.setenv(
        "ALLOWED_ORIGIN_REGEX", r"https://fund-engine-[a-z0-9-]+\.vercel\.app"
    )
    client = TestClient(create_app())
    origin = "https://fund-engine-abc123.vercel.app"

    response = client.options(
        "/api/v1/mfd/scores",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_preflight_rejects_unknown_origin(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://fund-engine.vercel.app")
    monkeypatch.delenv("ALLOWED_ORIGIN_REGEX", raising=False)
    client = TestClient(create_app())

    response = client.options(
        "/api/v1/mfd/scores",
        headers={
            "Origin": "https://not-allowed.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
