from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from wrapper_smoke_support import (
    assert_help_smoke,
    run_command,
    run_python_module_help,
    run_python_script_help,
)

import ids.ops.model_bundle_manage as manage  # noqa: E402
from ids.core.model_bundle import (  # noqa: E402
    build_composite_inference_contract_metadata,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)
from ids.core.model_bundle_activation import SUPPORTED_ACTIVATION_RECORD_VERSION  # noqa: E402


def write_bundle(bundle_root: Path, *, bundle_name: str, threshold: float) -> Path:
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
                "bundle_name": bundle_name,
                "created_at": "2026-03-29T00:00:00+07:00",
                "model_key": "catboost_full_data",
                "model_family": "CatBoostClassifier",
                "model_artifact": "model.cbm",
                "feature_columns_file": "feature_columns.json",
                "threshold": threshold,
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
                        threshold=threshold,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return bundle_root


def write_composite_bundle(bundle_root: Path, *, bundle_name: str, threshold: float) -> Path:
    bundle_root.mkdir(parents=True, exist_ok=True)
    stage1_feature_columns_path = bundle_root / "stage1_feature_columns.json"
    stage2_feature_columns_path = bundle_root / "stage2_feature_columns.json"
    stage1_feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", "f2"]}),
        encoding="utf-8",
    )
    stage2_feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", "f2", "f3"]}),
        encoding="utf-8",
    )
    (bundle_root / "stage1_model.cbm").write_text("stage1", encoding="utf-8")
    (bundle_root / "stage2_model.cbm").write_text("stage2", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "bundle_name": bundle_name,
                "created_at": "2026-03-29T00:00:00+07:00",
                "model_key": "catboost_full_data",
                "model_family": "CatBoostClassifier",
                "model_artifact": "stage1_model.cbm",
                "feature_columns_file": "stage1_feature_columns.json",
                "threshold": threshold,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "feature_count": 2,
                "train_rows": 123,
                "metrics_file": "metrics.json",
                "training_summary_file": "training_summary.json",
                "compatibility": {
                    "feature_schema": build_feature_schema_metadata(stage1_feature_columns_path),
                    "inference_contract": build_composite_inference_contract_metadata(
                        positive_label="Attack",
                        negative_label="Benign",
                        threshold=threshold,
                        stage2_model_artifact="stage2_model.cbm",
                        stage2_feature_columns_path=stage2_feature_columns_path,
                        top1_confidence_threshold=0.5589,
                        runner_up_margin_threshold=0.3097,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return bundle_root


def read_activation_record(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manage_status_reports_not_ready_without_activation_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"

    rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["activation_record_exists"] is False
    assert payload["runtime_ready"] is False


def test_manage_verify_promote_status_and_rollback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    bundle_a = write_bundle(tmp_path / "bundle-a", bundle_name="bundle-a", threshold=0.5)
    bundle_b = write_bundle(tmp_path / "bundle-b", bundle_name="bundle-b", threshold=0.7)

    verify_rc = manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "verify",
            "--bundle-root",
            str(bundle_a),
        ]
    )
    verify_payload = json.loads(capsys.readouterr().out)
    assert verify_rc == 0
    assert verify_payload["compatible"] is True
    assert verify_payload["bundle_name"] == "bundle-a"

    promote_a_rc = manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "promote",
            "--bundle-root",
            str(bundle_a),
        ]
    )
    promote_a_payload = json.loads(capsys.readouterr().out)
    promote_a_record = read_activation_record(activation_path)
    assert promote_a_rc == 0
    assert promote_a_payload["active_bundle_name"] == "bundle-a"
    assert promote_a_payload["active_bundle_root"] == str(bundle_a.resolve())
    assert promote_a_payload["verification_status"] == "verified"
    assert "previous_bundle_root" not in promote_a_payload
    assert promote_a_record["record_version"] == SUPPORTED_ACTIVATION_RECORD_VERSION
    assert promote_a_record["active_bundle_root"] == str(bundle_a.resolve())
    assert promote_a_record["active_bundle_name"] == "bundle-a"
    assert promote_a_record["verification_status"] == "verified"
    assert "previous_bundle_root" not in promote_a_record
    assert "previous_bundle_name" not in promote_a_record

    promote_b_rc = manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "activate",
            "--bundle-root",
            str(bundle_b),
        ]
    )
    promote_b_payload = json.loads(capsys.readouterr().out)
    promote_b_record = read_activation_record(activation_path)
    assert promote_b_rc == 0
    assert promote_b_payload["active_bundle_name"] == "bundle-b"
    assert promote_b_payload["active_bundle_root"] == str(bundle_b.resolve())
    assert promote_b_payload["verification_status"] == "verified"
    assert promote_b_payload["previous_bundle_root"] == str(bundle_a.resolve())
    assert promote_b_payload["previous_bundle_name"] == "bundle-a"
    assert promote_b_record["record_version"] == SUPPORTED_ACTIVATION_RECORD_VERSION
    assert promote_b_record["active_bundle_root"] == str(bundle_b.resolve())
    assert promote_b_record["active_bundle_name"] == "bundle-b"
    assert promote_b_record["verification_status"] == "verified"
    assert promote_b_record["previous_bundle_root"] == str(bundle_a.resolve())
    assert promote_b_record["previous_bundle_name"] == "bundle-a"

    status_rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    status_payload = json.loads(capsys.readouterr().out)
    assert status_rc == 0
    assert status_payload["active_bundle_root"] == str(bundle_b.resolve())
    assert status_payload["active_bundle_name"] == "bundle-b"
    assert status_payload["verification_status"] == "verified"
    assert status_payload["previous_bundle_root"] == str(bundle_a.resolve())
    assert status_payload["previous_bundle_name"] == "bundle-a"

    rollback_rc = manage.main(["--activation-path", str(activation_path), "--json", "rollback"])
    rollback_payload = json.loads(capsys.readouterr().out)
    rollback_record = read_activation_record(activation_path)
    assert rollback_rc == 0
    assert rollback_payload["active_bundle_root"] == str(bundle_a.resolve())
    assert rollback_payload["active_bundle_name"] == "bundle-a"
    assert rollback_payload["verification_status"] == "verified"
    assert rollback_payload["previous_bundle_root"] == str(bundle_b.resolve())
    assert rollback_payload["previous_bundle_name"] == "bundle-b"
    assert rollback_record["record_version"] == SUPPORTED_ACTIVATION_RECORD_VERSION
    assert rollback_record["active_bundle_root"] == str(bundle_a.resolve())
    assert rollback_record["active_bundle_name"] == "bundle-a"
    assert rollback_record["verification_status"] == "verified"
    assert rollback_record["previous_bundle_root"] == str(bundle_b.resolve())
    assert rollback_record["previous_bundle_name"] == "bundle-b"


def test_manage_verify_accepts_composite_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    composite_bundle = write_composite_bundle(
        tmp_path / "composite-bundle",
        bundle_name="composite-bundle",
        threshold=0.5,
    )

    verify_rc = manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "verify",
            "--bundle-root",
            str(composite_bundle),
        ]
    )
    verify_payload = json.loads(capsys.readouterr().out)

    assert verify_rc == 0
    assert verify_payload["compatible"] is True
    assert verify_payload["bundle_name"] == "composite-bundle"
    assert verify_payload["bundle_root"] == str(composite_bundle.resolve())
    assert verify_payload["runtime_contract_kind"] == "composite"
    assert verify_payload["is_composite_contract"] is True
    assert verify_payload["stage2_model_path"] == str((composite_bundle / "stage2_model.cbm").resolve())
    assert verify_payload["stage2_feature_columns_path"] == str(
        (composite_bundle / "stage2_feature_columns.json").resolve()
    )
    assert verify_payload["stage2_closed_set_labels"] == ["DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"]
    assert verify_payload["stage2_top1_confidence_threshold"] == pytest.approx(0.5589)
    assert verify_payload["stage2_runner_up_margin_threshold"] == pytest.approx(0.3097)


def test_manage_status_reports_composite_readiness_metadata(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    composite_bundle = write_composite_bundle(
        tmp_path / "composite-bundle",
        bundle_name="composite-bundle",
        threshold=0.5,
    )

    promote_rc = manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "promote",
            "--bundle-root",
            str(composite_bundle),
        ]
    )
    capsys.readouterr()

    status_rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    status_payload = json.loads(capsys.readouterr().out)

    assert promote_rc == 0
    assert status_rc == 0
    assert status_payload["runtime_contract_kind"] == "composite"
    assert status_payload["is_composite_contract"] is True
    assert status_payload["inference_contract_version"] == "ids_two_stage_family_contract.v1"
    assert status_payload["stage2_model_path"] == str((composite_bundle / "stage2_model.cbm").resolve())
    assert status_payload["stage2_feature_columns_path"] == str(
        (composite_bundle / "stage2_feature_columns.json").resolve()
    )
    assert status_payload["stage2_closed_set_labels"] == ["DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"]
    assert status_payload["stage2_top1_confidence_threshold"] == pytest.approx(0.5589)
    assert status_payload["stage2_runner_up_margin_threshold"] == pytest.approx(0.3097)


def test_manage_rollback_fails_without_previous_known_good(
    tmp_path: Path,
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    bundle_a = write_bundle(tmp_path / "bundle-a", bundle_name="bundle-a", threshold=0.5)
    manage.main(
        [
            "--activation-path",
            str(activation_path),
            "promote",
            "--bundle-root",
            str(bundle_a),
        ]
    )

    with pytest.raises(SystemExit, match="previous known-good bundle"):
        manage.main(["--activation-path", str(activation_path), "rollback"])


def test_manage_failed_promote_preserves_previous_active_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    bundle_a = write_bundle(tmp_path / "bundle-a", bundle_name="bundle-a", threshold=0.5)
    bundle_b = write_bundle(tmp_path / "bundle-b", bundle_name="bundle-b", threshold=0.7)

    manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "promote",
            "--bundle-root",
            str(bundle_a),
        ]
    )
    capsys.readouterr()

    bundle_b_manifest_path = bundle_b / "model_bundle.json"
    bundle_b_payload = json.loads(bundle_b_manifest_path.read_text(encoding="utf-8"))
    bundle_b_payload["compatibility"]["inference_contract"]["version"] = "ids_binary_classifier.v999"
    bundle_b_manifest_path.write_text(
        json.dumps(bundle_b_payload),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Unsupported inference contract version"):
        manage.main(
            [
                "--activation-path",
                str(activation_path),
                "promote",
                "--bundle-root",
                str(bundle_b),
            ]
        )

    status_rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    status_payload = json.loads(capsys.readouterr().out)
    activation_record = read_activation_record(activation_path)

    assert status_rc == 0
    assert status_payload["active_bundle_root"] == str(bundle_a.resolve())
    assert status_payload["active_bundle_name"] == "bundle-a"
    assert status_payload["verification_status"] == "verified"
    assert "previous_bundle_name" not in status_payload
    assert activation_record["record_version"] == SUPPORTED_ACTIVATION_RECORD_VERSION
    assert activation_record["active_bundle_root"] == str(bundle_a.resolve())
    assert activation_record["active_bundle_name"] == "bundle-a"
    assert activation_record["verification_status"] == "verified"
    assert "previous_bundle_root" not in activation_record
    assert "previous_bundle_name" not in activation_record


def test_manage_failed_promote_preserves_previous_active_bundle_for_invalid_composite_candidate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    bundle_a = write_bundle(tmp_path / "bundle-a", bundle_name="bundle-a", threshold=0.5)
    composite_bundle = write_composite_bundle(
        tmp_path / "composite-bundle",
        bundle_name="composite-bundle",
        threshold=0.5,
    )

    manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "promote",
            "--bundle-root",
            str(bundle_a),
        ]
    )
    capsys.readouterr()

    composite_manifest_path = composite_bundle / "model_bundle.json"
    composite_payload = json.loads(composite_manifest_path.read_text(encoding="utf-8"))
    composite_payload["compatibility"]["inference_contract"]["stage2"]["closed_set_labels"] = [
        "Attack",
        "Benign",
    ]
    composite_manifest_path.write_text(json.dumps(composite_payload), encoding="utf-8")

    with pytest.raises(SystemExit, match="Composite stage2 closed_set_labels"):
        manage.main(
            [
                "--activation-path",
                str(activation_path),
                "promote",
                "--bundle-root",
                str(composite_bundle),
            ]
        )

    status_rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    status_payload = json.loads(capsys.readouterr().out)
    activation_record = read_activation_record(activation_path)

    assert status_rc == 0
    assert status_payload["active_bundle_root"] == str(bundle_a.resolve())
    assert status_payload["active_bundle_name"] == "bundle-a"
    assert status_payload["verification_status"] == "verified"
    assert status_payload["runtime_contract_kind"] == "binary"
    assert status_payload["is_composite_contract"] is False
    assert activation_record["record_version"] == SUPPORTED_ACTIVATION_RECORD_VERSION
    assert activation_record["active_bundle_root"] == str(bundle_a.resolve())
    assert activation_record["active_bundle_name"] == "bundle-a"
    assert activation_record["verification_status"] == "verified"
    assert "previous_bundle_root" not in activation_record
    assert "previous_bundle_name" not in activation_record


def test_manage_failed_promote_preserves_previous_active_composite_bundle_for_invalid_composite_candidate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    composite_bundle_a = write_composite_bundle(
        tmp_path / "composite-bundle-a",
        bundle_name="composite-bundle-a",
        threshold=0.5,
    )
    composite_bundle_b = write_composite_bundle(
        tmp_path / "composite-bundle-b",
        bundle_name="composite-bundle-b",
        threshold=0.7,
    )

    manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "promote",
            "--bundle-root",
            str(composite_bundle_a),
        ]
    )
    capsys.readouterr()

    composite_b_manifest_path = composite_bundle_b / "model_bundle.json"
    composite_b_payload = json.loads(composite_b_manifest_path.read_text(encoding="utf-8"))
    composite_b_payload["compatibility"]["inference_contract"]["stage2"]["closed_set_labels"] = [
        "Attack",
        "Benign",
    ]
    composite_b_manifest_path.write_text(json.dumps(composite_b_payload), encoding="utf-8")

    with pytest.raises(SystemExit, match="Composite stage2 closed_set_labels"):
        manage.main(
            [
                "--activation-path",
                str(activation_path),
                "promote",
                "--bundle-root",
                str(composite_bundle_b),
            ]
        )

    status_rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    status_payload = json.loads(capsys.readouterr().out)
    activation_record = read_activation_record(activation_path)

    assert status_rc == 0
    assert status_payload["active_bundle_root"] == str(composite_bundle_a.resolve())
    assert status_payload["active_bundle_name"] == "composite-bundle-a"
    assert status_payload["verification_status"] == "verified"
    assert status_payload["runtime_contract_kind"] == "composite"
    assert status_payload["is_composite_contract"] is True
    assert status_payload["stage2_model_path"] == str((composite_bundle_a / "stage2_model.cbm").resolve())
    assert status_payload["stage2_feature_columns_path"] == str(
        (composite_bundle_a / "stage2_feature_columns.json").resolve()
    )
    assert activation_record["record_version"] == SUPPORTED_ACTIVATION_RECORD_VERSION
    assert activation_record["active_bundle_root"] == str(composite_bundle_a.resolve())
    assert activation_record["active_bundle_name"] == "composite-bundle-a"
    assert activation_record["verification_status"] == "verified"
    assert "previous_bundle_root" not in activation_record
    assert "previous_bundle_name" not in activation_record


def test_script_wrapper_help_runs_through_module_entrypoint() -> None:
    help_run = run_python_module_help("scripts.ids_model_bundle_manage")
    assert_help_smoke(help_run, "scripts.ids_model_bundle_manage")
    assert "usage:" in help_run.stdout.lower()


def test_script_wrapper_help_runs_through_direct_file_entrypoint() -> None:
    help_run = run_python_script_help("scripts/ids_model_bundle_manage.py")
    assert_help_smoke(help_run, "scripts/ids_model_bundle_manage.py")
    assert "usage:" in help_run.stdout.lower()


def test_canonical_module_help_surface_is_available() -> None:
    help_run = run_command([sys.executable, "-m", "ids.ops.model_bundle_manage", "--help"])
    assert_help_smoke(help_run, "ids.ops.model_bundle_manage")
    assert "usage:" in help_run.stdout.lower()
