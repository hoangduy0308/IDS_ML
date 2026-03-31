from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tomllib

import ids.ops.same_host_stack as stack  # noqa: E402
from ids.core.model_bundle import (  # noqa: E402
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _build_stack_config(tmp_path: Path) -> stack.SameHostStackConfig:
    repo_root = REPO_ROOT.resolve()
    operator_runtime = tmp_path / "runtime"
    operator_logs = tmp_path / "logs"
    operator_runtime.mkdir(parents=True, exist_ok=True)
    operator_logs.mkdir(parents=True, exist_ok=True)

    secret_key_file = tmp_path / "secrets" / "console.secret"
    secret_key_file.parent.mkdir(parents=True, exist_ok=True)
    secret_key_file.write_text("production-secret\n", encoding="utf-8")
    admin_password_file = tmp_path / "secrets" / "admin.password"
    admin_password_file.write_text("correct-password\n", encoding="utf-8")

    operator_env_file = tmp_path / "etc" / "ids-operator-console.env"
    operator_env_file.parent.mkdir(parents=True, exist_ok=True)
    operator_env_file.write_text(
        "\n".join(
            [
                f"IDS_OPERATOR_CONSOLE_DATABASE_PATH={operator_runtime / 'operator_console.db'}",
                f"IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH={operator_logs / 'ids_live_sensor_summary.jsonl'}",
                f"IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE={secret_key_file}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return stack.SameHostStackConfig(
        repo_root=repo_root,
        python_binary=Path(sys.executable).resolve(),
        operator_env_file=operator_env_file.resolve(),
        model_manage_entrypoint=(repo_root / "ids" / "ops" / "model_bundle_manage.py").resolve(),
        operator_manage_entrypoint=(repo_root / "ids" / "ops" / "operator_console_manage.py").resolve(),
        operator_server_entrypoint=(repo_root / "ids" / "console" / "server.py").resolve(),
        activation_path=(tmp_path / "runtime" / "active_bundle.json").resolve(),
        live_sensor_interface="eth0",
        dumpcap_binary=Path(sys.executable).resolve(),
        extractor_command_prefix=(str(Path(sys.executable).resolve()),),
        spool_dir=(tmp_path / "runtime" / "sensor").resolve(),
        alerts_output_path=(tmp_path / "logs" / "ids_live_alerts.jsonl").resolve(),
        quarantine_output_path=(tmp_path / "logs" / "ids_live_quarantine.jsonl").resolve(),
        summary_output_path=(tmp_path / "logs" / "ids_live_sensor_summary.jsonl").resolve(),
        candidate_bundle_root=(tmp_path / "bundles" / "candidate").resolve(),
        admin_username="admin",
        admin_password_file=admin_password_file.resolve(),
    )


def _run_python_command(argv: list[str]) -> str:
    completed = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(argv)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed.stdout.strip()


def test_repo_installable_bootstrap_proof_lifecycle_and_activation_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _build_stack_config(tmp_path)
    _write_bundle_contract(Path(config.candidate_bundle_root))

    executed: list[list[str]] = []

    def fake_runner(argv: list[str] | tuple[str, ...]) -> str:
        command = [str(part) for part in argv]
        executed.append(command)
        if len(command) >= 2 and command[1].endswith("model_bundle_manage.py"):
            module_command = [command[0], "-m", "ids.ops.model_bundle_manage", *command[2:]]
            return _run_python_command(module_command)
        if len(command) >= 2 and command[1].endswith("operator_console_manage.py"):
            if "migrate" in command:
                return json.dumps({"ok": True, "action": "migrate"})
            if "bootstrap-admin" in command:
                return json.dumps({"ok": True, "action": "bootstrap-admin"})
        if command[:2] == ["systemctl", "start"]:
            return ""
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(
        stack,
        "validate_stack_preflight",
        lambda _config: {"ready": True, "command": "preflight"},
    )
    monkeypatch.setattr(
        stack,
        "build_stack_status_payload",
        lambda *_args, **_kwargs: {
            "ready": True,
            "command": "status",
            "components": {"reverse_proxy_edge_seam": {"payload": {"configured": False}}},
        },
    )
    monkeypatch.setattr(
        stack,
        "build_stack_smoke_payload",
        lambda *_args, **_kwargs: {
            "ready": True,
            "command": "smoke",
            "components": {"reverse_proxy_edge_seam": {"payload": {"configured": False}}},
        },
    )
    monkeypatch.setattr(
        stack,
        "_build_notification_path_component",
        lambda _config: {"ok": True, "state": "disabled", "detail": None, "payload": {"enabled": False}},
    )

    payload = stack.run_stack_bootstrap(config, command_runner=fake_runner)

    assert payload["bootstrap_ready"] is True
    assert [step["step"] for step in payload["steps"]] == [
        "prepare_host_layout",
        "verify_candidate_bundle",
        "promote_candidate_bundle",
        "migrate_operator_console",
        "bootstrap_operator_admin",
        "stack_preflight",
        "start_operator_console_service",
        "start_live_sensor_service",
        "stack_status",
        "stack_smoke",
    ]

    verify_command = executed[0]
    promote_command = executed[1]
    assert verify_command[1].replace("\\", "/").endswith("ids/ops/model_bundle_manage.py")
    assert promote_command[1].replace("\\", "/").endswith("ids/ops/model_bundle_manage.py")
    assert "--activation-path" in verify_command and "--bundle-root" in verify_command
    assert "--activation-path" in promote_command and "--bundle-root" in promote_command

    activation_payload = stack.build_bundle_status_payload(Path(config.activation_path))
    assert activation_payload["runtime_ready"] is True
    assert activation_payload["active_bundle_name"] == "bundle-proof"


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
    assert "python3 -m ids.ops.live_sensor_preflight" in live_sensor_service
    assert "python3 -m ids.runtime.live_sensor" in live_sensor_service
