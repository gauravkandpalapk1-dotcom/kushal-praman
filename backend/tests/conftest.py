"""Test configuration: temp SQLite DB + temp storage, set BEFORE the app is imported."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="kp_test_"))
os.environ.update({
    "KP_MODE": "demo",
    "DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    "STORAGE_DIR": str(_TMP / "storage"),
    "JWT_SECRET": "test-secret-not-for-production-0123456789",
    "FRONTEND_DIST": str(_TMP / "no-frontend"),
    "ANTHROPIC_API_KEY": "",
    "GEMINI_API_KEY": "",
    "ASR_PROVIDER": "none",
    "OCR_PROVIDER": "none",
    "KAPPA_MIN_PAIRS": "30",
    "METRIC_MIN_N": "10",
})

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import ROOT, get_settings  # noqa: E402
from backend.app.main import app  # noqa: E402

DEMO_VIDEO = ROOT / "storage" / "demo" / "practical_demo.mp4"
PASSWORDS = {"admin@kp.demo": "Admin@2026", "raj@kp.demo": "Candidate@2026",
             "a07@kp.demo": "Assessor@2026", "a12@kp.demo": "Assessor@2026"}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def settings():
    return get_settings()


def login(client: TestClient, email: str, password: str | None = None) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password or PASSWORDS[email]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def fresh(client):
    """Reset all data to the 'fresh' demo stage and return auth headers for the demo users."""
    admin = login(client, "admin@kp.demo")
    r = client.post("/api/v1/demo/reset", json={"stage": "fresh"}, headers=admin)
    assert r.status_code == 200, r.text
    return {
        "admin": login(client, "admin@kp.demo"),
        "raj": login(client, "raj@kp.demo"),
        "a07": login(client, "a07@kp.demo"),
        "a12": login(client, "a12@kp.demo"),
    }


@pytest.fixture(autouse=True)
def _reset_login_throttle():
    """Tests share one client/IP; keep failed-login counters from leaking between tests."""
    from backend.app.security import login_throttle
    login_throttle.reset()
    yield
