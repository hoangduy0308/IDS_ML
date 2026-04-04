from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_REPO_ROOT = REPO_ROOT


def _site_packages_has_ids_console_server() -> bool:
    """Check if ids.console.server is importable under the same contract that
    ids.ops.module_validation._run_module_check uses in production.

    We spawn `python -I -c "import ids.console.server"` with cwd set to the
    interpreter's parent directory and a PYTHON*-scrubbed environment. This
    matches critical-pattern [20260403] "Bind Privileged Bootstrap Execution
    To The Validated Interpreter Contract": the check runs under the exact
    same isolation as the production validator will later use.

    Why not importlib.metadata.distribution? Because conftest.py line 12-13
    adds REPO_ROOT to sys.path, so importlib.metadata will pick up any
    stale `ids_ml_new.egg-info/` in the repo root and falsely report the
    package as installed, even when it is NOT in site-packages. The production
    validator's subprocess has no such sys.path luxury, so our check must be
    just as strict.
    """
    python_bin = Path(sys.executable).resolve()
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    result = subprocess.run(
        [str(python_bin), "-I", "-c", "import ids.console.server"],
        cwd=python_bin.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


@pytest.fixture(scope="session", autouse=True)
def _ensure_editable_install() -> None:
    """Ensure ids-ml-new is installed as editable into the interpreter's
    site-packages before any test runs.

    Rationale: tests/ops/test_ids_operator_console_ops.py preflight tests
    invoke ids.ops.module_validation._run_module_check which spawns a
    subprocess with `python -I` (isolated mode), cwd=python_binary.parent,
    and a PYTHON*-scrubbed environment. In that subprocess, ids.console.server
    can only be imported if the ids-ml-new package is present in the
    interpreter's site-packages. This mirrors the production contract
    documented in critical-pattern [20260403] "Bind Privileged Bootstrap
    Execution To The Validated Interpreter Contract".

    This fixture is idempotent: it uses the same isolated-subprocess check
    as production to detect whether the package is really installed. If the
    check passes, it is a no-op. Otherwise, it runs `pip install -e .` once
    per session and re-verifies via the same subprocess check.
    """
    if _site_packages_has_ids_console_server():
        return

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to install ids-ml-new as editable package.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    if not _site_packages_has_ids_console_server():
        raise RuntimeError(
            "pip install -e . reported success but ids.console.server is still "
            "not importable under python -I with scrubbed env. This likely means "
            "the package was installed to a different interpreter than sys.executable, "
            "or the install did not place ids/ on site-packages."
        )
