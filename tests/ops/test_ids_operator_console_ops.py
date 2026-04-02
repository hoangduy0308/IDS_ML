from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import os
import sqlite3
import shutil
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
import ids.ops.operator_console_manage as manage  # noqa: E402
import ids.console.notifications as notifications  # noqa: E402
import ids.console.ops as ops  # noqa: E402
import ids.ops.operator_console_preflight as preflight  # noqa: E402
from ids.console.config import load_operator_console_config  # noqa: E402
from ids.console.db import OperatorStore  # noqa: E402
from ids.console.ops import run_smoke_checks  # noqa: E402
from ids.ops.operator_console_preflight import (  # noqa: E402
    OperatorConsolePreflightConfig,
    validate_preflight,
)


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_backup_bundle(source_dir: Path, destination_root: Path) -> tuple[Path, Path]:
    destination_root.mkdir(parents=True, exist_ok=True)
    copied_backup_dir = destination_root / source_dir.name
    shutil.copytree(source_dir, copied_backup_dir)
    integrity_path = source_dir.parent / f"{source_dir.name}.integrity.json"
    copied_integrity_path = destination_root / integrity_path.name
    shutil.copy2(integrity_path, copied_integrity_path)
    return copied_backup_dir, copied_integrity_path


def _make_preflight_config(tmp_path: Path, **overrides: object) -> OperatorConsolePreflightConfig:
    runtime_dir = tmp_path / "runtime"
    logs_dir = tmp_path / "logs"
    templates_dir = tmp_path / "templates"
    static_dir = tmp_path / "static"
    runtime_dir.mkdir()
    logs_dir.mkdir()
    templates_dir.mkdir()
    static_dir.mkdir()

    db_path = runtime_dir / "operator_console.db"
    manage.main(["--database-path", str(db_path), "migrate", "--allow-bootstrap"])
    secret_path = tmp_path / "secrets" / "console.secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text("production-secret\n", encoding="utf-8")
    manage.main(
        [
            "--database-path",
            str(db_path),
            "bootstrap-admin",
            "--username",
            "admin",
            "--password",
            "correct-password",
        ]
    )

    kwargs: dict[str, object] = {
        "python_binary": Path(sys.executable).resolve(),
        "app_module": "ids.console.server",
        "manage_module": "ids.ops.operator_console_manage",
        "database_path": db_path,
        "alerts_input_path": logs_dir / "ids_live_alerts.jsonl",
        "quarantine_input_path": logs_dir / "ids_live_quarantine.jsonl",
        "summary_input_path": logs_dir / "ids_live_sensor_summary.jsonl",
        "templates_dir": templates_dir,
        "static_dir": static_dir,
        "environment": "production",
        "public_base_url": "https://console.example",
        "root_path": "",
        "forwarded_allow_ips": "127.0.0.1",
        "secret_key": None,
        "secret_key_file": secret_path,
        "telegram_bot_token": None,
        "telegram_chat_id": None,
    }
    kwargs.update(overrides)
    return OperatorConsolePreflightConfig(**kwargs)


def test_manage_status_migrate_and_bootstrap_admin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "operator_console.db"

    status_before = manage.main(["--database-path", str(db_path), "--json", "status"])
    captured_before = json.loads(capsys.readouterr().out)
    assert status_before == 2
    assert captured_before["schema_state"] == "missing"

    migrate_rc = manage.main(["--database-path", str(db_path), "--json", "migrate", "--allow-bootstrap"])
    captured_migrate = json.loads(capsys.readouterr().out)
    assert migrate_rc == 0
    assert captured_migrate["schema_state"] == "current"
    assert captured_migrate["admin_count"] == 0

    password_file = tmp_path / "admin.password"
    password_file.write_text("correct-password\n", encoding="utf-8")
    bootstrap_rc = manage.main(
        [
            "--database-path",
            str(db_path),
            "--json",
            "bootstrap-admin",
            "--username",
            "admin",
            "--password-file",
            str(password_file),
        ]
    )
    captured_bootstrap = json.loads(capsys.readouterr().out)
    assert bootstrap_rc == 0
    assert captured_bootstrap["admin_count"] == 1
    assert captured_bootstrap["runtime_ready"] is True


def test_manage_backup_restore_retention_and_smoke(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "operator_console.db"
    templates_dir = REPO_ROOT / "scripts/ids_operator_console/templates"
    static_dir = REPO_ROOT / "scripts/ids_operator_console/static"
    secret_file = tmp_path / "console.secret"
    secret_file.write_text("ops-secret\n", encoding="utf-8")

    manage.main(["--database-path", str(db_path), "migrate", "--allow-bootstrap"])
    capsys.readouterr()
    manage.main(
        [
            "--database-path",
            str(db_path),
            "bootstrap-admin",
            "--username",
            "admin",
            "--password",
            "correct-password",
        ]
    )
    capsys.readouterr()
    store = OperatorStore.open(db_path)
    try:
        store.store_summary(
            summary_ts="2026-03-29T01:00:00+00:00",
            payload={
                "window_seconds": 60,
                "alert_count": 0,
                "anomaly_count": 0,
                "active_bundle": {
                    "active_bundle_name": "bundle-a",
                    "compatibility_status": "compatible",
                    "activated_at": "2026-03-29T00:55:00+00:00",
                    "previous_bundle_name": "bundle-prev",
                },
            },
        )
        alert_id = store.upsert_alert(
            source_event_id="backup-alert-001",
            event_ts="2026-03-29T01:01:00+00:00",
            severity="high",
            src_ip="10.50.0.5",
            dst_ip="10.50.0.7",
            payload={"event_type": "model_prediction", "score": 0.97},
        )
        delivery_id = store.save_notification_delivery(
            alert_id=alert_id,
            channel="telegram",
            target="-100backup",
            dedupe_key="backup-alert-001",
            payload={"text": "backup failed delivery"},
            status="pending",
        )
        store.mark_notification_attempt(
            delivery_id=delivery_id,
            status="failed",
            last_error="telegram outage",
        )
    finally:
        store.close()

    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_ENVIRONMENT", "production")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL", "https://console.example")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE", str(secret_file))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TEMPLATES_DIR", str(templates_dir))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_STATIC_DIR", str(static_dir))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_ALERTS_INPUT_PATH", str(tmp_path / "logs" / "ids_live_alerts.jsonl"))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_QUARANTINE_INPUT_PATH", str(tmp_path / "logs" / "ids_live_quarantine.jsonl"))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH", str(tmp_path / "logs" / "ids_live_sensor_summary.jsonl"))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID", "-100backup")
    (tmp_path / "logs").mkdir()

    backup_root = tmp_path / "backups"
    backup_rc = manage.main(
        [
            "--database-path",
            str(db_path),
            "--json",
            "backup",
            "--output-dir",
            str(backup_root),
        ]
    )
    backup_payload = json.loads(capsys.readouterr().out)
    assert backup_rc == 0
    backup_dir = Path(backup_payload["backup_dir"])
    assert (backup_dir / "manifest.json").is_file()
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    backup_integrity_path = backup_dir.parent / f"{backup_dir.name}.integrity.json"
    assert backup_integrity_path.is_file()
    backup_integrity = json.loads(backup_integrity_path.read_text(encoding="utf-8"))
    assert "ops-secret" not in json.dumps(manifest)
    assert manifest["secret_references"]["secret_key"]["source"] == "file"
    assert backup_integrity["database"]["backup_sha256"] == manifest["database"]["backup_sha256"]

    restored_db = tmp_path / "restored" / "operator_console.db"
    with pytest.raises(Exception, match="service-stopped"):
        manage.main(
            [
                "--database-path",
                str(restored_db),
                "restore",
                "--backup-dir",
                str(backup_dir),
            ]
        )

    restore_rc = manage.main(
        [
            "--database-path",
            str(restored_db),
            "--json",
            "restore",
            "--backup-dir",
            str(backup_dir),
            "--service-stopped",
        ]
    )
    restore_payload = json.loads(capsys.readouterr().out)
    assert restore_rc == 0
    assert restore_payload["schema_state"] == "current"
    assert restore_payload["admin_count"] == 1
    restored_store = OperatorStore.open(restored_db)
    try:
        restored_summary = restored_store.list_recent_summaries(limit=1)[0]
        restored_notification = restored_store.get_notification_delivery_summary(channel="telegram")
    finally:
        restored_store.close()
    restored_payload_json = json.loads(restored_summary["payload_json"])
    assert restored_payload_json["active_bundle"]["active_bundle_name"] == "bundle-a"
    assert restored_payload_json["active_bundle"]["previous_bundle_name"] == "bundle-prev"
    assert restored_notification["failed_count"] == 1
    assert restored_notification["last_error"] is not None
    assert restored_notification["last_error"]["last_error"] == "telegram outage"

    restored_env = dict(os.environ)
    restored_env["IDS_OPERATOR_CONSOLE_DATABASE_PATH"] = str(restored_db)
    restored_config = load_operator_console_config(environ=restored_env, repo_root=REPO_ROOT)
    restored_smoke = run_smoke_checks(restored_config)
    assert restored_smoke.readiness_payload["components"]["active_bundle"]["ok"] is True
    assert (
        restored_smoke.readiness_payload["components"]["active_bundle"]["state"]["active_bundle_name"]
        == "bundle-a"
    )
    assert restored_smoke.readiness_payload["components"]["notification"]["enabled"] is True
    assert restored_smoke.readiness_payload["components"]["notification"]["failed_count"] == 1
    assert restored_smoke.readiness_payload["components"]["notification"]["state"] == "degraded"
    assert restored_smoke.readiness_payload["components"]["notification"]["target"] is None
    assert restored_smoke.readiness_payload["components"]["notification"]["last_error"]["present"] is True
    assert "message" not in restored_smoke.readiness_payload["components"]["notification"]["last_error"]
    assert restored_smoke.readiness_payload["ready"] is True

    tamper_target_db = tmp_path / "tamper-target" / "operator_console.db"
    tamper_target_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(restored_db, tamper_target_db)
    tamper_target_digest = _file_digest(tamper_target_db)

    digest_blank_root = tmp_path / "tampered-digest-blank"
    digest_blank_dir, _ = _copy_backup_bundle(backup_dir, digest_blank_root)
    digest_blank_manifest_path = digest_blank_dir / "manifest.json"
    digest_blank_manifest = json.loads(digest_blank_manifest_path.read_text(encoding="utf-8"))
    digest_blank_manifest["database"]["backup_sha256"] = ""
    digest_blank_manifest_path.write_text(
        json.dumps(digest_blank_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="digest"):
        manage.main(
            [
                "--database-path",
                str(tamper_target_db),
                "restore",
                "--backup-dir",
                str(digest_blank_dir),
                "--service-stopped",
            ]
        )
    assert _file_digest(tamper_target_db) == tamper_target_digest

    digest_missing_root = tmp_path / "tampered-digest-missing"
    digest_missing_dir, _ = _copy_backup_bundle(backup_dir, digest_missing_root)
    digest_missing_manifest_path = digest_missing_dir / "manifest.json"
    digest_missing_manifest = json.loads(digest_missing_manifest_path.read_text(encoding="utf-8"))
    digest_missing_manifest["database"].pop("backup_sha256", None)
    digest_missing_manifest_path.write_text(
        json.dumps(digest_missing_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="digest"):
        manage.main(
            [
                "--database-path",
                str(tamper_target_db),
                "restore",
                "--backup-dir",
                str(digest_missing_dir),
                "--service-stopped",
            ]
        )
    assert _file_digest(tamper_target_db) == tamper_target_digest

    schema_tampered_root = tmp_path / "tampered-schema"
    schema_tampered_dir, schema_tampered_integrity_path = _copy_backup_bundle(backup_dir, schema_tampered_root)
    schema_tampered_db = schema_tampered_dir / "operator_console.db"
    schema_tampered_db.unlink()
    legacy_conn = sqlite3.connect(schema_tampered_db)
    try:
        legacy_conn.execute("CREATE TABLE legacy_state (id INTEGER PRIMARY KEY)")
        legacy_conn.commit()
    finally:
        legacy_conn.close()
    schema_digest = _file_digest(schema_tampered_db)
    schema_manifest_path = schema_tampered_dir / "manifest.json"
    schema_manifest = json.loads(schema_manifest_path.read_text(encoding="utf-8"))
    schema_manifest["database"]["backup_sha256"] = schema_digest
    schema_manifest_path.write_text(
        json.dumps(schema_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    schema_integrity = json.loads(schema_tampered_integrity_path.read_text(encoding="utf-8"))
    schema_integrity["database"]["backup_sha256"] = schema_digest
    schema_tampered_integrity_path.write_text(
        json.dumps(schema_integrity, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="current schema"):
        manage.main(
            [
                "--database-path",
                str(tamper_target_db),
                "restore",
                "--backup-dir",
                str(schema_tampered_dir),
                "--service-stopped",
            ]
        )
    assert _file_digest(tamper_target_db) == tamper_target_digest

    path_tampered_root = tmp_path / "tampered-path"
    path_tampered_dir, _ = _copy_backup_bundle(backup_dir, path_tampered_root)
    path_manifest_path = path_tampered_dir / "manifest.json"
    path_manifest = json.loads(path_manifest_path.read_text(encoding="utf-8"))
    outside_db = tmp_path / "outside.db"
    shutil.copy2(path_tampered_dir / path_manifest["database"]["backup_file"], outside_db)
    path_manifest["database"]["backup_file"] = "../outside.db"
    path_manifest_path.write_text(
        json.dumps(path_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="trusted backup integrity metadata"):
        manage.main(
            [
                "--database-path",
                str(tamper_target_db),
                "restore",
                "--backup-dir",
                str(path_tampered_dir),
                "--service-stopped",
            ]
        )
    assert _file_digest(tamper_target_db) == tamper_target_digest

    restored_redrive_rc = manage.main(
        [
            "--database-path",
            str(restored_db),
            "--json",
            "notify-redrive",
            "--limit",
            "10",
        ]
    )
    restored_redrive_payload = json.loads(capsys.readouterr().out)
    assert restored_redrive_rc == 0
    assert restored_redrive_payload["redriven"] == 1
    assert restored_redrive_payload["status"]["failed_count"] == 0
    assert restored_redrive_payload["status"]["pending_count"] >= 1

    smoke_rc = manage.main(["--database-path", str(db_path), "--json", "smoke"])
    smoke_payload = json.loads(capsys.readouterr().out)
    assert smoke_rc == 0
    assert smoke_payload["health_status"] == 200
    assert smoke_payload["readiness_status"] == 200
    assert smoke_payload["ready"] is True
    assert smoke_payload["notification"]["enabled"] is True
    assert smoke_payload["notification"]["state"] == "degraded"
    assert smoke_payload["notification"]["failed_count"] == 1

    second_backup_rc = manage.main(
        [
            "--database-path",
            str(db_path),
            "--json",
            "backup",
            "--output-dir",
            str(backup_root),
        ]
    )
    assert second_backup_rc == 0
    second_backup_payload = json.loads(capsys.readouterr().out)
    assert Path(second_backup_payload["backup_dir"]).is_dir()

    prune_rc = manage.main(
        [
            "--database-path",
            str(db_path),
            "--json",
            "prune-retention",
            "--backup-root",
            str(backup_root),
            "--keep-last",
            "1",
        ]
    )
    prune_payload = json.loads(capsys.readouterr().out)
    assert prune_rc == 0
    assert len(prune_payload["kept"]) == 1
    assert len(prune_payload["removed"]) == 1
    assert not (backup_root / f"{prune_payload['removed'][0]}.integrity.json").exists()


def test_manage_notification_commands_surface_runtime_contract(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "operator_console.db"
    templates_dir = REPO_ROOT / "scripts/ids_operator_console/templates"
    static_dir = REPO_ROOT / "scripts/ids_operator_console/static"
    alerts_path = tmp_path / "logs" / "ids_live_alerts.jsonl"
    quarantine_path = tmp_path / "logs" / "ids_live_quarantine.jsonl"
    summary_path = tmp_path / "logs" / "ids_live_sensor_summary.jsonl"

    manage.main(["--database-path", str(db_path), "migrate", "--allow-bootstrap"])
    capsys.readouterr()
    manage.main(
        [
            "--database-path",
            str(db_path),
            "bootstrap-admin",
            "--username",
            "admin",
            "--password",
            "correct-password",
        ]
    )
    capsys.readouterr()

    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_SECRET_KEY", "dev-secret")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TEMPLATES_DIR", str(templates_dir))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_STATIC_DIR", str(static_dir))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_ALERTS_INPUT_PATH", str(alerts_path))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_QUARANTINE_INPUT_PATH", str(quarantine_path))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH", str(summary_path))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID", "-100ops")

    sent_messages: list[str] = []

    def fake_send(_config: object, *, chat_id: str, text: str) -> str:
        sent_messages.append(f"{chat_id}:{text}")
        return f"msg-{len(sent_messages)}"

    monkeypatch.setattr(ops, "send_telegram_message", fake_send)
    monkeypatch.setattr(notifications, "send_telegram_message", fake_send)

    _append_jsonl(
        alerts_path,
        {
            "event_type": "model_prediction",
            "source_event_id": "ops-alert-1",
            "timestamp": "2026-03-29T02:00:00+00:00",
            "severity": "high",
            "src_ip": "10.10.0.5",
            "dst_ip": "10.10.0.7",
            "is_alert": True,
        },
    )

    notify_status_rc = manage.main(["--database-path", str(db_path), "--json", "notify-status"])
    notify_status_payload = json.loads(capsys.readouterr().out)
    assert notify_status_rc == 0
    assert notify_status_payload["enabled"] is True
    assert notify_status_payload["state"] == "ok"
    assert notify_status_payload["target"] == "-100ops"

    parser = manage._build_parser()  # noqa: SLF001
    parsed_worker_args = parser.parse_args(["--database-path", str(db_path), "notify-worker"])
    assert parsed_worker_args.iterations is None

    test_send_rc = manage.main(
        ["--database-path", str(db_path), "--json", "notify-test-send", "--text", "operator ping"]
    )
    test_send_payload = json.loads(capsys.readouterr().out)
    assert test_send_rc == 0
    assert test_send_payload["provider_message_id"] == "msg-1"

    run_once_rc = manage.main(["--database-path", str(db_path), "--json", "notify-run-once"])
    run_once_payload = json.loads(capsys.readouterr().out)
    assert run_once_rc == 0
    assert run_once_payload["ingest"]["alerts_ingested"] == 1
    assert run_once_payload["queued"] == 1
    assert run_once_payload["dispatch"]["sent"] == 1

    worker_rc = manage.main(
        [
            "--database-path",
            str(db_path),
            "--json",
            "notify-worker",
            "--iterations",
            "1",
            "--poll-interval-seconds",
            "0",
        ]
    )
    worker_payload = json.loads(capsys.readouterr().out)
    assert worker_rc == 0
    assert worker_payload["iterations"] == 1

    store = OperatorStore.open(db_path)
    try:
        alert_id = store.upsert_alert(
            source_event_id="ops-alert-failed",
            event_ts="2026-03-29T02:01:00+00:00",
            severity="high",
            src_ip="10.10.0.8",
            dst_ip="10.10.0.9",
            payload={"event_type": "model_prediction", "score": 0.88},
        )
        failed_delivery_id = store.save_notification_delivery(
            alert_id=alert_id,
            channel="telegram",
            target="-100ops",
            dedupe_key="ops-alert-failed",
            payload={"text": "failed delivery"},
            status="pending",
        )
        store.mark_notification_attempt(
            delivery_id=failed_delivery_id,
            status="failed",
            last_error="telegram outage",
        )
    finally:
        store.close()

    redrive_rc = manage.main(
        ["--database-path", str(db_path), "--json", "notify-redrive", "--limit", "10"]
    )
    redrive_payload = json.loads(capsys.readouterr().out)
    assert redrive_rc == 0
    assert redrive_payload["redriven"] == 1
    assert redrive_payload["status"]["pending_count"] >= 1

    smoke_rc = manage.main(["--database-path", str(db_path), "--json", "smoke"])
    smoke_payload = json.loads(capsys.readouterr().out)
    assert smoke_rc == 0
    assert smoke_payload["ready"] is True
    assert smoke_payload["notification"]["enabled"] is True
    assert smoke_payload["notification"]["channel"] == "telegram"
    assert smoke_payload["notification"]["target"] is None


@pytest.mark.parametrize(
    ("tamper_manifest", "expected_error"),
    [
        (lambda path: path.write_text("{", encoding="utf-8"), "backup manifest is not valid JSON"),
        (
            lambda path: (
                path.parent.parent / f"{path.parent.name}.integrity.json"
            ).write_text("{", encoding="utf-8"),
            "backup integrity metadata is not valid JSON",
        ),
    ],
)
def test_restore_normalizes_corrupted_backup_metadata_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tamper_manifest,
    expected_error: str,
) -> None:
    db_path = tmp_path / "operator_console.db"
    templates_dir = REPO_ROOT / "scripts/ids_operator_console/templates"
    static_dir = REPO_ROOT / "scripts/ids_operator_console/static"
    secret_file = tmp_path / "console.secret"
    secret_file.write_text("ops-secret\n", encoding="utf-8")

    manage.main(["--database-path", str(db_path), "migrate", "--allow-bootstrap"])
    capsys.readouterr()
    manage.main(
        [
            "--database-path",
            str(db_path),
            "bootstrap-admin",
            "--username",
            "admin",
            "--password",
            "correct-password",
        ]
    )
    capsys.readouterr()

    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_ENVIRONMENT", "production")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL", "https://console.example")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE", str(secret_file))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TEMPLATES_DIR", str(templates_dir))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_STATIC_DIR", str(static_dir))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_ALERTS_INPUT_PATH", str(tmp_path / "logs" / "ids_live_alerts.jsonl"))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_QUARANTINE_INPUT_PATH", str(tmp_path / "logs" / "ids_live_quarantine.jsonl"))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH", str(tmp_path / "logs" / "ids_live_sensor_summary.jsonl"))
    (tmp_path / "logs").mkdir()

    backup_root = tmp_path / "backups"
    backup_rc = manage.main(
        [
            "--database-path",
            str(db_path),
            "--json",
            "backup",
            "--output-dir",
            str(backup_root),
        ]
    )
    backup_payload = json.loads(capsys.readouterr().out)
    assert backup_rc == 0
    backup_dir = Path(backup_payload["backup_dir"])

    restored_db = tmp_path / "restored" / "operator_console.db"
    tamper_manifest(backup_dir / "manifest.json")

    with pytest.raises(Exception, match=expected_error):
        manage.main(
            [
                "--database-path",
                str(restored_db),
                "restore",
                "--backup-dir",
                str(backup_dir),
                "--service-stopped",
            ]
        )


def test_manage_requires_explicit_migrate_before_bootstrap(tmp_path: Path) -> None:
    db_path = tmp_path / "operator_console.db"
    store = OperatorStore.open(db_path)
    store.close()

    with pytest.raises(SystemExit, match="run migrate"):
        manage.main(
            [
                "--database-path",
                str(db_path),
                "bootstrap-admin",
                "--username",
                "admin",
                "--password",
                "correct-password",
            ]
        )


def test_preflight_accepts_valid_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    validate_preflight(config)


def test_preflight_rejects_missing_admin_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    fresh_db = tmp_path / "runtime" / "fresh.db"
    manage.main(["--database-path", str(fresh_db), "migrate", "--allow-bootstrap"])
    missing_admin_config = OperatorConsolePreflightConfig(
        **{**config.__dict__, "database_path": fresh_db}
    )

    with pytest.raises(ValueError, match="no admin user"):
        validate_preflight(missing_admin_config)


def test_preflight_rejects_telegram_pairing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path, telegram_bot_token="token-only", telegram_chat_id=None)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="must be set together"):
        validate_preflight(config)
