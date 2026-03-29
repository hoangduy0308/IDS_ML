from __future__ import annotations

import os
from pathlib import Path
import sys
import json

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.ids_live_sensor_preflight as preflight  # noqa: E402
from scripts.ids_live_sensor_preflight import (  # noqa: E402
    LiveSensorPreflightConfig,
    validate_preflight,
)
from scripts.ids_model_bundle import (  # noqa: E402
    ModelBundleContractError,
    build_activation_record_payload,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
    write_activation_record,
)


def make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def write_bundle_contract(bundle_root: Path) -> Path:
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
                "bundle_name": "bundle-under-test",
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


def make_config(tmp_path: Path, **overrides: object) -> LiveSensorPreflightConfig:
    spool_dir = tmp_path / "spool"
    log_dir = tmp_path / "logs"
    spool_dir.mkdir()
    log_dir.mkdir()
    bundle_root = write_bundle_contract(tmp_path / "bundle")
    activation_path = tmp_path / "active_bundle.json"
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=bundle_root,
            active_bundle_name="bundle-under-test",
            activated_at="2026-03-29T00:00:00+07:00",
        ),
    )
    kwargs: dict[str, object] = {
        "interface": "eth0",
        "dumpcap_binary": make_executable(tmp_path / "bin" / "dumpcap"),
        "java_binary": make_executable(tmp_path / "bin" / "java"),
        "extractor_binary": make_executable(tmp_path / "bin" / "Cmd"),
        "jnetpcap_path": tmp_path / "lib" / "jnetpcap.jar",
        "activation_path": activation_path,
        "spool_dir": spool_dir,
        "alerts_output_path": log_dir / "alerts.jsonl",
        "quarantine_output_path": log_dir / "quarantine.jsonl",
        "summary_output_path": log_dir / "summary.jsonl",
    }
    Path(kwargs["jnetpcap_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(kwargs["jnetpcap_path"]).write_text("jar", encoding="utf-8")
    kwargs.update(overrides)
    return LiveSensorPreflightConfig(**kwargs)


def test_validate_preflight_accepts_existing_runtime_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_config(tmp_path)
    network_root = tmp_path / "sys" / "class" / "net" / config.interface
    network_root.mkdir(parents=True)

    real_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if path == Path("/sys/class/net") / config.interface:
            return True
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    validate_preflight(config)


def test_validate_preflight_rejects_missing_interface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_config(tmp_path, interface="missing0")
    real_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if path == Path("/sys/class/net") / "missing0":
            return False
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(FileNotFoundError, match="interface not found"):
        validate_preflight(config)


def test_validate_preflight_rejects_non_executable_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    non_exec_binary = tmp_path / "bin" / "dumpcap-nonexec"
    non_exec_binary.parent.mkdir(parents=True, exist_ok=True)
    non_exec_binary.write_text("not executable\n", encoding="utf-8")
    config = make_config(tmp_path, dumpcap_binary=non_exec_binary)
    real_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if path == Path("/sys/class/net") / config.interface:
            return True
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(
        preflight,
        "_is_executable_file",
        lambda path: False if Path(path) == config.dumpcap_binary else True,
    )

    with pytest.raises(PermissionError, match="dumpcap_binary is not executable"):
        validate_preflight(config)


def test_validate_preflight_rejects_missing_activation_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_config(tmp_path, activation_path=tmp_path / "missing.json")
    real_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if path == Path("/sys/class/net") / config.interface:
            return True
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(FileNotFoundError, match="activation_path not found"):
        validate_preflight(config)


def test_validate_preflight_rejects_incompatible_active_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_config(tmp_path)
    manifest_path = config.activation_path.parent / "bundle" / "model_bundle.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["compatibility"]["feature_schema"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    real_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if path == Path("/sys/class/net") / config.interface:
            return True
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ModelBundleContractError, match="feature schema digest mismatch"):
        validate_preflight(config)
