from __future__ import annotations

from pathlib import Path
import sys

import pytest

from wrapper_smoke_support import assert_help_smoke, run_python_module_help, run_python_script_help

REPO_ROOT = Path(__file__).resolve().parents[2]
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
        "telegram_bot_token_file": None,
        "telegram_chat_id": None,
    }
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
    assert "--manage-module ids.ops.operator_console_manage" in service_text
    assert "--app-module ids.console.server" in service_text
    assert "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR=/opt/ids_ml_new/ids/console/templates" in service_text
    assert "IDS_OPERATOR_CONSOLE_STATIC_DIR=/opt/ids_ml_new/ids/console/static" in service_text
    assert "python3 -m ids.ops.operator_console_preflight" in service_text
    assert "python3 -m ids.console.server" in service_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE" in service_text

    assert "-m ids.ops.operator_console_manage --database-path \"$IDS_OPERATOR_CONSOLE_DATABASE_PATH\" notify-worker" in notify_service_text
    assert "--iterations 1" not in notify_service_text
    assert "notify-worker --poll-interval-seconds 30" in notify_service_text
    assert "--manage-module ids.ops.operator_console_manage" in notify_service_text
    assert "--app-module ids.console.server" in notify_service_text
    assert "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR=/opt/ids_ml_new/ids/console/templates" in notify_service_text
    assert "IDS_OPERATOR_CONSOLE_STATIC_DIR=/opt/ids_ml_new/ids/console/static" in notify_service_text
    assert "python3 -m ids.ops.operator_console_preflight" in notify_service_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE" in notify_service_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID" in notify_service_text

    assert "proxy_set_header Host $host;" in nginx_text
    assert "proxy_set_header X-Forwarded-Proto https;" in nginx_text
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in nginx_text


def test_preflight_rejects_notification_enabled_missing_manage_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_preflight_config(
        tmp_path,
        manage_module=None,
        telegram_bot_token="token",
        telegram_chat_id="-100preflight",
    )
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="manage_module"):
        validate_preflight(config)


def test_preflight_rejects_chat_only_pairing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path, telegram_bot_token=None, telegram_chat_id="-100chat-only")
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="must be set together"):
        validate_preflight(config)


@pytest.mark.parametrize(
    ("app_module", "error_match"),
    [
        ("   ", "app_module must not be blank"),
        ("ids..console.server", "app_module must be a dotted Python module path"),
    ],
)
def test_preflight_rejects_blank_or_malformed_app_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    app_module: str,
    error_match: str,
) -> None:
    config = _make_preflight_config(tmp_path, app_module=app_module)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match=error_match):
        validate_preflight(config)


def test_preflight_rejects_non_importable_manage_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_preflight_config(
        tmp_path,
        manage_module="ids.ops.does_not_exist",
        telegram_bot_token="token",
        telegram_chat_id="-100preflight",
    )
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(
        ValueError,
        match="manage_module is not importable by python_binary: ids.ops.does_not_exist",
    ):
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
                "--app-module",
                str(config.app_module),
                "--manage-module",
                str(config.manage_module),
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


def test_script_wrapper_help_runs_through_module_entrypoint() -> None:
    help_run = run_python_module_help("scripts.ids_operator_console_preflight")
    assert_help_smoke(help_run, "scripts.ids_operator_console_preflight")
    assert "usage:" in help_run.stdout.lower()


def test_script_wrapper_help_runs_through_direct_file_entrypoint() -> None:
    help_run = run_python_script_help("scripts/ids_operator_console_preflight.py")
    assert_help_smoke(help_run, "scripts/ids_operator_console_preflight.py")
    assert "usage:" in help_run.stdout.lower()
