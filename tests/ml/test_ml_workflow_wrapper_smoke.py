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
    "scripts.train_iot_diad_binary",
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
