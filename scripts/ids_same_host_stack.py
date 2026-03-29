from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Sequence
from urllib.request import urlopen

from scripts.ids_live_sensor_preflight import (
    LiveSensorPreflightConfig,
    validate_preflight as validate_live_sensor_preflight,
)
from scripts.ids_live_sensor_health import (
    LiveSensorHealthConfig,
    build_live_sensor_health_payload,
)
from scripts.ids_model_bundle import build_bundle_status_payload
from scripts.ids_operator_console.config import (
    OperatorConsoleConfig,
    PLACEHOLDER_SECRET_VALUES,
    load_operator_console_config,
)
from scripts.ids_operator_console.health import (
    build_notification_component,
    build_readiness_payload,
)
from scripts.ids_operator_console.ops import (
    notification_status,
    redrive_notification_failures,
    run_smoke_checks,
)
from scripts.ids_operator_console_preflight import (
    OperatorConsolePreflightConfig,
    validate_preflight as validate_operator_console_preflight,
)


CommandRunner = Callable[[Sequence[str]], str]
ProxyChecker = Callable[[str, float], tuple[int, str | None]]


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
    sensor_freshness_window_seconds: float = 300.0
    proxy_public_url: str | None = None
    proxy_timeout_seconds: float = 5.0
    operator_backup_dir: Path | None = None
    notification_redrive_limit: int = 100
    candidate_bundle_root: Path | None = None
    admin_username: str | None = None
    admin_password: str | None = None
    admin_password_file: Path | None = None


def _build_failure_payload(exc: Exception, **payload: Any) -> dict[str, Any]:
    payload["error_type"] = type(exc).__name__
    payload["detail"] = str(exc)
    return payload


def _build_failure_component(
    *,
    exc: Exception,
    state: str,
    payload: dict[str, Any] | None = None,
    detail: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    component: dict[str, Any] = {
        "ok": False,
        "state": state,
        "detail": str(exc) if detail is None else detail,
        "payload": _build_failure_payload(exc, **(payload or {})),
    }
    component.update(extra)
    return component


def _path_state_from_exception(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "missing"
    if isinstance(exc, PermissionError):
        return "permission_denied"
    return "invalid"


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


def _default_proxy_checker(url: str, timeout_seconds: float) -> tuple[int, str | None]:
    with urlopen(url, timeout=timeout_seconds) as response:
        return int(getattr(response, "status", 200)), response.geturl()


def _build_bundle_component(config: SameHostStackConfig) -> dict[str, Any]:
    try:
        payload = build_bundle_status_payload(Path(config.activation_path).resolve())
    except Exception as exc:
        return _build_failure_component(
            exc=exc,
            state="invalid",
            payload={"activation_path": str(Path(config.activation_path).resolve())},
        )
    ok = bool(payload.get("runtime_ready"))
    return {
        "ok": ok,
        "state": "ready" if ok else "degraded",
        "detail": None if ok else str(payload.get("detail", "activation contract is not runtime-ready")),
        "payload": payload,
    }


def _build_live_sensor_component(config: SameHostStackConfig) -> dict[str, Any]:
    try:
        payload = build_live_sensor_health_payload(
            LiveSensorHealthConfig(
                activation_path=config.activation_path,
                summary_output_path=config.summary_output_path,
                freshness_window_seconds=config.sensor_freshness_window_seconds,
            ),
            now=datetime.now(timezone.utc),
        )
    except Exception as exc:
        return _build_failure_component(
            exc=exc,
            state="degraded",
            payload={
                "activation_path": str(Path(config.activation_path).resolve()),
                "summary_output_path": str(Path(config.summary_output_path).resolve()),
            },
        )
    return {
        "ok": bool(payload.get("ready")),
        "state": "ready" if payload.get("ready") else "degraded",
        "detail": None if payload.get("ready") else "live sensor runtime health is degraded",
        "payload": payload,
    }


def _build_operator_status_component(config: SameHostStackConfig) -> dict[str, Any]:
    try:
        payload = build_readiness_payload(load_stack_operator_config(config))
    except Exception as exc:
        return _build_failure_component(
            exc=exc,
            state="degraded",
            payload={"operator_env_file": str(Path(config.operator_env_file).resolve())},
        )
    ok = bool(payload.get("ready"))
    return {
        "ok": ok,
        "state": "ready" if ok else "degraded",
        "detail": None if ok else "operator console readiness is degraded",
        "payload": payload,
    }


def _build_operator_smoke_component(config: SameHostStackConfig) -> dict[str, Any]:
    try:
        smoke = run_smoke_checks(load_stack_operator_config(config))
    except Exception as exc:
        return _build_failure_component(
            exc=exc,
            state="degraded",
            payload={"operator_env_file": str(Path(config.operator_env_file).resolve())},
        )
    redirect_ok = smoke.redirect_status in {200, 302, 307, 308}
    ok = smoke.health_status == 200 and smoke.readiness_status == 200 and redirect_ok
    return {
        "ok": ok,
        "state": "ready" if ok else "degraded",
        "detail": None if ok else "operator console smoke checks did not pass",
        "payload": {
            "health_status": smoke.health_status,
            "readiness_status": smoke.readiness_status,
            "redirect_status": smoke.redirect_status,
            "readiness_payload": smoke.readiness_payload,
        },
    }


def _build_notification_path_component(config: SameHostStackConfig) -> dict[str, Any]:
    try:
        payload = build_notification_component(load_stack_operator_config(config), include_sensitive=False)
    except Exception as exc:
        return _build_failure_component(
            exc=exc,
            state="degraded",
            payload={
                "enabled": False,
                "configured": False,
                "operator_env_file": str(Path(config.operator_env_file).resolve()),
            },
        )
    enabled = bool(payload.get("enabled"))
    ok = bool(payload.get("ok")) or not enabled
    return {
        "ok": ok,
        "state": str(payload.get("state", "unknown")),
        "detail": None if ok else "notification runtime is enabled but not healthy",
        "payload": payload,
    }


def _build_proxy_component(
    config: SameHostStackConfig,
    *,
    proxy_checker: ProxyChecker,
) -> dict[str, Any]:
    proxy_public_url = None if config.proxy_public_url is None else str(config.proxy_public_url).strip()
    if not proxy_public_url:
        return {
            "ok": True,
            "state": "unconfigured",
            "detail": None,
            "gating": False,
            "payload": {
                "configured": False,
                "public_url": None,
            },
        }

    try:
        status_code, final_url = proxy_checker(proxy_public_url, float(config.proxy_timeout_seconds))
    except Exception as exc:
        return {
            "ok": False,
            "state": "degraded",
            "detail": str(exc),
            "gating": False,
            "payload": {
                "configured": True,
                "public_url": proxy_public_url,
                "status_code": None,
                "final_url": None,
            },
        }

    ok = 200 <= status_code < 400
    return {
        "ok": ok,
        "state": "reachable" if ok else "degraded",
        "detail": None if ok else f"proxy returned HTTP {status_code}",
        "gating": False,
        "payload": {
            "configured": True,
            "public_url": proxy_public_url,
            "status_code": status_code,
            "final_url": final_url,
        },
    }


def _build_stack_health_payload(
    config: SameHostStackConfig,
    *,
    command_name: str,
    proxy_checker: ProxyChecker,
) -> dict[str, Any]:
    bundle_component = _build_bundle_component(config)
    live_sensor_component = _build_live_sensor_component(config)
    operator_component = (
        _build_operator_smoke_component(config)
        if command_name == "smoke"
        else _build_operator_status_component(config)
    )
    notification_component = _build_notification_path_component(config)
    proxy_component = _build_proxy_component(config, proxy_checker=proxy_checker)

    ready = all(
        [
            bundle_component["ok"],
            live_sensor_component["ok"],
            operator_component["ok"],
            notification_component["ok"],
        ]
    )
    return {
        "service": "ids-same-host-stack",
        "command": command_name,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ready": ready,
        "status": "ok" if ready else "degraded",
        "components": {
            "model_activation_contract": bundle_component,
            "live_sensor_data_path": live_sensor_component,
            "operator_visibility_path": operator_component,
            "outbound_notification_path": notification_component,
            "reverse_proxy_edge_seam": proxy_component,
        },
    }


def build_stack_status_payload(
    config: SameHostStackConfig,
    *,
    proxy_checker: ProxyChecker = _default_proxy_checker,
) -> dict[str, Any]:
    return _build_stack_health_payload(
        config,
        command_name="status",
        proxy_checker=proxy_checker,
    )


def build_stack_smoke_payload(
    config: SameHostStackConfig,
    *,
    proxy_checker: ProxyChecker = _default_proxy_checker,
) -> dict[str, Any]:
    return _build_stack_health_payload(
        config,
        command_name="smoke",
        proxy_checker=proxy_checker,
    )


def _run_supervisor_restart(
    command_runner: CommandRunner,
    *,
    service_name: str,
) -> tuple[list[str], dict[str, Any]]:
    argv = ["systemctl", "restart", service_name]
    try:
        command_runner(argv)
    except Exception as exc:
        return argv, {
            "ok": False,
            "state": "restart_failed",
            "detail": str(exc),
            "service": service_name,
        }
    return argv, {
        "ok": True,
        "state": "restarted",
        "detail": None,
        "service": service_name,
    }


def run_stack_recovery(
    config: SameHostStackConfig,
    *,
    command_runner: CommandRunner | None = None,
    proxy_checker: ProxyChecker = _default_proxy_checker,
) -> dict[str, Any]:
    effective_command_runner = run_command if command_runner is None else command_runner
    steps: list[dict[str, Any]] = []
    restart_results: list[dict[str, Any]] = []

    bundle_component = _build_bundle_component(config)
    steps.append(
        {
            "step": "verify_activation_contract",
            "result": bundle_component,
        }
    )

    for step_name, service_name in (
        ("restart_live_sensor_service", config.live_sensor_service_name),
        ("restart_operator_console_service", config.console_service_name),
    ):
        argv, result = _run_supervisor_restart(effective_command_runner, service_name=service_name)
        restart_results.append(result)
        steps.append(
            {
                "step": step_name,
                "argv": argv,
                "result": result,
            }
        )

    notification_component = _build_notification_path_component(config)
    notification_is_enabled = bool(notification_component.get("payload", {}).get("enabled"))
    if notification_is_enabled:
        argv, result = _run_supervisor_restart(
            effective_command_runner,
            service_name=config.notification_service_name,
        )
        restart_results.append(result)
        steps.append(
            {
                "step": "restart_notification_service",
                "argv": argv,
                "result": result,
            }
        )
    elif notification_component.get("state") == "disabled":
        steps.append(
            {
                "step": "notification_service_disabled",
                "result": {
                    "ok": True,
                    "state": "disabled",
                    "detail": None,
                    "service": config.notification_service_name,
                },
            }
        )
    else:
        steps.append(
            {
                "step": "notification_service_unavailable",
                "result": notification_component,
            }
        )

    status_payload = build_stack_status_payload(config, proxy_checker=proxy_checker)
    smoke_payload = build_stack_smoke_payload(config, proxy_checker=proxy_checker)
    steps.append(
        {
            "step": "stack_status",
            "result": status_payload,
        }
    )
    steps.append(
        {
            "step": "stack_smoke",
            "result": smoke_payload,
        }
    )

    recovery_ready = all(result["ok"] for result in restart_results) and bool(
        status_payload.get("ready") and smoke_payload.get("ready")
    )
    return {
        "command": "recover",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "recovery_ready": recovery_ready,
        "status": "ok" if recovery_ready else "degraded",
        "notification_enabled": notification_is_enabled,
        "steps": steps,
        "diagnosis": {
            "status": status_payload,
            "smoke": smoke_payload,
        },
    }


def _require_operator_backup_dir(config: SameHostStackConfig) -> Path:
    if config.operator_backup_dir is None:
        raise ValueError("operator_backup_dir is required for restore inventory checks")
    resolved = Path(config.operator_backup_dir).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"operator_backup_dir not found: {resolved}")
    manifest_path = resolved / "manifest.json"
    if manifest_path.is_file():
        return resolved
    backup_dirs = sorted(
        [path for path in resolved.iterdir() if path.is_dir() and path.name.startswith("backup-")],
        key=lambda path: path.name,
        reverse=True,
    )
    if not backup_dirs:
        raise FileNotFoundError(f"operator backup manifest not found under: {resolved}")
    return backup_dirs[0]


def _build_restore_bundle_inventory(config: SameHostStackConfig) -> dict[str, Any]:
    payload = build_bundle_status_payload(Path(config.activation_path).resolve())
    referenced_bundle_roots: list[dict[str, Any]] = []
    for field in ("active_bundle_root", "previous_bundle_root"):
        raw_root = payload.get(field)
        if raw_root in (None, ""):
            continue
        resolved_root = Path(str(raw_root)).resolve()
        referenced_bundle_roots.append(
            {
                "field": field,
                "path": str(resolved_root),
                "exists": resolved_root.is_dir(),
            }
        )

    ok = bool(payload.get("runtime_ready")) and all(root["exists"] for root in referenced_bundle_roots)
    detail = None
    if not ok:
        detail = str(payload.get("detail", "activation contract restore inventory is incomplete"))
        missing_root = next((root["path"] for root in referenced_bundle_roots if not root["exists"]), None)
        if missing_root is not None:
            detail = f"referenced bundle root missing: {missing_root}"
    return {
        "ok": ok,
        "state": "ready" if ok else "degraded",
        "detail": detail,
        "payload": {
            "activation_contract": payload,
            "referenced_bundle_roots": referenced_bundle_roots,
        },
    }


def _load_backup_manifest(backup_dir: Path) -> tuple[Path, dict[str, Any], Path]:
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"backup manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backup_file_name = str(manifest.get("database", {}).get("backup_file", "operator_console.db"))
    database_backup_path = (backup_dir / backup_file_name).resolve()
    if not database_backup_path.is_file():
        raise FileNotFoundError(f"backup database not found: {database_backup_path}")
    return manifest_path, manifest, database_backup_path


def _evaluate_secret_reference(
    reference_name: str,
    *,
    reference_payload: dict[str, Any],
    current_value: str | None,
    current_source: Path | None,
    reject_placeholders: bool,
) -> dict[str, Any]:
    configured = bool(reference_payload.get("configured"))
    source = reference_payload.get("source")
    if not configured:
        return {
            "ok": True,
            "state": "not_configured",
            "detail": None,
            "payload": {
                "reference_name": reference_name,
                "configured": False,
                "source": source,
            },
        }
    if source == "file":
        ok = current_source is not None and Path(current_source).is_file()
        return {
            "ok": ok,
            "state": "bound" if ok else "missing",
            "detail": None if ok else f"{reference_name} file reference is not rebound on the host",
            "payload": {
                "reference_name": reference_name,
                "configured": True,
                "source": source,
                "path": str(current_source) if current_source is not None else None,
            },
        }
    normalized = None if current_value is None else str(current_value).strip()
    ok = bool(normalized)
    if ok and reject_placeholders:
        ok = normalized not in PLACEHOLDER_SECRET_VALUES
    return {
        "ok": ok,
        "state": "bound" if ok else "missing",
        "detail": None if ok else f"{reference_name} env value is not rebound on the host",
        "payload": {
            "reference_name": reference_name,
            "configured": True,
            "source": source or "env",
        },
    }


def _build_operator_restore_inventory(config: SameHostStackConfig) -> dict[str, Any]:
    operator_config = load_stack_operator_config(config)
    backup_dir = _require_operator_backup_dir(config)
    manifest_path, manifest, database_backup_path = _load_backup_manifest(backup_dir)
    database_path = operator_config.database_path.resolve()

    secret_references = manifest.get("secret_references", {})
    secret_key_reference = _evaluate_secret_reference(
        "secret_key",
        reference_payload=dict(secret_references.get("secret_key", {})),
        current_value=operator_config.secret_key,
        current_source=operator_config.secret_key_source,
        reject_placeholders=True,
    )
    telegram_reference = _evaluate_secret_reference(
        "telegram_bot_token",
        reference_payload=dict(secret_references.get("telegram_bot_token", {})),
        current_value=operator_config.telegram_bot_token,
        current_source=operator_config.telegram_bot_token_source,
        reject_placeholders=False,
    )

    ok = all(
        [
            database_path.is_file(),
            manifest_path.is_file(),
            database_backup_path.is_file(),
            secret_key_reference["ok"],
            telegram_reference["ok"],
        ]
    )
    detail = None
    if not ok:
        if not database_path.is_file():
            detail = f"operator database not found: {database_path}"
        elif not database_backup_path.is_file():
            detail = f"backup database not found: {database_backup_path}"
        elif not secret_key_reference["ok"]:
            detail = str(secret_key_reference["detail"])
        elif not telegram_reference["ok"]:
            detail = str(telegram_reference["detail"])
        else:
            detail = "operator restore inventory is incomplete"

    return {
        "ok": ok,
        "state": "ready" if ok else "degraded",
        "detail": detail,
        "payload": {
            "database_path": str(database_path),
            "database_exists": database_path.is_file(),
            "backup_dir": str(backup_dir),
            "manifest_path": str(manifest_path),
            "database_backup_path": str(database_backup_path),
            "secret_references": {
                "secret_key": secret_key_reference,
                "telegram_bot_token": telegram_reference,
            },
        },
    }


def _build_live_sensor_evidence_inventory(config: SameHostStackConfig) -> dict[str, Any]:
    log_root = Path(config.summary_output_path).resolve().parent
    paths = {
        "alerts_output_path": Path(config.alerts_output_path).resolve(),
        "quarantine_output_path": Path(config.quarantine_output_path).resolve(),
        "summary_output_path": Path(config.summary_output_path).resolve(),
        "log_root": log_root,
    }
    return {
        "ok": True,
        "state": "preserve_when_practical",
        "detail": "live-sensor JSONL outputs and logs are operator evidence, not primary restore state",
        "gating": False,
        "payload": {
            "preserve_when_practical": True,
            "primary_restore_state": False,
            "paths": {
                name: {
                    "path": str(path),
                    "exists": path.exists(),
                }
                for name, path in paths.items()
            },
        },
    }


def build_stack_restore_inventory_payload(config: SameHostStackConfig) -> dict[str, Any]:
    try:
        bundle_inventory = _build_restore_bundle_inventory(config)
    except Exception as exc:
        bundle_inventory = _build_failure_component(
            exc=exc,
            state="degraded",
            payload={"activation_path": str(Path(config.activation_path).resolve())},
        )
    try:
        operator_inventory = _build_operator_restore_inventory(config)
    except Exception as exc:
        operator_inventory = _build_failure_component(
            exc=exc,
            state="degraded",
            payload={"operator_backup_dir": str(config.operator_backup_dir) if config.operator_backup_dir else None},
        )
    evidence_inventory = _build_live_sensor_evidence_inventory(config)
    inventory_ready = bool(bundle_inventory["ok"] and operator_inventory["ok"])
    return {
        "command": "restore-inventory",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "inventory_ready": inventory_ready,
        "status": "ok" if inventory_ready else "degraded",
        "components": {
            "activation_restore_state": bundle_inventory,
            "operator_console_restore_state": operator_inventory,
            "live_sensor_operator_evidence": evidence_inventory,
        },
    }


def _build_live_sensor_revalidation_component(config: SameHostStackConfig) -> dict[str, Any]:
    try:
        validate_live_sensor_preflight(build_sensor_preflight_config(config))
    except Exception as exc:
        return {
            "ok": False,
            "state": "degraded",
            "detail": str(exc),
        }
    return {
        "ok": True,
        "state": "ready",
        "detail": None,
    }


def _extract_bundle_visibility(status_payload: dict[str, Any]) -> dict[str, Any]:
    active_bundle_component = (
        status_payload.get("components", {})
        .get("operator_visibility_path", {})
        .get("payload", {})
        .get("components", {})
        .get("active_bundle", {})
    )
    ok = bool(active_bundle_component.get("ok"))
    return {
        "ok": ok,
        "state": "reestablished" if ok else "missing",
        "detail": None if ok else "operator visibility does not yet expose active bundle state",
        "payload": active_bundle_component,
    }


def run_stack_post_restore_check(
    config: SameHostStackConfig,
    *,
    command_runner: CommandRunner | None = None,
    proxy_checker: ProxyChecker = _default_proxy_checker,
) -> dict[str, Any]:
    inventory_payload = build_stack_restore_inventory_payload(config)
    live_sensor_revalidation = _build_live_sensor_revalidation_component(config)
    recovery_payload = run_stack_recovery(
        config,
        command_runner=command_runner,
        proxy_checker=proxy_checker,
    )

    steps: list[dict[str, Any]] = [
        {
            "step": "restore_inventory",
            "result": inventory_payload,
        },
        {
            "step": "live_sensor_preflight_revalidation",
            "result": live_sensor_revalidation,
        },
        {
            "step": "stack_recovery",
            "result": recovery_payload,
        },
    ]

    notification_component: dict[str, Any]
    notification_runtime_component = _build_notification_path_component(config)
    notification_is_enabled = bool(notification_runtime_component.get("payload", {}).get("enabled"))
    if notification_is_enabled:
        try:
            operator_config = load_stack_operator_config(config)
            notification_component = notification_status(operator_config)
        except Exception as exc:
            notification_component = _build_failure_component(
                exc=exc,
                state="degraded",
                payload={"operator_env_file": str(Path(config.operator_env_file).resolve())},
                enabled=True,
            )
        steps.append(
            {
                "step": "notification_status",
                "result": notification_component,
            }
        )
        if int(notification_component.get("failed_count", 0)) > 0:
            try:
                redrive_result = redrive_notification_failures(
                    operator_config,
                    limit=int(config.notification_redrive_limit),
                )
                notification_component = redrive_result.status
                steps.append(
                    {
                        "step": "notification_redrive",
                        "result": {
                            "redriven": redrive_result.redriven,
                            "status": redrive_result.status,
                        },
                    }
                )
            except Exception as exc:
                notification_component = _build_failure_component(
                    exc=exc,
                    state="degraded",
                    payload={"notification_redrive_limit": int(config.notification_redrive_limit)},
                    enabled=True,
                )
                steps.append(
                    {
                        "step": "notification_redrive",
                        "result": notification_component,
                    }
                )
    else:
        notification_component = notification_runtime_component if notification_runtime_component.get("state") == "disabled" else {
            "ok": True,
            "state": "disabled",
            "enabled": False,
        }
        steps.append(
            {
                "step": "notification_disabled",
                "result": notification_component,
            }
        )

    final_status = build_stack_status_payload(config, proxy_checker=proxy_checker)
    final_smoke = build_stack_smoke_payload(config, proxy_checker=proxy_checker)
    bundle_visibility = _extract_bundle_visibility(final_status)
    steps.append(
        {
            "step": "final_status",
            "result": final_status,
        }
    )
    steps.append(
        {
            "step": "final_smoke",
            "result": final_smoke,
        }
    )

    notification_ok = bool(notification_component.get("ok") or notification_component.get("state") == "disabled")
    post_restore_ready = all(
        [
            inventory_payload["inventory_ready"],
            live_sensor_revalidation["ok"],
            recovery_payload["recovery_ready"],
            notification_ok,
            final_status.get("ready"),
            final_smoke.get("ready"),
            bundle_visibility["ok"],
        ]
    )
    return {
        "command": "post-restore-check",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "post_restore_ready": post_restore_ready,
        "status": "ok" if post_restore_ready else "degraded",
        "steps": steps,
        "diagnosis": {
            "status": final_status,
            "smoke": final_smoke,
            "bundle_visibility_reestablished": bundle_visibility,
        },
    }


def validate_stack_preflight(config: SameHostStackConfig) -> dict[str, Any]:
    host_layout_checks: dict[str, dict[str, Any]] = {}

    def check_directory(path: Path, *, name: str) -> Path | None:
        try:
            checked = _require_existing_directory(path, name=name)
        except Exception as exc:
            host_layout_checks[name] = {
                "ok": False,
                "state": _path_state_from_exception(exc),
                "detail": str(exc),
                "path": str(Path(path).resolve()),
            }
            return None
        host_layout_checks[name] = {
            "ok": True,
            "state": "ready",
            "detail": None,
            "path": str(checked),
        }
        return checked

    def check_file(path: Path, *, name: str, executable: bool = False) -> Path | None:
        try:
            checked = _require_existing_file(path, name=name, executable=executable)
        except Exception as exc:
            host_layout_checks[name] = {
                "ok": False,
                "state": _path_state_from_exception(exc),
                "detail": str(exc),
                "path": str(Path(path).resolve()),
                "executable_required": executable,
            }
            return None
        host_layout_checks[name] = {
            "ok": True,
            "state": "ready",
            "detail": None,
            "path": str(checked),
            "executable_required": executable,
        }
        return checked

    repo_root = check_directory(config.repo_root, name="repo_root")
    python_binary = check_file(config.python_binary, name="python_binary", executable=True)
    model_manage_entrypoint = check_file(
        config.model_manage_entrypoint,
        name="model_manage_entrypoint",
    )
    operator_manage_entrypoint = check_file(
        config.operator_manage_entrypoint,
        name="operator_manage_entrypoint",
    )
    operator_server_entrypoint = check_file(
        config.operator_server_entrypoint,
        name="operator_server_entrypoint",
    )
    operator_env_file = check_file(config.operator_env_file, name="operator_env_file")

    try:
        operator_config = load_stack_operator_config(config)
        operator_config_component = {
            "ok": True,
            "status": "ready",
            "detail": None,
            "database_path": str(operator_config.database_path),
            "summary_input_path": str(operator_config.summary_input_path),
        }
    except Exception as exc:
        operator_config = None
        operator_config_component = {
            "ok": False,
            "status": "degraded",
            "detail": str(exc),
            "database_path": None,
            "summary_input_path": None,
        }

    bundle_status = _build_bundle_component(config)

    try:
        validate_live_sensor_preflight(build_sensor_preflight_config(config))
        live_sensor_preflight = {
            "ok": True,
            "status": "ready",
            "detail": None,
            "activation_path": str(Path(config.activation_path).resolve()),
            "summary_output_path": str(Path(config.summary_output_path).resolve()),
        }
    except Exception as exc:
        live_sensor_preflight = {
            "ok": False,
            "status": "degraded",
            "detail": str(exc),
            "activation_path": str(Path(config.activation_path).resolve()),
            "summary_output_path": str(Path(config.summary_output_path).resolve()),
        }

    try:
        validate_operator_console_preflight(build_operator_preflight_config(config))
        operator_console_preflight = {
            "ok": True,
            "status": "ready",
            "detail": None,
            "database_path": str(operator_config.database_path) if operator_config is not None else None,
            "summary_input_path": str(operator_config.summary_input_path) if operator_config is not None else None,
        }
    except Exception as exc:
        operator_console_preflight = {
            "ok": False,
            "status": "degraded",
            "detail": str(exc),
            "database_path": str(operator_config.database_path) if operator_config is not None else None,
            "summary_input_path": str(operator_config.summary_input_path) if operator_config is not None else None,
        }

    notification_component = _build_notification_path_component(config)
    notification_status = str(notification_component.get("state", "degraded"))
    notification_payload = dict(notification_component.get("payload", {}))

    ready = all(check["ok"] for check in host_layout_checks.values()) and all(
        [
            bundle_status["ok"],
            live_sensor_preflight["ok"],
            operator_console_preflight["ok"],
            notification_component["ok"],
        ]
    )
    return {
        "ready": ready,
        "command": "preflight",
        "host_layout": {
            "repo_root": str(repo_root) if repo_root is not None else str(Path(config.repo_root).resolve()),
            "python_binary": str(python_binary) if python_binary is not None else str(Path(config.python_binary).resolve()),
            "operator_env_file": str(operator_env_file) if operator_env_file is not None else str(Path(config.operator_env_file).resolve()),
            "model_manage_entrypoint": str(model_manage_entrypoint) if model_manage_entrypoint is not None else str(Path(config.model_manage_entrypoint).resolve()),
            "operator_manage_entrypoint": str(operator_manage_entrypoint) if operator_manage_entrypoint is not None else str(Path(config.operator_manage_entrypoint).resolve()),
            "operator_server_entrypoint": str(operator_server_entrypoint) if operator_server_entrypoint is not None else str(Path(config.operator_server_entrypoint).resolve()),
            "sensor_spool_dir": str(Path(config.spool_dir).resolve()),
            "sensor_log_root": str(Path(config.summary_output_path).resolve().parent),
            "operator_database_path": str(operator_config.database_path) if operator_config is not None else None,
            "operator_secret_source": (
                str(operator_config.secret_key_source)
                if operator_config is not None and operator_config.secret_key_source is not None
                else ("inline" if operator_config is not None else None)
            ),
        },
        "host_layout_checks": host_layout_checks,
        "components": {
            "bundle_activation": bundle_status,
            "operator_config": operator_config_component,
            "live_sensor_preflight": live_sensor_preflight,
            "operator_console_preflight": operator_console_preflight,
            "notification": {
                "ok": notification_component["ok"],
                "status": notification_status,
                "enabled": bool(notification_payload.get("enabled")),
                "detail": notification_component.get("detail"),
                "payload": notification_payload,
            },
        },
        "status": "ok" if ready else "degraded",
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
    redacted_argv: list[str] = []
    redact_next = False
    for part in argv:
        string_part = str(part)
        if redact_next:
            redacted_argv.append("***REDACTED***")
            redact_next = False
            continue
        redacted_argv.append(string_part)
        if string_part == "--password":
            redact_next = True
    completed = subprocess.run(
        [str(part) for part in argv],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(redacted_argv)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed.stdout.strip()


def _run_json_command(command_runner: CommandRunner, argv: Sequence[str]) -> dict[str, Any]:
    stdout = command_runner(argv)
    return json.loads(stdout) if stdout else {}


def _build_password_args(config: SameHostStackConfig) -> list[str]:
    if config.admin_password is not None:
        raise ValueError("inline admin_password is not supported; use admin_password_file")
    if config.admin_password_file is None:
        raise ValueError("admin_password_file is required for bootstrap")
    password_file = _require_existing_file(
        config.admin_password_file,
        name="admin_password_file",
    )
    return ["--password-file", str(password_file)]


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
    proxy_checker: ProxyChecker = _default_proxy_checker,
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

    notification_runtime_component = _build_notification_path_component(config)
    notification_is_enabled = bool(notification_runtime_component.get("payload", {}).get("enabled"))
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
    elif notification_runtime_component.get("state") != "disabled":
        steps.append(
            {
                "step": "notification_service_unavailable",
                "result": notification_runtime_component,
            }
        )

    status_payload = build_stack_status_payload(config, proxy_checker=proxy_checker)
    smoke_payload = build_stack_smoke_payload(config, proxy_checker=proxy_checker)
    steps.append(
        {
            "step": "stack_status",
            "result": status_payload,
        }
    )
    steps.append(
        {
            "step": "stack_smoke",
            "result": smoke_payload,
        }
    )
    proxy_component = smoke_payload.get("components", {}).get("reverse_proxy_edge_seam")
    if proxy_component and proxy_component.get("payload", {}).get("configured"):
        steps.append(
            {
                "step": "proxy_seam_smoke",
                "result": proxy_component,
            }
        )

    bootstrap_ready = bool(status_payload.get("ready") and smoke_payload.get("ready"))
    return {
        "bootstrap_ready": bootstrap_ready,
        "command": "bootstrap",
        "status": "ok" if bootstrap_ready else "degraded",
        "notification_enabled": notification_is_enabled,
        "steps": steps,
        "diagnosis": {
            "status": status_payload,
            "smoke": smoke_payload,
        },
    }
