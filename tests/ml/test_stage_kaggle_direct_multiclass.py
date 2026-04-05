from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ml_pipeline.benchmark.stage_kaggle_direct_multiclass import (
    assert_safe_output_root,
    stage_kernel_bundle,
)
from wrapper_smoke_support import assert_help_smoke, run_python_module_help


def test_stage_kaggle_direct_multiclass_bundle(tmp_path: Path) -> None:
    bundle_root = tmp_path / "artifacts" / "kaggle" / "kernels" / "direct_multiclass"
    report_contract_path = tmp_path / "artifacts" / "modeling" / "cic_iot_diad_2024_family_views" / "direct_multiclass" / "reports" / "direct_multiclass_eval.json"

    stage_kernel_bundle(
        bundle_root=bundle_root,
        dataset_id="hdiiii/cic-iot-diad-2024",
        kernel_id="hdiiii/ids-multiclass-direct-baseline",
        title="IDS Direct Multiclass Baseline",
        direct_script_path=Path(r"F:\Work\IDS_ML_New\ml_pipeline\training\train_iot_diad_direct_multiclass.py"),
        helper_script_path=Path(r"F:\Work\IDS_ML_New\ml_pipeline\training\train_iot_diad_family_classifier.py"),
        gpu_devices="0:1",
        report_contract_path=report_contract_path,
    )

    metadata = json.loads((bundle_root / "kernel-metadata.json").read_text(encoding="utf-8"))
    readme = (bundle_root / "README.md").read_text(encoding="utf-8")
    direct_script = (bundle_root / "train_direct_multiclass.py").read_text(encoding="utf-8")
    helper_script = (bundle_root / "train_iot_diad_family_classifier.py").read_text(encoding="utf-8")

    assert metadata["id"] == "hdiiii/ids-multiclass-direct-baseline"
    assert metadata["code_file"] == "train_direct_multiclass.py"
    assert metadata["dataset_sources"] == ["hdiiii/cic-iot-diad-2024"]
    assert "direct_multiclass_eval.json" in readme
    assert str(report_contract_path.as_posix()) in readme
    assert 'from train_iot_diad_family_classifier import (' not in direct_script
    assert '/kaggle/working/direct_multiclass_results' in direct_script
    assert "DEFAULT_VIEW_NAME = \"direct_multiclass\"" in direct_script
    assert "def run_training" in helper_script
    assert "DEFAULT_VIEW_NAME = \"attack_only\"" in helper_script


def test_stage_kaggle_direct_multiclass_help_smoke() -> None:
    completed = run_python_module_help("scripts.stage_kaggle_direct_multiclass")
    assert_help_smoke(completed, "scripts.stage_kaggle_direct_multiclass")
    assert "usage:" in completed.stdout.lower()


def test_stage_kaggle_direct_multiclass_rejects_unsafe_bundle_root() -> None:
    unsafe_root = Path(tempfile.gettempdir()).resolve()

    with pytest.raises(ValueError, match="Refusing to operate on approved root directly"):
        assert_safe_output_root(unsafe_root)
