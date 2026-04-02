"""Tests for the /live-logs screen — written FIRST (TDD).

Bead: ids_ml_new-ut75
Story: Phase 3 / Story 3.3 — Live Logs screen + polling JS TDD

Run order:
1. These tests must FAIL first (501 stub still in place)
2. Implement /live-logs + live_logs.html + console.js initLiveLogsPoller
3. These tests must PASS

NOTE: No JS timer/setInterval tests. Tests verify server-rendered HTML only.
The polling contract is proven by data-live-logs-poll attribute presence
and the existing /api/v1/* tests from Phase 1.
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


def _build_live_logs_test_app(tmp_path: Path, *, seed_data: bool = True) -> TestClient:
    """Build a test client with optional seeded alert and anomaly data."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "live-logs-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="secret")
        if seed_data:
            # Seed alerts
            for i in range(5):
                store.upsert_alert(
                    source_event_id=f"live-alert-{i:03d}",
                    event_ts=f"2026-04-01T{10 + i:02d}:00:00+00:00",
                    severity="high" if i % 2 == 0 else "medium",
                    src_ip=f"10.0.1.{i + 1}",
                    dst_ip="192.168.1.1",
                    src_port=4000 + i,
                    dst_port=443,
                    protocol="tcp",
                    fingerprint=f"fp-live-{i:03d}",
                    payload={"score": 0.8 + i * 0.02},
                )
            # Seed anomalies
            for j in range(3):
                store.store_anomaly(
                    source_event_id=f"live-anom-{j:03d}",
                    event_ts=f"2026-04-01T{10 + j:02d}:30:00+00:00",
                    anomaly_type="schema_anomaly",
                    reason=f"live anomaly reason {j}",
                    redacted_summary=f"live summary {j}",
                    payload={"anomaly_type": "schema_anomaly", "index": j},
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

def test_live_logs_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    """Unauthenticated GET /live-logs must redirect to /login, not 501 or 200."""
    client = _build_live_logs_test_app(tmp_path)
    response = client.get("/live-logs", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# ── Authenticated: status 200 ─────────────────────────────────────────────────

def test_live_logs_returns_200_when_authenticated(tmp_path: Path) -> None:
    """GET /live-logs returns 200 (not 501) after authentication."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Ensure the /live-logs stub is replaced with a real handler."
    )


# ── Page structure ────────────────────────────────────────────────────────────

def test_live_logs_response_is_html(tmp_path: Path) -> None:
    """Response Content-Type must be text/html."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_live_logs_extends_base_template(tmp_path: Path) -> None:
    """Page must render via base.html — look for shell structure markers."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200
    body = response.text
    assert "shell" in body, "Shell layout classes not found — base.html not extended"
    assert "app-sidebar" in body, "Sidebar not rendered — base.html not extended"


def test_live_logs_page_title_present(tmp_path: Path) -> None:
    """Page must contain 'Live Logs' or similar in the body."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("Live Logs", "live-logs", "Live logs")), (
        "Page title/heading not found in live-logs response"
    )


# ── Polling container contract ────────────────────────────────────────────────

def test_live_logs_has_feed_container_id(tmp_path: Path) -> None:
    """Page must have a container with id='live-logs-feed'."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200
    body = response.text
    assert 'id="live-logs-feed"' in body, (
        "Container with id='live-logs-feed' not found — required for polling JS"
    )


def test_live_logs_has_data_live_logs_poll_attribute(tmp_path: Path) -> None:
    """Container must have data-live-logs-poll attribute set to 7000."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200
    body = response.text
    assert 'data-live-logs-poll="7000"' in body, (
        "data-live-logs-poll='7000' attribute not found on live-logs-feed container"
    )


# ── Initial server-rendered feed rows ────────────────────────────────────────

def test_live_logs_renders_initial_alert_rows(tmp_path: Path) -> None:
    """Initial server-rendered page must include seeded alert rows."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200
    body = response.text
    assert "live-alert-" in body, (
        "Alert rows not found in live-logs initial render"
    )


def test_live_logs_renders_initial_anomaly_rows(tmp_path: Path) -> None:
    """Initial server-rendered page must include seeded anomaly rows."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200
    body = response.text
    assert "live-anom-" in body, (
        "Anomaly rows not found in live-logs initial render"
    )


def test_live_logs_renders_multiple_seeded_alerts(tmp_path: Path) -> None:
    """Multiple seeded alert IDs must appear in the initial render."""
    client = _build_live_logs_test_app(tmp_path)
    _login(client)
    response = client.get("/live-logs")
    assert response.status_code == 200
    body = response.text
    # Check at least 2 of the 5 seeded alerts appear
    found = sum(1 for i in range(5) if f"live-alert-{i:03d}" in body)
    assert found >= 2, f"Expected at least 2 alert rows but found {found}"


# ── console.js polling function ───────────────────────────────────────────────

def test_console_js_has_init_live_logs_poller(tmp_path: Path) -> None:
    """console.js must define initLiveLogsPoller function."""
    console_js = REPO_ROOT / "ids" / "console" / "static" / "console.js"
    source = console_js.read_text(encoding="utf-8")
    assert "initLiveLogsPoller" in source, (
        "initLiveLogsPoller function not found in console.js"
    )


def test_console_js_poller_reads_poll_interval_attribute(tmp_path: Path) -> None:
    """console.js poller must read data-live-logs-poll attribute."""
    console_js = REPO_ROOT / "ids" / "console" / "static" / "console.js"
    source = console_js.read_text(encoding="utf-8")
    assert "data-live-logs-poll" in source, (
        "data-live-logs-poll attribute not referenced in console.js poller"
    )


def test_console_js_poller_uses_set_interval(tmp_path: Path) -> None:
    """console.js poller must use setInterval for polling."""
    console_js = REPO_ROOT / "ids" / "console" / "static" / "console.js"
    source = console_js.read_text(encoding="utf-8")
    assert "setInterval" in source, (
        "setInterval not found in console.js — required for live logs polling"
    )


def test_console_js_poller_called_from_init(tmp_path: Path) -> None:
    """initLiveLogsPoller must be called from the init() function."""
    console_js = REPO_ROOT / "ids" / "console" / "static" / "console.js"
    source = console_js.read_text(encoding="utf-8")
    assert "initLiveLogsPoller()" in source, (
        "initLiveLogsPoller() call not found in console.js — must be called from init()"
    )
