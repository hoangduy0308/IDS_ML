from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tomllib

import pytest

import ids.ops.same_host_stack as stack  # noqa: E402
from ids.core.model_bundle import (  # noqa: E402
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)
from ids.core.model_bundle_activation import SUPPORTED_ACTIVATION_RECORD_VERSION  # noqa: E402
from ids.ops.module_validation import resolve_importable_module  # noqa: E402
from repo_installable_proof_support import (
    REPO_ROOT,
    resolve_console_script,
    run_command,
    scripts_dir,
    _shadow_finder_sitecustomize_body,
    site_packages_dir,
    venv_python,
)


def _write_bundle_contract(bundle_root: Path) -> Path:
    bundle_root.mkdir(parents=True, exist_ok=True)
    feature_columns_path = bundle_root / "feature_columns.json"
    feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", "f2"]}),
        encoding="utf-8",
    )
    (bundle_root / "model.cbm").write_text("model", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "bundle_name": "bundle-proof",
                "created_at": "2026-03-29T00:00:00+07:00",
                "model_key": "catboost_full_data",
                "model_family": "CatBoostClassifier",
                "model_artifact": "model.cbm",
                "feature_columns_file": "feature_columns.json",
                "threshold": 0.5,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "feature_count": 2,
                "train_rows": 123,
                "metrics_file": "metrics.json",
                "training_summary_file": "training_summary.json",
                "compatibility": {
                    "feature_schema": build_feature_schema_metadata(feature_columns_path),
                    "inference_contract": build_inference_contract_metadata(
                        positive_label="Attack",
                        negative_label="Benign",
                        threshold=0.5,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return bundle_root


def _write_operator_env(
    path: Path,
    *,
    database_path: Path,
    alerts_output_path: Path,
    quarantine_output_path: Path,
    summary_output_path: Path,
    secret_key_file: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "IDS_OPERATOR_CONSOLE_ENVIRONMENT=production",
                "IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL=https://console.example",
                f"IDS_OPERATOR_CONSOLE_DATABASE_PATH={database_path}",
                f"IDS_OPERATOR_CONSOLE_ALERTS_INPUT_PATH={alerts_output_path}",
                f"IDS_OPERATOR_CONSOLE_QUARANTINE_INPUT_PATH={quarantine_output_path}",
                f"IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH={summary_output_path}",
                f"IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE={secret_key_file}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_sitecustomize(site_dir: Path) -> Path:
    site_dir.mkdir(parents=True, exist_ok=True)
    path = site_dir / "sitecustomize.py"
    path.write_text(
        "\n".join(
            [
                "import os",
                "if os.environ.get('IDS_TEST_BYPASS_INTERFACE') == '1':",
                "    import ids.ops.live_sensor_preflight as live_sensor_preflight",
                "    live_sensor_preflight._require_interface = lambda interface: interface",
            ]
        )
        + "\n"
        + _shadow_finder_sitecustomize_body(),
        encoding="utf-8",
    )
    return path


def _write_fake_systemctl(fake_bin: Path, *, venv_python: Path) -> Path:
    fake_bin.mkdir(parents=True, exist_ok=True)
    helper = fake_bin / "fake_systemctl.py"
    helper.write_text(
        "\n".join(
            [
                "from datetime import datetime, timezone",
                "import json",
                "import os",
                "from pathlib import Path",
                "import sys",
                "",
                "def _write_summary() -> None:",
                "    activation_path = Path(os.environ['IDS_TEST_FAKE_SYSTEMCTL_ACTIVATION_PATH'])",
                "    summary_output_path = Path(os.environ['IDS_TEST_FAKE_SYSTEMCTL_SUMMARY_OUTPUT'])",
                "    payload = json.loads(activation_path.read_text(encoding='utf-8'))",
                "    summary_output_path.parent.mkdir(parents=True, exist_ok=True)",
                "    summary_event = {",
                "        'event_type': 'live_sensor_summary',",
                "        'timestamp': datetime.now(timezone.utc).isoformat(),",
                "        'reason': 'capture-ok',",
                "        'active_bundle': {",
                "            'activation_path': str(activation_path.resolve()),",
                "            'active_bundle_root': payload['active_bundle_root'],",
                "            'active_bundle_name': payload['active_bundle_name'],",
                "        },",
                "    }",
                "    summary_output_path.write_text(json.dumps(summary_event) + '\\n', encoding='utf-8')",
                "",
                "def main(argv: list[str]) -> int:",
                "    log_path = Path(os.environ['IDS_TEST_FAKE_SYSTEMCTL_LOG'])",
                "    log_path.parent.mkdir(parents=True, exist_ok=True)",
                "    display_argv = [Path(argv[0]).name, *argv[1:]]",
                "    with log_path.open('a', encoding='utf-8') as handle:",
                "        handle.write(' '.join(display_argv) + '\\n')",
                "    if len(argv) >= 3 and argv[1] == 'start' and argv[2] == 'ids-live-sensor.service':",
                "        _write_summary()",
                "    return 0",
                "",
                "raise SystemExit(main(sys.argv))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    if os.name == "nt":
        wrapper = fake_bin / "systemctl.cmd"
        wrapper.write_text(
            f'@"{venv_python}" "{helper}" %*\r\n',
            encoding="utf-8",
        )
    else:
        wrapper = fake_bin / "systemctl"
        wrapper.write_text(
            f'#!/bin/sh\nexec "{venv_python}" "{helper}" "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        wrapper.chmod(wrapper.stat().st_mode | 0o111)
    return wrapper


def _stack_base_argv(
    *,
    ids_stack: Path,
    repo_root: Path,
    venv_python: Path,
    operator_env_file: Path,
    activation_path: Path,
    spool_dir: Path,
    alerts_output_path: Path,
    quarantine_output_path: Path,
    summary_output_path: Path,
) -> list[str]:
    return [
        str(ids_stack),
        "--repo-root",
        str(repo_root),
        "--python-binary",
        str(venv_python),
        "--operator-env-file",
        str(operator_env_file),
        "--activation-path",
        str(activation_path),
        "--interface",
        "test0",
        "--dumpcap-binary",
        str(venv_python),
        "--extractor-command-prefix",
        str(venv_python),
        "--spool-dir",
        str(spool_dir),
        "--alerts-output-path",
        str(alerts_output_path),
        "--quarantine-output-path",
        str(quarantine_output_path),
        "--summary-output-path",
        str(summary_output_path),
    ]


def test_repo_installable_bootstrap_proof_runs_installed_ids_stack_lifecycle(tmp_path: Path) -> None:
    venv_python_path = venv_python(tmp_path)
    install = run_command(
        [str(venv_python_path), "-m", "pip", "install", "-e", str(REPO_ROOT)],
        cwd=tmp_path,
    )
    assert install.returncode == 0, install.stderr

    scripts_dir_path = scripts_dir(venv_python_path)
    ids_stack = resolve_console_script(scripts_dir_path, "ids-stack")
    ids_bundle_manage = resolve_console_script(scripts_dir_path, "ids-model-bundle-manage")

    runtime_dir = tmp_path / "runtime"
    logs_dir = tmp_path / "logs"
    bundles_dir = tmp_path / "bundles"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    bundle_root = _write_bundle_contract(bundles_dir / "candidate")

    secret_key_file = tmp_path / "secrets" / "console.secret"
    secret_key_file.parent.mkdir(parents=True, exist_ok=True)
    secret_key_file.write_text("production-secret\n", encoding="utf-8")
    admin_password_file = tmp_path / "secrets" / "admin.password"
    admin_password_file.write_text("correct-password\n", encoding="utf-8")

    activation_path = runtime_dir / "active_bundle.json"
    spool_dir = runtime_dir / "sensor"
    alerts_output_path = logs_dir / "ids_live_alerts.jsonl"
    quarantine_output_path = logs_dir / "ids_live_quarantine.jsonl"
    summary_output_path = logs_dir / "ids_live_sensor_summary.jsonl"
    operator_env_file = _write_operator_env(
        tmp_path / "etc" / "ids-operator-console.env",
        database_path=runtime_dir / "operator_console.db",
        alerts_output_path=alerts_output_path,
        quarantine_output_path=quarantine_output_path,
        summary_output_path=summary_output_path,
        secret_key_file=secret_key_file,
    )

    site_packages = site_packages_dir(venv_python_path)
    _write_sitecustomize(site_packages)
    fake_bin = tmp_path / "fake-bin"
    _write_fake_systemctl(fake_bin, venv_python=venv_python_path)
    systemctl_log = tmp_path / "fake-systemctl.log"

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(fake_bin), env.get("PATH", "")])
    env["IDS_TEST_BYPASS_INTERFACE"] = "1"
    env["IDS_TEST_FAKE_SYSTEMCTL_ACTIVATION_PATH"] = str(activation_path)
    env["IDS_TEST_FAKE_SYSTEMCTL_SUMMARY_OUTPUT"] = str(summary_output_path)
    env["IDS_TEST_FAKE_SYSTEMCTL_LOG"] = str(systemctl_log)

    stack_base_argv = _stack_base_argv(
        ids_stack=ids_stack,
        repo_root=REPO_ROOT,
        venv_python=venv_python_path,
        operator_env_file=operator_env_file,
        activation_path=activation_path,
        spool_dir=spool_dir,
        alerts_output_path=alerts_output_path,
        quarantine_output_path=quarantine_output_path,
        summary_output_path=summary_output_path,
    )

    bootstrap = run_command(
        [
            *stack_base_argv,
            "--json",
            "bootstrap",
            "--candidate-bundle-root",
            str(bundle_root),
            "--admin-username",
            "admin",
            "--admin-password-file",
            str(admin_password_file),
        ],
        cwd=tmp_path,
        env=env,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr
    bootstrap_payload = json.loads(bootstrap.stdout)
    assert bootstrap_payload["bootstrap_ready"] is True
    assert [step["step"] for step in bootstrap_payload["steps"]] == [
        "stack_preflight",
        "prepare_host_layout",
        "verify_candidate_bundle",
        "promote_candidate_bundle",
        "migrate_operator_console",
        "bootstrap_operator_admin",
        "start_operator_console_service",
        "start_live_sensor_service",
        "stack_status",
        "stack_smoke",
    ]
    preflight_step = bootstrap_payload["steps"][0]["result"]
    assert preflight_step["ready"] is False
    assert preflight_step["bootstrap_gate_ready"] is True
    assert preflight_step["components"]["bundle_activation"]["ok"] is False
    assert preflight_step["components"]["live_sensor_preflight"]["ok"] is False
    assert preflight_step["components"]["operator_console_preflight"]["ok"] is False

    preflight = run_command([*stack_base_argv, "--json", "preflight"], cwd=tmp_path, env=env)
    status = run_command([*stack_base_argv, "--json", "status"], cwd=tmp_path, env=env)
    smoke = run_command([*stack_base_argv, "--json", "smoke"], cwd=tmp_path, env=env)
    bundle_status = run_command(
        [
            str(ids_bundle_manage),
            "--activation-path",
            str(activation_path),
            "--json",
            "status",
        ],
        cwd=tmp_path,
        env=env,
    )

    assert preflight.returncode == 0, preflight.stderr
    assert status.returncode == 0, status.stderr
    assert smoke.returncode == 0, smoke.stderr
    assert bundle_status.returncode == 0, bundle_status.stderr
    assert json.loads(preflight.stdout)["ready"] is True
    assert json.loads(status.stdout)["ready"] is True
    assert json.loads(smoke.stdout)["ready"] is True
    assert json.loads(bundle_status.stdout)["runtime_ready"] is True

    activation_payload = stack.build_bundle_status_payload(activation_path)
    activation_record = json.loads(activation_path.read_text(encoding="utf-8"))
    assert activation_payload["runtime_ready"] is True
    assert activation_payload["active_bundle_root"] == str(bundle_root.resolve())
    assert activation_payload["active_bundle_name"] == "bundle-proof"
    assert activation_payload["verification_status"] == "verified"
    assert activation_record["record_version"] == SUPPORTED_ACTIVATION_RECORD_VERSION
    assert activation_record["active_bundle_root"] == str(bundle_root.resolve())
    assert activation_record["active_bundle_name"] == "bundle-proof"
    assert activation_record["verification_status"] == "verified"
    assert "previous_bundle_root" not in activation_record
    assert "previous_bundle_name" not in activation_record

    systemctl_calls = systemctl_log.read_text(encoding="utf-8").splitlines()
    assert systemctl_calls == [
        "fake_systemctl.py start ids-operator-console.service",
        "fake_systemctl.py start ids-live-sensor.service",
    ]

    shadow_root = tmp_path / "shadow"
    shadow_path = shadow_root.joinpath("ids", "ops", "model_bundle_manage.py")
    shadow_path.parent.mkdir(parents=True, exist_ok=True)
    shadow_path.write_text("raise RuntimeError('shadowed import crash')\n", encoding="utf-8")

    shadow_env = dict(env)
    shadow_env["IDS_TEST_SHADOW_IMPORT_MODULE"] = "ids.ops.model_bundle_manage"
    shadow_env["IDS_TEST_SHADOW_IMPORT_ROOT"] = str(shadow_root)

    degraded_preflight = run_command(
        [
            *stack_base_argv,
            "--json",
            "preflight",
        ],
        cwd=tmp_path,
        env=shadow_env,
    )

    assert degraded_preflight.returncode == 2
    degraded_payload = json.loads(degraded_preflight.stdout)
    assert degraded_payload["ready"] is False
    assert degraded_payload["host_layout_checks"]["model_manage_module"]["state"] == "invalid"
    assert "model_manage_module resolved outside repo_root" in degraded_payload[
        "host_layout_checks"
    ]["model_manage_module"]["detail"]


def test_repo_installable_bootstrap_proof_rejects_clean_venv_without_install(tmp_path: Path) -> None:
    clean_python = venv_python(tmp_path)

    with pytest.raises(
        ValueError,
        match="app_module is not importable by python_binary: ids.console.server",
    ):
        resolve_importable_module(clean_python, "ids.console.server", name="app_module")


def test_repo_installable_bootstrap_proof_blocks_hostile_module_before_mutation(tmp_path: Path) -> None:
    venv_python_path = venv_python(tmp_path)
    install = run_command(
        [str(venv_python_path), "-m", "pip", "install", "-e", str(REPO_ROOT)],
        cwd=tmp_path,
    )
    assert install.returncode == 0, install.stderr

    scripts_dir_path = scripts_dir(venv_python_path)
    ids_stack = resolve_console_script(scripts_dir_path, "ids-stack")

    runtime_dir = tmp_path / "runtime"
    logs_dir = tmp_path / "logs"
    bundles_dir = tmp_path / "bundles"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    bundle_root = _write_bundle_contract(bundles_dir / "candidate")

    secret_key_file = tmp_path / "secrets" / "console.secret"
    secret_key_file.parent.mkdir(parents=True, exist_ok=True)
    secret_key_file.write_text("production-secret\n", encoding="utf-8")
    admin_password_file = tmp_path / "secrets" / "admin.password"
    admin_password_file.write_text("correct-password\n", encoding="utf-8")

    activation_path = runtime_dir / "active_bundle.json"
    spool_dir = runtime_dir / "sensor"
    alerts_output_path = logs_dir / "ids_live_alerts.jsonl"
    quarantine_output_path = logs_dir / "ids_live_quarantine.jsonl"
    summary_output_path = logs_dir / "ids_live_sensor_summary.jsonl"
    operator_env_file = _write_operator_env(
        tmp_path / "etc" / "ids-operator-console.env",
        database_path=runtime_dir / "operator_console.db",
        alerts_output_path=alerts_output_path,
        quarantine_output_path=quarantine_output_path,
        summary_output_path=summary_output_path,
        secret_key_file=secret_key_file,
    )

    site_packages = site_packages_dir(venv_python_path)
    _write_sitecustomize(site_packages)
    fake_bin = tmp_path / "fake-bin"
    _write_fake_systemctl(fake_bin, venv_python=venv_python_path)
    systemctl_log = tmp_path / "fake-systemctl.log"

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(fake_bin), env.get("PATH", "")])
    env["IDS_TEST_BYPASS_INTERFACE"] = "1"
    env["IDS_TEST_FAKE_SYSTEMCTL_ACTIVATION_PATH"] = str(activation_path)
    env["IDS_TEST_FAKE_SYSTEMCTL_SUMMARY_OUTPUT"] = str(summary_output_path)
    env["IDS_TEST_FAKE_SYSTEMCTL_LOG"] = str(systemctl_log)

    shadow_root = tmp_path / "shadow"
    shadow_path = shadow_root.joinpath("ids", "ops", "model_bundle_manage.py")
    shadow_path.parent.mkdir(parents=True, exist_ok=True)
    shadow_path.write_text("raise RuntimeError('shadowed import crash')\n", encoding="utf-8")

    shadow_env = dict(env)
    shadow_env["IDS_TEST_SHADOW_IMPORT_MODULE"] = "ids.ops.model_bundle_manage"
    shadow_env["IDS_TEST_SHADOW_IMPORT_ROOT"] = str(shadow_root)

    stack_base_argv = _stack_base_argv(
        ids_stack=ids_stack,
        repo_root=REPO_ROOT,
        venv_python=venv_python_path,
        operator_env_file=operator_env_file,
        activation_path=activation_path,
        spool_dir=spool_dir,
        alerts_output_path=alerts_output_path,
        quarantine_output_path=quarantine_output_path,
        summary_output_path=summary_output_path,
    )

    blocked_bootstrap = run_command(
        [
            *stack_base_argv,
            "--json",
            "bootstrap",
            "--candidate-bundle-root",
            str(bundle_root),
            "--admin-username",
            "admin",
            "--admin-password-file",
            str(admin_password_file),
        ],
        cwd=tmp_path,
        env=shadow_env,
    )

    assert blocked_bootstrap.returncode == 2, blocked_bootstrap.stderr
    blocked_payload = json.loads(blocked_bootstrap.stdout)
    assert blocked_payload["bootstrap_ready"] is False
    assert blocked_payload["status"] == "degraded"
    assert [step["step"] for step in blocked_payload["steps"]] == ["stack_preflight"]
    assert blocked_payload["diagnosis"]["preflight"]["bootstrap_gate_ready"] is False
    assert blocked_payload["diagnosis"]["preflight"]["host_layout_checks"]["model_manage_module"]["state"] == (
        "invalid"
    )
    assert not activation_path.exists()
    assert not (runtime_dir / "operator_console.db").exists()
    assert not systemctl_log.exists()


def test_repo_installable_bootstrap_proof_canonical_command_surface() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]
    assert scripts["ids-stack"] == "ids.ops.same_host_stack_manage:main"
    assert scripts["ids-model-bundle-manage"] == "ids.ops.model_bundle_manage:main"

    stack_doc = (REPO_ROOT / "docs" / "current" / "operations" / "ids_same_host_stack_operations.md").read_text(
        encoding="utf-8"
    )
    assert "ids-stack" in stack_doc
    assert "compatibility entrypoint" in stack_doc

    live_sensor_service = (REPO_ROOT / "deploy" / "systemd" / "ids-live-sensor.service").read_text(
        encoding="utf-8"
    )
    assert "/opt/ids_ml_new/.venv/bin/python -m ids.ops.live_sensor_preflight" in live_sensor_service
    assert "/opt/ids_ml_new/.venv/bin/python -m ids.runtime.live_sensor" in live_sensor_service
    assert "/usr/bin/python3" not in live_sensor_service
