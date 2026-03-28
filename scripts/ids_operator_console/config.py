from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_RELOAD = False
DEFAULT_LOG_LEVEL = "info"
DEFAULT_SESSION_COOKIE_NAME = "ids_operator_session"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_bool(raw: str, *, name: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean-like value, got {raw!r}")


def _parse_port(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"IDS_OPERATOR_CONSOLE_PORT must be an integer, got {raw!r}") from exc
    if value < 1 or value > 65535:
        raise ValueError(f"IDS_OPERATOR_CONSOLE_PORT must be between 1 and 65535, got {value}")
    return value


def _resolve_path(raw: str, *, root: Path) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


@dataclass(frozen=True)
class OperatorConsoleConfig:
    host: str
    port: int
    reload: bool
    log_level: str
    secret_key: str
    session_cookie_name: str
    database_path: Path
    alerts_input_path: Path
    quarantine_input_path: Path
    summary_input_path: Path
    templates_dir: Path
    static_dir: Path

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("host must not be blank")
        if self.port < 1 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")
        if not self.secret_key.strip():
            raise ValueError("secret_key must not be blank")
        if not self.session_cookie_name.strip():
            raise ValueError("session_cookie_name must not be blank")

    def ensure_runtime_dirs(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


def load_operator_console_config(
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
) -> OperatorConsoleConfig:
    env = dict(os.environ if environ is None else environ)
    root = (repo_root or _repo_root()).resolve()

    host = env.get("IDS_OPERATOR_CONSOLE_HOST", DEFAULT_HOST).strip()
    port = _parse_port(env["IDS_OPERATOR_CONSOLE_PORT"]) if "IDS_OPERATOR_CONSOLE_PORT" in env else DEFAULT_PORT
    reload = (
        _parse_bool(env["IDS_OPERATOR_CONSOLE_RELOAD"], name="IDS_OPERATOR_CONSOLE_RELOAD")
        if "IDS_OPERATOR_CONSOLE_RELOAD" in env
        else DEFAULT_RELOAD
    )
    log_level = env.get("IDS_OPERATOR_CONSOLE_LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().lower()
    secret_key = env.get("IDS_OPERATOR_CONSOLE_SECRET_KEY", "change-me")
    session_cookie_name = env.get(
        "IDS_OPERATOR_CONSOLE_SESSION_COOKIE_NAME",
        DEFAULT_SESSION_COOKIE_NAME,
    )

    database_path = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_DATABASE_PATH", "artifacts/operator_console/operator_console.db"),
        root=root,
    )
    alerts_input_path = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_ALERTS_INPUT_PATH", "ids_live_alerts.jsonl"),
        root=root,
    )
    quarantine_input_path = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_QUARANTINE_INPUT_PATH", "ids_live_quarantine.jsonl"),
        root=root,
    )
    summary_input_path = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH", "ids_live_sensor_summary.jsonl"),
        root=root,
    )
    templates_dir = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_TEMPLATES_DIR", "scripts/ids_operator_console/templates"),
        root=root,
    )
    static_dir = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_STATIC_DIR", "scripts/ids_operator_console/static"),
        root=root,
    )

    return OperatorConsoleConfig(
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        secret_key=secret_key,
        session_cookie_name=session_cookie_name,
        database_path=database_path,
        alerts_input_path=alerts_input_path,
        quarantine_input_path=quarantine_input_path,
        summary_input_path=summary_input_path,
        templates_dir=templates_dir,
        static_dir=static_dir,
    )

