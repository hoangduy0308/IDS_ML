from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


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
    secret_key: str
    telegram_bot_token: str | None = None
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


def validate_preflight(config: OperatorConsolePreflightConfig) -> None:
    _require_existing_file(config.python_binary, name="python_binary", executable=True)
    _require_existing_file(config.app_entrypoint, name="app_entrypoint")
    _require_existing_parent(config.database_path, name="database_path")
    _require_existing_parent(config.alerts_input_path, name="alerts_input_path")
    _require_existing_parent(config.quarantine_input_path, name="quarantine_input_path")
    _require_existing_parent(config.summary_input_path, name="summary_input_path")
    _require_existing_directory(config.templates_dir, name="templates_dir")
    _require_existing_directory(config.static_dir, name="static_dir")

    secret_key = config.secret_key.strip()
    if not secret_key:
        raise ValueError("secret_key must not be blank")
    if secret_key == "change-me":
        raise ValueError("secret_key must not use default placeholder value")

    token = _clean_optional(config.telegram_bot_token)
    chat_id = _clean_optional(config.telegram_chat_id)
    if (token is None) != (chat_id is None):
        raise ValueError(
            "telegram_bot_token and telegram_chat_id must be set together or both omitted"
        )


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
    parser.add_argument("--secret-key", required=True)
    parser.add_argument("--telegram-bot-token", default=None)
    parser.add_argument("--telegram-chat-id", default=None)
    return parser.parse_args(argv)


def build_config_from_args(args: argparse.Namespace) -> OperatorConsolePreflightConfig:
    return OperatorConsolePreflightConfig(
        python_binary=Path(args.python_binary),
        app_entrypoint=Path(args.app_entrypoint),
        database_path=Path(args.database_path),
        alerts_input_path=Path(args.alerts_input_path),
        quarantine_input_path=Path(args.quarantine_input_path),
        summary_input_path=Path(args.summary_input_path),
        templates_dir=Path(args.templates_dir),
        static_dir=Path(args.static_dir),
        secret_key=str(args.secret_key),
        telegram_bot_token=_clean_optional(args.telegram_bot_token),
        telegram_chat_id=_clean_optional(args.telegram_chat_id),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validate_preflight(build_config_from_args(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
