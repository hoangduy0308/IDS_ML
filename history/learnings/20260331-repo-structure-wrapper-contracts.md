---
date: 2026-03-31
feature: repo-structure-rationalization
categories: [pattern, decision, failure]
severity: critical
tags: [architecture, testing, wrappers, migration, docs, error-handling, filesystem, security]
---

# Learning: Treat Compatibility Wrappers As Executable Contracts

**Category:** failure
**Severity:** critical
**Tags:** [wrappers, testing, compatibility, runtime, ops, ml]
**Applicable-when:** Any phased refactor keeps legacy entrypoints, CLIs, or service startup surfaces alive while moving implementation behind new canonical modules.

## What Happened

This repo rationalization intentionally kept `scripts/*` entrypoints alive while moving real implementation under `ids/*` and `ml_pipeline/*`. Execution initially validated canonical modules well enough to ship the structural moves, but review still found that runtime wrappers, ops wrappers, and migrated ML wrappers were not being exercised directly. The result was a review-fix wave that added `tests/runtime/test_ids_runtime_wrapper_smoke.py`, wrapper smoke checks in `tests/ops/*`, and `tests/ml/test_ml_workflow_wrapper_smoke.py` before the feature could close cleanly.

## Root Cause / Key Insight

The team treated wrappers as incidental shims instead of as supported execution contracts. That was the wrong mental model. If phase 1 promises that `python -m scripts.*`, runbooks, or supervisor/systemd surfaces still work, then those wrappers are part of the product contract and must be proven by CI just like the canonical modules behind them.

## Recommendation for Future Work

When a migration preserves old entrypoints, add wrapper-smoke coverage in the same bead that moves the implementation. Never defer wrapper verification to review. Treat compatibility seams as executable contracts, not documentation-only promises.

---

# Learning: Keep Canonical Modules Independent From Compatibility Layers

**Category:** decision
**Severity:** critical
**Tags:** [architecture, core, imports, compatibility]
**Applicable-when:** Introducing a new canonical package tree while preserving old wrapper surfaces during a staged refactor.

## What Happened

The approved plan kept `ids.core` intentionally narrow and required `scripts/*` to act only as thin compatibility shims. During execution, `ids.core.model_bundle` absorbed lifecycle behavior and canonical runtime code still imported bundle helpers through `scripts/ids_model_bundle.py`. Review had to split lifecycle helpers into `ids/ops/model_bundle_lifecycle.py`, return `ids/core/model_bundle.py` to contract-only responsibilities, and repoint canonical imports away from the wrapper layer.

## Root Cause / Key Insight

Without an explicit guardrail, “get it working” pressure will let legacy seams leak back into the canonical architecture. Once `ids/*` code depends on `scripts/*`, the new structure becomes cosmetic and the boundary drift the refactor was supposed to remove reappears immediately. Likewise, if `core` is not defended as a leaf-only contract zone, it grows into an operational junk drawer.

## Recommendation for Future Work

Never allow canonical package code to import from compatibility wrappers. Enforce `scripts -> ids/ml_pipeline`, never the reverse. When creating a shared/core package, restrict it to contracts, schemas, validators, and config primitives, and fail review if lifecycle or operational behavior drifts back into it.

---

# Learning: Harden Mirrored Test Trees Against Hidden Coverage Drift

**Category:** pattern
**Severity:** standard
**Tags:** [testing, pytest, migration, bootstrap]
**Applicable-when:** Reorganizing a flat test suite into domain-based folders or changing import roots under pytest.

## What Happened

This refactor successfully introduced domain-mirrored tests and a shared `tests/conftest.py`, and the suite ultimately closed at `295 passed`. Review still found two subtle hygiene gaps: a duplicated test name in `tests/runtime/test_ids_live_sensor_health.py` that silently shadowed a malformed-summary case, and leftover per-file `sys.path` / `REPO_ROOT` hacks in migrated console and ops tests. Those issues did not break the suite outright, but they weakened confidence that the new mirrored layout was being validated honestly.

## Root Cause / Key Insight

Passing tests after a tree move is not enough. Test identity and import bootstrap are part of the migration contract too. Duplicate test names can silently erase coverage, and obsolete per-file bootstrap code can mask whether the new shared pytest layout actually works on its own.

## Recommendation for Future Work

When moving tests into a mirrored tree, require two cleanup checks before closing the bead: no duplicate test names in the touched modules, and no redundant per-file bootstrap once shared `conftest.py` exists. Treat test-layout hygiene as part of the migration definition of done, not as later polish.

---

# Learning: Normalize Hostile Metadata At Contract Boundaries

**Category:** failure
**Severity:** critical
**Tags:** [error-handling, metadata, model-bundle, restore, fail-closed]
**Applicable-when:** Any refactor or runtime path reads manifests, activation records, or backup metadata from disk and multiple callers depend on one domain-specific contract error.

## What Happened

The review rerun found that malformed bundle metadata, activation records, and backup metadata were still leaking raw `KeyError`, `ValueError`, or JSON parse exceptions from `ids/core/model_bundle.py`, `ids/core/model_bundle_activation.py`, and `ids/console/ops.py`. The cleanup wave had to normalize those edge failures into `ModelBundleContractError`, `ActiveBundleResolutionError`, and `OpsError`, then add regression tests that exercised corrupted JSON, missing required fields, and invalid version/digest values.

## Root Cause / Key Insight

Those file boundaries were still treating metadata as mostly well-formed and relying on generic conversions before translating errors into domain language. That makes downstream runtime and CLI behavior inconsistent: some callers fail closed cleanly while others surface raw parser exceptions that do not match the contract the rest of the system expects.

## Recommendation for Future Work

Whenever a module owns a manifest or activation contract, catch JSON decode failures, missing-field lookups, and type coercion errors at that boundary and re-raise exactly one domain-specific failure type. Add malformed-metadata tests in the same bead that introduces or moves the parser so review does not become the first place the contract is exercised against hostile input.

---

# Learning: Resolve Paths Then Prove Root Containment For Host-Level File Operations

**Category:** failure
**Severity:** critical
**Tags:** [filesystem, path-resolution, containment, restore, security]
**Applicable-when:** Any ops, restore, or preflight path accepts file or directory inputs from config, manifests, or operator-supplied arguments on the host.

## What Happened

The review rerun exposed two related path-safety gaps in `ids/ops/same_host_stack.py`: the same-host path helpers resolved paths before enforcing the absolute-path contract, and restore inventory trusted manifest-controlled backup paths without proving they stayed under the selected backup root. The cleanup wave changed the helpers to reject non-absolute inputs up front, introduced explicit root-containment checks for manifest-derived paths, and added regression tests that cover relative inputs and attempted backup-path escapes.

## Root Cause / Key Insight

Path normalization and path authorization were being treated as the same step. They are not. `Path.resolve()` can canonicalize a path, but it does not prove the caller was allowed to point at that target or that a joined path remained inside the intended root after normalization.

## Recommendation for Future Work

For every host-level filesystem seam, validate absolute-path and containment rules explicitly instead of assuming normalization makes an input safe. When a path comes from a manifest or other external metadata, anchor it to the intended root, resolve it, and then prove it still lives under that root before reading or restoring anything.
