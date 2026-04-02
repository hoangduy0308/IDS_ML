"""Tests for the /overview screen — written FIRST (TDD).

Bead: ids_ml_new-wnnq
Story: Phase 2 / Story 2.1 — Overview screen TDD

Run order:
1. These tests must FAIL first (501 stub still in place)
2. Implement /overview + overview.html
3. These tests must PASS
"""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.console.alerts import add_investigation_note, transition_alert_status  # noqa: E402
from ids.console.auth import ensure_admin_user  # noqa: E402
from ids.console.config import load_operator_console_config  # noqa: E402
from ids.console.db import open_existing_operator_store  # noqa: E402
from ids.console.migrations import migrate_operator_store  # noqa: E402
from ids.console.web import create_operator_console_web_app  # noqa: E402


def _build_overview_test_app(tmp_path: Path) -> tuple[TestClient, int]:
    """Build a test client with seeded data for overview tests."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "overview-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    alert_id = None
    try:
        ensure_admin_user(store, username="admin", password="secret")

        # Seed alerts (more than 8 to verify limit=8 in overview)
        for i in range(10):
            aid = store.upsert_alert(
                source_event_id=f"overview-alert-{i:03d}",
                event_ts=f"2026-03-28T{10 + i:02d}:00:00+00:00",
                severity="high" if i % 2 == 0 else "medium",
                src_ip=f"10.0.0.{i + 1}",
                dst_ip="192.168.1.1",
                src_port=1024 + i,
                dst_port=443,
                protocol="tcp",
                fingerprint=f"fp-overview-{i:03d}",
                payload={"score": 0.8 + i * 0.01},
            )
            if i == 0:
                alert_id = aid

        # Seed anomalies (more than 8 to verify limit=8 in overview)
        for j in range(10):
            store.store_anomaly(
                source_event_id=f"overview-anom-{j:03d}",
                event_ts=f"2026-03-28T{10 + j:02d}:01:00+00:00",
                anomaly_type="schema_anomaly",
                reason=f"missing feature {j}",
                redacted_summary=f"redacted {j}",
                payload={"anomaly_type": "schema_anomaly", "index": j},
            )

        # Seed a summary so readiness bundle info is available
        store.store_summary(
            summary_ts="2026-03-28T16:22:00+00:00",
            payload={
                "window_seconds": 60,
                "alert_count": 10,
                "anomaly_count": 10,
                "active_bundle": {
                    "active_bundle_name": "bundle-overview",
                    "compatibility_status": "compatible",
                    "activated_at": "2026-03-28T10:00:00+00:00",
                    "previous_bundle_name": None,
                },
            },
        )
    finally:
        store.close()

    app = create_operator_console_web_app(config)
    client = TestClient(app, base_url="http://testserver")
    return client, alert_id


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Login failed: {response.status_code}"
    assert response.headers["location"] == "/overview"


# ── Unauthenticated access ────────────────────────────────────────────────────

def test_overview_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    """Unauthenticated GET /overview must redirect to /login, not 501 or 200."""
    client, _ = _build_overview_test_app(tmp_path)
    response = client.get("/overview", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# ── Authenticated: status 200 ─────────────────────────────────────────────────

def test_overview_returns_200_when_authenticated(tmp_path: Path) -> None:
    """GET /overview returns 200 (not 501) after authentication."""
    client, _ = _build_overview_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Ensure the /overview stub is replaced with a real handler."
    )


# ── Page structure ────────────────────────────────────────────────────────────

def test_overview_response_is_html(tmp_path: Path) -> None:
    """Response Content-Type must be text/html."""
    client, _ = _build_overview_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_overview_extends_base_template(tmp_path: Path) -> None:
    """Page must render via base.html — look for shell structure markers."""
    client, _ = _build_overview_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.text
    # base.html produces these structural elements
    assert "shell" in body, "Shell layout classes not found — base.html not extended"
    assert "app-sidebar" in body, "Sidebar not rendered — base.html not extended"


def test_overview_page_title_present(tmp_path: Path) -> None:
    """Overview page should contain 'Overview' or 'Tổng quan' in the body."""
    client, _ = _build_overview_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("Overview", "Tổng quan")), (
        "Page title/heading not found in overview response"
    )


# ── Readiness data ────────────────────────────────────────────────────────────

def test_overview_contains_readiness_data(tmp_path: Path) -> None:
    """Overview page must render readiness/system-status information."""
    client, _ = _build_overview_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.text
    # readiness dict has 'ready', 'status', 'components'
    # The template should render something indicating system status
    assert any(marker in body for marker in (
        "ready", "Ready", "status", "Status", "Sẵn sàng"
    )), "Readiness status not found in overview page body"


# ── Alert preview ─────────────────────────────────────────────────────────────

def test_overview_renders_alert_preview_rows(tmp_path: Path) -> None:
    """Overview page must render alert preview rows (capped at 8)."""
    client, _ = _build_overview_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.text
    # We seeded 10 alerts; limit=8 means at most 8 rows
    # Check the source event IDs are present (at least one of them)
    assert "overview-alert-" in body, (
        "Alert preview rows not found in overview page body"
    )


def test_overview_alert_preview_capped_at_eight(tmp_path: Path) -> None:
    """Alert preview must show at most 8 rows even when more exist."""
    client, _ = _build_overview_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.text
    # We seeded 10 alerts (index 0-9). With limit=8, the last 2 are excluded.
    # Since list_alerts orders by event_ts DESC, the first 8 newest appear.
    # Alerts 2-9 (event_ts 12:00-19:00) are the newest 8; alert-000 and alert-001 are cut.
    # Count occurrences of alert IDs in text — there should be <= 8
    alert_occurrences = sum(
        1 for i in range(10) if f"overview-alert-{i:03d}" in body
    )
    assert alert_occurrences <= 8, (
        f"Found {alert_occurrences} alert IDs but limit=8 should cap at 8"
    )


# ── Anomaly preview ───────────────────────────────────────────────────────────

def test_overview_renders_anomaly_preview_rows(tmp_path: Path) -> None:
    """Overview page must render anomaly preview rows (capped at 8)."""
    client, _ = _build_overview_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.text
    assert "overview-anom-" in body, (
        "Anomaly preview rows not found in overview page body"
    )


# ── No _prepare_health_snapshot usage ────────────────────────────────────────

def test_overview_does_not_use_prepare_health_snapshot(tmp_path: Path) -> None:
    """Verify no reference to _prepare_health_snapshot in web.py (banned function)."""
    web_py = REPO_ROOT / "ids" / "console" / "web.py"
    source = web_py.read_text(encoding="utf-8")
    assert "_prepare_health_snapshot" not in source, (
        "_prepare_health_snapshot is banned — use build_readiness_payload() instead"
    )
