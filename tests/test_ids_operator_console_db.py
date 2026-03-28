from __future__ import annotations

from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console.db import (  # noqa: E402
    OperatorStore,
    bootstrap_operator_store,
    connect_operator_db,
)


def test_bootstrap_operator_store_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "operator_console.db"
    connection = connect_operator_db(db_path)
    try:
        bootstrap_operator_store(connection)
        bootstrap_operator_store(connection)

        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    finally:
        connection.close()

    assert {
        "sensors",
        "ingest_offsets",
        "alerts",
        "anomalies",
        "summaries",
        "alert_notes",
        "alert_status_history",
        "suppression_rules",
        "admin_users",
        "admin_sessions",
        "notification_deliveries",
    }.issubset(tables)


def test_operator_store_primitives_cover_console_state(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        offset = store.record_ingest_offset(
            stream_name="alerts",
            source_path=tmp_path / "ids_live_alerts.jsonl",
            file_inode=101,
            file_device=55,
            file_size=2048,
            offset_bytes=1500,
            last_record_ts="2026-03-28T14:35:00+00:00",
        )
        assert offset is not None
        assert offset["offset_bytes"] == 1500
        assert offset["stream_name"] == "alerts"

        alert_id = store.upsert_alert(
            source_event_id="alert-001",
            event_ts="2026-03-28T14:36:00+00:00",
            severity="high",
            src_ip="10.0.0.5",
            dst_ip="192.168.1.9",
            src_port=443,
            dst_port=51111,
            protocol="tcp",
            fingerprint="fp-alert-001",
            payload={"event_type": "model_prediction", "score": 0.98},
        )
        assert alert_id > 0

        note_id = store.add_alert_note(alert_id=alert_id, note_text="Investigating source host")
        assert note_id > 0

        updated_alert = store.update_alert_status(alert_id=alert_id, to_status="investigating")
        assert updated_alert["triage_status"] == "investigating"

        status_history = store.list_alert_status_history(alert_id=alert_id)
        assert len(status_history) == 1
        assert status_history[0]["from_status"] == "new"
        assert status_history[0]["to_status"] == "investigating"

        notes = store.list_alert_notes(alert_id=alert_id)
        assert len(notes) == 1
        assert notes[0]["note_text"] == "Investigating source host"

        anomaly_id = store.store_anomaly(
            event_ts="2026-03-28T14:37:00+00:00",
            anomaly_type="schema_anomaly",
            reason="missing feature",
            redacted_summary="invalid packet feature set",
            payload={"anomaly_type": "schema_anomaly", "reason": "invalid_schema"},
            source_event_id="anom-001",
        )
        assert anomaly_id > 0
        anomalies = store.list_anomalies(limit=10)
        assert len(anomalies) == 1
        assert anomalies[0]["anomaly_type"] == "schema_anomaly"

        summary_id = store.store_summary(
            summary_ts="2026-03-28T14:38:00+00:00",
            payload={"window_seconds": 60, "alert_count": 1},
        )
        summary_id_again = store.store_summary(
            summary_ts="2026-03-28T14:38:00+00:00",
            payload={"window_seconds": 60, "alert_count": 2},
        )
        assert summary_id == summary_id_again
        summaries = store.list_recent_summaries(limit=5)
        assert len(summaries) == 1
        assert json.loads(summaries[0]["payload_json"])["alert_count"] == 2

        rule_id = store.create_suppression_rule(
            rule_name="Suppress trusted scanner",
            match_field="src_ip",
            match_value="10.0.0.5",
            applies_to="model_alert",
        )
        assert rule_id > 0
        suppression = store.list_active_suppression_rules()
        assert len(suppression) == 1
        assert suppression[0]["match_value"] == "10.0.0.5"

        admin = store.upsert_admin_user(username="admin", password_hash="pbkdf2$hash")
        assert admin["username"] == "admin"

        session = store.upsert_admin_session(
            session_id="session-001",
            username="admin",
            csrf_token="csrf-001",
            expires_at="2026-03-29T00:00:00+00:00",
        )
        assert session["session_id"] == "session-001"
        assert store.get_admin_session("session-001") is not None

        delivery_id = store.save_notification_delivery(
            alert_id=alert_id,
            channel="telegram",
            target="ops-room",
            dedupe_key="alert-001",
            payload={"text": "Alert alert-001"},
            status="pending",
        )
        pending = store.list_pending_notification_deliveries(channel="telegram")
        assert len(pending) == 1
        assert pending[0]["id"] == delivery_id

        attempted = store.mark_notification_attempt(
            delivery_id=delivery_id,
            status="sent",
            provider_message_id="telegram-12345",
        )
        assert attempted["status"] == "sent"
        assert attempted["attempt_count"] == 1
        assert store.list_pending_notification_deliveries(channel="telegram") == []
    finally:
        store.close()
