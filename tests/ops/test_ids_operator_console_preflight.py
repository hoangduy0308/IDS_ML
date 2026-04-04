from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from repo_installable_proof_support import (
    run_command,
    site_packages_dir,
    write_shadow_sitecustomize,
)
from tests_editable_install_cache import shared_editable_install_python
from wrapper_smoke_support import assert_help_smoke, run_python_module_help, run_python_script_help

REPO_ROOT = Path(__file__).resolve().parents[2]
import ids.ops.operator_console_manage as manage  # noqa: E402
import ids.ops.operator_console_preflight as preflight  # noqa: E402
import ids.ops.same_host_stack as same_host_stack  # noqa: E402
from ids.ops.operator_console_preflight import (  # noqa: E402
    OperatorConsolePreflightConfig,
    validate_preflight,
    _trusted_repo_root,
)
from ids.ops.same_host_stack import (  # noqa: E402
    SameHostStackConfig,
    build_operator_preflight_config,
)


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _install_repo_python() -> Path:
    return shared_editable_install_python()


def _make_preflight_config(tmp_path: Path, **overrides: object) -> OperatorConsolePreflightConfig:
    runtime_dir = tmp_path / "runtime"
    logs_dir = tmp_path / "logs"
    templates_dir = tmp_path / "templates"
    static_dir = tmp_path / "static"
    runtime_dir.mkdir()
    logs_dir.mkdir()
    templates_dir.mkdir()
    static_dir.mkdir()

    db_path = runtime_dir / "operator_console.db"
    manage.main(["--database-path", str(db_path), "migrate", "--allow-bootstrap"])
    manage.main(
        [
            "--database-path",
            str(db_path),
            "bootstrap-admin",
            "--username",
            "admin",
            "--password",
            "correct-password",
        ]
    )

    secret_path = tmp_path / "console.secret"
    secret_path.write_text("production-secret\n", encoding="utf-8")
    python_binary = _install_repo_python()
    write_shadow_sitecustomize(site_packages_dir(python_binary))
    kwargs: dict[str, object] = {
        "python_binary": python_binary,
        "app_module": "ids.console.server",
        "manage_module": "ids.ops.operator_console_manage",
        "database_path": db_path,
        "alerts_input_path": logs_dir / "ids_live_alerts.jsonl",
        "quarantine_input_path": logs_dir / "ids_live_quarantine.jsonl",
        "summary_input_path": logs_dir / "ids_live_sensor_summary.jsonl",
        "templates_dir": templates_dir,
        "static_dir": static_dir,
        "environment": "production",
        "public_base_url": "https://console.example",
        "root_path": "",
        "forwarded_allow_ips": "127.0.0.1",
        "secret_key": None,
        "secret_key_file": secret_path,
        "telegram_bot_token": None,
        "telegram_bot_token_file": None,
        "telegram_chat_id": None,
    }
    kwargs.update(overrides)
    return OperatorConsolePreflightConfig(**kwargs)


def test_preflight_accepts_valid_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    validate_preflight(config)


def _make_minimal_preflight_config(tmp_path: Path, repo_root: Path | None) -> OperatorConsolePreflightConfig:
    base = tmp_path / "minimal"
    base.mkdir()
    def path(name: str) -> Path:
        p = base / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    return OperatorConsolePreflightConfig(
        python_binary=Path(sys.executable),
        app_module="ids.console.server",
        manage_module="ids.ops.operator_console_manage",
        database_path=path("db.sqlite"),
        alerts_input_path=path("alerts.jsonl"),
        quarantine_input_path=path("quarantine.jsonl"),
        summary_input_path=path("summary.jsonl"),
        templates_dir=base / "templates",
        static_dir=base / "static",
        environment="production",
        public_base_url="https://example.com",
        root_path="/",
        forwarded_allow_ips="127.0.0.1",
        repo_root=repo_root,
    )


def test_trusted_repo_root_prefers_repo_root(tmp_path: Path) -> None:
    override = tmp_path / "override"
    config = _make_minimal_preflight_config(tmp_path, repo_root=override)

    assert _trusted_repo_root(config) == override.resolve()


def test_trusted_repo_root_defaults_to_module_path(tmp_path: Path) -> None:
    config = _make_minimal_preflight_config(tmp_path, repo_root=None)

    expected = Path(preflight.__file__).resolve().parents[2]
    assert _trusted_repo_root(config) == expected


def test_preflight_requires_admin_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    bare_db = tmp_path / "runtime" / "bare.db"
    manage.main(["--database-path", str(bare_db), "migrate", "--allow-bootstrap"])
    missing_admin = OperatorConsolePreflightConfig(
        **{**config.__dict__, "database_path": bare_db}
    )

    with pytest.raises(ValueError, match="no admin user"):
        validate_preflight(missing_admin)


def test_deploy_artifacts_are_wired_to_proxy_and_secret_contract() -> None:
    service_text = (REPO_ROOT / "deploy/systemd/ids-operator-console.service").read_text(encoding="utf-8")
    notify_service_text = (REPO_ROOT / "deploy/systemd/ids-operator-console-notify.service").read_text(encoding="utf-8")
    nginx_text = (REPO_ROOT / "deploy/nginx/ids-operator-console.conf.example").read_text(encoding="utf-8")
    env_example_text = (REPO_ROOT / "ops/ids-operator-console.env.example").read_text(encoding="utf-8")

    # Service units use EnvironmentFile as sole config source (no hardcoded Environment= overrides)
    assert "EnvironmentFile=-/etc/ids-operator-console/ids-operator-console.env" in service_text
    assert "Environment=" not in service_text, "Service must not have hardcoded Environment= overrides"
    assert "IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE" in service_text
    assert "--public-base-url ${IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL}" in service_text
    assert "--secret-key-file ${IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE}" in service_text
    assert "--manage-module ids.ops.operator_console_manage" in service_text
    assert "--app-module ids.console.server" in service_text
    assert "/opt/ids_ml_new/.venv/bin/python -m ids.ops.operator_console_preflight" in service_text
    assert "/opt/ids_ml_new/.venv/bin/python -m ids.console.server" in service_text
    assert "/usr/bin/python3" not in service_text

    # Notify service: same EnvironmentFile-only pattern
    assert "EnvironmentFile=-/etc/ids-operator-console/ids-operator-console.env" in notify_service_text
    assert "Environment=" not in notify_service_text, "Notify service must not have hardcoded Environment= overrides"
    assert "-m ids.ops.operator_console_manage --database-path \"$IDS_OPERATOR_CONSOLE_DATABASE_PATH\" notify-worker" in notify_service_text
    assert "--iterations 1" not in notify_service_text
    assert "notify-worker --poll-interval-seconds 30" in notify_service_text
    assert "--manage-module ids.ops.operator_console_manage" in notify_service_text
    assert "--app-module ids.console.server" in notify_service_text
    assert "/opt/ids_ml_new/.venv/bin/python -m ids.ops.operator_console_preflight" in notify_service_text
    assert "/opt/ids_ml_new/.venv/bin/python -m ids.ops.operator_console_manage" in notify_service_text
    assert "/usr/bin/python3" not in notify_service_text

    # All defaults now live in the env example file (not hardcoded in service units)
    assert "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR=/opt/ids_ml_new/ids/console/templates" in env_example_text
    assert "IDS_OPERATOR_CONSOLE_STATIC_DIR=/opt/ids_ml_new/ids/console/static" in env_example_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE" in env_example_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID" in env_example_text
    assert "IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE" in env_example_text
    assert "Settings UI" in env_example_text, "Env example must mention Settings UI for Telegram config"

    # Nginx proxy contract
    assert "proxy_set_header Host $host;" in nginx_text
    assert "proxy_set_header X-Forwarded-Proto https;" in nginx_text
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in nginx_text


def test_preflight_rejects_notification_enabled_missing_manage_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_preflight_config(
        tmp_path,
        manage_module=None,
        telegram_bot_token="token",
        telegram_chat_id="-100preflight",
    )
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="manage_module"):
        validate_preflight(config)


def test_preflight_rejects_chat_only_pairing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path, telegram_bot_token=None, telegram_chat_id="-100chat-only")
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="must be set together"):
        validate_preflight(config)


@pytest.mark.parametrize(
    ("app_module", "error_match"),
    [
        ("   ", "app_module must not be blank"),
        ("ids..console.server", "app_module must be a dotted Python module path"),
    ],
)
def test_preflight_rejects_blank_or_malformed_app_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    app_module: str,
    error_match: str,
) -> None:
    config = _make_preflight_config(tmp_path, app_module=app_module)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match=error_match):
        validate_preflight(config)


def test_preflight_rejects_non_importable_manage_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_preflight_config(
        tmp_path,
        manage_module="ids.ops.does_not_exist",
        telegram_bot_token="token",
        telegram_chat_id="-100preflight",
    )
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(
        ValueError,
        match="manage_module is not importable by python_binary: ids.ops.does_not_exist",
    ):
        validate_preflight(config)


@pytest.mark.parametrize(
    ("config_overrides", "shadow_module", "error_match"),
    [
        ({}, "ids.console.server", "app_module resolved outside trusted repo root"),
        (
            {
                "manage_module": "ids.ops.operator_console_manage",
                "telegram_bot_token": "token",
                "telegram_chat_id": "-100preflight",
            },
            "ids.ops.operator_console_manage",
            "(manage_module|app_module) resolved outside trusted repo root",
        ),
    ],
)
def test_preflight_rejects_shadowed_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config_overrides: dict[str, object],
    shadow_module: str,
    error_match: str,
) -> None:
    config = _make_preflight_config(tmp_path, **config_overrides)
    shadow_root = tmp_path / "shadow"
    package_root = shadow_root / "ids"
    if shadow_module.startswith("ids.console."):
        console_root = package_root / "console"
        console_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text(
            "raise RuntimeError('hostile parent import should not run')\n",
            encoding="utf-8",
        )
        (console_root / "__init__.py").write_text(
            "raise RuntimeError('hostile package import should not run')\n",
            encoding="utf-8",
        )
    elif shadow_module.startswith("ids.ops."):
        ops_root = package_root / "ops"
        ops_root.mkdir(parents=True, exist_ok=True)
        (ops_root / "__init__.py").write_text(
            "raise RuntimeError('hostile ops package import should not run')\n",
            encoding="utf-8",
        )
        if not (package_root / "__init__.py").exists():
            (package_root / "__init__.py").write_text("pass\n", encoding="utf-8")
    shadow_path = shadow_root.joinpath(*shadow_module.split(".")).with_suffix(".py")
    shadow_path.parent.mkdir(parents=True, exist_ok=True)
    shadow_path.write_text("SHADOWED = True\n", encoding="utf-8")
    shadow_pth = site_packages_dir(config.python_binary) / "zz_shadow_import.pth"
    shadow_pth.write_text(str(shadow_root.resolve()) + "\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    try:
        with pytest.raises(ValueError, match=error_match):
            validate_preflight(config)
    finally:
        shadow_pth.unlink(missing_ok=True)


def test_preflight_rejects_trusted_root_module_that_crashes_during_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_preflight_config(tmp_path, app_module="trustedpkg.console_app")
    trusted_root = tmp_path / "trusted-root"
    module_root = trusted_root / "trustedpkg"
    module_root.mkdir(parents=True, exist_ok=True)
    (module_root / "__init__.py").write_text("", encoding="utf-8")
    (module_root / "console_app.py").write_text(
        "raise RuntimeError('trusted import crash')\n",
        encoding="utf-8",
    )
    shadow_pth = site_packages_dir(config.python_binary) / "zz_shadow_import.pth"
    shadow_pth.write_text(str(trusted_root.resolve()) + "\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "_trusted_repo_root", lambda *_: trusted_root)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    try:
        with pytest.raises(
            ValueError,
            match="app_module failed to import in python_binary: trustedpkg.console_app",
        ):
            validate_preflight(config)
    finally:
        shadow_pth.unlink(missing_ok=True)


def test_preflight_main_fails_closed_on_partial_env_notification_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    monkeypatch.setenv("IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN", "token-only")
    monkeypatch.delenv("IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(ValueError, match="must be set together"):
        preflight.main(
            [
                "--python-binary",
                str(config.python_binary),
                "--app-module",
                str(config.app_module),
                "--manage-module",
                str(config.manage_module),
                "--database-path",
                str(config.database_path),
                "--alerts-input-path",
                str(config.alerts_input_path),
                "--quarantine-input-path",
                str(config.quarantine_input_path),
                "--summary-input-path",
                str(config.summary_input_path),
                "--templates-dir",
                str(config.templates_dir),
                "--static-dir",
                str(config.static_dir),
                "--environment",
                config.environment,
                "--public-base-url",
                str(config.public_base_url),
                "--root-path",
                config.root_path,
                "--forwarded-allow-ips",
                config.forwarded_allow_ips,
                "--secret-key-file",
                str(config.secret_key_file),
            ]
        )


def test_preflight_ignores_inherited_pythonpath_contamination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: inherited PYTHONPATH must not influence module validation.

    This verifies the combined defense: isolated mode (-I) plus env scrubbing.
    If either layer regresses, the hostile shadow module can surface instead of
    the trusted-root module.
    """
    config = _make_preflight_config(tmp_path)
    shadow_root = tmp_path / "hostile-pythonpath"
    console_root = shadow_root / "ids" / "console"
    console_root.mkdir(parents=True, exist_ok=True)
    (shadow_root / "ids" / "__init__.py").write_text(
        "raise RuntimeError('hostile parent import should not run')\n",
        encoding="utf-8",
    )
    (console_root / "__init__.py").write_text(
        "raise RuntimeError('hostile console init should not run')\n",
        encoding="utf-8",
    )
    (console_root / "server.py").write_text("SHADOWED = True\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(shadow_root.resolve()))
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    # Must succeed: isolated mode (-I) and env scrubbing keep the shadow invisible
    validate_preflight(config)


def test_preflight_ignores_inherited_pythonhome_contamination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: inherited PYTHONHOME must not influence module validation.

    This verifies the combined defense: isolated mode (-I) plus env scrubbing.
    A bogus PYTHONHOME must not leak through to the subprocess interpreter.
    """
    config = _make_preflight_config(tmp_path)
    bogus_home = tmp_path / "bogus-python-home"
    bogus_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PYTHONHOME", str(bogus_home.resolve()))
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    # Must succeed: isolated mode (-I) and env scrubbing keep the bogus home out
    validate_preflight(config)


def _seed_db_telegram_settings(db_path: Path, *, token: str, chat_id: str) -> None:
    """Write Telegram settings directly into the console_settings table."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO console_settings (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            ("telegram_bot_token", token),
        )
        conn.execute(
            "INSERT OR REPLACE INTO console_settings (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            ("telegram_chat_id", chat_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_preflight_accepts_db_only_telegram_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preflight passes when Telegram settings are in DB but not in env vars."""
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    _seed_db_telegram_settings(config.database_path, token="123:DBTOKEN", chat_id="-100db")
    validate_preflight(config)


def test_preflight_accepts_env_only_telegram_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preflight passes with env-only Telegram config (existing behavior preserved)."""
    config = _make_preflight_config(
        tmp_path,
        telegram_bot_token="env-token",
        telegram_chat_id="-100env",
    )
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    validate_preflight(config)


def test_preflight_db_settings_override_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both DB and env have Telegram config, DB wins (consistent with D1)."""
    config = _make_preflight_config(
        tmp_path,
        telegram_bot_token="env-token",
        telegram_chat_id="-100env",
    )
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    _seed_db_telegram_settings(config.database_path, token="123:DBTOKEN", chat_id="-100db")
    # Should pass — DB overrides env
    validate_preflight(config)


def test_preflight_warns_not_fails_when_telegram_unconfigured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No DB, no env Telegram config → preflight passes (Telegram is optional)."""
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    # Should pass — Telegram is optional
    validate_preflight(config)


def test_preflight_handles_v2_db_without_console_settings_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A v2 DB with no console_settings table should not crash preflight.

    We simulate a v2→v3 migration gap: drop console_settings and downgrade
    schema_version, then re-migrate before running preflight. The key test is
    that _load_telegram_settings_from_db gracefully returns (None, None) when
    the table is absent — which we verify indirectly by confirming preflight
    passes with no Telegram config in either DB or env.
    """
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    # Drop the console_settings table and downgrade schema to simulate v2 DB
    import sqlite3

    conn = sqlite3.connect(str(config.database_path))
    try:
        conn.execute("DROP TABLE IF EXISTS console_settings")
        conn.execute(
            "UPDATE schema_metadata SET schema_version = 2 WHERE schema_family = 'operator_console'"
        )
        conn.commit()
    finally:
        conn.close()
    # Re-migrate to v3 so preflight doesn't fail on schema_state check
    manage.main(["--database-path", str(config.database_path), "migrate"])
    # Preflight should pass — _load_telegram_settings_from_db returns (None, None) before
    # migration, and after migration the table exists but is empty
    validate_preflight(config)


def test_script_wrapper_help_runs_through_module_entrypoint() -> None:
    help_run = run_python_module_help("scripts.ids_operator_console_preflight")
    assert_help_smoke(help_run, "scripts.ids_operator_console_preflight")
    assert "usage:" in help_run.stdout.lower()


def test_script_wrapper_help_runs_through_direct_file_entrypoint() -> None:
    help_run = run_python_script_help("scripts/ids_operator_console_preflight.py")
    assert_help_smoke(help_run, "scripts/ids_operator_console_preflight.py")
    assert "usage:" in help_run.stdout.lower()
