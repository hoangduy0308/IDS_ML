## Problem Statement

Source epic: `ids_ml_new-urzq`.

The hermetic-import regressions added in the review-fix wave cover clean-venv failure and shadow modules injected through `sitecustomize`, but they no longer exercise the original hostile inherited-environment seam that the wave was supposed to close. If `_build_import_env()` stops scrubbing `PYTHONPATH` or `PYTHONHOME` again, the current tests can remain green while the caller-environment leak quietly returns.

## Evidence

**File:** `ids/ops/module_validation.py`
**Line(s):** 20-24

```python
def _build_import_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONSAFEPATH", None)
    return env
```

**File:** `tests/ops/test_ids_operator_console_preflight.py`
**Line(s):** 221-238

```python
def test_preflight_rejects_shadowed_module(...):
    ...
    monkeypatch.setenv("IDS_TEST_SHADOW_IMPORT_MODULE", shadow_module)
    monkeypatch.setenv("IDS_TEST_SHADOW_IMPORT_ROOT", str(shadow_root))
```

**Why this is a problem:** the tests no longer pin the explicit caller-environment contamination contract that motivated the scrubber in the first place.

## Proposed Solutions

### Option A - Recommended: add explicit inherited-env regressions
**Pros:** directly protects the seam this review-fix wave was opened to close.
**Cons:** requires a little more test harness setup.
**Effort:** Small

### Option B - rely on clean-venv and sitecustomize coverage only
**Pros:** no new tests.
**Cons:** leaves the original PYTHONPATH/PYTHONHOME regression path unguarded.
**Effort:** None

## Acceptance Criteria

- [ ] Regression coverage proves that inherited `PYTHONPATH` contamination does not influence packaged module validation.
- [ ] Regression coverage proves that inherited `PYTHONHOME` contamination does not influence packaged module validation.
- [ ] The new tests fail if `_build_import_env()` stops scrubbing those caller-environment variables.
