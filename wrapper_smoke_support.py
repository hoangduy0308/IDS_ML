from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def run_command(argv: Sequence[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def run_python_module_help(module_name: str) -> subprocess.CompletedProcess[str]:
    return run_command([sys.executable, "-m", module_name, "--help"])


def run_python_script_help(script_relative_path: str) -> subprocess.CompletedProcess[str]:
    return run_command([sys.executable, str(REPO_ROOT / script_relative_path), "--help"])


def assert_help_smoke(completed: subprocess.CompletedProcess[str], label: str) -> None:
    assert_command_smoke(completed, label)


def assert_command_smoke(completed: subprocess.CompletedProcess[str], label: str) -> None:
    assert completed.returncode == 0, completed.stderr
    combined_output = f"{completed.stdout}\n{completed.stderr}".lower()
    assert "traceback" not in combined_output, label
