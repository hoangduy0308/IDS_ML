from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json
import sqlite3


DEFAULT_SENSOR_ID = "sensor-local"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _encode_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def connect_operator_db(database_path: Path) -> sqlite3.Connection:
    resolved = Path(database_path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(resolved))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def bootstrap_operator_store(connection: sqlite3.Connection) -> None:
    schema_sql = """
    CREATE TABLE IF NOT EXISTS sensors (
        sensor_id TEXT PRIMARY KEY,
        host_label TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS ingest_offsets (
        stream_name TEXT PRIMARY KEY,
        sensor_id TEXT NOT NULL,
        source_path TEXT NOT NULL,
        file_inode INTEGER,
        file_device INTEGER,
        file_size INTEGER,
        offset_bytes INTEGER NOT NULL DEFAULT 0,
        last_record_ts TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT NOT NULL,
        source_event_id TEXT,
        event_ts TEXT NOT NULL,
        severity TEXT,
        src_ip TEXT,
        dst_ip TEXT,
        src_port INTEGER,
        dst_port INTEGER,
        protocol TEXT,
        fingerprint TEXT,
        payload_json TEXT NOT NULL,
        triage_status TEXT NOT NULL DEFAULT 'new',
        triage_updated_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE,
        UNIQUE(sensor_id, source_event_id)
    );

    CREATE TABLE IF NOT EXISTS anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT NOT NULL,
        source_event_id TEXT,
        event_ts TEXT NOT NULL,
        anomaly_type TEXT NOT NULL,
        reason TEXT,
        redacted_summary TEXT,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT NOT NULL,
        summary_ts TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE,
        UNIQUE(sensor_id, summary_ts)
    );

    CREATE TABLE IF NOT EXISTS alert_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER NOT NULL,
        note_text TEXT NOT NULL,
        author TEXT NOT NULL DEFAULT 'admin',
        created_at TEXT NOT NULL,
        FOREIGN KEY(alert_id) REFERENCES alerts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS alert_status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER NOT NULL,
        from_status TEXT,
        to_status TEXT NOT NULL,
        changed_by TEXT NOT NULL DEFAULT 'admin',
        changed_at TEXT NOT NULL,
        FOREIGN KEY(alert_id) REFERENCES alerts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS suppression_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT NOT NULL,
        rule_name TEXT NOT NULL,
        match_field TEXT NOT NULL,
        match_value TEXT NOT NULL,
        applies_to TEXT NOT NULL DEFAULT 'model_alert',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_login_at TEXT
    );

    CREATE TABLE IF NOT EXISTS admin_sessions (
        session_id TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        csrf_token TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(username) REFERENCES admin_users(username) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS notification_deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER,
        channel TEXT NOT NULL,
        target TEXT NOT NULL,
        dedupe_key TEXT,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_attempt_at TEXT,
        next_attempt_at TEXT,
        last_error TEXT,
        provider_message_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(alert_id) REFERENCES alerts(id) ON DELETE SET NULL,
        UNIQUE(channel, target, dedupe_key)
    );

    CREATE INDEX IF NOT EXISTS idx_alerts_sensor_event_ts ON alerts(sensor_id, event_ts DESC);
    CREATE INDEX IF NOT EXISTS idx_alerts_triage_status ON alerts(triage_status);
    CREATE INDEX IF NOT EXISTS idx_anomalies_sensor_event_ts ON anomalies(sensor_id, event_ts DESC);
    CREATE INDEX IF NOT EXISTS idx_summaries_sensor_summary_ts ON summaries(sensor_id, summary_ts DESC);
    CREATE INDEX IF NOT EXISTS idx_notification_status_next_attempt ON notification_deliveries(status, next_attempt_at);
    CREATE INDEX IF NOT EXISTS idx_status_history_alert_changed_at ON alert_status_history(alert_id, changed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_notes_alert_created_at ON alert_notes(alert_id, created_at DESC);
    """
    with connection:
        connection.executescript(schema_sql)


class OperatorStore:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    @classmethod
    def open(cls, database_path: Path) -> "OperatorStore":
        connection = connect_operator_db(database_path)
        bootstrap_operator_store(connection)
        return cls(connection)

    def close(self) -> None:
        self._connection.close()

    def upsert_sensor(self, *, sensor_id: str = DEFAULT_SENSOR_ID, host_label: str | None = None) -> dict[str, Any]:
        now = _utc_now_iso()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO sensors (sensor_id, host_label, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sensor_id) DO UPDATE SET
                    host_label = COALESCE(excluded.host_label, sensors.host_label),
                    updated_at = excluded.updated_at
                """,
                (sensor_id, host_label, now, now),
            )
        return self.get_sensor(sensor_id)

    def get_sensor(self, sensor_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM sensors WHERE sensor_id = ?",
            (sensor_id,),
        ).fetchone()
        return _row_to_dict(row)

    def record_ingest_offset(
        self,
        *,
        stream_name: str,
        source_path: Path,
        file_inode: int | None,
        file_device: int | None,
        file_size: int | None,
        offset_bytes: int,
        last_record_ts: str | None,
        sensor_id: str = DEFAULT_SENSOR_ID,
    ) -> dict[str, Any]:
        if offset_bytes < 0:
            raise ValueError("offset_bytes must be >= 0")
        self.upsert_sensor(sensor_id=sensor_id)
        now = _utc_now_iso()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO ingest_offsets (
                    stream_name,
                    sensor_id,
                    source_path,
                    file_inode,
                    file_device,
                    file_size,
                    offset_bytes,
                    last_record_ts,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stream_name) DO UPDATE SET
                    sensor_id = excluded.sensor_id,
                    source_path = excluded.source_path,
                    file_inode = excluded.file_inode,
                    file_device = excluded.file_device,
                    file_size = excluded.file_size,
                    offset_bytes = excluded.offset_bytes,
                    last_record_ts = excluded.last_record_ts,
                    updated_at = excluded.updated_at
                """,
                (
                    stream_name,
                    sensor_id,
                    str(Path(source_path).resolve()),
                    file_inode,
                    file_device,
                    file_size,
                    offset_bytes,
                    last_record_ts,
                    now,
                ),
            )
        return self.get_ingest_offset(stream_name)

    def get_ingest_offset(self, stream_name: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM ingest_offsets WHERE stream_name = ?",
            (stream_name,),
        ).fetchone()
        return _row_to_dict(row)

    def upsert_alert(
        self,
        *,
        event_ts: str,
        payload: Mapping[str, Any],
        sensor_id: str = DEFAULT_SENSOR_ID,
        source_event_id: str | None = None,
        severity: str | None = None,
        src_ip: str | None = None,
        dst_ip: str | None = None,
        src_port: int | None = None,
        dst_port: int | None = None,
        protocol: str | None = None,
        fingerprint: str | None = None,
    ) -> int:
        self.upsert_sensor(sensor_id=sensor_id)
        now = _utc_now_iso()
        payload_json = _encode_payload(payload)

        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO alerts (
                    sensor_id,
                    source_event_id,
                    event_ts,
                    severity,
                    src_ip,
                    dst_ip,
                    src_port,
                    dst_port,
                    protocol,
                    fingerprint,
                    payload_json,
                    triage_status,
                    triage_updated_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
                ON CONFLICT(sensor_id, source_event_id) DO UPDATE SET
                    event_ts = excluded.event_ts,
                    severity = excluded.severity,
                    src_ip = excluded.src_ip,
                    dst_ip = excluded.dst_ip,
                    src_port = excluded.src_port,
                    dst_port = excluded.dst_port,
                    protocol = excluded.protocol,
                    fingerprint = excluded.fingerprint,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    sensor_id,
                    source_event_id,
                    event_ts,
                    severity,
                    src_ip,
                    dst_ip,
                    src_port,
                    dst_port,
                    protocol,
                    fingerprint,
                    payload_json,
                    now,
                    now,
                    now,
                ),
            )

            if source_event_id is None:
                return int(cursor.lastrowid)

            row = self._connection.execute(
                """
                SELECT id FROM alerts
                WHERE sensor_id = ? AND source_event_id = ?
                """,
                (sensor_id, source_event_id),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to resolve upserted alert id")
        return int(row["id"])

    def list_alerts(self, *, limit: int = 100, triage_status: str | None = None) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if triage_status is None:
            rows = self._connection.execute(
                "SELECT * FROM alerts ORDER BY event_ts DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT * FROM alerts
                WHERE triage_status = ?
                ORDER BY event_ts DESC, id DESC
                LIMIT ?
                """,
                (triage_status, limit),
            ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def update_alert_status(self, *, alert_id: int, to_status: str, changed_by: str = "admin") -> dict[str, Any]:
        if not to_status.strip():
            raise ValueError("to_status must not be blank")
        now = _utc_now_iso()
        existing = self._connection.execute(
            "SELECT triage_status FROM alerts WHERE id = ?",
            (alert_id,),
        ).fetchone()
        if existing is None:
            raise KeyError(f"alert {alert_id} not found")

        from_status = str(existing["triage_status"])
        with self._connection:
            self._connection.execute(
                """
                UPDATE alerts
                SET triage_status = ?, triage_updated_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (to_status, now, now, alert_id),
            )
            self._connection.execute(
                """
                INSERT INTO alert_status_history (alert_id, from_status, to_status, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (alert_id, from_status, to_status, changed_by, now),
            )
        row = self._connection.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        result = _row_to_dict(row)
        if result is None:
            raise RuntimeError("Alert disappeared after status update")
        return result

    def list_alert_status_history(self, *, alert_id: int) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT * FROM alert_status_history
            WHERE alert_id = ?
            ORDER BY changed_at DESC, id DESC
            """,
            (alert_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def add_alert_note(self, *, alert_id: int, note_text: str, author: str = "admin") -> int:
        if not note_text.strip():
            raise ValueError("note_text must not be blank")
        now = _utc_now_iso()
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO alert_notes (alert_id, note_text, author, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (alert_id, note_text, author, now),
            )
        return int(cursor.lastrowid)

    def list_alert_notes(self, *, alert_id: int) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT * FROM alert_notes
            WHERE alert_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (alert_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def store_anomaly(
        self,
        *,
        event_ts: str,
        anomaly_type: str,
        payload: Mapping[str, Any],
        sensor_id: str = DEFAULT_SENSOR_ID,
        source_event_id: str | None = None,
        reason: str | None = None,
        redacted_summary: str | None = None,
    ) -> int:
        self.upsert_sensor(sensor_id=sensor_id)
        now = _utc_now_iso()
        payload_json = _encode_payload(payload)
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO anomalies (
                    sensor_id,
                    source_event_id,
                    event_ts,
                    anomaly_type,
                    reason,
                    redacted_summary,
                    payload_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sensor_id,
                    source_event_id,
                    event_ts,
                    anomaly_type,
                    reason,
                    redacted_summary,
                    payload_json,
                    now,
                    now,
                ),
            )
        return int(cursor.lastrowid)

    def list_anomalies(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "SELECT * FROM anomalies ORDER BY event_ts DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def store_summary(
        self,
        *,
        summary_ts: str,
        payload: Mapping[str, Any],
        sensor_id: str = DEFAULT_SENSOR_ID,
    ) -> int:
        self.upsert_sensor(sensor_id=sensor_id)
        now = _utc_now_iso()
        payload_json = _encode_payload(payload)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO summaries (sensor_id, summary_ts, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(sensor_id, summary_ts) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (sensor_id, summary_ts, payload_json, now, now),
            )
            row = self._connection.execute(
                """
                SELECT id FROM summaries
                WHERE sensor_id = ? AND summary_ts = ?
                """,
                (sensor_id, summary_ts),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to resolve summary id")
        return int(row["id"])

    def list_recent_summaries(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "SELECT * FROM summaries ORDER BY summary_ts DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def create_suppression_rule(
        self,
        *,
        rule_name: str,
        match_field: str,
        match_value: str,
        applies_to: str = "model_alert",
        sensor_id: str = DEFAULT_SENSOR_ID,
        is_active: bool = True,
    ) -> int:
        self.upsert_sensor(sensor_id=sensor_id)
        now = _utc_now_iso()
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO suppression_rules (
                    sensor_id,
                    rule_name,
                    match_field,
                    match_value,
                    applies_to,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sensor_id,
                    rule_name,
                    match_field,
                    match_value,
                    applies_to,
                    1 if is_active else 0,
                    now,
                    now,
                ),
            )
        return int(cursor.lastrowid)

    def list_active_suppression_rules(
        self,
        *,
        sensor_id: str = DEFAULT_SENSOR_ID,
        applies_to: str | None = None,
    ) -> list[dict[str, Any]]:
        if applies_to is None:
            rows = self._connection.execute(
                """
                SELECT * FROM suppression_rules
                WHERE sensor_id = ? AND is_active = 1
                ORDER BY updated_at DESC, id DESC
                """,
                (sensor_id,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT * FROM suppression_rules
                WHERE sensor_id = ? AND is_active = 1 AND applies_to = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (sensor_id, applies_to),
            ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def upsert_admin_user(
        self,
        *,
        username: str,
        password_hash: str,
        is_active: bool = True,
        last_login_at: str | None = None,
    ) -> dict[str, Any]:
        if not username.strip():
            raise ValueError("username must not be blank")
        if not password_hash.strip():
            raise ValueError("password_hash must not be blank")
        now = _utc_now_iso()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO admin_users (
                    username,
                    password_hash,
                    is_active,
                    created_at,
                    updated_at,
                    last_login_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at,
                    last_login_at = COALESCE(excluded.last_login_at, admin_users.last_login_at)
                """,
                (username, password_hash, 1 if is_active else 0, now, now, last_login_at),
            )
        result = self.get_admin_user(username)
        if result is None:
            raise RuntimeError("Failed to resolve admin user after upsert")
        return result

    def get_admin_user(self, username: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM admin_users WHERE username = ?",
            (username,),
        ).fetchone()
        return _row_to_dict(row)

    def upsert_admin_session(
        self,
        *,
        session_id: str,
        username: str,
        csrf_token: str,
        expires_at: str,
    ) -> dict[str, Any]:
        if self.get_admin_user(username) is None:
            raise KeyError(f"admin user {username!r} does not exist")
        now = _utc_now_iso()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO admin_sessions (
                    session_id,
                    username,
                    csrf_token,
                    expires_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    username = excluded.username,
                    csrf_token = excluded.csrf_token,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (session_id, username, csrf_token, expires_at, now, now),
            )
        result = self.get_admin_session(session_id)
        if result is None:
            raise RuntimeError("Failed to resolve admin session after upsert")
        return result

    def get_admin_session(self, session_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM admin_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return _row_to_dict(row)

    def purge_expired_admin_sessions(self, *, as_of_ts: str | None = None) -> int:
        threshold = as_of_ts or _utc_now_iso()
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM admin_sessions WHERE expires_at < ?",
                (threshold,),
            )
        return int(cursor.rowcount)

    def save_notification_delivery(
        self,
        *,
        channel: str,
        target: str,
        payload: Mapping[str, Any],
        alert_id: int | None = None,
        dedupe_key: str | None = None,
        status: str = "pending",
        next_attempt_at: str | None = None,
    ) -> int:
        now = _utc_now_iso()
        payload_json = _encode_payload(payload)
        with self._connection:
            if dedupe_key is None:
                cursor = self._connection.execute(
                    """
                    INSERT INTO notification_deliveries (
                        alert_id,
                        channel,
                        target,
                        dedupe_key,
                        payload_json,
                        status,
                        attempt_count,
                        next_attempt_at,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, NULL, ?, ?, 0, ?, ?, ?)
                    """,
                    (alert_id, channel, target, payload_json, status, next_attempt_at, now, now),
                )
                return int(cursor.lastrowid)

            self._connection.execute(
                """
                INSERT INTO notification_deliveries (
                    alert_id,
                    channel,
                    target,
                    dedupe_key,
                    payload_json,
                    status,
                    attempt_count,
                    next_attempt_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                ON CONFLICT(channel, target, dedupe_key) DO UPDATE SET
                    alert_id = COALESCE(excluded.alert_id, notification_deliveries.alert_id),
                    payload_json = excluded.payload_json,
                    status = excluded.status,
                    next_attempt_at = excluded.next_attempt_at,
                    updated_at = excluded.updated_at
                """,
                (alert_id, channel, target, dedupe_key, payload_json, status, next_attempt_at, now, now),
            )
            row = self._connection.execute(
                """
                SELECT id FROM notification_deliveries
                WHERE channel = ? AND target = ? AND dedupe_key = ?
                """,
                (channel, target, dedupe_key),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to resolve notification delivery id")
        return int(row["id"])

    def mark_notification_attempt(
        self,
        *,
        delivery_id: int,
        status: str,
        last_error: str | None = None,
        next_attempt_at: str | None = None,
        provider_message_id: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now_iso()
        with self._connection:
            self._connection.execute(
                """
                UPDATE notification_deliveries
                SET
                    status = ?,
                    attempt_count = attempt_count + 1,
                    last_attempt_at = ?,
                    next_attempt_at = ?,
                    last_error = ?,
                    provider_message_id = COALESCE(?, provider_message_id),
                    updated_at = ?
                WHERE id = ?
                """,
                (status, now, next_attempt_at, last_error, provider_message_id, now, delivery_id),
            )
        result = self.get_notification_delivery(delivery_id)
        if result is None:
            raise KeyError(f"notification delivery {delivery_id} not found")
        return result

    def get_notification_delivery(self, delivery_id: int) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM notification_deliveries WHERE id = ?",
            (delivery_id,),
        ).fetchone()
        return _row_to_dict(row)

    def list_pending_notification_deliveries(
        self,
        *,
        channel: str = "telegram",
        as_of_ts: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        threshold = as_of_ts or _utc_now_iso()
        rows = self._connection.execute(
            """
            SELECT * FROM notification_deliveries
            WHERE channel = ?
              AND status IN ('pending', 'retry')
              AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (channel, threshold, limit),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]


def open_operator_store(database_path: Path) -> OperatorStore:
    return OperatorStore.open(database_path)


def bootstrap_operator_store_path(database_path: Path) -> None:
    with closing(connect_operator_db(database_path)) as connection:
        bootstrap_operator_store(connection)


__all__ = [
    "DEFAULT_SENSOR_ID",
    "OperatorStore",
    "bootstrap_operator_store",
    "bootstrap_operator_store_path",
    "connect_operator_db",
    "open_operator_store",
]
