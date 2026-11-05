"""Test configuration and local-only test database."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="mfd-dashboard-tests-"))

os.environ["MFD_PROJECT_ROOT"] = str(PROJECT_ROOT)
os.environ["MFD_CONFIG_DIR"] = str(PROJECT_ROOT / "config")
os.environ["MFD_SAMPLES_DIR"] = str(TEST_DATA_DIR / "samples")
os.environ["MFD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["MFD_DATABASE_URL"] = (
    f"sqlite:///{(TEST_DATA_DIR / 'test.sqlite3').as_posix()}"
)

from mfd_dashboard.core.paths import PREVIEWS_DIR  # noqa: E402
from mfd_dashboard.db.base import Base  # noqa: E402
from mfd_dashboard.db.session import engine  # noqa: E402
from mfd_dashboard.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    for path in PREVIEWS_DIR.glob("*.json"):
        path.unlink()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client
