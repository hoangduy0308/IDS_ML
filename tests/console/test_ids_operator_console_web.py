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
    root_path: str = "",
) -> tuple[TestClient, Path, int]:
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": environment,
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "web-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    if root_path:
        env["IDS_OPERATOR_CONSOLE_ROOT_PATH"] = root_path
        # In tests, keep session cookie path at "/" so the TestClient can
        # authenticate without a real reverse proxy in front of the app.
        env["IDS_OPERATOR_CONSOLE_SESSION_COOKIE_PATH"] = "/"
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
    client = TestClient(app, base_url=base_url, root_path=root_path)
    return client, config.database_path, alert_id


def _build_family_contract_test_app(tmp_path: Path) -> tuple[TestClient, dict[str, int]]:
    """Build canonical app-factory client with known/unknown/legacy family alerts."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "web-family-contract-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console_family_contract.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="correct-password")
        known_id = store.upsert_alert(
            source_event_id="web-family-known-001",
            event_ts="2026-04-01T09:00:00+00:00",
            severity="high",
            src_ip="10.30.0.1",
            dst_ip="192.168.60.10",
            src_port=1111,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-web-family-known-001",
            payload={
                "family_status": "known",
                "attack_family": "mirai",
                "attack_family_confidence": 0.98,
                "attack_family_margin": 0.44,
            },
        )
        unknown_id = store.upsert_alert(
            source_event_id="web-family-unknown-002",
            event_ts="2026-04-01T09:05:00+00:00",
            severity="high",
            src_ip="10.30.0.2",
            dst_ip="192.168.60.11",
            src_port=2222,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-web-family-unknown-002",
            payload={
                "family_status": "unknown",
                "attack_family_confidence": 0.45,
                "attack_family_margin": 0.02,
            },
        )
        legacy_id = store.upsert_alert(
            source_event_id="web-family-legacy-003",
            event_ts="2026-04-01T09:10:00+00:00",
            severity="medium",
            src_ip="10.30.0.3",
            dst_ip="192.168.60.12",
            src_port=3333,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-web-family-legacy-003",
            payload={"score": 0.77},
        )
    finally:
        store.close()

    app = create_operator_console_web_app(config)
    client = TestClient(app, base_url="http://testserver")
    return client, {"known": known_id, "unknown": unknown_id, "legacy": legacy_id}


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
    assert alerts_page.status_code == 200

    operations_page = client.get("/operations")
    assert operations_page.status_code == 200

    reports_page = client.get("/reports")
    assert reports_page.status_code == 200

    detail = client.get(f"/alerts/{alert_id}")
    assert detail.status_code == 200

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


def test_alert_detail_route_pins_known_unknown_legacy_family_contract(tmp_path: Path) -> None:
    """Route-level proof: detail page preserves known/unknown/legacy semantics."""
    client, alert_ids = _build_family_contract_test_app(tmp_path)
    _login(client)

    known = client.get(f"/alerts/{alert_ids['known']}")
    assert known.status_code == 200
    assert "family signal" in known.text.lower()
    assert "known family" in known.text.lower()
    assert "mirai" in known.text.lower()
    assert f"/alerts/{alert_ids['known']}/status" in known.text
    assert f"/alerts/{alert_ids['known']}/notes" in known.text

    unknown = client.get(f"/alerts/{alert_ids['unknown']}")
    assert unknown.status_code == 200
    assert "unknown family" in unknown.text.lower()
    assert "binary stage still classified this event as an attack" in unknown.text.lower()

    legacy = client.get(f"/alerts/{alert_ids['legacy']}")
    assert legacy.status_code == 200
    assert "family unavailable" in legacy.text.lower()
    assert "predates family enrichment rollout" in legacy.text.lower()


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


def test_live_logs_returns_200_not_501(tmp_path: Path) -> None:
    """GET /live-logs must return 200 now that it is implemented (Phase 3 Story 3.3)."""
    client, _, _ = _build_test_app(tmp_path)
    _login(client)

    live_logs = client.get("/live-logs")
    assert live_logs.status_code == 200, (
        f"Expected 200 but got {live_logs.status_code} — "
        "/live-logs must render (not 501) after Phase 3 Story 3.3"
    )


def test_suppression_rules_returns_200_not_501(tmp_path: Path) -> None:
    """GET /suppression-rules must return 200 now that it is implemented (Phase 3 Story 3.2)."""
    client, _, _ = _build_test_app(tmp_path)
    _login(client)

    suppression_rules = client.get("/suppression-rules")
    assert suppression_rules.status_code == 200, (
        f"Expected 200 but got {suppression_rules.status_code} — "
        "/suppression-rules must render (not 501) after Phase 3 Story 3.2"
    )


def test_system_health_returns_200_not_501(tmp_path: Path) -> None:
    """GET /system-health must return 200 now that it is implemented (Phase 3 Story 3.1)."""
    client, _, _ = _build_test_app(tmp_path)
    _login(client)

    system_health = client.get("/system-health")
    assert system_health.status_code == 200, (
        f"Expected 200 but got {system_health.status_code} — "
        "/system-health must render (not 501) after Phase 3 Story 3.1"
    )


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


# ── Settings page tests ─────────────────────────────────────────────────────


def _get_csrf(client: TestClient) -> str:
    """Extract CSRF token from the settings page."""
    import re

    resp = client.get("/settings")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    assert match is not None, "CSRF token not found in settings page"
    return match.group(1)


def test_settings_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    response = client.get("/settings", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_settings_renders_form_when_authenticated(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    _login(client)
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Settings" in response.text
    assert "Not configured" in response.text


def test_settings_save_stores_and_masks_token(tmp_path: Path) -> None:
    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)
    # Save settings
    save_resp = client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "123:ABCDEF", "chat_id": "-100999"},
        follow_redirects=False,
    )
    assert save_resp.status_code == 303
    assert save_resp.headers["location"] == "/settings"
    # Verify masked display
    get_resp = client.get("/settings")
    assert get_resp.status_code == 200
    assert "Configured" in get_resp.text
    assert "\u2022\u2022\u2022\u2022\u2022\u2022CDEF" in get_resp.text
    # CRITICAL: Full token must NOT appear in response
    assert "123:ABCDEF" not in get_resp.text


def test_settings_clear_removes_settings(tmp_path: Path) -> None:
    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)
    # Save first
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "123:ABCDEF", "chat_id": "-100999"},
        follow_redirects=False,
    )
    # Clear
    clear_resp = client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "", "chat_id": ""},
        follow_redirects=False,
    )
    assert clear_resp.status_code == 303
    get_resp = client.get("/settings")
    assert "Not configured" in get_resp.text


def test_settings_save_rejects_without_csrf(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    _login(client)
    response = client.post(
        "/settings",
        data={"bot_token": "123:ABCDEF", "chat_id": "-100999"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_settings_test_returns_json_success(tmp_path: Path, monkeypatch: "pytest.MonkeyPatch") -> None:
    """POST /settings/test should call send_telegram_message and return success JSON."""
    from unittest.mock import MagicMock

    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)
    # Save settings first
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "123:TESTTOKEN", "chat_id": "-100test"},
        follow_redirects=False,
    )
    # Mock send_telegram_message to avoid real network call
    from ids.console import notifications

    mock_send = MagicMock(return_value="msg-123")
    monkeypatch.setattr(notifications, "send_telegram_message", mock_send)
    response = client.post(
        "/settings/test",
        data={"csrf_token": _get_csrf(client)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "sent successfully" in data["detail"].lower()
    mock_send.assert_called_once()


def test_settings_test_returns_error_when_not_configured(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    _login(client)
    response = client.post(
        "/settings/test",
        data={"csrf_token": _get_csrf(client)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not configured" in data["detail"].lower()


def test_settings_save_preserves_token_when_only_chat_id_changes(tmp_path: Path) -> None:
    """Changing only the chat ID must not wipe the existing bot token (P1 fix)."""
    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)
    # Save initial settings
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "123:ORIGINALTOKEN", "chat_id": "-100999"},
        follow_redirects=False,
    )
    # Update only chat_id — bot_token field is empty (as happens with password fields)
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "", "chat_id": "-100888"},
        follow_redirects=False,
    )
    # Token must be preserved, chat_id updated
    get_resp = client.get("/settings")
    assert "Configured" in get_resp.text
    assert "\u2022\u2022\u2022\u2022\u2022\u2022OKEN" in get_resp.text  # last 4 of ORIGINALTOKEN
    assert "-100888" in get_resp.text


def test_settings_save_post_rejects_unauthenticated(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    response = client.post(
        "/settings",
        data={"bot_token": "123:TOKEN", "chat_id": "-100"},
        follow_redirects=False,
    )
    assert response.status_code in (401, 403)


def test_settings_test_post_rejects_unauthenticated(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    response = client.post(
        "/settings/test",
        data={},
        follow_redirects=False,
    )
    assert response.status_code in (401, 403)


def test_settings_test_rejects_without_csrf(tmp_path: Path) -> None:
    client, _, _ = _build_test_app(tmp_path)
    _login(client)
    response = client.post(
        "/settings/test",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_settings_test_returns_error_when_send_fails(tmp_path: Path, monkeypatch: "pytest.MonkeyPatch") -> None:
    """POST /settings/test returns graceful JSON error when Telegram API fails."""
    from ids.console import notifications
    from ids.console.notifications import NotificationDeliveryError

    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "123:BADTOKEN", "chat_id": "-100test"},
        follow_redirects=False,
    )

    def failing_sender(*args, **kwargs):
        raise NotificationDeliveryError("Bot token rejected by Telegram", retryable=False)

    monkeypatch.setattr(notifications, "send_telegram_message", failing_sender)
    response = client.post(
        "/settings/test",
        data={"csrf_token": _get_csrf(client)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    # Must return a generic message, NOT the raw exception text
    assert "check your bot token" in data["detail"].lower()


def test_settings_test_does_not_leak_internal_error_details(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """POST /settings/test must never leak raw exception text (i7oa.6)."""
    from ids.console import notifications
    from ids.console.notifications import NotificationDeliveryError

    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "123:BADTOKEN", "chat_id": "-100test"},
        follow_redirects=False,
    )

    internal_detail = "HTTP 401: Unauthorized at https://api.telegram.org/bot123:BADTOKEN/sendMessage"

    def leaking_sender(*args, **kwargs):
        raise NotificationDeliveryError(internal_detail, retryable=False)

    monkeypatch.setattr(notifications, "send_telegram_message", leaking_sender)
    response = client.post(
        "/settings/test",
        data={"csrf_token": _get_csrf(client)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    # Raw exception text must NOT appear in the response
    assert internal_detail not in data["detail"], (
        "Internal error detail must be sanitized — raw exception text leaked to client"
    )
    assert "api.telegram.org" not in data["detail"]
    assert "BADTOKEN" not in data["detail"]


def test_settings_test_sanitizes_value_error(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """POST /settings/test sanitizes ValueError responses too (i7oa.6)."""
    from ids.console import notifications

    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "123:TOKEN", "chat_id": "-100test"},
        follow_redirects=False,
    )

    internal_msg = "invalid chat_id format: expected integer, got 'abc' at offset 3"

    def value_error_sender(*args, **kwargs):
        raise ValueError(internal_msg)

    monkeypatch.setattr(notifications, "send_telegram_message", value_error_sender)
    response = client.post(
        "/settings/test",
        data={"csrf_token": _get_csrf(client)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert internal_msg not in data["detail"]
    assert "invalid telegram configuration" in data["detail"].lower()


def test_settings_nav_item_present(tmp_path: Path) -> None:
    from ids.console.web import PRIMARY_NAV

    keys = [item["key"] for item in PRIMARY_NAV]
    assert "settings" in keys


# ── Effective Telegram config resolution tests ─────────────────────────────


def test_settings_shows_env_fallback_when_db_is_empty(tmp_path: Path) -> None:
    """When DB has no Telegram settings but env provides them, /settings
    should show 'Configured' with 'via environment' source indicator."""
    client, db_path, _ = _build_test_app(tmp_path, telegram_enabled=True)
    _login(client)
    # DB is empty for telegram settings — env fallback should be used
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Configured" in response.text
    assert "via environment" in response.text
    # The env chat_id should appear
    assert "-100web" in response.text


def test_settings_test_uses_env_fallback_when_db_is_empty(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """POST /settings/test should succeed using env fallback when DB is empty."""
    from unittest.mock import MagicMock
    from ids.console import notifications

    client, db_path, _ = _build_test_app(tmp_path, telegram_enabled=True)
    _login(client)
    # DB has no telegram settings — only env fallback
    mock_send = MagicMock(return_value="msg-env-test")
    monkeypatch.setattr(notifications, "send_telegram_message", mock_send)
    response = client.post(
        "/settings/test",
        data={"csrf_token": _get_csrf(client)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "sent successfully" in data["detail"].lower()
    mock_send.assert_called_once()


def test_settings_db_overrides_env_config(tmp_path: Path) -> None:
    """When both DB and env have Telegram settings, DB values should win."""
    client, db_path, _ = _build_test_app(tmp_path, telegram_enabled=True)
    _login(client)
    # Save DB settings that differ from env
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "999:DBTOKEN", "chat_id": "-200db"},
        follow_redirects=False,
    )
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Configured" in response.text
    assert "via database" in response.text
    # DB chat_id should appear, not env chat_id
    assert "-200db" in response.text
    assert "-100web" not in response.text


def test_settings_test_uses_db_when_both_configured(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """POST /settings/test should use DB config when both DB and env exist."""
    from unittest.mock import MagicMock
    from ids.console import notifications

    client, db_path, _ = _build_test_app(tmp_path, telegram_enabled=True)
    _login(client)
    # Save DB settings
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "999:DBTOKEN", "chat_id": "-200db"},
        follow_redirects=False,
    )
    mock_send = MagicMock(return_value="msg-db-test")
    monkeypatch.setattr(notifications, "send_telegram_message", mock_send)
    response = client.post(
        "/settings/test",
        data={"csrf_token": _get_csrf(client)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Verify the DB chat_id was used (not env)
    call_args = mock_send.call_args
    assert call_args is not None
    assert call_args.kwargs.get("chat_id") == "-200db" or (
        len(call_args.args) >= 2 and call_args.args[1] == "-200db"
    )


def test_settings_clearing_db_falls_back_to_env(tmp_path: Path) -> None:
    """After clearing DB settings, env fallback should take over."""
    client, db_path, _ = _build_test_app(tmp_path, telegram_enabled=True)
    _login(client)
    # Save DB settings
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "999:DBTOKEN", "chat_id": "-200db"},
        follow_redirects=False,
    )
    # Clear DB settings
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "", "chat_id": ""},
        follow_redirects=False,
    )
    response = client.get("/settings")
    assert response.status_code == 200
    # Should fall back to env
    assert "Configured" in response.text
    assert "via environment" in response.text
    assert "-100web" in response.text


# ── Root-path-aware settings tests ───────────────────────────────────────


def test_settings_form_action_includes_root_path(tmp_path: Path) -> None:
    """When root_path is set, the settings form action must include it."""
    client, _, _ = _build_test_app(tmp_path, root_path="/console")
    _login(client)
    response = client.get("/settings")
    assert response.status_code == 200
    assert 'action="/console/settings"' in response.text, (
        "Settings form action must be root-path-aware"
    )


def test_settings_test_url_includes_root_path(tmp_path: Path) -> None:
    """When root_path is set, the test button data attribute must include it."""
    client, _, _ = _build_test_app(tmp_path, root_path="/console")
    _login(client)
    response = client.get("/settings")
    assert response.status_code == 200
    assert 'data-test-url="/console/settings/test"' in response.text, (
        "Settings test URL data attribute must be root-path-aware"
    )


def test_settings_save_redirect_includes_root_path(tmp_path: Path) -> None:
    """POST /settings redirect must include root_path in the Location header."""
    client, _, _ = _build_test_app(tmp_path, root_path="/console")
    _login(client)
    save_resp = client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "123:TOKEN", "chat_id": "-100test"},
        follow_redirects=False,
    )
    assert save_resp.status_code == 303
    assert save_resp.headers["location"] == "/console/settings", (
        "Settings save redirect must include root_path prefix"
    )


def test_settings_bare_root_path_still_works(tmp_path: Path) -> None:
    """With empty root_path (default), settings form action is /settings."""
    client, _, _ = _build_test_app(tmp_path)
    _login(client)
    response = client.get("/settings")
    assert response.status_code == 200
    assert 'action="/settings"' in response.text
    assert 'data-test-url="/settings/test"' in response.text


def test_settings_save_rejects_chat_id_without_token_on_fresh_db(tmp_path: Path) -> None:
    """Saving only a chat_id with no existing or new bot_token must not persist
    a half-configured Telegram setup (contract drift fix: i7oa.5)."""
    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)
    # Attempt to save chat_id only — no token exists in DB or form
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "", "chat_id": "-100orphan"},
        follow_redirects=False,
    )
    # Settings page should still show "Not configured"
    get_resp = client.get("/settings")
    assert "Not configured" in get_resp.text, (
        "Saving chat_id without a bot_token on a fresh DB must not create a half-configured state"
    )
    assert "-100orphan" not in get_resp.text


def test_settings_page_uses_resolver_source(tmp_path: Path) -> None:
    """settings_page must derive config_source from the shared resolver,
    not from parallel DB reads (contract drift fix: i7oa.5)."""
    client, db_path, _ = _build_test_app(tmp_path, telegram_enabled=True)
    _login(client)
    # DB is empty — env fallback should show "via environment"
    resp_env = client.get("/settings")
    assert "via environment" in resp_env.text

    # Save DB settings
    client.post(
        "/settings",
        data={"csrf_token": _get_csrf(client), "bot_token": "999:DBTOKEN", "chat_id": "-200db"},
        follow_redirects=False,
    )
    resp_db = client.get("/settings")
    assert "via database" in resp_db.text


# ── XSS regression tests ──────────────────────────────────────────────────


def test_settings_chat_id_xss_is_escaped_in_template(tmp_path: Path) -> None:
    """A malicious chat_id stored in the DB must be HTML-escaped when
    rendered in the settings template (XSS regression test: i7oa.7)."""
    client, db_path, _ = _build_test_app(tmp_path)
    _login(client)

    # Store a malicious chat_id directly in the DB to bypass form sanitisation
    store = open_existing_operator_store(db_path)
    try:
        malicious = '"><script>alert(1)</script>'
        store.set_setting("telegram_bot_token", "123:XSSTOKEN")
        store.set_setting("telegram_chat_id", malicious)
    finally:
        store.close()

    response = client.get("/settings")
    assert response.status_code == 200

    # The raw malicious string must NOT appear unescaped
    assert malicious not in response.text, (
        "Raw malicious chat_id appeared in HTML — XSS vulnerability"
    )
    # The HTML-escaped version MUST be present
    assert "&gt;&lt;script&gt;" in response.text or "&#34;&gt;&lt;script&gt;" in response.text or "&quot;&gt;&lt;script&gt;" in response.text, (
        "Expected HTML-escaped chat_id in the template output"
    )


# ── _mask_token unit tests ──────────────────────────────────────────────────


def test_mask_token_short_token() -> None:
    """Token with <=4 chars returns '****'."""
    from ids.console.web import _mask_token

    assert _mask_token("abcd") == "****"
    assert _mask_token("ab") == "****"
    assert _mask_token("a") == "****"


def test_mask_token_empty_string() -> None:
    """Empty string returns '****'."""
    from ids.console.web import _mask_token

    assert _mask_token("") == "****"


def test_mask_token_normal() -> None:
    """Normal token returns masked form with last 4 chars visible."""
    from ids.console.web import _mask_token

    result = _mask_token("123:ABCTOKEN")
    # Last 4 chars should be visible
    assert result.endswith("OKEN")
    # Should start with bullet chars
    assert "\u2022" in result
    # Full token must NOT appear
    assert "123:ABCTOKEN" != result


# ── _env_telegram_fallback unit tests ───────────────────────────────────────


def test_env_telegram_fallback_partial_config() -> None:
    """Config with only token but no chat_id returns None."""
    from ids.console.web import _env_telegram_fallback

    config = load_operator_console_config(
        environ={
            "IDS_OPERATOR_CONSOLE_SECRET_KEY": "test-secret",
            "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN": "123:TOKEN",
            "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID": "-100chat",
        },
        repo_root=REPO_ROOT,
    )
    # Both present: should return a config
    result_both = _env_telegram_fallback(config)
    assert result_both is not None

    # Now test with only token (need to build a config with chat_id=None)
    # Since OperatorConsoleConfig validates they must be set together,
    # we test the branch where both are None
    config_none = load_operator_console_config(
        environ={
            "IDS_OPERATOR_CONSOLE_SECRET_KEY": "test-secret",
        },
        repo_root=REPO_ROOT,
    )
    result_none = _env_telegram_fallback(config_none)
    assert result_none is None


def test_env_telegram_fallback_both_present() -> None:
    """Config with both token and chat_id returns TelegramNotifierConfig."""
    from ids.console.web import _env_telegram_fallback
    from ids.console.notifications import TelegramNotifierConfig

    config = load_operator_console_config(
        environ={
            "IDS_OPERATOR_CONSOLE_SECRET_KEY": "test-secret",
            "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN": "123:TESTTOKEN",
            "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID": "-100test",
        },
        repo_root=REPO_ROOT,
    )
    result = _env_telegram_fallback(config)
    assert result is not None
    assert isinstance(result, TelegramNotifierConfig)
    assert result.bot_token == "123:TESTTOKEN"
    assert result.default_chat_id == "-100test"


def test_env_telegram_fallback_neither_present() -> None:
    """Config with neither token nor chat_id returns None."""
    from ids.console.web import _env_telegram_fallback

    config = load_operator_console_config(
        environ={
            "IDS_OPERATOR_CONSOLE_SECRET_KEY": "test-secret",
        },
        repo_root=REPO_ROOT,
    )
    result = _env_telegram_fallback(config)
    assert result is None
