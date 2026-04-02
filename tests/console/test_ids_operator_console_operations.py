"""Tests for the /operations screen — written FIRST (TDD).

Bead: ids_ml_new-egf5
Story: Phase 2 / Story 2.3 — Operations screen TDD

Run order:
1. These tests must FAIL first (501 stub still in place)
2. Implement /operations + operations.html
3. These tests must PASS
"""
from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.console.auth import ensure_admin_user  # noqa: E402
from ids.console.config import load_operator_console_config  # noqa: E402
from ids.console.db import open_existing_operator_store  # noqa: E402
from ids.console.migrations import migrate_operator_store  # noqa: E402
from ids.console.web import create_operator_console_web_app  # noqa: E402


def _build_operations_test_app(tmp_path: Path) -> TestClient:
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "operations-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="secret")

        # Seed anomalies
        for i in range(5):
            store.store_anomaly(
                source_event_id=f"ops-anom-{i:03d}",
                event_ts=f"2026-03-29T{10 + i:02d}:00:00+00:00",
                anomaly_type="schema_anomaly" if i % 2 == 0 else "feature_drift",
                reason=f"ops anomaly reason {i}",
                redacted_summary=f"ops summary {i}",
                payload={"anomaly_type": "schema_anomaly", "index": i},
            )

        # Seed a summary for readiness bundle state
        store.store_summary(
            summary_ts="2026-03-29T16:00:00+00:00",
            payload={
                "window_seconds": 60,
                "alert_count": 0,
                "anomaly_count": 5,
                "active_bundle": {
                    "active_bundle_name": "bundle-ops",
                    "compatibility_status": "compatible",
                    "activated_at": "2026-03-29T09:00:00+00:00",
                    "previous_bundle_name": None,
                },
            },
        )
    finally:
        store.close()

    app = create_operator_console_web_app(config)
    return TestClient(app, base_url="http://testserver")


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Login failed: {response.status_code}"


# ── Unauthenticated ───────────────────────────────────────────────────────────

def test_operations_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    client = _build_operations_test_app(tmp_path)
    response = client.get("/operations", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# ── Authenticated: status 200 ─────────────────────────────────────────────────

def test_operations_returns_200_when_authenticated(tmp_path: Path) -> None:
    client = _build_operations_test_app(tmp_path)
    _login(client)
    response = client.get("/operations")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Ensure the /operations stub is replaced with a real handler."
    )


def test_operations_response_is_html(tmp_path: Path) -> None:
    client = _build_operations_test_app(tmp_path)
    _login(client)
    response = client.get("/operations")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_operations_extends_base_template(tmp_path: Path) -> None:
    client = _build_operations_test_app(tmp_path)
    _login(client)
    response = client.get("/operations")
    assert response.status_code == 200
    body = response.text
    assert "shell" in body
    assert "app-sidebar" in body


def test_operations_page_title_present(tmp_path: Path) -> None:
    client = _build_operations_test_app(tmp_path)
    _login(client)
    response = client.get("/operations")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("Operations", "Vận hành"))


# ── Anomaly data ──────────────────────────────────────────────────────────────

def test_operations_renders_anomaly_rows(tmp_path: Path) -> None:
    """Operations page must render the seeded anomaly rows."""
    client = _build_operations_test_app(tmp_path)
    _login(client)
    response = client.get("/operations")
    assert response.status_code == 200
    body = response.text
    assert "ops-anom-" in body, "Anomaly rows not found in operations page"


def test_operations_renders_all_seeded_anomalies(tmp_path: Path) -> None:
    """All 5 seeded anomalies must appear (limit=200)."""
    client = _build_operations_test_app(tmp_path)
    _login(client)
    response = client.get("/operations")
    assert response.status_code == 200
    body = response.text
    count = sum(1 for i in range(5) if f"ops-anom-{i:03d}" in body)
    assert count == 5, f"Expected all 5 anomalies but found {count}"


# ── Readiness data ────────────────────────────────────────────────────────────

def test_operations_contains_readiness_information(tmp_path: Path) -> None:
    """Operations page must render readiness/system-status information."""
    client = _build_operations_test_app(tmp_path)
    _login(client)
    response = client.get("/operations")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("ready", "Ready", "status", "Status"))


def test_operations_shows_anomaly_types(tmp_path: Path) -> None:
    """Operations page must show anomaly type labels."""
    client = _build_operations_test_app(tmp_path)
    _login(client)
    response = client.get("/operations")
    assert response.status_code == 200
    body = response.text
    assert any(atype in body for atype in ("schema_anomaly", "feature_drift"))


# ── Empty state ───────────────────────────────────────────────────────────────

def test_operations_empty_state_when_no_anomalies(tmp_path: Path) -> None:
    """Operations page with no anomalies should show a composed empty state message."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "ops-empty-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "empty_ops.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    from ids.console.config import load_operator_console_config
    from ids.console.migrations import migrate_operator_store
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="secret")
    finally:
        store.close()
    app = create_operator_console_web_app(config)
    client = TestClient(app, base_url="http://testserver")
    client.post("/login", data={"username": "admin", "password": "secret"}, follow_redirects=False)
    response = client.get("/operations")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in (
        "No anomalies", "anomaly", "Anomaly"
    )), "Empty state message not found"
