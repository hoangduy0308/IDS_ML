from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep as runtime_sleep
from typing import Any
import json
import shutil
import sqlite3

from starlette.testclient import TestClient

from .config import OperatorConsoleConfig, PLACEHOLDER_SECRET_VALUES
from .db import open_existing_operator_store
from .health import build_notification_component, build_readiness_payload
from .migrations import assert_runtime_ready, inspect_operator_store
from .notification_runtime import NotificationRuntimeConfig, run_notification_maintenance_cycle, run_notification_worker
from .notifications import redrive_failed_telegram_notifications, send_telegram_message
from .web import create_operator_console_web_app


class OpsError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupResult:
    backup_dir: Path
    database_backup_path: Path
    manifest_path: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class RestoreResult:
    database_path: Path
    manifest_path: Path
    inspection: Any


@dataclass(frozen=True)
class RetentionResult:
    backup_root: Path
    kept: list[str]
    removed: list[str]


@dataclass(frozen=True)
class SmokeResult:
    health_status: int
    readiness_status: int
    redirect_status: int
    readiness_payload: dict[str, Any]


@dataclass(frozen=True)
class NotificationTestSendResult:
    target: str
    provider_message_id: str


@dataclass(frozen=True)
class NotificationRedriveResult:
    redriven: int
    status: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp_slug() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%S%fZ")


def _secret_reference(config: OperatorConsoleConfig, *, value: str | None, source: Path | None) -> dict[str, Any]:
    if value is None:
        return {"configured": False, "source": None}
    if source is not None:
        return {"configured": True, "source": "file", "path": str(source)}
    return {"configured": True, "source": "env"}


def _database_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_backup_manifest(config: OperatorConsoleConfig) -> dict[str, Any]:
    inspection = assert_runtime_ready(config.database_path)
    return {
        "manifest_version": 1,
        "created_at": _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "database": {
            "path": str(config.database_path),
            "schema_state": inspection.schema_state,
            "schema_version": inspection.schema_version,
            "admin_count": inspection.admin_count,
        },
        "runtime": {
            "environment": config.environment,
            "public_base_url": config.public_base_url,
            "root_path": config.root_path,
            "forwarded_allow_ips": config.forwarded_allow_ips,
            "session_cookie_name": config.session_cookie_name,
            "session_cookie_path": config.session_cookie_path,
            "session_cookie_same_site": config.session_cookie_same_site,
            "session_cookie_https_only": config.session_cookie_https_only,
        },
        "paths": {
            "alerts_input_path": str(config.alerts_input_path),
            "quarantine_input_path": str(config.quarantine_input_path),
            "summary_input_path": str(config.summary_input_path),
            "templates_dir": str(config.templates_dir),
            "static_dir": str(config.static_dir),
        },
        "secret_references": {
            "secret_key": _secret_reference(
                config,
                value=config.secret_key,
                source=config.secret_key_source,
            ),
            "telegram_bot_token": _secret_reference(
                config,
                value=config.telegram_bot_token,
                source=config.telegram_bot_token_source,
            ),
        },
    }


def create_backup(config: OperatorConsoleConfig, *, backup_root: Path) -> BackupResult:
    manifest = build_backup_manifest(config)
    backup_dir = Path(backup_root).resolve() / f"backup-{_timestamp_slug()}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    database_backup_path = backup_dir / "operator_console.db"

    source = sqlite3.connect(str(config.database_path))
    destination = sqlite3.connect(str(database_backup_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    manifest["database"]["backup_file"] = database_backup_path.name
    manifest["database"]["backup_sha256"] = _database_digest(database_backup_path)
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return BackupResult(
        backup_dir=backup_dir,
        database_backup_path=database_backup_path,
        manifest_path=manifest_path,
        manifest=manifest,
    )


def _load_manifest(backup_dir: Path) -> tuple[Path, dict[str, Any], Path]:
    resolved = Path(backup_dir).resolve()
    manifest_path = resolved / "manifest.json"
    if not manifest_path.is_file():
        raise OpsError(f"backup manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backup_name = str(manifest.get("database", {}).get("backup_file", "operator_console.db"))
    database_backup_path = (resolved / backup_name).resolve()
    try:
        database_backup_path.relative_to(resolved)
    except ValueError as exc:
        raise OpsError("backup database must remain inside the selected backup directory") from exc
    if not database_backup_path.is_file():
        raise OpsError(f"backup database not found: {database_backup_path}")
    return manifest_path, manifest, database_backup_path


def _validate_restore_secret_references(config: OperatorConsoleConfig, manifest: dict[str, Any]) -> None:
    secret_ref = manifest.get("secret_references", {}).get("secret_key", {})
    source_type = secret_ref.get("source")
    if source_type == "file":
        if config.secret_key_source is None or not config.secret_key_source.is_file():
            raise OpsError("restore requires a readable secret_key file reference")
    else:
        if config.secret_key.strip() in PLACEHOLDER_SECRET_VALUES or not config.secret_key.strip():
            raise OpsError("restore requires a non-placeholder secret_key to be rebound")


def restore_backup(
    config: OperatorConsoleConfig,
    *,
    backup_dir: Path,
    service_stopped: bool,
) -> RestoreResult:
    if not service_stopped:
        raise OpsError("restore requires explicit offline confirmation via --service-stopped")

    manifest_path, manifest, database_backup_path = _load_manifest(backup_dir)
    _validate_restore_secret_references(config, manifest)
    expected_digest = str(manifest.get("database", {}).get("backup_sha256", "")).strip()
    if not expected_digest:
        raise OpsError("backup manifest is missing the recorded database digest")
    if _database_digest(database_backup_path) != expected_digest:
        raise OpsError("backup database digest does not match manifest")

    destination_path = config.database_path.resolve()
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(
        prefix="ids-operator-console-restore-",
        dir=str(destination_path.parent),
    ) as temp_dir:
        temp_database = Path(temp_dir) / "restored.db"
        source = sqlite3.connect(str(database_backup_path))
        destination = sqlite3.connect(str(temp_database))
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        inspection = inspect_operator_store(temp_database)
        if inspection.schema_state != "current":
            raise OpsError("restored database is not on the current schema")

        backup_existing = destination_path.with_suffix(destination_path.suffix + ".pre-restore")
        if backup_existing.exists():
            backup_existing.unlink()
        try:
            if destination_path.exists():
                destination_path.replace(backup_existing)
            temp_database.replace(destination_path)
        except Exception:
            if backup_existing.exists() and not destination_path.exists():
                backup_existing.replace(destination_path)
            raise

    return RestoreResult(
        database_path=destination_path,
        manifest_path=manifest_path,
        inspection=inspection,
    )


def prune_backup_retention(*, backup_root: Path, keep_last: int) -> RetentionResult:
    if keep_last < 1:
        raise ValueError("keep_last must be >= 1")
    resolved = Path(backup_root).resolve()
    if not resolved.exists():
        return RetentionResult(backup_root=resolved, kept=[], removed=[])
    backup_dirs = sorted(
        [path for path in resolved.iterdir() if path.is_dir() and path.name.startswith("backup-")],
        key=lambda path: path.name,
        reverse=True,
    )
    kept_paths = backup_dirs[:keep_last]
    removed_paths = backup_dirs[keep_last:]
    for stale in removed_paths:
        shutil.rmtree(stale)
    return RetentionResult(
        backup_root=resolved,
        kept=[path.name for path in kept_paths],
        removed=[path.name for path in removed_paths],
    )


def run_smoke_checks(config: OperatorConsoleConfig) -> SmokeResult:
    app = create_operator_console_web_app(config)
    base_url = config.public_base_url or "http://testserver"
    client = TestClient(app, base_url=base_url)
    health = client.get("/healthz")
    readiness = client.get("/readyz")
    root = client.get("/", follow_redirects=False)
    return SmokeResult(
        health_status=health.status_code,
        readiness_status=readiness.status_code,
        redirect_status=root.status_code,
        readiness_payload=build_readiness_payload(config, include_sensitive=True),
    )


def notification_status(config: OperatorConsoleConfig) -> dict[str, Any]:
    return build_notification_component(config, include_sensitive=True)


def _notification_runtime_config(
    config: OperatorConsoleConfig,
    *,
    poll_interval_seconds: float = 30.0,
) -> NotificationRuntimeConfig:
    return NotificationRuntimeConfig.from_operator_console_config(
        config,
        worker_poll_interval_seconds=poll_interval_seconds,
    )


def run_notification_maintenance_once(config: OperatorConsoleConfig) -> dict[str, Any]:
    result = run_notification_maintenance_cycle(_notification_runtime_config(config))
    return {
        "ingest": {
            "alerts_ingested": result.ingest.alerts_ingested,
            "anomalies_ingested": result.ingest.anomalies_ingested,
            "summaries_ingested": result.ingest.summaries_ingested,
            "parse_errors": result.ingest.parse_errors,
            "streams_scanned": result.ingest.streams_scanned,
        },
        "queued": result.queued,
        "dispatch": {
            "queued": result.dispatch.queued,
            "sent": result.dispatch.sent,
            "retried": result.dispatch.retried,
            "failed": result.dispatch.failed,
            "scanned": result.dispatch.scanned,
        },
        "status": {
            "enabled": result.status.enabled,
            "configured": result.status.configured,
            "channel": result.status.channel,
            "target": result.status.target,
            "pending_count": result.status.pending_count,
            "retry_count": result.status.retry_count,
            "failed_count": result.status.failed_count,
            "sent_count": result.status.sent_count,
            "due_count": result.status.due_count,
            "oldest_due_at": result.status.oldest_due_at,
            "last_error": result.status.last_error,
        },
    }


def run_notification_worker_iterations(
    config: OperatorConsoleConfig,
    *,
    iterations: int | None,
    poll_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    sleep_fn = runtime_sleep if poll_interval_seconds > 0 else (lambda _seconds: None)
    results = run_notification_worker(
        _notification_runtime_config(config, poll_interval_seconds=poll_interval_seconds),
        iterations=iterations,
        sleep_fn=sleep_fn,
    )
    latest = results[-1]
    return {
        "iterations": len(results),
        "last_cycle": {
            "queued": latest.queued,
            "dispatch": {
                "sent": latest.dispatch.sent,
                "retried": latest.dispatch.retried,
                "failed": latest.dispatch.failed,
                "scanned": latest.dispatch.scanned,
            },
            "status": {
                "enabled": latest.status.enabled,
                "configured": latest.status.configured,
                "pending_count": latest.status.pending_count,
                "retry_count": latest.status.retry_count,
                "failed_count": latest.status.failed_count,
                "sent_count": latest.status.sent_count,
                "due_count": latest.status.due_count,
            },
        },
    }


def send_test_notification(config: OperatorConsoleConfig, *, text: str) -> NotificationTestSendResult:
    runtime_config = _notification_runtime_config(config)
    if runtime_config.telegram is None:
        raise OpsError("telegram notifications are disabled")
    provider_message_id = send_telegram_message(
        runtime_config.telegram,
        chat_id=runtime_config.telegram.default_chat_id,
        text=text,
    )
    return NotificationTestSendResult(
        target=runtime_config.telegram.default_chat_id,
        provider_message_id=provider_message_id,
    )


def redrive_notification_failures(
    config: OperatorConsoleConfig,
    *,
    limit: int = 100,
) -> NotificationRedriveResult:
    store = open_existing_operator_store(config.database_path)
    try:
        redriven = redrive_failed_telegram_notifications(store, limit=limit)
    finally:
        store.close()
    return NotificationRedriveResult(redriven=redriven, status=notification_status(config))
