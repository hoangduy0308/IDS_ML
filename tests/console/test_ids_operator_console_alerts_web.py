"""Tests for the /alerts and /alerts/{id} screens — written FIRST (TDD).

Bead: ids_ml_new-ibzr
Story: Phase 2 / Story 2.2 — Alerts queue + Alert Detail screens TDD

Run order:
1. These tests must FAIL first (501 stubs still in place)
2. Implement /alerts, /alerts/{id}, POST /alerts/{id}/notes, POST /alerts/{id}/status
3. These tests must PASS
"""
from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.console.alerts import (  # noqa: E402
    add_investigation_note,
    transition_alert_status,
)
from ids.console.auth import ensure_admin_user  # noqa: E402
from ids.console.config import load_operator_console_config  # noqa: E402
from ids.console.db import open_existing_operator_store  # noqa: E402
from ids.console.migrations import migrate_operator_store  # noqa: E402
from ids.console.web import create_operator_console_web_app  # noqa: E402


def _build_alerts_test_app(tmp_path: Path) -> tuple[TestClient, int, int]:
    """Build test client with two alerts — one suppressed, one acknowledged."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "alerts-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    attack_id: int = -1
    ack_id: int = -1
    try:
        ensure_admin_user(store, username="admin", password="secret")

        # Alert 1: attack alert (will be suppressed via suppression rule)
        attack_id = store.upsert_alert(
            source_event_id="alerts-web-attack-001",
            event_ts="2026-03-29T10:00:00+00:00",
            severity="critical",
            src_ip="10.99.0.5",
            dst_ip="192.168.1.10",
            src_port=4444,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-attack-001",
            payload={"src_ip": "10.99.0.5", "score": 0.99},
        )
        # Add suppression rule matching this alert's src_ip
        store.create_suppression_rule(
            rule_name="suppress-attack-src",
            match_field="src_ip",
            match_value="10.99.0.5",
            applies_to="model_alert",
        )

        # Alert 2: acknowledged alert with a note
        ack_id = store.upsert_alert(
            source_event_id="alerts-web-ack-002",
            event_ts="2026-03-29T11:00:00+00:00",
            severity="high",
            src_ip="10.10.0.2",
            dst_ip="192.168.1.20",
            src_port=55000,
            dst_port=80,
            protocol="tcp",
            fingerprint="fp-ack-002",
            payload={"score": 0.85},
        )
        transition_alert_status(store, alert_id=ack_id, to_status="acknowledged", changed_by="admin")
        add_investigation_note(
            store,
            alert_id=ack_id,
            note_text="Initial triage note",
            author="admin",
        )
    finally:
        store.close()

    app = create_operator_console_web_app(config)
    client = TestClient(app, base_url="http://testserver")
    return client, attack_id, ack_id


def _build_family_detail_test_app(tmp_path: Path) -> tuple[TestClient, int, int, int]:
    """Build test client with known/unknown/legacy family-state alerts."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "family-detail-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console_family.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    known_id: int = -1
    unknown_id: int = -1
    legacy_id: int = -1
    try:
        ensure_admin_user(store, username="admin", password="secret")

        known_id = store.upsert_alert(
            source_event_id="alerts-web-known-003",
            event_ts="2026-03-30T10:00:00+00:00",
            severity="high",
            src_ip="10.20.0.3",
            dst_ip="192.168.1.30",
            src_port=3333,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-known-003",
            payload={
                "family_status": "known",
                "attack_family": "mirai",
                "attack_family_confidence": 0.97,
                "attack_family_margin": 0.42,
            },
        )
        unknown_id = store.upsert_alert(
            source_event_id="alerts-web-unknown-004",
            event_ts="2026-03-30T11:00:00+00:00",
            severity="high",
            src_ip="10.20.0.4",
            dst_ip="192.168.1.31",
            src_port=4444,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-unknown-004",
            payload={
                "family_status": "unknown",
                "attack_family_confidence": 0.49,
                "attack_family_margin": 0.01,
            },
        )
        legacy_id = store.upsert_alert(
            source_event_id="alerts-web-legacy-005",
            event_ts="2026-03-30T12:00:00+00:00",
            severity="medium",
            src_ip="10.20.0.5",
            dst_ip="192.168.1.32",
            src_port=5555,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-legacy-005",
            payload={"score": 0.82},
        )
    finally:
        store.close()

    app = create_operator_console_web_app(config)
    client = TestClient(app, base_url="http://testserver")
    return client, known_id, unknown_id, legacy_id


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Login failed: {response.status_code}"


def _get_csrf(client: TestClient) -> str:
    """Extract CSRF token from the overview page (it's in a hidden form input)."""
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.text
    # The sidebar has a logout form with csrf_token
    import re
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
    assert match, "Could not find csrf_token in page"
    return match.group(1)


# ── Unauthenticated ───────────────────────────────────────────────────────────

def test_alerts_queue_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    client, _, _ = _build_alerts_test_app(tmp_path)
    response = client.get("/alerts", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_alert_detail_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    response = client.get(f"/alerts/{ack_id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# ── Alerts queue: status 200 ──────────────────────────────────────────────────

def test_alerts_queue_returns_200_when_authenticated(tmp_path: Path) -> None:
    client, _, _ = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get("/alerts")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Ensure the /alerts stub is replaced."
    )


def test_alerts_queue_response_is_html(tmp_path: Path) -> None:
    client, _, _ = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get("/alerts")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_alerts_queue_extends_base_template(tmp_path: Path) -> None:
    client, _, _ = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get("/alerts")
    assert response.status_code == 200
    body = response.text
    assert "shell" in body
    assert "app-sidebar" in body


def test_alerts_queue_shows_alert_rows(tmp_path: Path) -> None:
    """Both seeded alerts must appear in the queue (include_suppressed=True)."""
    client, attack_id, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get("/alerts")
    assert response.status_code == 200
    body = response.text
    assert "alerts-web-attack-001" in body
    assert "alerts-web-ack-002" in body


def test_alerts_queue_marks_suppressed_row(tmp_path: Path) -> None:
    """Suppressed alerts must have a visible suppressed marker."""
    client, _, _ = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get("/alerts")
    assert response.status_code == 200
    body = response.text
    assert "suppressed" in body.lower(), (
        "Expected 'suppressed' marker in alerts queue for suppressed alert row"
    )


# ── Status filter ─────────────────────────────────────────────────────────────

def test_alerts_status_filter_returns_only_matching_rows(tmp_path: Path) -> None:
    """?status=acknowledged should show the ack alert but not the new/attack one."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get("/alerts?status=acknowledged")
    assert response.status_code == 200
    body = response.text
    assert "alerts-web-ack-002" in body
    # The attack alert is "new" triage status, so it must NOT appear
    assert "alerts-web-attack-001" not in body


def test_alerts_status_filter_new_excludes_ack_row(tmp_path: Path) -> None:
    """?status=new should show the attack alert but not the ack one."""
    client, _, _ = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get("/alerts?status=new")
    assert response.status_code == 200
    body = response.text
    assert "alerts-web-attack-001" in body
    assert "alerts-web-ack-002" not in body


# ── Alert detail ──────────────────────────────────────────────────────────────

def test_alert_detail_returns_200(tmp_path: Path) -> None:
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Ensure the /alerts/{{id}} stub is replaced."
    )


def test_alert_detail_response_is_html(tmp_path: Path) -> None:
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_alert_detail_shows_alert_identifiers(tmp_path: Path) -> None:
    """Alert detail must show source event ID, IPs, protocol."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200
    body = response.text
    assert "alerts-web-ack-002" in body
    assert "10.10.0.2" in body
    assert "192.168.1.20" in body


def test_alert_detail_shows_notes_section(tmp_path: Path) -> None:
    """Alert detail must render the note that was seeded."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200
    body = response.text
    assert "Initial triage note" in body


def test_alert_detail_shows_status_history_section(tmp_path: Path) -> None:
    """Alert detail must render status history (acknowledged transition)."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200
    body = response.text
    # Status history should mention 'acknowledged'
    assert "acknowledged" in body.lower()


def test_alert_detail_shows_triage_form(tmp_path: Path) -> None:
    """Alert detail must render the triage status update form."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200
    body = response.text
    # POST form to /alerts/{id}/status
    assert f"/alerts/{ack_id}/status" in body


def test_alert_detail_shows_note_form(tmp_path: Path) -> None:
    """Alert detail must render the investigation note form."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200
    body = response.text
    assert f"/alerts/{ack_id}/notes" in body


def test_alert_detail_returns_404_for_unknown_id(tmp_path: Path) -> None:
    """GET /alerts/99999 must return 404 (not 501, not 500)."""
    client, _, _ = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.get("/alerts/99999")
    assert response.status_code == 404


def test_alert_detail_known_family_explanation(tmp_path: Path) -> None:
    client, known_id, _, _ = _build_family_detail_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{known_id}")
    assert response.status_code == 200
    body = response.text
    assert "Family Signal" in body
    assert "known family" in body.lower()
    assert "mirai" in body.lower()
    assert "97.0%" in body


def test_alert_detail_unknown_family_explanation(tmp_path: Path) -> None:
    client, _, unknown_id, _ = _build_family_detail_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{unknown_id}")
    assert response.status_code == 200
    body = response.text
    assert "unknown family" in body.lower()
    assert "binary stage still classified this event as an attack" in body.lower()


def test_alert_detail_legacy_family_fallback(tmp_path: Path) -> None:
    client, _, _, legacy_id = _build_family_detail_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{legacy_id}")
    assert response.status_code == 200
    body = response.text
    assert "family unavailable" in body.lower()
    assert "predates family enrichment rollout" in body.lower()


def test_alert_detail_family_block_keeps_triage_and_notes_controls(tmp_path: Path) -> None:
    client, known_id, _, _ = _build_family_detail_test_app(tmp_path)
    _login(client)
    response = client.get(f"/alerts/{known_id}")
    assert response.status_code == 200
    body = response.text
    assert f"/alerts/{known_id}/status" in body
    assert f"/alerts/{known_id}/notes" in body


# ── POST /alerts/{id}/notes ───────────────────────────────────────────────────

def test_add_note_redirects_after_success(tmp_path: Path) -> None:
    """POST /alerts/{id}/notes with valid CSRF must redirect 303 to detail page."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    csrf = _get_csrf(client)

    response = client.post(
        f"/alerts/{ack_id}/notes",
        data={"csrf_token": csrf, "note_text": "Follow-up note from test"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/alerts/{ack_id}"


def test_add_note_persists_in_detail(tmp_path: Path) -> None:
    """Note added via POST must appear on the detail page after redirect."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    csrf = _get_csrf(client)

    client.post(
        f"/alerts/{ack_id}/notes",
        data={"csrf_token": csrf, "note_text": "Persistent note content"},
        follow_redirects=True,
    )
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200
    assert "Persistent note content" in response.text


def test_add_note_rejects_missing_csrf(tmp_path: Path) -> None:
    """POST without CSRF token must be rejected (403)."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.post(
        f"/alerts/{ack_id}/notes",
        data={"csrf_token": "", "note_text": "should be rejected"},
        follow_redirects=False,
    )
    assert response.status_code in (400, 403)


def test_add_note_rejects_invalid_csrf(tmp_path: Path) -> None:
    """POST with wrong CSRF token must be rejected (403)."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.post(
        f"/alerts/{ack_id}/notes",
        data={"csrf_token": "bad-token-xyz", "note_text": "should be rejected"},
        follow_redirects=False,
    )
    assert response.status_code in (400, 403)


# ── POST /alerts/{id}/status ──────────────────────────────────────────────────

def test_update_status_redirects_after_success(tmp_path: Path) -> None:
    """POST /alerts/{id}/status with valid CSRF must redirect 303 to detail."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    csrf = _get_csrf(client)

    response = client.post(
        f"/alerts/{ack_id}/status",
        data={"csrf_token": csrf, "new_status": "investigating"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/alerts/{ack_id}"


def test_update_status_reflects_on_reload(tmp_path: Path) -> None:
    """Status updated via POST must appear on the detail page after reload."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    csrf = _get_csrf(client)

    client.post(
        f"/alerts/{ack_id}/status",
        data={"csrf_token": csrf, "new_status": "resolved"},
        follow_redirects=True,
    )
    response = client.get(f"/alerts/{ack_id}")
    assert response.status_code == 200
    assert "resolved" in response.text.lower()


def test_update_status_rejects_missing_csrf(tmp_path: Path) -> None:
    """POST without CSRF must be rejected."""
    client, _, ack_id = _build_alerts_test_app(tmp_path)
    _login(client)
    response = client.post(
        f"/alerts/{ack_id}/status",
        data={"csrf_token": "", "new_status": "resolved"},
        follow_redirects=False,
    )
    assert response.status_code in (400, 403)
