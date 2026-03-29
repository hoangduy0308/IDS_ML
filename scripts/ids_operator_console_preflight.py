from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scripts.ids_operator_console.config import PLACEHOLDER_SECRET_VALUES
from scripts.ids_operator_console.migrations import inspect_operator_store


@dataclass(frozen=True)
class OperatorConsolePreflightConfig:
    python_binary: Path
    app_entrypoint: Path
    database_path: Path
    alerts_input_path: Path
    quarantine_input_path: Path
    summary_input_path: Path
    templates_dir: Path
    static_dir: Path
    environment: str
    public_base_url: str | None
    root_path: str
    forwarded_allow_ips: str
    secret_key: str | None = None
    secret_key_file: Path | None = None
    telegram_bot_token: str | None = None
    telegram_bot_token_file: Path | None = None
    telegram_chat_id: str | None = None


def _require_existing_file(path: Path, *, name: str, executable: bool = False) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if not resolved.is_file():
        raise FileNotFoundError(f"{name} not found: {resolved}")
    if executable and not _is_executable_file(resolved):
        raise PermissionError(f"{name} is not executable: {resolved}")
    if not os.access(resolved, os.R_OK):
        raise PermissionError(f"{name} is not readable: {resolved}")
    return resolved


def _require_existing_directory(path: Path, *, name: str) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if not resolved.is_dir():
        raise FileNotFoundError(f"{name} not found: {resolved}")
    if not os.access(resolved, os.R_OK):
        raise PermissionError(f"{name} is not readable: {resolved}")
    return resolved


def _require_existing_parent(path: Path, *, name: str) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    parent = resolved.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"{name} parent directory not found: {parent}")
    if not os.access(parent, os.W_OK):
        raise PermissionError(f"{name} parent directory is not writable: {parent}")
    return resolved


def _is_executable_file(path: Path) -> bool:
    return bool(path.stat().st_mode & 0o111)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _load_secret_value(config: OperatorConsolePreflightConfig) -> str:
    if config.secret_key and config.secret_key_file:
        raise ValueError("secret_key and secret_key_file may not both be set")
    if config.secret_key_file is not None:
        path = _require_existing_file(config.secret_key_file, name="secret_key_file")
        secret = path.read_text(encoding="utf-8").strip()
    else:
        secret = (config.secret_key or "").strip()
    if not secret:
        raise ValueError("secret_key must not be blank")
    if secret in PLACEHOLDER_SECRET_VALUES:
        raise ValueError("secret_key must not use default placeholder value")
    return secret


def _load_optional_secret(*, value: str | None, file_path: Path | None, name: str) -> str | None:
    if value and file_path:
        raise ValueError(f"{name} and {name}_file may not both be set")
    if file_path is not None:
        path = _require_existing_file(file_path, name=f"{name}_file")
        return path.read_text(encoding="utf-8").strip() or None
    return _clean_optional(value)


def validate_preflight(config: OperatorConsolePreflightConfig) -> None:
    _require_existing_file(config.python_binary, name="python_binary", executable=True)
    _require_existing_file(config.app_entrypoint, name="app_entrypoint")
    _require_existing_file(config.database_path, name="database_path")
    _require_existing_parent(config.alerts_input_path, name="alerts_input_path")
    _require_existing_parent(config.quarantine_input_path, name="quarantine_input_path")
    _require_existing_parent(config.summary_input_path, name="summary_input_path")
    _require_existing_directory(config.templates_dir, name="templates_dir")
    _require_existing_directory(config.static_dir, name="static_dir")
    _load_secret_value(config)

    if config.environment == "production":
        if not config.public_base_url:
            raise ValueError("production requires public_base_url")
        if not str(config.public_base_url).startswith("https://"):
            raise ValueError("production public_base_url must use https")
    if config.root_path and not config.root_path.startswith("/"):
        raise ValueError("root_path must start with '/'")
    if not config.forwarded_allow_ips.strip():
        raise ValueError("forwarded_allow_ips must not be blank")

    token = _load_optional_secret(
        value=config.telegram_bot_token,
        file_path=config.telegram_bot_token_file,
        name="telegram_bot_token",
    )
    chat_id = _clean_optional(config.telegram_chat_id)
    if (token is None) != (chat_id is None):
        raise ValueError(
            "telegram_bot_token and telegram_chat_id must be set together or both omitted"
        )

    inspection = inspect_operator_store(config.database_path)
    if inspection.schema_state != "current":
        raise ValueError(
            f"database schema is not current ({inspection.schema_state}); run migrate first"
        )
    if inspection.admin_count < 1:
        raise ValueError("database has no admin user; run bootstrap-admin first")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate IDS operator console runtime contract before systemd starts the service."
        )
    )
    parser.add_argument("--python-binary", type=Path, required=True)
    parser.add_argument("--app-entrypoint", type=Path, required=True)
    parser.add_argument("--database-path", type=Path, required=True)
    parser.add_argument("--alerts-input-path", type=Path, required=True)
    parser.add_argument("--quarantine-input-path", type=Path, required=True)
    parser.add_argument("--summary-input-path", type=Path, required=True)
    parser.add_argument("--templates-dir", type=Path, required=True)
    parser.add_argument("--static-dir", type=Path, required=True)
    parser.add_argument("--environment", default="development")
    parser.add_argument("--public-base-url", default=None)
    parser.add_argument("--root-path", default="")
    parser.add_argument("--forwarded-allow-ips", default="127.0.0.1")
    parser.add_argument("--secret-key", default=None)
    parser.add_argument("--secret-key-file", type=Path, default=None)
    parser.add_argument("--telegram-bot-token", default=None)
    parser.add_argument("--telegram-bot-token-file", type=Path, default=None)
    parser.add_argument("--telegram-chat-id", default=None)
    return parser.parse_args(argv)


def build_config_from_args(args: argparse.Namespace) -> OperatorConsolePreflightConfig:
    env_secret_key_file = _clean_optional(os.environ.get("IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE"))
    env_telegram_token = _clean_optional(os.environ.get("IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN"))
    env_telegram_token_file = _clean_optional(
        os.environ.get("IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE")
    )
    env_telegram_chat_id = _clean_optional(os.environ.get("IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID"))
    return OperatorConsolePreflightConfig(
        python_binary=Path(args.python_binary),
        app_entrypoint=Path(args.app_entrypoint),
        database_path=Path(args.database_path),
        alerts_input_path=Path(args.alerts_input_path),
        quarantine_input_path=Path(args.quarantine_input_path),
        summary_input_path=Path(args.summary_input_path),
        templates_dir=Path(args.templates_dir),
        static_dir=Path(args.static_dir),
        environment=str(args.environment).strip().lower(),
        public_base_url=_clean_optional(args.public_base_url),
        root_path=str(args.root_path or "").strip(),
        forwarded_allow_ips=str(args.forwarded_allow_ips),
        secret_key=_clean_optional(args.secret_key),
        secret_key_file=args.secret_key_file or (Path(env_secret_key_file) if env_secret_key_file else None),
        telegram_bot_token=_clean_optional(args.telegram_bot_token) or env_telegram_token,
        telegram_bot_token_file=args.telegram_bot_token_file
        or (Path(env_telegram_token_file) if env_telegram_token_file else None),
        telegram_chat_id=_clean_optional(args.telegram_chat_id) or env_telegram_chat_id,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validate_preflight(build_config_from_args(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
