## Problem Statement

Source epic: `ids_ml_new-urzq`.

The new shared editable-install proof helper caches a venv only by `cache_key` plus the `pyproject.toml` hash. Because editable installs point at a specific checkout path and interpreter, a later test run from another checkout or another Python can silently reuse a stale environment that still resolves to the previous source tree. This weakens the repo-installable proof by making it possible for tests to validate the wrong checkout or interpreter without rerunning installation.

## Evidence

**File:** `tests/ops/repo_installable_proof_support.py`
**Line(s):** 44-64

```python
def shared_editable_repo_python(cache_key: str) -> Path:
    cache_root = Path(tempfile.gettempdir()) / f"ids_ml_new_{cache_key}"
    ...
    signature = hashlib.sha256(pyproject.read_bytes()).hexdigest()
    stamp_path = cache_root / ".editable-install.stamp"
    ...
    if not stamp_path.exists() or stamp_path.read_text(encoding="utf-8").strip() != signature:
        completed = run_command(
            [str(python_path), "-m", "pip", "install", "-e", str(REPO_ROOT)],
            cwd=cache_root,
        )
```

**Why this is a problem:** the cache does not encode the checkout root or interpreter identity, so a shared tempdir can prove the wrong installation target.

## Proposed Solutions

### Option A - Recommended: key the cache by checkout root + interpreter identity + install signature
**Pros:** keeps the shared-cache speedup while restoring hermetic proof behavior.
**Cons:** slightly more cache-management logic.
**Effort:** Small

### Option B - drop shared caching and recreate venv per proof run
**Pros:** simplest correctness story.
**Cons:** slower review and CI runtime.
**Effort:** Small

## Acceptance Criteria

- [ ] Shared proof venv reuse is invalidated when the checkout root changes.
- [ ] Shared proof venv reuse is invalidated when the interpreter path or interpreter version changes.
- [ ] The helper still cleans stale shadow-path contamination without silently proving a different checkout than the one under test.
