"""Tests for the /suppression-rules screen — written FIRST (TDD).

Bead: ids_ml_new-7vke
Story: Phase 3 / Story 3.2 — Suppression Rules screen TDD

Run order:
1. These tests must FAIL first (501 stub still in place)
2. Implement GET + POST handlers + suppression_rules.html
3. These tests must PASS
"""
from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.console.auth import ensure_admin_user  # noqa: E402
from ids.console.config import load_operator_console_config  # noqa: E402
from ids.console.db import open_existing_operator_store  # noqa: E402
from ids.console.migrations import migrate_operator_store  # noqa: E402
from ids.console.web import create_operator_console_web_app  # noqa: E402


def _build_suppression_test_app(tmp_path: Path, *, seed_rules: bool = True) -> TestClient:
    """Build a test client with optional seeded suppression rules."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "suppression-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="secret")
        if seed_rules:
            store.create_suppression_rule(
                rule_name="Block scanner",
                match_field="src_ip",
                match_value="10.99.0.5",
                applies_to="model_alert",
            )
            store.create_suppression_rule(
                rule_name="Block noisy host",
                match_field="src_ip",
                match_value="10.88.0.1",
                applies_to="model_alert",
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


def _get_csrf(client: TestClient) -> str:
    """Extract CSRF token from the overview page."""
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.text
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
    assert match, "Could not find csrf_token in page"
    return match.group(1)


# ── Unauthenticated access ────────────────────────────────────────────────────

def test_suppression_rules_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    """Unauthenticated GET /suppression-rules must redirect to /login."""
    client = _build_suppression_test_app(tmp_path)
    response = client.get("/suppression-rules", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# ── GET /suppression-rules: authenticated ─────────────────────────────────────

def test_suppression_rules_returns_200_when_authenticated(tmp_path: Path) -> None:
    """GET /suppression-rules returns 200 (not 501) after authentication."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Ensure the /suppression-rules stub is replaced with a real handler."
    )


def test_suppression_rules_response_is_html(tmp_path: Path) -> None:
    """Response Content-Type must be text/html."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_suppression_rules_extends_base_template(tmp_path: Path) -> None:
    """Page must render via base.html — look for shell structure markers."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200
    body = response.text
    assert "shell" in body, "Shell layout classes not found — base.html not extended"
    assert "app-sidebar" in body, "Sidebar not rendered — base.html not extended"


def test_suppression_rules_page_title_present(tmp_path: Path) -> None:
    """Page must contain 'Suppression' or 'Rules' in the body."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("Suppression", "suppression", "Rules", "rules")), (
        "Page title/heading not found in suppression-rules response"
    )


# ── Active rules rendering ────────────────────────────────────────────────────

def test_suppression_rules_renders_seeded_rules(tmp_path: Path) -> None:
    """Seeded rules must appear in the active rules table."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200
    body = response.text
    assert "Block scanner" in body, "Expected rule 'Block scanner' in rules list"
    assert "Block noisy host" in body, "Expected rule 'Block noisy host' in rules list"


def test_suppression_rules_renders_rule_details(tmp_path: Path) -> None:
    """Rules must show match_field and match_value."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200
    body = response.text
    assert "src_ip" in body, "match_field not rendered in rules table"
    assert "10.99.0.5" in body, "match_value not rendered in rules table"


def test_suppression_rules_renders_all_seeded_rules(tmp_path: Path) -> None:
    """Both seeded rules must appear."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200
    body = response.text
    assert "10.99.0.5" in body
    assert "10.88.0.1" in body


# ── Empty state ───────────────────────────────────────────────────────────────

def test_suppression_rules_empty_state_when_no_rules(tmp_path: Path) -> None:
    """When no rules exist, page renders an empty state message."""
    client = _build_suppression_test_app(tmp_path, seed_rules=False)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in (
        "No active", "no active", "No rules", "no rules", "empty", "no suppression"
    )), "Empty state message not found in suppression-rules page when no rules exist"


# ── Add rule form ─────────────────────────────────────────────────────────────

def test_suppression_rules_add_form_present(tmp_path: Path) -> None:
    """Add rule form must be present with required input fields."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.get("/suppression-rules")
    assert response.status_code == 200
    body = response.text
    assert 'name="rule_name"' in body, "rule_name input not found in add form"
    assert 'name="match_field"' in body, "match_field input not found in add form"
    assert 'name="match_value"' in body, "match_value input not found in add form"
    assert 'name="csrf_token"' in body, "csrf_token hidden input not found in add form"


# ── POST /suppression-rules: add rule ────────────────────────────────────────

def test_suppression_rules_post_add_redirects_with_valid_csrf(tmp_path: Path) -> None:
    """POST /suppression-rules with valid CSRF → 303 redirect to /suppression-rules."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    csrf = _get_csrf(client)
    response = client.post(
        "/suppression-rules",
        data={
            "csrf_token": csrf,
            "rule_name": "New test rule",
            "match_field": "dst_ip",
            "match_value": "192.168.100.1",
            "applies_to": "model_alert",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"Expected 303 redirect but got {response.status_code}"
    )
    assert response.headers["location"] == "/suppression-rules"


def test_suppression_rules_post_add_rule_appears_after_redirect(tmp_path: Path) -> None:
    """After POST add, the new rule appears in the GET /suppression-rules response."""
    client = _build_suppression_test_app(tmp_path, seed_rules=False)
    _login(client)
    csrf = _get_csrf(client)
    client.post(
        "/suppression-rules",
        data={
            "csrf_token": csrf,
            "rule_name": "Created via form",
            "match_field": "src_ip",
            "match_value": "172.16.0.99",
            "applies_to": "model_alert",
        },
        follow_redirects=False,
    )
    # Now verify the rule appears
    get_response = client.get("/suppression-rules")
    assert get_response.status_code == 200
    body = get_response.text
    assert "Created via form" in body, "Newly created rule not found after POST add"
    assert "172.16.0.99" in body


def test_suppression_rules_post_add_rejects_invalid_csrf(tmp_path: Path) -> None:
    """POST /suppression-rules with invalid CSRF must be rejected (400 or 403)."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.post(
        "/suppression-rules",
        data={
            "csrf_token": "invalid-token",
            "rule_name": "Bad rule",
            "match_field": "src_ip",
            "match_value": "10.0.0.1",
            "applies_to": "model_alert",
        },
        follow_redirects=False,
    )
    assert response.status_code in (400, 403), (
        f"Expected 400 or 403 for invalid CSRF, got {response.status_code}"
    )


def test_suppression_rules_post_add_rejects_missing_csrf(tmp_path: Path) -> None:
    """POST /suppression-rules with no CSRF token must be rejected."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.post(
        "/suppression-rules",
        data={
            "csrf_token": "",
            "rule_name": "Bad rule",
            "match_field": "src_ip",
            "match_value": "10.0.0.2",
        },
        follow_redirects=False,
    )
    assert response.status_code in (400, 403), (
        f"Expected 400 or 403 for missing CSRF, got {response.status_code}"
    )


# ── POST /suppression-rules/{id}/deactivate ───────────────────────────────────

def test_suppression_rule_deactivate_redirects_with_valid_csrf(tmp_path: Path) -> None:
    """POST /suppression-rules/{id}/deactivate with valid CSRF → 303 redirect."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    csrf = _get_csrf(client)

    # Get the rule id from the page
    get_resp = client.get("/suppression-rules")
    body = get_resp.text

    # Extract first rule id from a deactivate form action
    match = re.search(r'/suppression-rules/(\d+)/deactivate', body)
    assert match, "Could not find a deactivate form action in suppression-rules page"
    rule_id = match.group(1)

    response = client.post(
        f"/suppression-rules/{rule_id}/deactivate",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"Expected 303 redirect but got {response.status_code}"
    )
    assert response.headers["location"] == "/suppression-rules"


def test_suppression_rule_deactivate_rule_disappears_after_deactivation(tmp_path: Path) -> None:
    """After deactivation, the rule no longer appears in the active rules list."""
    client = _build_suppression_test_app(tmp_path, seed_rules=False)
    _login(client)
    csrf = _get_csrf(client)

    # Create a rule first
    client.post(
        "/suppression-rules",
        data={
            "csrf_token": csrf,
            "rule_name": "Soon to be deactivated",
            "match_field": "src_ip",
            "match_value": "10.55.0.55",
            "applies_to": "model_alert",
        },
        follow_redirects=False,
    )

    # Get rule id from page
    csrf = _get_csrf(client)
    get_resp = client.get("/suppression-rules")
    body = get_resp.text
    assert "Soon to be deactivated" in body

    match = re.search(r'/suppression-rules/(\d+)/deactivate', body)
    assert match, "Could not find deactivate link for newly created rule"
    rule_id = match.group(1)

    # Deactivate
    client.post(
        f"/suppression-rules/{rule_id}/deactivate",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )

    # Verify it's gone
    after_resp = client.get("/suppression-rules")
    assert after_resp.status_code == 200
    after_body = after_resp.text
    assert "Soon to be deactivated" not in after_body, (
        "Deactivated rule should no longer appear in active rules list"
    )


def test_suppression_rule_deactivate_returns_404_for_unknown_id(tmp_path: Path) -> None:
    """POST /suppression-rules/99999/deactivate with valid CSRF → 404."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    csrf = _get_csrf(client)
    response = client.post(
        "/suppression-rules/99999/deactivate",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 404, (
        f"Expected 404 for unknown rule_id, got {response.status_code}"
    )


def test_suppression_rule_deactivate_rejects_invalid_csrf(tmp_path: Path) -> None:
    """POST /suppression-rules/{id}/deactivate with invalid CSRF → 400 or 403."""
    client = _build_suppression_test_app(tmp_path)
    _login(client)
    response = client.post(
        "/suppression-rules/1/deactivate",
        data={"csrf_token": "bad-token"},
        follow_redirects=False,
    )
    assert response.status_code in (400, 403), (
        f"Expected 400 or 403 for invalid CSRF, got {response.status_code}"
    )
