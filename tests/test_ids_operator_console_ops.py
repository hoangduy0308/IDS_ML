from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.ids_operator_console_manage as manage  # noqa: E402
import scripts.ids_operator_console_preflight as preflight  # noqa: E402
from scripts.ids_operator_console.db import OperatorStore  # noqa: E402
from scripts.ids_operator_console_preflight import (  # noqa: E402
    OperatorConsolePreflightConfig,
    validate_preflight,
)


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


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
        "python_binary": _make_executable(tmp_path / "bin" / "python3"),
        "app_entrypoint": tmp_path / "scripts" / "ids_operator_console_server.py",
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
    Path(kwargs["app_entrypoint"]).parent.mkdir(parents=True, exist_ok=True)
    Path(kwargs["app_entrypoint"]).write_text("print('ok')\n", encoding="utf-8")
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
    assert (backup_dir / "manifest.json").is_file()
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "ops-secret" not in json.dumps(manifest)
    assert manifest["secret_references"]["secret_key"]["source"] == "file"

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

    smoke_rc = manage.main(["--database-path", str(db_path), "--json", "smoke"])
    smoke_payload = json.loads(capsys.readouterr().out)
    assert smoke_rc == 0
    assert smoke_payload["health_status"] == 200
    assert smoke_payload["readiness_status"] == 200
    assert smoke_payload["ready"] is True

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
