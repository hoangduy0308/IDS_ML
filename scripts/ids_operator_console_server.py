from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
from typing import Sequence

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console import OperatorConsoleConfig, load_operator_console_config


def build_operator_console_app(config: OperatorConsoleConfig) -> FastAPI:
    config.ensure_runtime_dirs()
    templates = Jinja2Templates(directory=str(config.templates_dir))

    app = FastAPI(title="IDS Operator Console", version="0.1.0")
    app.state.operator_console_config = config
    app.state.templates = templates

    if config.static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(config.static_dir)), name="static")

    @app.get("/healthz", response_class=JSONResponse)
    def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "ids-operator-console",
            "database_path": str(config.database_path),
        }

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        dashboard_template = config.templates_dir / "dashboard.html"
        if dashboard_template.exists():
            return templates.TemplateResponse(
                request=request,
                name="dashboard.html",
                context={
                    "request": request,
                    "title": "IDS Operator Console",
                },
            )
        return HTMLResponse(
            "<html><body><h1>IDS Operator Console bootstrap ready</h1></body></html>"
        )

    return app


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the IDS Operator Console service.")
    parser.add_argument("--host", help="Override bind host from environment config.")
    parser.add_argument("--port", type=int, help="Override bind port from environment config.")
    parser.add_argument("--log-level", help="Override log level from environment config.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn reload mode (development only).",
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


def run_server(app: FastAPI, *, config: OperatorConsoleConfig) -> None:
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level,
        reload=config.reload,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = _apply_cli_overrides(load_operator_console_config(), args)
    app = build_operator_console_app(config)
    run_server(app, config=config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
