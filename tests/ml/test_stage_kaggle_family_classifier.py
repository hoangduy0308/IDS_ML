from __future__ import annotations

import json
from pathlib import Path

from ml_pipeline.benchmark.stage_kaggle_family_classifier import stage_kernel_bundle
from wrapper_smoke_support import assert_help_smoke, run_python_module_help


def test_stage_kaggle_family_classifier_bundle(tmp_path: Path) -> None:
    bundle_root = tmp_path / "artifacts" / "kaggle" / "kernels" / "family_classifier"
    report_contract_path = tmp_path / "artifacts" / "modeling" / "cic_iot_diad_2024_family_views" / "family_classifier" / "reports" / "oracle_family_eval.json"

    stage_kernel_bundle(
        bundle_root=bundle_root,
        dataset_id="hdiiii/cic-iot-diad-2024",
        kernel_id="hdiiii/ids-stage2-family-classifier-full-data",
        title="Ids Stage2 Family Classifier Full Data",
        training_script_path=Path(r"F:\Work\IDS_ML_New\ml_pipeline\training\train_iot_diad_family_classifier.py"),
        gpu_devices="0",
        max_train_rows=25_000_000,
        iterations=500,
        class_weight_exponent=0.5,
        report_contract_path=report_contract_path,
    )

    metadata = json.loads((bundle_root / "kernel-metadata.json").read_text(encoding="utf-8"))
    readme = (bundle_root / "README.md").read_text(encoding="utf-8")
    training_script = (bundle_root / "train_family_classifier.py").read_text(encoding="utf-8")

    assert metadata["id"] == "hdiiii/ids-stage2-family-classifier-full-data"
    assert metadata["code_file"] == "train_family_classifier.py"
    assert metadata["dataset_sources"] == ["hdiiii/cic-iot-diad-2024"]
    assert "oracle_family_eval.json" in readme
    assert "25000000" in readme
    assert "500" in readme
    assert "0.5" in readme
    assert str(report_contract_path.as_posix()) in readme
    assert 'DEFAULT_TASK_TYPE = "GPU"' in training_script
    assert 'DEFAULT_DEVICES = "0"' in training_script
    assert "DEFAULT_MAX_TRAIN_ROWS = 25_000_000" in training_script
    assert "DEFAULT_ITERATIONS = 500" in training_script
    assert "DEFAULT_CLASS_WEIGHT_EXPONENT = 0.5" in training_script
    assert "/kaggle/working/family_classifier_results" in training_script
    assert "ensure_family_view_root" in training_script
    assert "/kaggle/input/cic-iot-diad-2024/cic-iot-diad-2024-binary-ids" in training_script


def test_stage_kaggle_family_classifier_help_smoke() -> None:
    completed = run_python_module_help("scripts.stage_kaggle_family_classifier")
    assert_help_smoke(completed, "scripts.stage_kaggle_family_classifier")
    assert "usage:" in completed.stdout.lower()
