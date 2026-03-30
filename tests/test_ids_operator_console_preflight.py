from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import ids.ops.operator_console_manage as manage  # noqa: E402
import ids.ops.operator_console_preflight as preflight  # noqa: E402
from ids.ops.operator_console_preflight import (  # noqa: E402
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

    secret_path = tmp_path / "console.secret"
    secret_path.write_text("production-secret\n", encoding="utf-8")
    kwargs: dict[str, object] = {
        "python_binary": _make_executable(tmp_path / "bin" / "python3"),
        "app_entrypoint": tmp_path / "scripts" / "ids_operator_console_server.py",
        "manage_entrypoint": tmp_path / "scripts" / "ids_operator_console_manage.py",
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
        "telegram_bot_token_file": None,
        "telegram_chat_id": None,
    }
    Path(kwargs["app_entrypoint"]).parent.mkdir(parents=True, exist_ok=True)
    Path(kwargs["app_entrypoint"]).write_text("print('ok')\n", encoding="utf-8")
    Path(kwargs["manage_entrypoint"]).write_text("print('ok')\n", encoding="utf-8")
    kwargs.update(overrides)
    return OperatorConsolePreflightConfig(**kwargs)


def test_preflight_accepts_valid_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    validate_preflight(config)


def test_preflight_requires_admin_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    bare_db = tmp_path / "runtime" / "bare.db"
    manage.main(["--database-path", str(bare_db), "migrate", "--allow-bootstrap"])
    missing_admin = OperatorConsolePreflightConfig(
        **{**config.__dict__, "database_path": bare_db}
    )

    with pytest.raises(ValueError, match="no admin user"):
        validate_preflight(missing_admin)


def test_deploy_artifacts_are_wired_to_proxy_and_secret_contract() -> None:
    service_text = (REPO_ROOT / "deploy/systemd/ids-operator-console.service").read_text(encoding="utf-8")
    notify_service_text = (REPO_ROOT / "deploy/systemd/ids-operator-console-notify.service").read_text(encoding="utf-8")
    nginx_text = (REPO_ROOT / "deploy/nginx/ids-operator-console.conf.example").read_text(encoding="utf-8")

    assert "EnvironmentFile=-/etc/ids-operator-console/ids-operator-console.env" in service_text
    assert "IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE" in service_text
    assert "--public-base-url ${IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL}" in service_text
    assert "--secret-key-file ${IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE}" in service_text
    assert "--manage-entrypoint /opt/ids_ml_new/scripts/ids_operator_console_manage.py" in service_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE" in service_text

    assert "ids_operator_console_manage.py --database-path \"$IDS_OPERATOR_CONSOLE_DATABASE_PATH\" notify-worker" in notify_service_text
    assert "--iterations 1" not in notify_service_text
    assert "notify-worker --poll-interval-seconds 30" in notify_service_text
    assert "--manage-entrypoint /opt/ids_ml_new/scripts/ids_operator_console_manage.py" in notify_service_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE" in notify_service_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID" in notify_service_text

    assert "proxy_set_header Host $host;" in nginx_text
    assert "proxy_set_header X-Forwarded-Proto https;" in nginx_text
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in nginx_text


def test_preflight_rejects_notification_enabled_missing_manage_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_preflight_config(
        tmp_path,
        manage_entrypoint=None,
        telegram_bot_token="token",
        telegram_chat_id="-100preflight",
    )
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="manage_entrypoint"):
        validate_preflight(config)


def test_preflight_rejects_chat_only_pairing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path, telegram_bot_token=None, telegram_chat_id="-100chat-only")
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="must be set together"):
        validate_preflight(config)


def test_preflight_main_fails_closed_on_partial_env_notification_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN", "token-only")
    monkeypatch.delenv("IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(ValueError, match="must be set together"):
        preflight.main(
            [
                "--python-binary",
                str(config.python_binary),
                "--app-entrypoint",
                str(config.app_entrypoint),
                "--manage-entrypoint",
                str(config.manage_entrypoint),
                "--database-path",
                str(config.database_path),
                "--alerts-input-path",
                str(config.alerts_input_path),
                "--quarantine-input-path",
                str(config.quarantine_input_path),
                "--summary-input-path",
                str(config.summary_input_path),
                "--templates-dir",
                str(config.templates_dir),
                "--static-dir",
                str(config.static_dir),
                "--environment",
                config.environment,
                "--public-base-url",
                str(config.public_base_url),
                "--root-path",
                config.root_path,
                "--forwarded-allow-ips",
                config.forwarded_allow_ips,
                "--secret-key-file",
                str(config.secret_key_file),
            ]
        )
