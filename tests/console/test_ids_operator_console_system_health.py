"""Tests for the /system-health screen — written FIRST (TDD).

Bead: ids_ml_new-cnh3
Story: Phase 3 / Story 3.1 — System Health screen TDD

Run order:
1. These tests must FAIL first (501 stub still in place)
2. Implement /system-health + system_health.html
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


def _build_system_health_test_app(tmp_path: Path) -> TestClient:
    """Build a test client with seeded data for system-health tests."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "system-health-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="secret")
        # Seed a summary so active_bundle component has data
        store.store_summary(
            summary_ts="2026-03-30T10:00:00+00:00",
            payload={
                "window_seconds": 60,
                "alert_count": 2,
                "anomaly_count": 1,
                "active_bundle": {
                    "active_bundle_name": "bundle-health",
                    "compatibility_status": "compatible",
                    "activated_at": "2026-03-30T09:00:00+00:00",
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


# ── Unauthenticated access ────────────────────────────────────────────────────

def test_system_health_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    """Unauthenticated GET /system-health must redirect to /login, not 501 or 200."""
    client = _build_system_health_test_app(tmp_path)
    response = client.get("/system-health", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# ── Authenticated: status 200 ─────────────────────────────────────────────────

def test_system_health_returns_200_when_authenticated(tmp_path: Path) -> None:
    """GET /system-health returns 200 (not 501) after authentication."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Ensure the /system-health stub is replaced with a real handler."
    )


# ── Page structure ────────────────────────────────────────────────────────────

def test_system_health_response_is_html(tmp_path: Path) -> None:
    """Response Content-Type must be text/html."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_system_health_extends_base_template(tmp_path: Path) -> None:
    """Page must render via base.html — look for shell structure markers."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert "shell" in body, "Shell layout classes not found — base.html not extended"
    assert "app-sidebar" in body, "Sidebar not rendered — base.html not extended"


def test_system_health_page_title_present(tmp_path: Path) -> None:
    """System Health page should contain 'System Health' or similar in the body."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("System Health", "system-health", "Health")), (
        "Page title/heading not found in system-health response"
    )


# ── Component sections ────────────────────────────────────────────────────────

def test_system_health_renders_config_component(tmp_path: Path) -> None:
    """System Health must render the config component section."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("config", "Config", "Configuration")), (
        "Config component not found in system-health page"
    )


def test_system_health_renders_schema_component(tmp_path: Path) -> None:
    """System Health must render the schema component section."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("schema", "Schema")), (
        "Schema component not found in system-health page"
    )


def test_system_health_renders_admin_bootstrap_component(tmp_path: Path) -> None:
    """System Health must render admin bootstrap status."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("admin", "Admin", "bootstrap", "Bootstrap")), (
        "Admin bootstrap component not found in system-health page"
    )


def test_system_health_renders_data_paths_component(tmp_path: Path) -> None:
    """System Health must render data paths component."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("data", "Data", "paths", "Paths", "alerts", "quarantine")), (
        "Data paths component not found in system-health page"
    )


def test_system_health_renders_active_bundle_component(tmp_path: Path) -> None:
    """System Health must render active bundle status."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("bundle", "Bundle", "active_bundle")), (
        "Active bundle component not found in system-health page"
    )


def test_system_health_renders_notification_component(tmp_path: Path) -> None:
    """System Health must render notification component state."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("notification", "Notification")), (
        "Notification component not found in system-health page"
    )


# ── Overall status badge ───────────────────────────────────────────────────────

def test_system_health_renders_overall_status(tmp_path: Path) -> None:
    """System Health must render the overall readiness status (ok/degraded)."""
    client = _build_system_health_test_app(tmp_path)
    _login(client)
    response = client.get("/system-health")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("ok", "OK", "ready", "Ready", "degraded", "status", "Status")), (
        "Overall status badge not found in system-health page"
    )
