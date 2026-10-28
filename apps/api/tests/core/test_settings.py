"""Tests for filesystem and environment-backed settings."""

from __future__ import annotations

from fund_engine.core.paths import CONFIG_DIR, MIGRATIONS_DIR, PROJECT_ROOT
from fund_engine.core.settings import config_path, database_url


def test_project_layout_is_resolvable():
    assert (PROJECT_ROOT / "src" / "fund_engine").is_dir()
    assert CONFIG_DIR.is_dir()
    assert MIGRATIONS_DIR.is_dir()
    assert (CONFIG_DIR / "rules.yaml").is_file()
    assert (CONFIG_DIR / "scoring_config.yaml").is_file()


def test_config_path_uses_existing_override(tmp_path, monkeypatch):
    custom = tmp_path / "rules.yaml"
    custom.write_text("rules: []\n", encoding="utf-8")
    monkeypatch.setenv("FUND_ENGINE_TEST_CONFIG", str(custom))

    assert config_path("FUND_ENGINE_TEST_CONFIG", "rules.yaml") == custom


def test_config_path_falls_back_when_override_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "FUND_ENGINE_TEST_CONFIG", str(tmp_path / "does-not-exist.yaml")
    )

    assert config_path("FUND_ENGINE_TEST_CONFIG", "rules.yaml") == (
        CONFIG_DIR / "rules.yaml"
    )


def test_config_path_falls_back_when_env_is_unset(monkeypatch):
    monkeypatch.delenv("FUND_ENGINE_TEST_CONFIG", raising=False)

    assert config_path("FUND_ENGINE_TEST_CONFIG", "rules.yaml") == (
        CONFIG_DIR / "rules.yaml"
    )


def test_database_url_treats_blank_as_unset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "   ")

    assert database_url() is None


def test_database_url_returns_configured_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    assert database_url() == "postgresql://user:pass@localhost/db"
