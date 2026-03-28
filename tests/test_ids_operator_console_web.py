from __future__ import annotations

from pathlib import Path
import sys

from starlette.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console.alerts import add_investigation_note, transition_alert_status  # noqa: E402
from scripts.ids_operator_console.auth import ensure_admin_user  # noqa: E402
from scripts.ids_operator_console.config import load_operator_console_config  # noqa: E402
from scripts.ids_operator_console.db import OperatorStore  # noqa: E402
from scripts.ids_operator_console.web import create_operator_console_web_app  # noqa: E402


def _build_test_app(tmp_path: Path) -> tuple[TestClient, OperatorStore, int]:
    env = {
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "web-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "scripts/ids_operator_console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "scripts/ids_operator_console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    store = OperatorStore.open(config.database_path)

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
        payload={"window_seconds": 60, "alert_count": 1, "anomaly_count": 1},
    )

    app = create_operator_console_web_app(config, store=store)
    client = TestClient(app)
    return client, store, alert_id


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "correct-password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_dashboard_redirects_to_login_when_unauthenticated(tmp_path: Path) -> None:
    client, store, _ = _build_test_app(tmp_path)
    try:
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
    finally:
        store.close()


def test_dashboard_renders_combined_console_with_health_and_anomaly_lane(tmp_path: Path) -> None:
    client, store, _ = _build_test_app(tmp_path)
    try:
        _login(client)
        response = client.get("/dashboard")
        assert response.status_code == 200
        body = response.text
        assert "Combined Console" in body
        assert "Sensor Health" in body
        assert "Anomaly Lane" in body
        assert "schema_anomaly" in body
    finally:
        store.close()


def test_alert_detail_and_sensor_aware_json_endpoints(tmp_path: Path) -> None:
    client, store, alert_id = _build_test_app(tmp_path)
    try:
        _login(client)

        detail = client.get(f"/alerts/{alert_id}")
        assert detail.status_code == 200
        body = detail.text
        assert f"Alert {alert_id}" in body
        assert "Correlated with known scanner host" in body
        assert "acknowledged" in body

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
    finally:
        store.close()
