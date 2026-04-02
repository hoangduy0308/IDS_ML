from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
from ids.console import load_operator_console_config, migrate_operator_store  # noqa: E402
from ids.console.auth import ensure_admin_user  # noqa: E402
from ids.console.db import open_existing_operator_store  # noqa: E402
import ids.console.server as canonical_server  # noqa: E402
import scripts.ids_operator_console_server as server  # noqa: E402


def _bootstrap_runtime_store(database_path: Path) -> None:
    migrate_operator_store(database_path, allow_bootstrap=True)
    store = open_existing_operator_store(database_path)
    try:
        ensure_admin_user(store, username="admin", password="correct-password")
    finally:
        store.close()


def test_console_server_wrapper_pins_supported_public_facade() -> None:
    assert server.__all__ == [
        "OPERATOR_CONSOLE_APP_IMPORT",
        "build_operator_console_app",
        "create_operator_console_app",
        "run_server",
        "main",
    ]
    assert server.OPERATOR_CONSOLE_APP_IMPORT == canonical_server.OPERATOR_CONSOLE_APP_IMPORT
    assert server.build_operator_console_app is canonical_server.build_operator_console_app
    assert server.create_operator_console_app is canonical_server.create_operator_console_app


def test_load_operator_console_config_resolves_repo_relative_defaults(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    config = load_operator_console_config(environ={}, repo_root=repo_root)

    assert config.environment == "development"
    assert config.host == "127.0.0.1"
    assert config.port == 8765
    assert config.database_path == (repo_root / "artifacts/operator_console/operator_console.db").resolve()
    assert config.templates_dir == (repo_root / "ids/console/templates").resolve()
    assert config.static_dir == (repo_root / "ids/console/static").resolve()
    assert config.session_cookie_https_only is False
    assert config.root_path == ""


def test_load_operator_console_config_supports_secret_file_and_proxy_contract(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    secret_path = repo_root / "secrets" / "console.secret"
    secret_path.parent.mkdir(parents=True)
    secret_path.write_text("very-secret-value\n", encoding="utf-8")

    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "production",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE": str(secret_path),
        "IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL": "https://console.example/internal",
        "IDS_OPERATOR_CONSOLE_ROOT_PATH": "/internal",
        "IDS_OPERATOR_CONSOLE_FORWARDED_ALLOW_IPS": "127.0.0.1,10.0.0.10",
    }

    config = load_operator_console_config(environ=env, repo_root=repo_root)

    assert config.environment == "production"
    assert config.secret_key == "very-secret-value"
    assert config.secret_key_source == secret_path.resolve()
    assert config.public_base_url == "https://console.example/internal"
    assert config.root_path == "/internal"
    assert config.session_cookie_https_only is True
    assert config.session_cookie_path == "/internal"


def test_load_operator_console_config_rejects_invalid_port(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    env = {"IDS_OPERATOR_CONSOLE_PORT": "bad-port"}

    with pytest.raises(ValueError, match="IDS_OPERATOR_CONSOLE_PORT must be an integer"):
        load_operator_console_config(environ=env, repo_root=repo_root)


def test_load_operator_console_config_rejects_insecure_production_contract(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "production",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "change-me",
        "IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL": "http://console.example",
    }

    with pytest.raises(ValueError, match="placeholder value|must use https"):
        load_operator_console_config(environ=env, repo_root=repo_root)


def test_build_operator_console_app_wires_health_and_console_routes(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    templates_dir = REPO_ROOT / "ids/console/templates"
    static_dir = REPO_ROOT / "ids/console/static"
    db_path = repo_root / "runtime" / "operator_console.db"
    _bootstrap_runtime_store(db_path)
    env = {
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(db_path),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(templates_dir),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(static_dir),
    }
    config = load_operator_console_config(environ=env, repo_root=repo_root)

    app = server.build_operator_console_app(config)
    client = TestClient(app)

    assert app.state.operator_console_config == config
    assert app.state.templates is not None
    assert any(route.path == "/healthz" for route in app.routes)
    assert any(route.path == "/readyz" for route in app.routes)
    assert any(route.path == "/overview" for route in app.routes)
    assert any(route.path == "/alerts" for route in app.routes)
    assert any(route.path == "/operations" for route in app.routes)
    assert any(route.path == "/reports" for route in app.routes)
    assert any(route.path == "/dashboard" for route in app.routes)
    assert any(route.path == "/anomalies" for route in app.routes)
    assert any(route.path == "/api/v1/console/snapshot" for route in app.routes)

    health_response = client.get("/healthz")
    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert health_payload == {
        "status": "ok",
        "service": "ids-operator-console",
    }

    ready_response = client.get("/readyz")
    assert ready_response.status_code == 200
    ready_payload = ready_response.json()
    assert ready_payload == {
        "status": "ok",
        "ready": True,
        "service": "ids-operator-console",
    }

    root_response = client.get("/", follow_redirects=False)
    assert root_response.status_code == 303
    assert root_response.headers["location"] == "/login"


def test_main_loads_config_and_invokes_run_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    db_path = runtime_root / "operator_console.db"
    _bootstrap_runtime_store(db_path)

    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TEMPLATES_DIR", str(REPO_ROOT / "ids/console/templates"))
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_STATIC_DIR", str(REPO_ROOT / "ids/console/static"))

    captured: dict[str, object] = {}

    def fake_run_server(*, config: object) -> None:
        captured["config"] = config

    monkeypatch.setattr(server, "run_server", fake_run_server)

    exit_code = server.main(["--host", "0.0.0.0", "--port", "9900", "--log-level", "warning", "--reload"])

    assert exit_code == 0
    cfg = captured["config"]
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9900
    assert cfg.log_level == "warning"
    assert cfg.reload is True


def test_run_server_forwards_full_uvicorn_runtime_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    db_path = repo_root / "runtime" / "operator_console.db"
    _bootstrap_runtime_store(db_path)

    env = {
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(db_path),
        "IDS_OPERATOR_CONSOLE_HOST": "0.0.0.0",
        "IDS_OPERATOR_CONSOLE_PORT": "9900",
        "IDS_OPERATOR_CONSOLE_LOG_LEVEL": "warning",
        "IDS_OPERATOR_CONSOLE_RELOAD": "true",
        "IDS_OPERATOR_CONSOLE_FORWARDED_ALLOW_IPS": "127.0.0.1,10.0.0.10",
        "IDS_OPERATOR_CONSOLE_ROOT_PATH": "/internal",
    }
    config = load_operator_console_config(environ=env, repo_root=repo_root)

    captured: dict[str, object] = {}

    def fake_uvicorn_run(app: object, **kwargs: object) -> None:
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(canonical_server.uvicorn, "run", fake_uvicorn_run)

    server.run_server(config=config)

    assert captured["app"] == canonical_server.OPERATOR_CONSOLE_APP_IMPORT
    assert captured["kwargs"] == {
        "host": config.host,
        "port": config.port,
        "log_level": config.log_level,
        "reload": config.reload,
        "factory": True,
        "proxy_headers": True,
        "forwarded_allow_ips": config.forwarded_allow_ips,
        "root_path": config.root_path,
    }
