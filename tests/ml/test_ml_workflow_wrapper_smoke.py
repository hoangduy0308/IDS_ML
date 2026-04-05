from __future__ import annotations

import pytest

from wrapper_smoke_support import assert_help_smoke, run_python_module_help, run_python_script_help

WRAPPER_MODULES = [
    "scripts.stage_kaggle_benchmark",
    "scripts.stage_kaggle_direct_multiclass",
    "scripts.stage_kaggle_promotion",
    "scripts.preprocess_iot_diad",
    "scripts.package_final_model",
    "scripts.posttrain_threshold_analysis",
    "scripts.stage_kaggle_scaling",
    "scripts.stage_kaggle_tuning",
    "scripts.tune_top_models",
    "scripts.train_iot_diad_binary",
]

DIRECT_FILE_WRAPPERS = [
    "scripts/package_final_model.py",
    "scripts/stage_kaggle_tuning.py",
    "scripts/tune_top_models.py",
]


@pytest.mark.parametrize("module_name", WRAPPER_MODULES)
def test_migrated_ml_wrapper_help_smoke(module_name: str) -> None:
    completed = run_python_module_help(module_name)
    assert_help_smoke(completed, module_name)
    assert completed.stdout.strip(), module_name
    assert "usage:" in completed.stdout.lower(), module_name


@pytest.mark.parametrize("script_relative_path", DIRECT_FILE_WRAPPERS)
def test_migrated_ml_wrapper_direct_file_help_smoke(script_relative_path: str) -> None:
    completed = run_python_script_help(script_relative_path)
    assert_help_smoke(completed, script_relative_path)
    assert completed.stdout.strip(), script_relative_path
    assert "usage:" in completed.stdout.lower(), script_relative_path
