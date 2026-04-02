## Problem Statement

Source epic: `ids_ml_new-urzq`.

`resolve_importable_module()` now treats `importlib.util.find_spec()` as the decisive module-validation step and returns only `spec.origin`. That weakens the packaged preflight contract in two ways: it no longer proves that the target module can actually import cleanly in the selected interpreter, and for dotted module names it can execute parent-package import side effects before the trusted-root check rejects the resolved origin. This matters because the review-fix wave claimed hermetic trusted-origin validation for production service module slots, but the current implementation still allows pre-check side effects and can green-light a module path that only fails once the service actually imports it.

## Evidence

**File:** `ids/ops/module_validation.py`
**Line(s):** 38-71

```python
completed = subprocess.run(
    [
        str(Path(python_binary).resolve()),
        "-I",
        "-c",
        (
            "import importlib.util, json, pathlib; "
            f"name={normalized!r}; "
            "spec = importlib.util.find_spec(name); "
            "assert spec is not None, f'{name} is not importable'; "
            "origin = getattr(spec, 'origin', None); "
            "assert origin and origin not in {'built-in', 'frozen'}, f'{name} has no module origin'; "
            "print(json.dumps({'origin': str(pathlib.Path(origin).resolve())}))"
        ),
    ],
)
```

**Why this is a problem:** `find_spec()` for dotted names can import parent packages before containment is checked, and the code never verifies that the target module itself can complete import successfully in the deployed interpreter.

## Proposed Solutions

### Option A - Recommended: split resolution from final import proof
**Pros:** preserves side-effect-safe trusted-root resolution first, then proves the final module import only after the origin has been authorized.
**Cons:** requires a small refactor in the helper and matching test updates.
**Effort:** Medium

### Option B - keep origin-only resolution and narrow the contract
**Pros:** smaller code change.
**Cons:** weakens D4/D6 semantics and leaves service-start failures outside preflight.
**Effort:** Small

## Acceptance Criteria

- [ ] Module validation authorizes dotted module paths without allowing untrusted parent-package import side effects before the trusted-root check.
- [ ] After trusted-root authorization passes, the helper proves the target module can actually import in the selected interpreter or documents and enforces an equivalent stronger contract.
- [ ] Regression coverage includes a dotted-name hostile parent-package case and a trusted-root module that crashes during import.
