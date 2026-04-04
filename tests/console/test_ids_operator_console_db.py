from __future__ import annotations

from pathlib import Path
import json

import pytest

from ids.console.db import (  # noqa: E402
    ALLOWED_SETTING_KEYS,
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
        "console_settings",
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
    assert current.schema_version == 3
    assert current.runtime_ready is False


def test_deactivate_suppression_rule_returns_true_and_sets_inactive(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        rule_id = store.create_suppression_rule(
            rule_name="Suppress scanner",
            match_field="src_ip",
            match_value="10.0.0.1",
        )
        result = store.deactivate_suppression_rule(rule_id=rule_id)
        assert result is True

        row = store._connection.execute(
            "SELECT is_active FROM suppression_rules WHERE id = ?",
            (rule_id,),
        ).fetchone()
        assert row is not None
        assert row["is_active"] == 0
    finally:
        store.close()


def test_deactivate_suppression_rule_returns_false_when_already_inactive(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        rule_id = store.create_suppression_rule(
            rule_name="Suppress scanner",
            match_field="src_ip",
            match_value="10.0.0.2",
        )
        first = store.deactivate_suppression_rule(rule_id=rule_id)
        assert first is True

        second = store.deactivate_suppression_rule(rule_id=rule_id)
        assert second is False
    finally:
        store.close()


def test_deactivated_rule_absent_from_list_active_suppression_rules(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        rule_id = store.create_suppression_rule(
            rule_name="Suppress scanner",
            match_field="src_ip",
            match_value="10.0.0.3",
        )
        active_before = store.list_active_suppression_rules()
        assert any(r["id"] == rule_id for r in active_before)

        store.deactivate_suppression_rule(rule_id=rule_id)

        active_after = store.list_active_suppression_rules()
        assert not any(r["id"] == rule_id for r in active_after)
    finally:
        store.close()


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


def test_migration_v2_to_v3_adds_console_settings_table(tmp_path: Path) -> None:
    """Create a v2 database (no console_settings table), migrate to v3, verify table exists."""
    db_path = tmp_path / "operator_console.db"
    connection = connect_operator_db(db_path)
    try:
        # Manually create a v2 schema: all legacy tables + schema_metadata stamped v2
        # but WITHOUT console_settings table.
        connection.executescript("""
            CREATE TABLE sensors (sensor_id TEXT PRIMARY KEY, host_label TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE ingest_offsets (stream_name TEXT PRIMARY KEY, sensor_id TEXT NOT NULL, source_path TEXT NOT NULL, file_inode INTEGER, file_device INTEGER, file_size INTEGER, offset_bytes INTEGER NOT NULL DEFAULT 0, last_record_ts TEXT, updated_at TEXT NOT NULL);
            CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, sensor_id TEXT NOT NULL, source_event_id TEXT, event_ts TEXT NOT NULL, severity TEXT, src_ip TEXT, dst_ip TEXT, src_port INTEGER, dst_port INTEGER, protocol TEXT, fingerprint TEXT, payload_json TEXT NOT NULL, triage_status TEXT NOT NULL DEFAULT 'new', triage_updated_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(sensor_id, source_event_id));
            CREATE TABLE anomalies (id INTEGER PRIMARY KEY AUTOINCREMENT, sensor_id TEXT NOT NULL, source_event_id TEXT, event_ts TEXT NOT NULL, anomaly_type TEXT NOT NULL, reason TEXT, redacted_summary TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE summaries (id INTEGER PRIMARY KEY AUTOINCREMENT, sensor_id TEXT NOT NULL, summary_ts TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(sensor_id, summary_ts));
            CREATE TABLE alert_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id INTEGER NOT NULL, note_text TEXT NOT NULL, author TEXT NOT NULL DEFAULT 'admin', created_at TEXT NOT NULL);
            CREATE TABLE alert_status_history (id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id INTEGER NOT NULL, from_status TEXT, to_status TEXT NOT NULL, changed_by TEXT NOT NULL DEFAULT 'admin', changed_at TEXT NOT NULL);
            CREATE TABLE suppression_rules (id INTEGER PRIMARY KEY AUTOINCREMENT, sensor_id TEXT NOT NULL, rule_name TEXT NOT NULL, match_field TEXT NOT NULL, match_value TEXT NOT NULL, applies_to TEXT NOT NULL DEFAULT 'model_alert', is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE admin_users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_login_at TEXT);
            CREATE TABLE admin_sessions (session_id TEXT PRIMARY KEY, username TEXT NOT NULL, csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE notification_deliveries (id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id INTEGER, channel TEXT NOT NULL, target TEXT NOT NULL, dedupe_key TEXT, payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempt_count INTEGER NOT NULL DEFAULT 0, last_attempt_at TEXT, next_attempt_at TEXT, last_error TEXT, provider_message_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(channel, target, dedupe_key));
            CREATE TABLE schema_metadata (schema_family TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, updated_at TEXT NOT NULL);
            INSERT INTO schema_metadata (schema_family, schema_version, updated_at) VALUES ('ids_operator_console', 2, '2026-04-01T00:00:00Z');
        """)
        # Verify: no console_settings table yet
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        assert "console_settings" not in tables
    finally:
        connection.close()

    # Run inspect — should detect needs-migration
    pre = inspect_operator_store(db_path)
    assert pre.schema_state == "needs-migration"
    assert pre.schema_version == 2

    # Run migration
    post = migrate_operator_store(db_path)
    assert post.schema_state == "current"
    assert post.schema_version == 3

    # Verify console_settings table exists and data is intact
    connection = connect_operator_db(db_path)
    try:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        assert "console_settings" in tables
    finally:
        connection.close()


def test_fresh_bootstrap_creates_console_settings_at_v3(tmp_path: Path) -> None:
    """Fresh DB via migrate --allow-bootstrap should create console_settings and stamp v3."""
    db_path = tmp_path / "operator_console.db"
    result = migrate_operator_store(db_path, allow_bootstrap=True)
    assert result.schema_state == "current"
    assert result.schema_version == 3

    connection = connect_operator_db(db_path)
    try:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        assert "console_settings" in tables
    finally:
        connection.close()


def test_migration_v2_to_v3_is_idempotent(tmp_path: Path) -> None:
    """Running migrate twice on a v3 DB should not fail."""
    db_path = tmp_path / "operator_console.db"
    migrate_operator_store(db_path, allow_bootstrap=True)
    result = migrate_operator_store(db_path)
    assert result.schema_state == "current"
    assert result.schema_version == 3


def test_get_setting_returns_none_for_nonexistent_key(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        assert store.get_setting("nonexistent_key") is None
    finally:
        store.close()


def test_set_setting_stores_and_get_setting_retrieves(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        store.set_setting("telegram_bot_token", "123:ABCDEF")
        assert store.get_setting("telegram_bot_token") == "123:ABCDEF"
    finally:
        store.close()


def test_set_setting_upserts_on_conflict(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        store.set_setting("telegram_bot_token", "old_token")
        store.set_setting("telegram_bot_token", "new_token")
        assert store.get_setting("telegram_bot_token") == "new_token"
    finally:
        store.close()


def test_set_setting_stores_empty_string(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        store.set_setting("telegram_bot_token", "")
        assert store.get_setting("telegram_bot_token") == ""
    finally:
        store.close()


def test_set_setting_updates_updated_at_on_upsert(tmp_path: Path) -> None:
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        store.set_setting("telegram_bot_token", "value1")
        row1 = store._connection.execute(
            "SELECT updated_at FROM console_settings WHERE key = ?",
            ("telegram_bot_token",),
        ).fetchone()
        ts1 = row1["updated_at"]

        store.set_setting("telegram_bot_token", "value2")
        row2 = store._connection.execute(
            "SELECT updated_at FROM console_settings WHERE key = ?",
            ("telegram_bot_token",),
        ).fetchone()
        ts2 = row2["updated_at"]

        assert ts2 >= ts1
    finally:
        store.close()


def test_set_setting_rejects_unknown_key(tmp_path: Path) -> None:
    """set_setting must raise ValueError for keys not in ALLOWED_SETTING_KEYS."""
    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        with pytest.raises(ValueError, match="Unknown setting key"):
            store.set_setting("bad_key", "val")
    finally:
        store.close()
