from __future__ import annotations

import argparse
from dataclasses import replace
from typing import Sequence

import uvicorn
from fastapi import FastAPI

from ids.console import OperatorConsoleConfig, load_operator_console_config
from ids.console.web import create_operator_console_web_app

OPERATOR_CONSOLE_APP_IMPORT = "ids.console.server:create_operator_console_app"


def build_operator_console_app(config: OperatorConsoleConfig) -> FastAPI:
    return create_operator_console_web_app(config)


def create_operator_console_app() -> FastAPI:
    return build_operator_console_app(load_operator_console_config())


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the IDS Operator Console service.")
    parser.add_argument("--host", help="Override bind host from environment config.")
    parser.add_argument("--port", type=int, help="Override bind port from environment config.")
    parser.add_argument("--log-level", help="Override log level from environment config.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn reload mode via the factory import string (development only).",
    )
    return parser.parse_args(argv)


def _apply_cli_overrides(config: OperatorConsoleConfig, args: argparse.Namespace) -> OperatorConsoleConfig:
    updates: dict[str, object] = {}
    if args.host is not None:
        updates["host"] = args.host
    if args.port is not None:
        updates["port"] = args.port
    if args.log_level is not None:
        updates["log_level"] = args.log_level
    if args.reload:
        updates["reload"] = True
    if not updates:
        return config
    return replace(config, **updates)


def run_server(*, config: OperatorConsoleConfig) -> None:
    uvicorn.run(
        OPERATOR_CONSOLE_APP_IMPORT,
        host=config.host,
        port=config.port,
        log_level=config.log_level,
        reload=config.reload,
        factory=True,
        proxy_headers=True,
        forwarded_allow_ips=config.forwarded_allow_ips,
        root_path=config.root_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = _apply_cli_overrides(load_operator_console_config(), args)
    run_server(config=config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
