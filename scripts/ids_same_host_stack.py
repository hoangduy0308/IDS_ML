from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Sequence

from scripts.ids_live_sensor_preflight import (
    LiveSensorPreflightConfig,
    validate_preflight as validate_live_sensor_preflight,
)
from scripts.ids_model_bundle import build_bundle_status_payload
from scripts.ids_operator_console.config import (
    OperatorConsoleConfig,
    load_operator_console_config,
)
from scripts.ids_operator_console_preflight import (
    OperatorConsolePreflightConfig,
    validate_preflight as validate_operator_console_preflight,
)


CommandRunner = Callable[[Sequence[str]], str]


@dataclass(frozen=True)
class SameHostStackConfig:
    repo_root: Path
    python_binary: Path
    operator_env_file: Path
    model_manage_entrypoint: Path
    operator_manage_entrypoint: Path
    operator_server_entrypoint: Path
    activation_path: Path
    live_sensor_interface: str
    dumpcap_binary: Path
    java_binary: Path
    extractor_binary: Path
    jnetpcap_path: Path
    spool_dir: Path
    alerts_output_path: Path
    quarantine_output_path: Path
    summary_output_path: Path
    console_service_name: str = "ids-operator-console.service"
    live_sensor_service_name: str = "ids-live-sensor.service"
    notification_service_name: str = "ids-operator-console-notify.service"
    candidate_bundle_root: Path | None = None
    admin_username: str | None = None
    admin_password: str | None = None
    admin_password_file: Path | None = None


def _require_existing_file(path: Path, *, name: str, executable: bool = False) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if not resolved.is_file():
        raise FileNotFoundError(f"{name} not found: {resolved}")
    if executable and not _is_executable_file(resolved):
        raise PermissionError(f"{name} is not executable: {resolved}")
    return resolved


def _require_existing_directory(path: Path, *, name: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if not resolved.is_dir():
        raise FileNotFoundError(f"{name} not found: {resolved}")
    return resolved


def _is_executable_file(path: Path) -> bool:
    if sys.platform.startswith("win"):
        return True
    return os.access(path, os.X_OK)


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        if "=" not in stripped:
            raise ValueError(f"invalid operator env line {lineno}: {raw_line!r}")
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid operator env line {lineno}: missing key")
        normalized = value.strip()
        if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
            normalized = normalized[1:-1]
        parsed[key] = normalized
    return parsed


def _default_operator_environment(config: SameHostStackConfig) -> dict[str, str]:
    repo_root = Path(config.repo_root).resolve()
    return {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "production",
        "IDS_OPERATOR_CONSOLE_HOST": "127.0.0.1",
        "IDS_OPERATOR_CONSOLE_PORT": "8765",
        "IDS_OPERATOR_CONSOLE_LOG_LEVEL": "info",
        "IDS_OPERATOR_CONSOLE_FORWARDED_ALLOW_IPS": "127.0.0.1",
        "IDS_OPERATOR_CONSOLE_ROOT_PATH": "",
        "IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL": "https://console.example",
        "IDS_OPERATOR_CONSOLE_SESSION_COOKIE_NAME": "ids_operator_session",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": "/var/lib/ids-operator-console/operator_console.db",
        "IDS_OPERATOR_CONSOLE_ALERTS_INPUT_PATH": str(Path(config.alerts_output_path).resolve()),
        "IDS_OPERATOR_CONSOLE_QUARANTINE_INPUT_PATH": str(Path(config.quarantine_output_path).resolve()),
        "IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH": str(Path(config.summary_output_path).resolve()),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(repo_root / "scripts" / "ids_operator_console" / "templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(repo_root / "scripts" / "ids_operator_console" / "static"),
        "IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE": "/etc/ids-operator-console/console.secret",
        "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN": "",
        "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE": "",
        "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID": "",
    }


def load_stack_operator_config(config: SameHostStackConfig) -> OperatorConsoleConfig:
    env_file = _require_existing_file(config.operator_env_file, name="operator_env_file")
    env = _default_operator_environment(config)
    env.update(_parse_env_file(env_file))
    return load_operator_console_config(environ=env, repo_root=Path(config.repo_root).resolve())


def notifications_enabled(config: SameHostStackConfig) -> bool:
    operator_config = load_stack_operator_config(config)
    return operator_config.telegram_bot_token is not None and operator_config.telegram_chat_id is not None


def build_sensor_preflight_config(config: SameHostStackConfig) -> LiveSensorPreflightConfig:
    return LiveSensorPreflightConfig(
        interface=str(config.live_sensor_interface).strip(),
        dumpcap_binary=Path(config.dumpcap_binary).resolve(),
        java_binary=Path(config.java_binary).resolve(),
        extractor_binary=Path(config.extractor_binary).resolve(),
        jnetpcap_path=Path(config.jnetpcap_path).resolve(),
        activation_path=Path(config.activation_path).resolve(),
        spool_dir=Path(config.spool_dir).resolve(),
        alerts_output_path=Path(config.alerts_output_path).resolve(),
        quarantine_output_path=Path(config.quarantine_output_path).resolve(),
        summary_output_path=Path(config.summary_output_path).resolve(),
    )


def build_operator_preflight_config(config: SameHostStackConfig) -> OperatorConsolePreflightConfig:
    operator_config = load_stack_operator_config(config)
    telegram_token = operator_config.telegram_bot_token if operator_config.telegram_bot_token_source is None else None
    return OperatorConsolePreflightConfig(
        python_binary=Path(config.python_binary).resolve(),
        app_entrypoint=Path(config.operator_server_entrypoint).resolve(),
        manage_entrypoint=Path(config.operator_manage_entrypoint).resolve(),
        database_path=operator_config.database_path,
        alerts_input_path=operator_config.alerts_input_path,
        quarantine_input_path=operator_config.quarantine_input_path,
        summary_input_path=operator_config.summary_input_path,
        templates_dir=operator_config.templates_dir,
        static_dir=operator_config.static_dir,
        environment=operator_config.environment,
        public_base_url=operator_config.public_base_url,
        root_path=operator_config.root_path,
        forwarded_allow_ips=operator_config.forwarded_allow_ips,
        secret_key=operator_config.secret_key if operator_config.secret_key_source is None else None,
        secret_key_file=operator_config.secret_key_source,
        telegram_bot_token=telegram_token,
        telegram_bot_token_file=operator_config.telegram_bot_token_source,
        telegram_chat_id=operator_config.telegram_chat_id,
    )


def validate_stack_preflight(config: SameHostStackConfig) -> dict[str, Any]:
    repo_root = _require_existing_directory(config.repo_root, name="repo_root")
    python_binary = _require_existing_file(config.python_binary, name="python_binary", executable=True)
    model_manage_entrypoint = _require_existing_file(
        config.model_manage_entrypoint,
        name="model_manage_entrypoint",
    )
    operator_manage_entrypoint = _require_existing_file(
        config.operator_manage_entrypoint,
        name="operator_manage_entrypoint",
    )
    operator_server_entrypoint = _require_existing_file(
        config.operator_server_entrypoint,
        name="operator_server_entrypoint",
    )
    operator_env_file = _require_existing_file(config.operator_env_file, name="operator_env_file")

    operator_config = load_stack_operator_config(config)
    bundle_status = build_bundle_status_payload(Path(config.activation_path).resolve())
    if not bundle_status.get("runtime_ready"):
        detail = str(bundle_status.get("detail", "activation contract is not runtime-ready"))
        raise ValueError(detail)

    validate_live_sensor_preflight(build_sensor_preflight_config(config))
    validate_operator_console_preflight(build_operator_preflight_config(config))

    notification_status = "enabled" if notifications_enabled(config) else "disabled"
    return {
        "ready": True,
        "command": "preflight",
        "host_layout": {
            "repo_root": str(repo_root),
            "python_binary": str(python_binary),
            "operator_env_file": str(operator_env_file),
            "model_manage_entrypoint": str(model_manage_entrypoint),
            "operator_manage_entrypoint": str(operator_manage_entrypoint),
            "operator_server_entrypoint": str(operator_server_entrypoint),
            "sensor_spool_dir": str(Path(config.spool_dir).resolve()),
            "sensor_log_root": str(Path(config.summary_output_path).resolve().parent),
            "operator_database_path": str(operator_config.database_path),
            "operator_secret_source": str(operator_config.secret_key_source)
            if operator_config.secret_key_source is not None
            else "inline",
        },
        "components": {
            "bundle_activation": bundle_status,
            "live_sensor_preflight": {
                "status": "ready",
                "activation_path": str(Path(config.activation_path).resolve()),
                "summary_output_path": str(Path(config.summary_output_path).resolve()),
            },
            "operator_console_preflight": {
                "status": "ready",
                "database_path": str(operator_config.database_path),
                "summary_input_path": str(operator_config.summary_input_path),
            },
            "notification": {
                "status": notification_status,
                "enabled": notification_status == "enabled",
            },
        },
    }


def prepare_host_layout(config: SameHostStackConfig) -> dict[str, Any]:
    load_stack_operator_config(config)
    created: list[str] = []
    for path in (
        Path(config.spool_dir).resolve(),
        Path(config.alerts_output_path).resolve().parent,
        Path(config.quarantine_output_path).resolve().parent,
        Path(config.summary_output_path).resolve().parent,
        build_operator_preflight_config(config).database_path.parent,
    ):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(str(path))
    return {
        "status": "prepared",
        "created_directories": created,
    }


def run_command(argv: Sequence[str]) -> str:
    completed = subprocess.run(
        [str(part) for part in argv],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(str(part) for part in argv)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed.stdout.strip()


def _run_json_command(command_runner: CommandRunner, argv: Sequence[str]) -> dict[str, Any]:
    stdout = command_runner(argv)
    return json.loads(stdout) if stdout else {}


def _build_password_args(config: SameHostStackConfig) -> list[str]:
    if bool(config.admin_password) == bool(config.admin_password_file):
        raise ValueError("exactly one of admin_password or admin_password_file must be set")
    if config.admin_password_file is not None:
        password_file = _require_existing_file(
            config.admin_password_file,
            name="admin_password_file",
        )
        return ["--password-file", str(password_file)]
    return ["--password", str(config.admin_password)]


def _require_bootstrap_inputs(config: SameHostStackConfig) -> tuple[Path, str]:
    if config.candidate_bundle_root is None:
        raise ValueError("candidate_bundle_root is required for bootstrap")
    if config.admin_username is None or not str(config.admin_username).strip():
        raise ValueError("admin_username is required for bootstrap")
    return Path(config.candidate_bundle_root).resolve(), str(config.admin_username).strip()


def run_stack_bootstrap(
    config: SameHostStackConfig,
    *,
    command_runner: CommandRunner = run_command,
) -> dict[str, Any]:
    candidate_bundle_root, admin_username = _require_bootstrap_inputs(config)
    operator_config = load_stack_operator_config(config)
    steps: list[dict[str, Any]] = []

    steps.append(
        {
            "step": "prepare_host_layout",
            "result": prepare_host_layout(config),
        }
    )

    verify_command = [
        str(Path(config.python_binary).resolve()),
        str(Path(config.model_manage_entrypoint).resolve()),
        "--activation-path",
        str(Path(config.activation_path).resolve()),
        "--json",
        "verify",
        "--bundle-root",
        str(candidate_bundle_root),
    ]
    steps.append(
        {
            "step": "verify_candidate_bundle",
            "argv": verify_command,
            "result": _run_json_command(command_runner, verify_command),
        }
    )

    promote_command = [
        str(Path(config.python_binary).resolve()),
        str(Path(config.model_manage_entrypoint).resolve()),
        "--activation-path",
        str(Path(config.activation_path).resolve()),
        "--json",
        "promote",
        "--bundle-root",
        str(candidate_bundle_root),
    ]
    steps.append(
        {
            "step": "promote_candidate_bundle",
            "argv": promote_command,
            "result": _run_json_command(command_runner, promote_command),
        }
    )

    migrate_command = [
        str(Path(config.python_binary).resolve()),
        str(Path(config.operator_manage_entrypoint).resolve()),
        "--database-path",
        str(operator_config.database_path),
        "--json",
        "migrate",
        "--allow-bootstrap",
    ]
    steps.append(
        {
            "step": "migrate_operator_console",
            "argv": migrate_command,
            "result": _run_json_command(command_runner, migrate_command),
        }
    )

    bootstrap_admin_command = [
        str(Path(config.python_binary).resolve()),
        str(Path(config.operator_manage_entrypoint).resolve()),
        "--database-path",
        str(operator_config.database_path),
        "--json",
        "bootstrap-admin",
        "--username",
        admin_username,
        *_build_password_args(config),
    ]
    steps.append(
        {
            "step": "bootstrap_operator_admin",
            "argv": bootstrap_admin_command,
            "result": _run_json_command(command_runner, bootstrap_admin_command),
        }
    )

    steps.append(
        {
            "step": "stack_preflight",
            "result": validate_stack_preflight(config),
        }
    )

    console_service_command = ["systemctl", "start", config.console_service_name]
    command_runner(console_service_command)
    steps.append(
        {
            "step": "start_operator_console_service",
            "argv": console_service_command,
            "result": {"status": "started", "service": config.console_service_name},
        }
    )

    live_sensor_service_command = ["systemctl", "start", config.live_sensor_service_name]
    command_runner(live_sensor_service_command)
    steps.append(
        {
            "step": "start_live_sensor_service",
            "argv": live_sensor_service_command,
            "result": {"status": "started", "service": config.live_sensor_service_name},
        }
    )

    notification_is_enabled = notifications_enabled(config)
    if notification_is_enabled:
        notification_service_command = ["systemctl", "start", config.notification_service_name]
        command_runner(notification_service_command)
        steps.append(
            {
                "step": "start_notification_service",
                "argv": notification_service_command,
                "result": {"status": "started", "service": config.notification_service_name},
            }
        )

    return {
        "bootstrap_ready": True,
        "command": "bootstrap",
        "notification_enabled": notification_is_enabled,
        "steps": steps,
        "next_contract_steps": [
            "stack status",
            "stack smoke",
            "optional reverse-proxy seam smoke when configured",
        ],
    }
