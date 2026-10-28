"""CORS settings tests (Vercel production + preview origins)."""

from __future__ import annotations

from fund_engine.core.settings import get_cors_settings


def test_cors_parses_exact_origins(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://fund-engine.vercel.app, http://localhost:3000 ,",
    )
    monkeypatch.delenv("ALLOWED_ORIGIN_REGEX", raising=False)

    origins, regex = get_cors_settings()

    assert origins == ["https://fund-engine.vercel.app", "http://localhost:3000"]
    assert regex is None


def test_cors_supports_preview_regex(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    monkeypatch.setenv(
        "ALLOWED_ORIGIN_REGEX", r"https://fund-engine-[a-z0-9-]+\.vercel\.app"
    )

    origins, regex = get_cors_settings()

    assert origins == []
    assert regex == r"https://fund-engine-[a-z0-9-]+\.vercel\.app"


def test_cors_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGIN_REGEX", raising=False)

    origins, regex = get_cors_settings()

    assert origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert regex is None
