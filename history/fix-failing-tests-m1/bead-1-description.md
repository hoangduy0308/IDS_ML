# Phase 1 / Story 1: Add editable install fixture + fix service unit assertion

## Summary

Fix the 4 failing tests in the repo test suite by adding a session-scoped pytest fixture that ensures `ids-ml-new` is installed as editable into the current interpreter's site-packages, and by updating one stale assertion in the live-sensor service-unit test. This closes audit finding M1 without touching any production code, service units, or security contracts.

## Phase Context

**Phase:** Phase 1 — Fix test drift
**What Changes:** `python -m pytest tests/ -q` reports `590 passed, 0 failed` on both local dev machines (without pre-installing the package) and CI. No production behavior changes.
**Unlocks Next:** M2 (CI/CD pipeline) can be safely added with confidence that all tests are green.

## Story Context

**Story:** Story 1 — Fix test drift (editable install fixture + assertion update)
**What Happens:** This single bead delivers the entire phase: session fixture in `tests/conftest.py`, one-line assertion fix in `tests/runtime/test_ids_live_sensor.py`, and verification that 590/590 tests pass.
**Contributes To:** Entire Phase 1 exit state (this is the only story in the phase).
**Unlocks:** Feature completion + M2 work.

## Planning Context

From `history/fix-failing-tests-m1/approach.md`:

- Fix A (fixture) is chosen over alternatives Skip/Remove `-I`/Add cwd/Create separate venv because it is the only approach that preserves the security contract of `ids/ops/module_validation.py::_run_module_check` while making tests pass in any environment.
- Fix B (assertion update) is preferred over "revert service unit to script path" because the service unit is the canonical form for installable packages — reverting would break packaging.
- Both fixes ship in one commit because Phase 1 exit state requires all tests green simultaneously.

## Institutional Learnings (MANDATORY — DO NOT VIOLATE)

### [20260403] Bind Privileged Bootstrap Execution To The Validated Interpreter Contract

From `history/learnings/critical-patterns.md`:
> "Preflight approval is meaningless if privileged bootstrap can still resolve code through a different interpreter, `cwd`, or inherited `PYTHON*` state. Future module-based bootstrap paths must run under the exact validated interpreter/env contract."

**Application to this bead:**
- DO NOT modify `ids/ops/module_validation.py` to add `cwd=REPO_ROOT`, remove `-I`, or relax env scrubbing.
- DO NOT pass `PYTHONPATH` into the subprocess.
- The fixture MUST use `sys.executable` (the same interpreter pytest is running under), not spawn a separate venv.

### [20260403] Prove Editable Installs In A Scrubbed Environment

> "In-tree or already-warmed verification is not enough to prove an install contract because it can hide missing source files, templates, or package data. Future packaging work should always run a fresh editable-install proof."

**Application to this bead:**
- The fixture MUST verify the install worked by calling `importlib.metadata.distribution("ids-ml-new")` after `pip install -e .`, not trust the pip exit code alone.
- If verification fails post-install, the fixture MUST raise `RuntimeError` with stdout+stderr captured.

### [20260330] Pin Multi-Token Runtime Contracts With End-To-End Tokenization Tests

> "Real risk lived in the tokenization chain across systemd, shell expansion, and argparse. The issue only became truly closed after tests exercised both the success round-trip and the missing-argument failure path."

**Application to this bead:**
- In `tests/runtime/test_ids_live_sensor.py`, when fixing line 513, KEEP ALL OTHER ASSERTIONS in `test_service_unit_keeps_preflight_and_stdout_journal_contract` intact. That test has 14 other tokenization assertions (shlex.split of ExecStart, the `--dumpcap-binary`, `--extractor-command-prefix` flags, the `StandardOutput=journal` line, etc.). Those are critical contracts.

### [20260331] Treat Compatibility Wrappers As Executable Contracts

> "Wrapper stability is not real unless CI exercises those wrappers directly."

**Application to this bead:**
- The fixture ensures tests exercise the same install contract that CI will use. No path hacks, no fallback behavior — if the package is not installable, tests MUST fail loudly.

## File Scope

### Files to modify (exactly 2)

**1. `tests/conftest.py`** (add ~35 lines)

Add this fixture at the top of the file (after existing imports, before any other fixtures):

```python
import importlib.metadata
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _ensure_editable_install() -> None:
    """Ensure ids-ml-new is installed as editable before any test runs.

    Rationale: tests/ops/test_ids_operator_console_ops.py preflight tests
    invoke ids.ops.module_validation._run_module_check which spawns a
    subprocess with `python -I` (isolated mode), cwd=python_binary.parent,
    and a PYTHON*-scrubbed environment. In that subprocess, ids.console.server
    can only be imported if the ids-ml-new package is present in the
    interpreter's site-packages. This mirrors the production contract
    documented in critical-pattern [20260403] "Bind Privileged Bootstrap
    Execution To The Validated Interpreter Contract".

    This fixture is idempotent: if the package is already installed, it
    is a no-op. Otherwise, it runs `pip install -e .` once per session
    and verifies success via importlib.metadata.distribution.
    """
    try:
        importlib.metadata.distribution("ids-ml-new")
        return
    except importlib.metadata.PackageNotFoundError:
        pass

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

    try:
        importlib.metadata.distribution("ids-ml-new")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            "pip install -e . reported success but ids-ml-new still not importable"
        ) from exc
```

If `tests/conftest.py` already has imports matching these, merge them; do not duplicate.

**2. `tests/runtime/test_ids_live_sensor.py`** (change 1 line at line 513)

```python
# BEFORE:
assert "ids_live_sensor_preflight.py" in content

# AFTER:
assert "-m ids.ops.live_sensor_preflight" in content
```

ALL OTHER LINES IN THE FILE MUST REMAIN UNCHANGED. In particular, lines 510-512 and 514-537 are part of the tokenization contract and must not be touched.

### Files that MUST NOT be modified

- `ids/ops/module_validation.py` — security contract; verify with `git diff ids/ops/module_validation.py` returns empty after work
- `ids/ops/operator_console_preflight.py` — callsite of the security contract
- `deploy/systemd/ids-live-sensor.service` — service unit is already correct
- `tests/ops/test_ids_operator_console_ops.py` — the 3 failing tests don't need logic changes; fixture makes them pass
- `pyproject.toml` — no dependency changes
- `requirements.txt` — no dependency changes
- Any production source file in `ids/` or `ml_pipeline/`

## Dependencies

None. This is the first and only bead in Phase 1.

## Verification Criteria

Run ALL of these checks after the edit. ALL must pass:

### Hard checks (blocking)

1. `python -m pytest tests/ -q --tb=line` completes with exit code 0 and output shows `590 passed`
2. `git diff ids/` produces empty output
3. `git diff deploy/` produces empty output
4. `git diff pyproject.toml requirements.txt` produces empty output
5. `git diff --stat tests/` shows exactly two files changed: `tests/conftest.py` and `tests/runtime/test_ids_live_sensor.py`
6. `python -m pip show ids-ml-new` returns package info (Name: ids-ml-new)
7. Running `python -m pytest tests/ -q` a second time in the same venv still shows `590 passed` (idempotency check)

### Soft checks (quality)

8. The fixture has a clear docstring referencing critical-pattern [20260403]
9. No `print()` or `logging` statements leaked into the fixture
10. Fixture does not create any new files in the repo (no `.pip-install-cache` or similar side effects)
11. Commit message is descriptive, e.g. `test(m1): ensure editable install fixture + fix service unit assertion (M1)`

## Pivot Signals

If any of these occur during execution, STOP and report — do not try to fix-forward:

- After adding fixture, the 3 preflight tests still fail with a different error (not "not importable") → root cause analysis needed, invoke debugging skill
- After fixing assertion, the service unit test still fails or another assertion in the same test starts failing → test drift is broader than expected
- Adding the fixture causes ≥1 regression in the 586 currently-passing tests → fixture scope is wrong, need to revisit
- `pip install -e .` fails on the dev machine due to broken Python environment → out of scope for M1, pause
- CI lacks permission to write to site-packages → may need to require CI to pre-install package before pytest

## Done Definition

Bead is closed only when ALL 7 hard checks pass AND the commit is made with the bead ID in the commit message.

## Estimated Effort

15-30 minutes for a single worker (read CONTEXT.md + approach.md, apply 2 edits, run pytest, verify diff, commit).
