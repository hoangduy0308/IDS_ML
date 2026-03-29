from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .db import bootstrap_operator_store, connect_operator_db


SCHEMA_FAMILY = "ids_operator_console"
CURRENT_SCHEMA_VERSION = 2
LEGACY_REQUIRED_TABLES = {
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
}


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoreInspection:
    database_path: Path
    database_exists: bool
    schema_state: str
    schema_version: int | None
    admin_count: int
    runtime_ready: bool
    detail: str


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _schema_metadata_exists(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_metadata'"
    ).fetchone()
    return row is not None


def _ensure_schema_metadata_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_metadata (
            schema_family TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _write_schema_version(connection: sqlite3.Connection, *, version: int) -> None:
    connection.execute(
        """
        INSERT INTO schema_metadata (schema_family, schema_version, updated_at)
        VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        ON CONFLICT(schema_family) DO UPDATE SET
            schema_version = excluded.schema_version,
            updated_at = excluded.updated_at
        """,
        (SCHEMA_FAMILY, version),
    )


def _read_schema_version(connection: sqlite3.Connection) -> int | None:
    if not _schema_metadata_exists(connection):
        return None
    row = connection.execute(
        """
        SELECT schema_version
        FROM schema_metadata
        WHERE schema_family = ?
        """,
        (SCHEMA_FAMILY,),
    ).fetchone()
    if row is None:
        return None
    return int(row["schema_version"])


def inspect_operator_store(database_path: Path) -> StoreInspection:
    resolved = Path(database_path).resolve()
    if not resolved.exists():
        return StoreInspection(
            database_path=resolved,
            database_exists=False,
            schema_state="missing",
            schema_version=None,
            admin_count=0,
            runtime_ready=False,
            detail="database file does not exist",
        )

    connection = connect_operator_db(resolved)
    try:
        tables = _table_names(connection)
        schema_version = _read_schema_version(connection)
        admin_count = 0
        if "admin_users" in tables:
            row = connection.execute("SELECT COUNT(*) AS count FROM admin_users").fetchone()
            admin_count = int(row["count"]) if row is not None else 0

        if schema_version == CURRENT_SCHEMA_VERSION:
            return StoreInspection(
                database_path=resolved,
                database_exists=True,
                schema_state="current",
                schema_version=schema_version,
                admin_count=admin_count,
                runtime_ready=admin_count > 0,
                detail="schema is current" if admin_count > 0 else "schema is current but no admin user exists",
            )

        if LEGACY_REQUIRED_TABLES.issubset(tables):
            return StoreInspection(
                database_path=resolved,
                database_exists=True,
                schema_state="legacy-v1",
                schema_version=None,
                admin_count=admin_count,
                runtime_ready=False,
                detail="legacy v1 schema requires explicit migration",
            )

        if not tables:
            return StoreInspection(
                database_path=resolved,
                database_exists=True,
                schema_state="empty",
                schema_version=None,
                admin_count=0,
                runtime_ready=False,
                detail="database exists but contains no operator schema",
            )

        return StoreInspection(
            database_path=resolved,
            database_exists=True,
            schema_state="unknown",
            schema_version=schema_version,
            admin_count=admin_count,
            runtime_ready=False,
            detail="database schema does not match known operator-console layouts",
        )
    finally:
        connection.close()


def assert_runtime_ready(database_path: Path) -> StoreInspection:
    inspection = inspect_operator_store(database_path)
    if not inspection.database_exists:
        raise MigrationError(
            f"operator database is missing: {inspection.database_path}. "
            "Run ids_operator_console_manage.py migrate --allow-bootstrap first."
        )
    if inspection.schema_state != "current":
        raise MigrationError(
            f"operator database is not runtime-ready ({inspection.schema_state}): {inspection.detail}. "
            "Run ids_operator_console_manage.py migrate before starting the service."
        )
    if inspection.admin_count < 1:
        raise MigrationError(
            f"operator database has no admin user: {inspection.database_path}. "
            "Run ids_operator_console_manage.py bootstrap-admin before starting the service."
        )
    return inspection


def migrate_operator_store(
    database_path: Path,
    *,
    allow_bootstrap: bool = False,
) -> StoreInspection:
    resolved = Path(database_path).resolve()
    pre = inspect_operator_store(resolved)
    if pre.schema_state == "missing" and not allow_bootstrap:
        raise MigrationError(
            f"operator database is missing: {resolved}. Pass --allow-bootstrap to initialize it."
        )
    if pre.schema_state == "unknown":
        raise MigrationError(f"refusing to migrate unknown schema at {resolved}")

    connection = connect_operator_db(resolved)
    try:
        with connection:
            if pre.schema_state in {"missing", "empty"}:
                if not allow_bootstrap:
                    raise MigrationError(
                        f"operator database is not initialized: {resolved}. "
                        "Pass --allow-bootstrap to create the current schema."
                    )
                bootstrap_operator_store(connection)
                _ensure_schema_metadata_table(connection)
                _write_schema_version(connection, version=CURRENT_SCHEMA_VERSION)
            elif pre.schema_state == "legacy-v1":
                _ensure_schema_metadata_table(connection)
                _write_schema_version(connection, version=CURRENT_SCHEMA_VERSION)
            elif pre.schema_state == "current":
                _ensure_schema_metadata_table(connection)
                _write_schema_version(connection, version=CURRENT_SCHEMA_VERSION)
            else:
                raise MigrationError(f"unsupported schema state: {pre.schema_state}")
    finally:
        connection.close()

    return inspect_operator_store(resolved)
