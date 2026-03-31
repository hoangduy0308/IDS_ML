from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_script_wrapper_help_runs_through_module_entrypoint() -> None:
    help_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.ids_operator_console_manage",
            "--help",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert help_run.returncode == 0, help_run.stderr
    assert "usage:" in help_run.stdout.lower()
    assert "traceback" not in help_run.stderr.lower()


def test_script_wrapper_help_runs_through_direct_file_entrypoint() -> None:
    help_run = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "ids_operator_console_manage.py"),
            "--help",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert help_run.returncode == 0, help_run.stderr
    assert "usage:" in help_run.stdout.lower()
    assert "traceback" not in help_run.stderr.lower()
