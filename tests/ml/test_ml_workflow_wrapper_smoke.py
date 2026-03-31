from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

WRAPPER_MODULES = [
    "scripts.stage_kaggle_benchmark",
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
    "scripts/stage_kaggle_tuning.py",
    "scripts/tune_top_models.py",
]


@pytest.mark.parametrize("module_name", WRAPPER_MODULES)
def test_migrated_ml_wrapper_help_smoke(module_name: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", module_name, "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip(), module_name
    assert "usage:" in completed.stdout.lower(), module_name


@pytest.mark.parametrize("script_relative_path", DIRECT_FILE_WRAPPERS)
def test_migrated_ml_wrapper_direct_file_help_smoke(script_relative_path: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / script_relative_path), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip(), script_relative_path
    assert "usage:" in completed.stdout.lower(), script_relative_path
