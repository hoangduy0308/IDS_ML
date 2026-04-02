from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
from ids.console.alerts import transition_alert_status  # noqa: E402
from ids.console.auth import ensure_admin_user  # noqa: E402
from ids.console.config import load_operator_console_config  # noqa: E402
from ids.console.db import open_existing_operator_store, OperatorStore  # noqa: E402
from ids.console.migrations import migrate_operator_store  # noqa: E402
from ids.console.reporting import (  # noqa: E402
    build_report_bundle,
    build_report_rollup,
    export_alert_rows,
    export_anomaly_rows,
    export_summary_rows,
)
from ids.console.web import create_operator_console_web_app  # noqa: E402


def _new_store(tmp_path: Path) -> OperatorStore:
    return OperatorStore.open(tmp_path / "operator_console.db")


def _seed_alert(store: OperatorStore, *, source_event_id: str, src_ip: str, severity: str = "high") -> int:
    return store.upsert_alert(
        source_event_id=source_event_id,
        event_ts="2026-03-28T16:00:00+00:00",
        severity=severity,
        src_ip=src_ip,
        dst_ip="192.168.10.2",
        src_port=443,
        dst_port=52222,
        protocol="tcp",
        fingerprint=f"fp-{source_event_id}",
        payload={"event_type": "model_prediction", "src_ip": src_ip, "score": 0.95},
    )


def test_export_alert_rows_supports_filters_and_suppression(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        alert_1 = _seed_alert(store, source_event_id="alert-001", src_ip="10.2.0.1", severity="high")
        alert_2 = _seed_alert(store, source_event_id="alert-002", src_ip="10.2.0.2", severity="medium")
        transition_alert_status(store, alert_id=alert_1, to_status="investigating")
        transition_alert_status(store, alert_id=alert_2, to_status="resolved")
        store.create_suppression_rule(
            rule_name="Suppress scanner",
            match_field="src_ip",
            match_value="10.2.0.1",
            applies_to="model_alert",
        )

        investigating = export_alert_rows(store, triage_status="investigating", include_suppressed=False)
        assert investigating == []

        all_investigating = export_alert_rows(store, triage_status="investigating", include_suppressed=True)
        assert len(all_investigating) == 1
        assert all_investigating[0]["source_event_id"] == "alert-001"
        assert all_investigating[0]["suppressed"] is True

        resolved = export_alert_rows(store, triage_status="resolved", include_suppressed=False)
        assert len(resolved) == 1
        assert resolved[0]["source_event_id"] == "alert-002"
    finally:
        store.close()


def test_export_anomaly_rows_default_to_redaction_safe_output(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        store.store_anomaly(
            source_event_id="anom-001",
            event_ts="2026-03-28T16:01:00+00:00",
            anomaly_type="schema_anomaly",
            reason="missing feature",
            redacted_summary="payload redacted",
            payload={"raw_payload": {"secret": "do-not-export"}, "reason": "missing feature"},
        )

        redacted = export_anomaly_rows(store, include_payload=False)
        assert len(redacted) == 1
        assert "payload" not in redacted[0]
        assert redacted[0]["redacted_summary"] == "payload redacted"

        with_payload = export_anomaly_rows(store, include_payload=True)
        assert len(with_payload) == 1
        assert with_payload[0]["payload"]["reason"] == "missing feature"
    finally:
        store.close()


def test_report_bundle_and_rollup_cover_alerts_anomalies_and_summaries(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        alert_id = _seed_alert(store, source_event_id="alert-003", src_ip="10.2.0.3", severity="critical")
        transition_alert_status(store, alert_id=alert_id, to_status="acknowledged")

        store.store_anomaly(
            source_event_id="anom-002",
            event_ts="2026-03-28T16:02:00+00:00",
            anomaly_type="schema_anomaly",
            reason="bad type",
            redacted_summary="schema mismatch",
            payload={"reason": "bad type"},
        )
        store.store_summary(
            summary_ts="2026-03-28T16:03:00+00:00",
            payload={"window_seconds": 60, "alert_count": 1, "anomaly_count": 1},
        )

        bundle = build_report_bundle(store)
        assert len(bundle["alerts"]) == 1
        assert len(bundle["anomalies"]) == 1
        assert len(bundle["summaries"]) == 1

        summaries = export_summary_rows(store)
        assert summaries[0]["payload"]["alert_count"] == 1

        rollup = build_report_rollup(bundle)
        assert rollup["alerts_total"] == 1
        assert rollup["alerts_by_status"]["acknowledged"] == 1
        assert rollup["alerts_by_severity"]["critical"] == 1
        assert rollup["anomalies_total"] == 1
        assert rollup["summaries_total"] == 1
        assert rollup["latest_summary_ts"] == "2026-03-28T16:03:00+00:00"
    finally:
        store.close()


# ── /reports route tests (TDD for bead ids_ml_new-6g24) ──────────────────────

def _build_reports_test_app(tmp_path: Path) -> TestClient:
    """Build test app with seeded data for /reports route tests."""
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "reports-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="secret")

        # Seed 3 alerts with different statuses
        for i, (src, sev, ts) in enumerate([
            ("10.1.0.1", "critical", "acknowledged"),
            ("10.1.0.2", "high", "resolved"),
            ("10.1.0.3", "medium", "new"),
        ]):
            aid = store.upsert_alert(
                source_event_id=f"rpt-alert-{i:03d}",
                event_ts=f"2026-03-29T{10 + i:02d}:00:00+00:00",
                severity=sev,
                src_ip=src,
                dst_ip="192.168.100.1",
                src_port=1000 + i,
                dst_port=443,
                protocol="tcp",
                fingerprint=f"fp-rpt-{i:03d}",
                payload={"score": 0.9},
            )
            if ts != "new":
                transition_alert_status(store, alert_id=aid, to_status=ts, changed_by="admin")

        # Seed 2 anomalies
        for j in range(2):
            store.store_anomaly(
                source_event_id=f"rpt-anom-{j:03d}",
                event_ts=f"2026-03-29T{12 + j:02d}:01:00+00:00",
                anomaly_type="schema_anomaly",
                reason=f"report anomaly {j}",
                redacted_summary=f"rpt summary {j}",
                payload={"index": j},
            )

        # Seed a summary
        store.store_summary(
            summary_ts="2026-03-29T14:00:00+00:00",
            payload={
                "window_seconds": 60,
                "alert_count": 3,
                "anomaly_count": 2,
                "active_bundle": {
                    "active_bundle_name": "bundle-rpt",
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


def _login_reports(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Login failed: {response.status_code}"


def test_reports_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    """Unauthenticated GET /reports must redirect to /login."""
    client = _build_reports_test_app(tmp_path)
    response = client.get("/reports", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_reports_returns_200_when_authenticated(tmp_path: Path) -> None:
    """GET /reports returns 200 (not 501) after authentication."""
    client = _build_reports_test_app(tmp_path)
    _login_reports(client)
    response = client.get("/reports")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Ensure the /reports stub is replaced with a real handler."
    )


def test_reports_response_is_html(tmp_path: Path) -> None:
    client = _build_reports_test_app(tmp_path)
    _login_reports(client)
    response = client.get("/reports")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_reports_extends_base_template(tmp_path: Path) -> None:
    client = _build_reports_test_app(tmp_path)
    _login_reports(client)
    response = client.get("/reports")
    assert response.status_code == 200
    body = response.text
    assert "shell" in body
    assert "app-sidebar" in body


def test_reports_page_title_present(tmp_path: Path) -> None:
    client = _build_reports_test_app(tmp_path)
    _login_reports(client)
    response = client.get("/reports")
    assert response.status_code == 200
    body = response.text
    assert any(marker in body for marker in ("Reports", "Báo cáo"))


def test_reports_shows_rollup_totals(tmp_path: Path) -> None:
    """Reports page must render the rollup totals (alert count, anomaly count)."""
    client = _build_reports_test_app(tmp_path)
    _login_reports(client)
    response = client.get("/reports")
    assert response.status_code == 200
    body = response.text
    # Rollup has alerts_total=3, anomalies_total=2
    assert "3" in body
    assert "2" in body


def test_reports_shows_status_breakdown(tmp_path: Path) -> None:
    """Reports page must render alerts_by_status breakdown."""
    client = _build_reports_test_app(tmp_path)
    _login_reports(client)
    response = client.get("/reports")
    assert response.status_code == 200
    body = response.text
    assert any(s in body.lower() for s in ("acknowledged", "resolved", "new"))


def test_reports_shows_severity_breakdown(tmp_path: Path) -> None:
    """Reports page must render alerts_by_severity breakdown."""
    client = _build_reports_test_app(tmp_path)
    _login_reports(client)
    response = client.get("/reports")
    assert response.status_code == 200
    body = response.text
    assert any(s in body.lower() for s in ("critical", "high", "medium"))


def test_reports_shows_summaries_section(tmp_path: Path) -> None:
    """Reports page must render recent summaries."""
    client = _build_reports_test_app(tmp_path)
    _login_reports(client)
    response = client.get("/reports")
    assert response.status_code == 200
    body = response.text
    # The seeded summary timestamp should appear
    assert "2026-03-29" in body
