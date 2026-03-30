from __future__ import annotations

from pathlib import Path
import json

from ids.console.db import (  # noqa: E402
    OperatorStore,
    bootstrap_operator_store,
    connect_operator_db,
)
from ids.console.migrations import inspect_operator_store, migrate_operator_store  # noqa: E402


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


def test_inspect_operator_store_reports_legacy_and_current_states(tmp_path: Path) -> None:
    db_path = tmp_path / "operator_console.db"

    legacy_store = OperatorStore.open(db_path)
    legacy_store.close()

    legacy = inspect_operator_store(db_path)
    assert legacy.schema_state == "legacy-v1"
    assert legacy.runtime_ready is False

    current = migrate_operator_store(db_path)
    assert current.schema_state == "current"
    assert current.schema_version == 2
    assert current.runtime_ready is False


def test_notification_delivery_summary_and_redrive_preserve_explicit_recovery(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        alert_id = store.upsert_alert(
            source_event_id="alert-redrive",
            event_ts="2026-03-28T14:40:00+00:00",
            severity="high",
            src_ip="10.0.0.8",
            dst_ip="192.168.1.10",
            payload={"event_type": "model_prediction", "score": 0.93},
        )
        delivery_id = store.save_notification_delivery(
            alert_id=alert_id,
            channel="telegram",
            target="ops-room",
            dedupe_key="alert-redrive",
            payload={"text": "Alert alert-redrive"},
            status="pending",
        )
        store.mark_notification_attempt(
            delivery_id=delivery_id,
            status="failed",
            last_error="telegram outage",
        )

        summary_before = store.get_notification_delivery_summary(channel="telegram")
        assert summary_before["failed_count"] == 1
        assert summary_before["due_count"] == 0
        assert summary_before["last_error"] is not None
        assert summary_before["last_error"]["last_error"] == "telegram outage"

        redriven = store.redrive_failed_notification_deliveries(channel="telegram")
        redriven_delivery = store.get_notification_delivery(delivery_id)
        summary_after = store.get_notification_delivery_summary(channel="telegram")

        assert redriven == 1
        assert redriven_delivery is not None
        assert redriven_delivery["status"] == "pending"
        assert redriven_delivery["attempt_count"] == 0
        assert redriven_delivery["last_error"] is None
        assert summary_after["pending_count"] == 1
        assert summary_after["failed_count"] == 0
        assert summary_after["due_count"] == 1
        assert summary_after["last_error"] is None
    finally:
        store.close()
