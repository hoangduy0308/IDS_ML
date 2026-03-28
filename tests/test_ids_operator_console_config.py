from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console import load_operator_console_config  # noqa: E402
import scripts.ids_operator_console_server as server  # noqa: E402


def test_load_operator_console_config_resolves_repo_relative_defaults(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    config = load_operator_console_config(environ={}, repo_root=repo_root)

    assert config.host == "127.0.0.1"
    assert config.port == 8765
    assert config.database_path == (repo_root / "artifacts/operator_console/operator_console.db").resolve()
    assert config.templates_dir == (repo_root / "scripts/ids_operator_console/templates").resolve()
    assert config.static_dir == (repo_root / "scripts/ids_operator_console/static").resolve()


def test_load_operator_console_config_rejects_invalid_port(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    env = {"IDS_OPERATOR_CONSOLE_PORT": "bad-port"}

    with pytest.raises(ValueError, match="IDS_OPERATOR_CONSOLE_PORT must be an integer"):
        load_operator_console_config(environ=env, repo_root=repo_root)


def test_build_operator_console_app_bootstraps_without_dashboard_modules(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    env = {
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(repo_root / "runtime" / "operator_console.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(repo_root / "templates_missing"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(repo_root / "static_missing"),
    }
    config = load_operator_console_config(environ=env, repo_root=repo_root)

    app = server.build_operator_console_app(config)

    assert app.state.operator_console_config == config
    assert app.state.templates is not None
    assert (repo_root / "runtime").exists()
    assert any(route.path == "/healthz" for route in app.routes)


def test_main_loads_config_and_invokes_run_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()

    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_DATABASE_PATH", str(runtime_root / "operator_console.db"))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TEMPLATES_DIR", str(runtime_root / "templates"))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_STATIC_DIR", str(runtime_root / "static"))

    captured: dict[str, object] = {}

    def fake_run_server(app: object, *, config: object) -> None:
        captured["app"] = app
        captured["config"] = config

    monkeypatch.setattr(server, "run_server", fake_run_server)

    exit_code = server.main(["--host", "0.0.0.0", "--port", "9900", "--log-level", "warning", "--reload"])

    assert exit_code == 0
    assert "app" in captured
    cfg = captured["config"]
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9900
    assert cfg.log_level == "warning"
    assert cfg.reload is True
