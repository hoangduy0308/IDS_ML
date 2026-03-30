from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


WRAPPER_MODULES = [
    "scripts.ids_inference",
    "scripts.ids_live_capture",
    "scripts.ids_live_sensor",
    "scripts.ids_live_sensor_health",
    "scripts.ids_live_sensor_sinks",
]


def test_phase1_runtime_wrapper_help_smoke() -> None:
    for module_name in WRAPPER_MODULES:
        completed = subprocess.run(
            [sys.executable, "-m", module_name, "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        combined_output = f"{completed.stdout}\n{completed.stderr}".lower()
        assert "traceback" not in combined_output, module_name
