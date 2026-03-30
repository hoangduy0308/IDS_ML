from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.ids_same_host_stack as stack  # noqa: E402
import scripts.ids_same_host_stack_manage as manage  # noqa: E402


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _write_operator_env(
    path: Path,
    *,
    database_path: Path,
    summary_output_path: Path,
    secret_key_file: Path,
    telegram_enabled: bool = False,
) -> Path:
    lines = [
        f"IDS_OPERATOR_CONSOLE_DATABASE_PATH={database_path}",
        f"IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH={summary_output_path}",
        f"IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE={secret_key_file}",
    ]
    if telegram_enabled:
        lines.extend(
            [
                "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN=test-token",
                "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID=-100stack",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _build_config(
    tmp_path: Path,
    *,
    telegram_enabled: bool = False,
) -> stack.SameHostStackConfig:
    repo_root = tmp_path / "repo"
    (repo_root / "scripts" / "ids_operator_console" / "templates").mkdir(parents=True, exist_ok=True)
    (repo_root / "scripts" / "ids_operator_console" / "static").mkdir(parents=True, exist_ok=True)
    model_manage = repo_root / "scripts" / "ids_model_bundle_manage.py"
    operator_manage = repo_root / "scripts" / "ids_operator_console_manage.py"
    operator_server = repo_root / "scripts" / "ids_operator_console_server.py"
    model_manage.write_text("print('model-manage')\n", encoding="utf-8")
    operator_manage.write_text("print('operator-manage')\n", encoding="utf-8")
    operator_server.write_text("print('operator-server')\n", encoding="utf-8")

    python_binary = _make_executable(tmp_path / "bin" / "python3")
    _make_executable(tmp_path / "bin" / "dumpcap")
    extractor_binary = _make_executable(tmp_path / "bin" / "extractor")

    secret_key_file = tmp_path / "secrets" / "console.secret"
    secret_key_file.parent.mkdir(parents=True, exist_ok=True)
    secret_key_file.write_text("production-secret\n", encoding="utf-8")
    admin_password_file = tmp_path / "secrets" / "admin.password"
    admin_password_file.write_text("correct-password\n", encoding="utf-8")

    operator_env_file = _write_operator_env(
        tmp_path / "etc" / "ids-operator-console.env",
        database_path=tmp_path / "runtime" / "operator_console.db",
        summary_output_path=tmp_path / "logs" / "ids_live_sensor_summary.jsonl",
        secret_key_file=secret_key_file,
        telegram_enabled=telegram_enabled,
    )

    return stack.SameHostStackConfig(
        repo_root=repo_root,
        python_binary=python_binary,
        operator_env_file=operator_env_file,
        model_manage_entrypoint=model_manage,
        operator_manage_entrypoint=operator_manage,
        operator_server_entrypoint=operator_server,
        activation_path=tmp_path / "runtime" / "active_bundle.json",
        live_sensor_interface="eth0",
        dumpcap_binary=tmp_path / "bin" / "dumpcap",
        extractor_command_prefix=(str(extractor_binary),),
        spool_dir=tmp_path / "runtime" / "sensor",
        alerts_output_path=tmp_path / "logs" / "ids_live_alerts.jsonl",
        quarantine_output_path=tmp_path / "logs" / "ids_live_quarantine.jsonl",
        summary_output_path=tmp_path / "logs" / "ids_live_sensor_summary.jsonl",
        candidate_bundle_root=tmp_path / "bundles" / "candidate",
        admin_username="admin",
        admin_password_file=admin_password_file,
    )


def _write_backup_artifacts(
    backup_dir: Path,
    *,
    database_path: Path,
    secret_key_source: str = "file",
    telegram_source: str | None = None,
) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_database = backup_dir / "operator_console.db"
    backup_database.write_text("sqlite-backup\n", encoding="utf-8")
    manifest = {
        "database": {
            "backup_file": backup_database.name,
        },
        "secret_references": {
            "secret_key": {
                "configured": True,
                "source": secret_key_source,
            },
            "telegram_bot_token": {
                "configured": telegram_source is not None,
                "source": telegram_source,
            },
        },
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.write_text("restored-db\n", encoding="utf-8")
    return manifest_path


def test_validate_stack_preflight_bootstrap_or_preflight_delegates_component_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)

    sensor_calls: list[stack.LiveSensorPreflightConfig] = []
    operator_calls: list[stack.OperatorConsolePreflightConfig] = []

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {
            "runtime_ready": True,
            "activation_path": str(path),
            "active_bundle_name": "bundle-under-test",
        },
    )
    monkeypatch.setattr(
        stack,
        "validate_live_sensor_preflight",
        lambda preflight_config: sensor_calls.append(preflight_config),
    )
    monkeypatch.setattr(
        stack,
        "validate_operator_console_preflight",
        lambda preflight_config: operator_calls.append(preflight_config),
    )

    payload = stack.validate_stack_preflight(config)

    assert payload["ready"] is True
    assert payload["components"]["notification"]["status"] == "disabled"
    assert sensor_calls and sensor_calls[0].summary_output_path == config.summary_output_path.resolve()
    assert sensor_calls and sensor_calls[0].extractor_command_prefix == config.extractor_command_prefix
    assert operator_calls and operator_calls[0].database_path == (
        tmp_path / "runtime" / "operator_console.db"
    ).resolve()
    assert payload["host_layout"]["operator_env_file"] == str(config.operator_env_file.resolve())


def test_validate_stack_preflight_bootstrap_or_preflight_requires_operator_env_file(
    tmp_path: Path,
) -> None:
    config = _build_config(tmp_path)
    config.operator_env_file.unlink()

    payload = stack.validate_stack_preflight(config)

    assert payload["ready"] is False
    assert payload["status"] == "degraded"
    assert payload["host_layout_checks"]["operator_env_file"]["state"] == "missing"
    assert payload["components"]["operator_config"]["status"] == "degraded"


def test_run_stack_bootstrap_bootstrap_or_preflight_executes_canonical_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(
        _build_config(tmp_path, telegram_enabled=True),
        proxy_public_url="https://console.example",
    )

    executed: list[list[str]] = []

    def fake_runner(argv: list[str] | tuple[str, ...]) -> str:
        command = [str(part) for part in argv]
        executed.append(command)
        if "verify" in command:
            return json.dumps({"action": "verify", "status": "ok"})
        if "promote" in command:
            return json.dumps({"action": "promote", "status": "ok"})
        if "migrate" in command:
            return json.dumps({"action": "migrate", "status": "ok"})
        if "bootstrap-admin" in command:
            return json.dumps({"action": "bootstrap-admin", "status": "ok"})
        return ""

    monkeypatch.setattr(
        stack,
        "validate_stack_preflight",
        lambda current_config: {"ready": True, "command": "preflight", "config": str(current_config.repo_root)},
    )
    monkeypatch.setattr(
        stack,
        "build_stack_status_payload",
        lambda *_args, **_kwargs: {
            "ready": True,
            "command": "status",
            "components": {
                "reverse_proxy_edge_seam": {
                    "state": "reachable",
                    "gating": False,
                    "payload": {"configured": True},
                }
            },
        },
    )
    monkeypatch.setattr(
        stack,
        "build_stack_smoke_payload",
        lambda *_args, **_kwargs: {
            "ready": True,
            "command": "smoke",
            "components": {
                "reverse_proxy_edge_seam": {
                    "state": "reachable",
                    "gating": False,
                    "payload": {"configured": True},
                }
            },
        },
    )
    monkeypatch.setattr(
        stack,
        "build_notification_component",
        lambda _config, include_sensitive=False: {
            "ok": True,
            "state": "ok",
            "enabled": True,
            "configured": True,
            "target": None,
            "last_error": None,
        },
    )

    payload = stack.run_stack_bootstrap(config, command_runner=fake_runner)

    assert payload["bootstrap_ready"] is True
    assert [step["step"] for step in payload["steps"]] == [
        "prepare_host_layout",
        "verify_candidate_bundle",
        "promote_candidate_bundle",
        "migrate_operator_console",
        "bootstrap_operator_admin",
        "stack_preflight",
        "start_operator_console_service",
        "start_live_sensor_service",
        "start_notification_service",
        "stack_status",
        "stack_smoke",
        "proxy_seam_smoke",
    ]
    assert executed == [
        [
            str(config.python_binary.resolve()),
            str(config.model_manage_entrypoint.resolve()),
            "--activation-path",
            str(config.activation_path.resolve()),
            "--json",
            "verify",
            "--bundle-root",
            str(config.candidate_bundle_root.resolve()),
        ],
        [
            str(config.python_binary.resolve()),
            str(config.model_manage_entrypoint.resolve()),
            "--activation-path",
            str(config.activation_path.resolve()),
            "--json",
            "promote",
            "--bundle-root",
            str(config.candidate_bundle_root.resolve()),
        ],
        [
            str(config.python_binary.resolve()),
            str(config.operator_manage_entrypoint.resolve()),
            "--database-path",
            str((tmp_path / "runtime" / "operator_console.db").resolve()),
            "--json",
            "migrate",
            "--allow-bootstrap",
        ],
        [
            str(config.python_binary.resolve()),
            str(config.operator_manage_entrypoint.resolve()),
            "--database-path",
            str((tmp_path / "runtime" / "operator_console.db").resolve()),
            "--json",
            "bootstrap-admin",
            "--username",
            "admin",
            "--password-file",
            str(config.admin_password_file.resolve()),
        ],
        ["systemctl", "start", "ids-operator-console.service"],
        ["systemctl", "start", "ids-live-sensor.service"],
        ["systemctl", "start", "ids-operator-console-notify.service"],
    ]
    assert payload["diagnosis"]["status"]["command"] == "status"
    assert payload["diagnosis"]["smoke"]["command"] == "smoke"


def test_run_stack_bootstrap_bootstrap_or_preflight_reports_degraded_post_start_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)

    def fake_runner(argv: list[str] | tuple[str, ...]) -> str:
        command = [str(part) for part in argv]
        if "verify" in command:
            return json.dumps({"action": "verify", "status": "ok"})
        if "promote" in command:
            return json.dumps({"action": "promote", "status": "ok"})
        if "migrate" in command:
            return json.dumps({"action": "migrate", "status": "ok"})
        if "bootstrap-admin" in command:
            return json.dumps({"action": "bootstrap-admin", "status": "ok"})
        return ""

    monkeypatch.setattr(
        stack,
        "validate_stack_preflight",
        lambda *_args, **_kwargs: {"ready": True, "command": "preflight"},
    )
    monkeypatch.setattr(
        stack,
        "build_stack_status_payload",
        lambda *_args, **_kwargs: {
            "ready": False,
            "command": "status",
            "components": {"reverse_proxy_edge_seam": {"payload": {"configured": False}}},
        },
    )
    monkeypatch.setattr(
        stack,
        "build_stack_smoke_payload",
        lambda *_args, **_kwargs: {
            "ready": False,
            "command": "smoke",
            "components": {"reverse_proxy_edge_seam": {"payload": {"configured": False}}},
        },
    )

    payload = stack.run_stack_bootstrap(config, command_runner=fake_runner)

    assert payload["bootstrap_ready"] is False
    assert payload["status"] == "degraded"


def test_manage_main_bootstrap_or_preflight_prints_json_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _build_config(tmp_path)

    def fake_validate(_: stack.SameHostStackConfig) -> dict[str, object]:
        return {"ready": True, "command": "preflight"}

    monkeypatch.setattr(manage, "validate_stack_preflight", fake_validate)

    exit_code = manage.main(
        [
            "--repo-root",
            str(config.repo_root),
            "--python-binary",
            str(config.python_binary),
            "--operator-env-file",
            str(config.operator_env_file),
            "--activation-path",
            str(config.activation_path),
            "--dumpcap-binary",
            str(config.dumpcap_binary),
            "--extractor-command-prefix",
            *config.extractor_command_prefix,
            "--spool-dir",
            str(config.spool_dir),
            "--alerts-output-path",
            str(config.alerts_output_path),
            "--quarantine-output-path",
            str(config.quarantine_output_path),
            "--summary-output-path",
            str(config.summary_output_path),
            "--json",
            "preflight",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["command"] == "preflight"


def test_manage_main_bootstrap_returns_degraded_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _build_config(tmp_path)

    monkeypatch.setattr(
        manage,
        "run_stack_bootstrap",
        lambda *_args, **_kwargs: {"bootstrap_ready": False, "command": "bootstrap"},
    )

    exit_code = manage.main(
        [
            "--repo-root",
            str(config.repo_root),
            "--python-binary",
            str(config.python_binary),
            "--operator-env-file",
            str(config.operator_env_file),
            "--activation-path",
            str(config.activation_path),
            "--dumpcap-binary",
            str(config.dumpcap_binary),
            "--extractor-command-prefix",
            *config.extractor_command_prefix,
            "--spool-dir",
            str(config.spool_dir),
            "--alerts-output-path",
            str(config.alerts_output_path),
            "--quarantine-output-path",
            str(config.quarantine_output_path),
            "--summary-output-path",
            str(config.summary_output_path),
            "--json",
            "bootstrap",
            "--candidate-bundle-root",
            str(config.candidate_bundle_root),
            "--admin-username",
            "admin",
            "--admin-password-file",
            str(config.admin_password_file),
        ]
    )

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out)["command"] == "bootstrap"


def test_build_stack_status_payload_status_or_smoke_keeps_failure_domains_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {"runtime_ready": True, "activation_path": str(path)},
    )
    monkeypatch.setattr(
        stack,
        "build_live_sensor_health_payload",
        lambda *_args, **_kwargs: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "build_readiness_payload",
        lambda _config: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "build_notification_component",
        lambda _config, include_sensitive=True: {
            "ok": True,
            "state": "disabled",
            "enabled": False,
        },
    )

    payload = stack.build_stack_status_payload(config)

    assert payload["ready"] is True
    assert set(payload["components"]) == {
        "model_activation_contract",
        "live_sensor_data_path",
        "operator_visibility_path",
        "outbound_notification_path",
        "reverse_proxy_edge_seam",
    }
    assert payload["components"]["outbound_notification_path"]["state"] == "disabled"
    assert payload["components"]["reverse_proxy_edge_seam"]["state"] == "unconfigured"


def test_build_stack_smoke_payload_status_or_smoke_keeps_proxy_non_gating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(_build_config(tmp_path), proxy_public_url="https://console.example")

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {"runtime_ready": True, "activation_path": str(path)},
    )
    monkeypatch.setattr(
        stack,
        "build_live_sensor_health_payload",
        lambda *_args, **_kwargs: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "run_smoke_checks",
        lambda _config: SimpleNamespace(
            health_status=200,
            readiness_status=200,
            redirect_status=307,
            readiness_payload={"ready": True, "status": "ok"},
        ),
    )
    monkeypatch.setattr(
        stack,
        "build_notification_component",
        lambda _config, include_sensitive=True: {
            "ok": True,
            "state": "disabled",
            "enabled": False,
        },
    )

    payload = stack.build_stack_smoke_payload(
        config,
        proxy_checker=lambda _url, _timeout: (502, None),
    )

    assert payload["ready"] is True
    assert payload["components"]["operator_visibility_path"]["payload"]["redirect_status"] == 307
    assert payload["components"]["reverse_proxy_edge_seam"]["state"] == "degraded"
    assert payload["components"]["reverse_proxy_edge_seam"]["gating"] is False


def test_build_stack_status_payload_status_or_smoke_returns_degraded_payload_on_contract_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda _path: (_ for _ in ()).throw(json.JSONDecodeError("bad json", "{", 1)),
    )
    monkeypatch.setattr(
        stack,
        "build_live_sensor_health_payload",
        lambda *_args, **_kwargs: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "build_readiness_payload",
        lambda _config: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "build_notification_component",
        lambda _config, include_sensitive=False: {
            "ok": True,
            "state": "disabled",
            "enabled": False,
            "target": None,
            "last_error": None,
        },
    )

    payload = stack.build_stack_status_payload(config)

    assert payload["ready"] is False
    bundle_component = payload["components"]["model_activation_contract"]
    assert bundle_component["state"] == "invalid"
    assert bundle_component["payload"]["error_type"] == "JSONDecodeError"


def test_build_stack_status_payload_status_or_smoke_redacts_notification_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path, telegram_enabled=True)

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {"runtime_ready": True, "activation_path": str(path)},
    )
    monkeypatch.setattr(
        stack,
        "build_live_sensor_health_payload",
        lambda *_args, **_kwargs: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "build_readiness_payload",
        lambda _config: {"ready": True, "status": "ok"},
    )

    captured_sensitive_flags: list[bool] = []

    def fake_notification_component(_config: object, include_sensitive: bool = False) -> dict[str, object]:
        captured_sensitive_flags.append(include_sensitive)
        return {
            "ok": True,
            "state": "ok",
            "enabled": True,
            "target": None,
            "last_error": None,
        }

    monkeypatch.setattr(stack, "build_notification_component", fake_notification_component)

    payload = stack.build_stack_status_payload(config)

    assert payload["ready"] is True
    assert captured_sensitive_flags == [False]
    assert payload["components"]["outbound_notification_path"]["payload"]["target"] is None


def test_manage_main_status_or_smoke_prints_json_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _build_config(tmp_path)

    monkeypatch.setattr(
        manage,
        "build_stack_status_payload",
        lambda _: {"ready": True, "command": "status"},
    )

    exit_code = manage.main(
        [
            "--repo-root",
            str(config.repo_root),
            "--python-binary",
            str(config.python_binary),
            "--operator-env-file",
            str(config.operator_env_file),
            "--activation-path",
            str(config.activation_path),
            "--dumpcap-binary",
            str(config.dumpcap_binary),
            "--extractor-command-prefix",
            *config.extractor_command_prefix,
            "--spool-dir",
            str(config.spool_dir),
            "--alerts-output-path",
            str(config.alerts_output_path),
            "--quarantine-output-path",
            str(config.quarantine_output_path),
            "--summary-output-path",
            str(config.summary_output_path),
            "--json",
            "status",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["command"] == "status"


def test_build_password_args_bootstrap_or_preflight_rejects_inline_password(tmp_path: Path) -> None:
    config = replace(_build_config(tmp_path), admin_password="inline-secret", admin_password_file=None)

    with pytest.raises(ValueError, match="inline admin_password is not supported"):
        stack._build_password_args(config)


def test_run_command_bootstrap_or_preflight_redacts_inline_password_on_failure() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        stack.run_command(
            [
                "python",
                "child.py",
                "--username",
                "admin",
                "--password",
                "super-secret",
            ]
        )

    message = str(exc_info.value)
    assert "super-secret" not in message
    assert "***REDACTED***" in message


def test_run_stack_recovery_restart_or_recovery_path_executes_supervisor_first_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path, telegram_enabled=True)

    executed: list[list[str]] = []

    def fake_runner(argv: list[str] | tuple[str, ...]) -> str:
        command = [str(part) for part in argv]
        executed.append(command)
        return ""

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {"runtime_ready": True, "activation_path": str(path)},
    )
    monkeypatch.setattr(
        stack,
        "build_live_sensor_health_payload",
        lambda *_args, **_kwargs: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "build_readiness_payload",
        lambda _config: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "run_smoke_checks",
        lambda _config: SimpleNamespace(
            health_status=200,
            readiness_status=200,
            redirect_status=307,
            readiness_payload={"ready": True, "status": "ok"},
        ),
    )
    monkeypatch.setattr(
        stack,
        "build_notification_component",
        lambda _config, include_sensitive=True: {
            "ok": True,
            "state": "ok",
            "enabled": True,
        },
    )

    payload = stack.run_stack_recovery(
        config,
        command_runner=fake_runner,
        proxy_checker=lambda _url, _timeout: (200, "https://console.example"),
    )

    assert payload["recovery_ready"] is True
    assert [step["step"] for step in payload["steps"]] == [
        "verify_activation_contract",
        "restart_live_sensor_service",
        "restart_operator_console_service",
        "restart_notification_service",
        "stack_status",
        "stack_smoke",
    ]
    assert executed == [
        ["systemctl", "restart", "ids-live-sensor.service"],
        ["systemctl", "restart", "ids-operator-console.service"],
        ["systemctl", "restart", "ids-operator-console-notify.service"],
    ]
    assert payload["diagnosis"]["status"]["command"] == "status"
    assert payload["diagnosis"]["smoke"]["command"] == "smoke"


def test_run_stack_recovery_restart_or_recovery_path_reports_degraded_diagnosis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)

    executed: list[list[str]] = []

    def fake_runner(argv: list[str] | tuple[str, ...]) -> str:
        command = [str(part) for part in argv]
        executed.append(command)
        return ""

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {"runtime_ready": True, "activation_path": str(path)},
    )
    monkeypatch.setattr(
        stack,
        "build_live_sensor_health_payload",
        lambda *_args, **_kwargs: {"ready": False, "status": "degraded"},
    )
    monkeypatch.setattr(
        stack,
        "build_readiness_payload",
        lambda _config: {"ready": True, "status": "ok"},
    )
    monkeypatch.setattr(
        stack,
        "run_smoke_checks",
        lambda _config: SimpleNamespace(
            health_status=200,
            readiness_status=503,
            redirect_status=307,
            readiness_payload={"ready": False, "status": "degraded"},
        ),
    )
    monkeypatch.setattr(
        stack,
        "build_notification_component",
        lambda _config, include_sensitive=True: {
            "ok": True,
            "state": "disabled",
            "enabled": False,
        },
    )

    payload = stack.run_stack_recovery(config, command_runner=fake_runner)

    assert payload["recovery_ready"] is False
    assert payload["notification_enabled"] is False
    assert executed == [
        ["systemctl", "restart", "ids-live-sensor.service"],
        ["systemctl", "restart", "ids-operator-console.service"],
    ]
    assert payload["steps"][3]["step"] == "notification_service_disabled"
    assert (
        payload["diagnosis"]["status"]["components"]["outbound_notification_path"]["state"]
        == "disabled"
    )
    assert (
        payload["diagnosis"]["status"]["components"]["live_sensor_data_path"]["state"]
        == "degraded"
    )


def test_manage_main_restart_or_recovery_path_prints_json_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _build_config(tmp_path)

    monkeypatch.setattr(
        manage,
        "run_stack_recovery",
        lambda _: {"recovery_ready": True, "command": "recover"},
    )

    exit_code = manage.main(
        [
            "--repo-root",
            str(config.repo_root),
            "--python-binary",
            str(config.python_binary),
            "--operator-env-file",
            str(config.operator_env_file),
            "--activation-path",
            str(config.activation_path),
            "--dumpcap-binary",
            str(config.dumpcap_binary),
            "--extractor-command-prefix",
            *config.extractor_command_prefix,
            "--spool-dir",
            str(config.spool_dir),
            "--alerts-output-path",
            str(config.alerts_output_path),
            "--quarantine-output-path",
            str(config.quarantine_output_path),
            "--summary-output-path",
            str(config.summary_output_path),
            "--json",
            "recover",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["command"] == "recover"


def test_build_stack_restore_inventory_restore_or_post_restore_checks_minimum_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    active_bundle_root = tmp_path / "bundles" / "active"
    previous_bundle_root = tmp_path / "bundles" / "previous"
    active_bundle_root.mkdir(parents=True, exist_ok=True)
    previous_bundle_root.mkdir(parents=True, exist_ok=True)
    backup_dir = tmp_path / "backups" / "backup-20260329T010203000000Z"
    _write_backup_artifacts(
        backup_dir,
        database_path=tmp_path / "runtime" / "operator_console.db",
    )
    config = replace(config, operator_backup_dir=backup_dir)

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {
            "runtime_ready": True,
            "activation_path": str(path),
            "active_bundle_root": str(active_bundle_root),
            "previous_bundle_root": str(previous_bundle_root),
        },
    )

    payload = stack.build_stack_restore_inventory_payload(config)

    assert payload["inventory_ready"] is True
    assert (
        payload["components"]["activation_restore_state"]["payload"]["referenced_bundle_roots"][0]["path"]
        == str(active_bundle_root.resolve())
    )
    assert (
        payload["components"]["operator_console_restore_state"]["payload"]["secret_references"]["secret_key"]["state"]
        == "bound"
    )
    assert payload["components"]["live_sensor_operator_evidence"]["gating"] is False
    assert (
        payload["components"]["live_sensor_operator_evidence"]["payload"]["primary_restore_state"]
        is False
    )


def test_build_stack_restore_inventory_restore_or_post_restore_selects_latest_backup_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    backup_root = tmp_path / "backups"
    older_backup = backup_root / "backup-20260328T010203000000Z"
    newer_backup = backup_root / "backup-20260329T010203000000Z"
    _write_backup_artifacts(older_backup, database_path=tmp_path / "runtime" / "operator_console.db")
    _write_backup_artifacts(newer_backup, database_path=tmp_path / "runtime" / "operator_console.db")
    config = replace(config, operator_backup_dir=backup_root)

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {"runtime_ready": True, "activation_path": str(path)},
    )

    payload = stack.build_stack_restore_inventory_payload(config)

    assert payload["inventory_ready"] is True
    assert (
        payload["components"]["operator_console_restore_state"]["payload"]["backup_dir"]
        == str(newer_backup.resolve())
    )


def test_build_stack_restore_inventory_restore_or_post_restore_reports_missing_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    backup_dir = tmp_path / "backups" / "backup-20260329T010203000000Z"
    backup_dir.mkdir(parents=True, exist_ok=True)
    config = replace(config, operator_backup_dir=backup_dir)

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {"runtime_ready": True, "activation_path": str(path)},
    )

    payload = stack.build_stack_restore_inventory_payload(config)

    assert payload["inventory_ready"] is False
    operator_state = payload["components"]["operator_console_restore_state"]
    assert operator_state["state"] == "degraded"
    assert operator_state["payload"]["error_type"] == "FileNotFoundError"


def test_build_stack_restore_inventory_restore_or_post_restore_reports_secret_rebind_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    backup_dir = tmp_path / "backups" / "backup-20260329T010203000000Z"
    _write_backup_artifacts(
        backup_dir,
        database_path=tmp_path / "runtime" / "operator_console.db",
        secret_key_source="env",
    )
    config = replace(config, operator_backup_dir=backup_dir)

    bad_secret = tmp_path / "etc" / "bad.env"
    bad_secret.parent.mkdir(parents=True, exist_ok=True)
    bad_secret.write_text(
        "\n".join(
                [
                    f"IDS_OPERATOR_CONSOLE_DATABASE_PATH={tmp_path / 'runtime' / 'operator_console.db'}",
                    f"IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH={tmp_path / 'logs' / 'ids_live_sensor_summary.jsonl'}",
                    "IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE=",
                    "IDS_OPERATOR_CONSOLE_SECRET_KEY=change-me",
                ]
            )
            + "\n",
        encoding="utf-8",
    )
    config = replace(config, operator_env_file=bad_secret)

    monkeypatch.setattr(
        stack,
        "build_bundle_status_payload",
        lambda path: {"runtime_ready": True, "activation_path": str(path)},
    )

    payload = stack.build_stack_restore_inventory_payload(config)

    assert payload["inventory_ready"] is False
    operator_state = payload["components"]["operator_console_restore_state"]
    assert operator_state["detail"] == "production secret_key must not use a placeholder value"


def test_run_stack_post_restore_check_restore_or_post_restore_redrives_notifications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(
        _build_config(tmp_path, telegram_enabled=True),
        operator_backup_dir=tmp_path / "backups" / "backup-20260329T010203000000Z",
        notification_redrive_limit=7,
    )

    monkeypatch.setattr(
        stack,
        "build_stack_restore_inventory_payload",
        lambda _config: {"inventory_ready": True, "command": "restore-inventory"},
    )
    monkeypatch.setattr(
        stack,
        "validate_live_sensor_preflight",
        lambda _config: None,
    )
    monkeypatch.setattr(
        stack,
        "run_stack_recovery",
        lambda *_args, **_kwargs: {"recovery_ready": True, "command": "recover"},
    )
    monkeypatch.setattr(
        stack,
        "notification_status",
        lambda _config: {
            "ok": False,
            "enabled": True,
            "state": "degraded",
            "failed_count": 2,
        },
    )

    redrive_calls: list[int] = []

    monkeypatch.setattr(
        stack,
        "redrive_notification_failures",
        lambda _config, limit: (
            redrive_calls.append(limit)
            or SimpleNamespace(
                redriven=2,
                status={
                    "ok": True,
                    "enabled": True,
                    "state": "ok",
                    "failed_count": 0,
                    "pending_count": 2,
                },
            )
        ),
    )
    monkeypatch.setattr(
        stack,
        "build_stack_status_payload",
        lambda *_args, **_kwargs: {
            "ready": True,
            "command": "status",
            "components": {
                "operator_visibility_path": {
                    "payload": {
                        "components": {
                            "active_bundle": {
                                "ok": True,
                                "state": {
                                    "active_bundle_name": "bundle-a",
                                },
                            }
                        }
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        stack,
        "build_notification_component",
        lambda _config, include_sensitive=False: {
            "ok": False,
            "state": "degraded",
            "enabled": True,
            "configured": True,
            "failed_count": 2,
            "target": None,
            "last_error": None,
        },
    )
    monkeypatch.setattr(
        stack,
        "build_stack_smoke_payload",
        lambda *_args, **_kwargs: {"ready": True, "command": "smoke"},
    )

    payload = stack.run_stack_post_restore_check(config)

    assert payload["post_restore_ready"] is True
    assert [step["step"] for step in payload["steps"]] == [
        "restore_inventory",
        "live_sensor_preflight_revalidation",
        "stack_recovery",
        "notification_status",
        "notification_redrive",
        "final_status",
        "final_smoke",
    ]
    assert redrive_calls == [7]
    assert payload["diagnosis"]["bundle_visibility_reestablished"]["state"] == "reestablished"


def test_run_stack_post_restore_check_restore_or_post_restore_skips_disabled_notification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(
        _build_config(tmp_path),
        operator_backup_dir=tmp_path / "backups" / "backup-20260329T010203000000Z",
    )

    monkeypatch.setattr(
        stack,
        "build_stack_restore_inventory_payload",
        lambda _config: {"inventory_ready": True, "command": "restore-inventory"},
    )
    monkeypatch.setattr(
        stack,
        "validate_live_sensor_preflight",
        lambda _config: None,
    )
    monkeypatch.setattr(
        stack,
        "run_stack_recovery",
        lambda *_args, **_kwargs: {"recovery_ready": True, "command": "recover"},
    )
    monkeypatch.setattr(
        stack,
        "build_stack_status_payload",
        lambda *_args, **_kwargs: {
            "ready": True,
            "command": "status",
            "components": {
                "operator_visibility_path": {
                    "payload": {
                        "components": {
                            "active_bundle": {
                                "ok": True,
                                "state": {
                                    "active_bundle_name": "bundle-a",
                                },
                            }
                        }
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        stack,
        "build_stack_smoke_payload",
        lambda *_args, **_kwargs: {"ready": True, "command": "smoke"},
    )

    payload = stack.run_stack_post_restore_check(config)

    assert payload["post_restore_ready"] is True
    assert payload["steps"][3]["step"] == "notification_disabled"
    assert payload["steps"][3]["result"]["state"] == "disabled"


def test_run_stack_post_restore_check_restore_or_post_restore_blocks_failed_notification_redrive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(
        _build_config(tmp_path, telegram_enabled=True),
        operator_backup_dir=tmp_path / "backups" / "backup-20260329T010203000000Z",
        notification_redrive_limit=3,
    )

    monkeypatch.setattr(
        stack,
        "build_stack_restore_inventory_payload",
        lambda _config: {"inventory_ready": True, "command": "restore-inventory"},
    )
    monkeypatch.setattr(stack, "validate_live_sensor_preflight", lambda _config: None)
    monkeypatch.setattr(
        stack,
        "run_stack_recovery",
        lambda *_args, **_kwargs: {"recovery_ready": True, "command": "recover"},
    )
    monkeypatch.setattr(
        stack,
        "notification_status",
        lambda _config: {"ok": False, "enabled": True, "state": "degraded", "failed_count": 2},
    )
    monkeypatch.setattr(
        stack,
        "build_notification_component",
        lambda _config, include_sensitive=False: {
            "ok": False,
            "state": "degraded",
            "enabled": True,
            "configured": True,
            "failed_count": 2,
            "target": None,
            "last_error": None,
        },
    )
    monkeypatch.setattr(
        stack,
        "redrive_notification_failures",
        lambda _config, limit: SimpleNamespace(
            redriven=0,
            status={"ok": False, "enabled": True, "state": "degraded", "failed_count": 2},
        ),
    )
    monkeypatch.setattr(
        stack,
        "build_stack_status_payload",
        lambda *_args, **_kwargs: {
            "ready": True,
            "command": "status",
            "components": {
                "operator_visibility_path": {
                    "payload": {"components": {"active_bundle": {"ok": True, "state": {"active_bundle_name": "bundle-a"}}}}
                }
            },
        },
    )
    monkeypatch.setattr(
        stack,
        "build_stack_smoke_payload",
        lambda *_args, **_kwargs: {"ready": True, "command": "smoke"},
    )

    payload = stack.run_stack_post_restore_check(config)

    assert payload["post_restore_ready"] is False
    assert payload["steps"][4]["step"] == "notification_redrive"
    assert payload["steps"][4]["result"]["status"]["state"] == "degraded"


@pytest.mark.parametrize("failing_field", ["status", "smoke", "bundle_visibility"])
def test_run_stack_post_restore_check_restore_or_post_restore_blocks_failed_final_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failing_field: str,
) -> None:
    config = replace(
        _build_config(tmp_path),
        operator_backup_dir=tmp_path / "backups" / "backup-20260329T010203000000Z",
    )

    monkeypatch.setattr(
        stack,
        "build_stack_restore_inventory_payload",
        lambda _config: {"inventory_ready": True, "command": "restore-inventory"},
    )
    monkeypatch.setattr(stack, "validate_live_sensor_preflight", lambda _config: None)
    monkeypatch.setattr(
        stack,
        "run_stack_recovery",
        lambda *_args, **_kwargs: {"recovery_ready": True, "command": "recover"},
    )
    monkeypatch.setattr(
        stack,
        "build_stack_status_payload",
        lambda *_args, **_kwargs: {
            "ready": failing_field != "status",
            "command": "status",
            "components": {
                "operator_visibility_path": {
                    "payload": {
                        "components": {
                            "active_bundle": {
                                "ok": failing_field != "bundle_visibility",
                                "state": {"active_bundle_name": "bundle-a"},
                            }
                        }
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        stack,
        "build_stack_smoke_payload",
        lambda *_args, **_kwargs: {"ready": failing_field != "smoke", "command": "smoke"},
    )

    payload = stack.run_stack_post_restore_check(config)

    assert payload["post_restore_ready"] is False


def test_manage_main_restore_or_post_restore_prints_json_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _build_config(tmp_path)
    backup_dir = tmp_path / "backups" / "backup-20260329T010203000000Z"
    backup_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        manage,
        "run_stack_post_restore_check",
        lambda _: {"post_restore_ready": True, "command": "post-restore-check"},
    )

    exit_code = manage.main(
        [
            "--repo-root",
            str(config.repo_root),
            "--python-binary",
            str(config.python_binary),
            "--operator-env-file",
            str(config.operator_env_file),
            "--activation-path",
            str(config.activation_path),
            "--dumpcap-binary",
            str(config.dumpcap_binary),
            "--extractor-command-prefix",
            *config.extractor_command_prefix,
            "--spool-dir",
            str(config.spool_dir),
            "--alerts-output-path",
            str(config.alerts_output_path),
            "--quarantine-output-path",
            str(config.quarantine_output_path),
            "--summary-output-path",
            str(config.summary_output_path),
            "--json",
            "post-restore-check",
            "--operator-backup-dir",
            str(backup_dir),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["command"] == "post-restore-check"


def test_stack_runbook_runbook_or_docs_matches_cli_surface() -> None:
    runbook = (REPO_ROOT / "docs" / "ids_same_host_stack_operations.md").read_text(
        encoding="utf-8"
    )

    for command_name in (
        "preflight",
        "bootstrap",
        "status",
        "smoke",
        "recover",
        "restore-inventory",
        "post-restore-check",
    ):
        assert f"`{command_name}`" in runbook

    for failure_domain in (
        "model_activation_contract",
        "live_sensor_data_path",
        "operator_visibility_path",
        "outbound_notification_path",
        "reverse_proxy_edge_seam",
    ):
        assert f"`{failure_domain}`" in runbook

    assert "ids_operator_console_manage.py" in runbook
    assert "notify-status" in runbook
    assert "notify-redrive" in runbook
