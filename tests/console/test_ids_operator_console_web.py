from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
from ids.console.alerts import add_investigation_note, transition_alert_status  # noqa: E402
from ids.console.auth import ensure_admin_user  # noqa: E402
from ids.console.config import load_operator_console_config  # noqa: E402
from ids.console.db import open_existing_operator_store  # noqa: E402
from ids.console.migrations import migrate_operator_store  # noqa: E402
from ids.console.web import create_operator_console_web_app  # noqa: E402


def _build_test_app(
    tmp_path: Path,
    *,
    environment: str = "development",
    telegram_enabled: bool = False,
    failed_notification: bool = False,
) -> tuple[TestClient, Path, int]:
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": environment,
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "web-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    if environment == "production":
        env["IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL"] = "https://console.example"
    if telegram_enabled:
        env["IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN"] = "telegram-token"
        env["IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID"] = "-100web"
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="correct-password")
        alert_id = store.upsert_alert(
            source_event_id="alert-web-001",
            event_ts="2026-03-28T16:20:00+00:00",
            severity="high",
            src_ip="10.20.0.5",
            dst_ip="192.168.50.11",
            src_port=443,
            dst_port=50222,
            protocol="tcp",
            fingerprint="fp-web-001",
            payload={"event_type": "model_prediction", "score": 0.99, "src_ip": "10.20.0.5"},
        )
        transition_alert_status(store, alert_id=alert_id, to_status="acknowledged", changed_by="admin")
        add_investigation_note(
            store,
            alert_id=alert_id,
            note_text="Correlated with known scanner host",
            author="admin",
        )
        store.store_anomaly(
            source_event_id="anom-web-001",
            event_ts="2026-03-28T16:21:00+00:00",
            anomaly_type="schema_anomaly",
            reason="missing feature",
            redacted_summary="payload redacted",
            payload={"anomaly_type": "schema_anomaly"},
        )
        store.store_summary(
            summary_ts="2026-03-28T16:22:00+00:00",
            payload={
                "window_seconds": 60,
                "alert_count": 1,
                "anomaly_count": 1,
                "active_bundle": {
                    "active_bundle_name": "bundle-a",
                    "compatibility_status": "compatible",
                    "activated_at": "2026-03-28T16:00:00+00:00",
                    "previous_bundle_name": "bundle-prev",
                },
            },
        )
        if telegram_enabled:
            delivery_id = store.save_notification_delivery(
                alert_id=alert_id,
                channel="telegram",
                target="-100web",
                dedupe_key="alert-web-001",
                payload={"text": "Alert alert-web-001"},
                status="pending",
            )
            if failed_notification:
                store.mark_notification_attempt(
                    delivery_id=delivery_id,
                    status="failed",
                    last_error="telegram outage",
                )
    finally:
        store.close()

    app = create_operator_console_web_app(config)
    base_url = "https://testserver" if environment == "production" else "http://testserver"
    client = TestClient(app, base_url=base_url)
    return client, config.database_path, alert_id


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "correct-password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/overview"


def test_overview_and_legacy_dashboard_redirect_to_login_when_unauthenticated(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    for path in ("/overview", "/dashboard"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_overview_renders_operator_surface_and_legacy_routes_redirect(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    _login(client)
    response = client.get("/overview")
    assert response.status_code == 200

    dashboard_redirect = client.get("/dashboard", follow_redirects=False)
    assert dashboard_redirect.status_code == 303
    assert dashboard_redirect.headers["location"] == "/overview"

    anomalies_redirect = client.get("/anomalies", follow_redirects=False)
    assert anomalies_redirect.status_code == 303
    assert anomalies_redirect.headers["location"] == "/operations"

    ready = client.get("/readyz")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["ready"] is True
    assert payload["components"]["admin_bootstrap"]["admin_count"] == 1
    assert payload["components"]["active_bundle"]["state"]["active_bundle_name"] == "bundle-a"
    assert payload["components"]["notification"]["state"] == "disabled"
    assert payload["components"]["notification"]["ok"] is True
    assert payload["components"]["notification"]["target"] is None

    health = client.get("/healthz")
    assert health.status_code == 200
    health_payload = health.json()
    assert health_payload["service"] == "ids-operator-console"
    assert health_payload["environment"] == "development"
    assert "database_path" in health_payload


def test_alert_detail_and_sensor_aware_json_endpoints(tmp_path: Path) -> None:
    client, _, alert_id = _build_test_app(tmp_path)
    _login(client)

    alerts_page = client.get("/alerts")
    assert alerts_page.status_code == 501

    operations_page = client.get("/operations")
    assert operations_page.status_code == 501

    reports_page = client.get("/reports")
    assert reports_page.status_code == 501

    detail = client.get(f"/alerts/{alert_id}")
    assert detail.status_code == 501

    snapshot = client.get("/api/v1/console/snapshot")
    assert snapshot.status_code == 200
    snapshot_json = snapshot.json()
    assert snapshot_json["sensor_id"] == "sensor-local"
    assert len(snapshot_json["alerts"]) == 1
    assert len(snapshot_json["anomalies"]) == 1
    assert len(snapshot_json["summaries"]) == 1

    alerts = client.get("/api/v1/alerts")
    anomalies = client.get("/api/v1/anomalies")
    summaries = client.get("/api/v1/summaries")
    assert alerts.status_code == 200
    assert anomalies.status_code == 200
    assert summaries.status_code == 200
    assert alerts.json()["sensor_id"] == "sensor-local"
    assert anomalies.json()["sensor_id"] == "sensor-local"
    assert summaries.json()["sensor_id"] == "sensor-local"


def test_production_login_sets_secure_session_cookie(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path, environment="production")
    response = client.post(
        "/login",
        data={"username": "admin", "password": "correct-password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "secure" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


def test_phase3_routes_return_501_not_404(tmp_path: Path) -> None:
    """Phase 3 routes must be registered (not 404) and return 501 until implemented."""
    client, _, _ = _build_test_app(tmp_path)
    _login(client)

    live_logs = client.get("/live-logs")
    assert live_logs.status_code == 501

    suppression_rules = client.get("/suppression-rules")
    assert suppression_rules.status_code == 501

    system_health = client.get("/system-health")
    assert system_health.status_code == 501


def test_readyz_keeps_core_ready_when_notification_component_is_degraded(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(
        tmp_path,
        telegram_enabled=True,
        failed_notification=True,
    )
    _login(client)
    ready = client.get("/readyz")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["ready"] is True
    assert payload["components"]["notification"]["enabled"] is True
    assert payload["components"]["notification"]["ok"] is False
    assert payload["components"]["notification"]["state"] == "degraded"
    assert payload["components"]["notification"]["failed_count"] == 1
    assert payload["components"]["notification"]["target"] is None
    assert payload["components"]["notification"]["last_error"]["present"] is True
    assert "message" not in payload["components"]["notification"]["last_error"]
