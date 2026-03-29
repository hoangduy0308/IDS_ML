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
    _make_executable(tmp_path / "bin" / "java")
    _make_executable(tmp_path / "bin" / "Cmd")

    secret_key_file = tmp_path / "secrets" / "console.secret"
    secret_key_file.parent.mkdir(parents=True, exist_ok=True)
    secret_key_file.write_text("production-secret\n", encoding="utf-8")

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
        java_binary=tmp_path / "bin" / "java",
        extractor_binary=tmp_path / "bin" / "Cmd",
        jnetpcap_path=tmp_path / "lib" / "jnetpcap.jar",
        spool_dir=tmp_path / "runtime" / "sensor",
        alerts_output_path=tmp_path / "logs" / "ids_live_alerts.jsonl",
        quarantine_output_path=tmp_path / "logs" / "ids_live_quarantine.jsonl",
        summary_output_path=tmp_path / "logs" / "ids_live_sensor_summary.jsonl",
        candidate_bundle_root=tmp_path / "bundles" / "candidate",
        admin_username="admin",
        admin_password="correct-password",
    )


def test_validate_stack_preflight_bootstrap_or_preflight_delegates_component_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    config.jnetpcap_path.parent.mkdir(parents=True, exist_ok=True)
    config.jnetpcap_path.write_text("jar\n", encoding="utf-8")

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
    assert operator_calls and operator_calls[0].database_path == (
        tmp_path / "runtime" / "operator_console.db"
    ).resolve()
    assert payload["host_layout"]["operator_env_file"] == str(config.operator_env_file.resolve())


def test_validate_stack_preflight_bootstrap_or_preflight_requires_operator_env_file(
    tmp_path: Path,
) -> None:
    config = _build_config(tmp_path)
    config.operator_env_file.unlink()

    with pytest.raises(FileNotFoundError, match="operator_env_file not found"):
        stack.validate_stack_preflight(config)


def test_run_stack_bootstrap_bootstrap_or_preflight_executes_canonical_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path, telegram_enabled=True)

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
            "--password",
            "correct-password",
        ],
        ["systemctl", "start", "ids-operator-console.service"],
        ["systemctl", "start", "ids-live-sensor.service"],
        ["systemctl", "start", "ids-operator-console-notify.service"],
    ]


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
            "--java-binary",
            str(config.java_binary),
            "--extractor-binary",
            str(config.extractor_binary),
            "--jnetpcap-path",
            str(config.jnetpcap_path),
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
            "--java-binary",
            str(config.java_binary),
            "--extractor-binary",
            str(config.extractor_binary),
            "--jnetpcap-path",
            str(config.jnetpcap_path),
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
