# Phase 5 Story Map: Module Validation Trust Boundary Hardening

**Feature:** ids-repo-installable-full-stack-packaging
**Phase:** 5
**Epic:** `ids_ml_new-fuf5`

---

## Story 1: Atomic Validation Pipeline

**Why now:** The TOCTOU gap between origin resolution and import proof was the #1 finding across 3 independent reviewers. It is the foundational change that most other beads depend on.

**Job:** Eliminate the time gap between module origin resolution and import proof by merging both subprocess scripts into a single atomic invocation.

**Done looks like:** `resolve_importable_module()` makes one subprocess call that resolves, checks containment, and imports in a single Python process. No inter-process gap exists.

**Beads:**
- `fuf5.1` — Merge module validation into single atomic subprocess (P2, foundational)
- `fuf5.4` — Check all dotted segment origins against trusted root (P2, depends on fuf5.1)
- `fuf5.5` — Add unit tests for module_validation.py error paths (P2, depends on fuf5.1)
- `fuf5.7` — Include subprocess stderr in error messages (P3, depends on fuf5.1)
- `fuf5.8` — Broaden exception handling in meta_path walker (P3, depends on fuf5.1)
- `fuf5.15` — Remove dead require_importable_module export (P3, depends on fuf5.1)

**Story order rationale:** This story must complete first because 5 of 7 Layer 2 beads depend on the merged script shape from fuf5.1.

---

## Story 2: Trust Boundary Fail-Closed Behavior

**Why now:** The second-highest-impact security finding. Module checks can currently report `ok: True` when the trust boundary cannot be verified.

**Job:** Ensure module validation never silently bypasses trusted-root enforcement, and both preflight surfaces derive trust from the same source.

**Done looks like:** When `repo_root` is invalid, all module checks fail immediately. Both preflight surfaces use the same trusted-root value.

**Beads:**
- `fuf5.2` — Fail module checks when repo_root directory is invalid (P2, no deps)
- `fuf5.6` — Unify trusted_repo_root derivation across preflight surfaces (P2, depends on fuf5.2)

**Story order rationale:** Independent of Story 1. Can run in parallel if file reservations permit (fuf5.2 touches `same_host_stack.py`, fuf5.6 touches `operator_console_preflight.py`).

---

## Story 3: Scrubbing Contract Verification

**Why now:** The PYTHONPATH/PYTHONHOME contamination tests have false confidence — they don't actually test the scrubbing code.

**Job:** Add direct unit tests for `_build_import_env()` so the scrubbing contract is independently verified, then strengthen the scrubbing to cover all PYTHON* prefixed vars.

**Done looks like:** A unit test for `_build_import_env()` fails if any scrubbing line is removed. The function scrubs all PYTHON*-prefixed vars, not just 3 specific ones.

**Beads:**
- `fuf5.3` — Add direct unit tests for _build_import_env scrubbing (P2, no deps)
- `fuf5.10` — Scrub all PYTHON-prefixed env vars (P3, depends on fuf5.3)

**Story order rationale:** Independent of Stories 1 and 2. Can run in parallel.

---

## Story 4: Test Infrastructure Cleanup

**Why now:** Several test code quality issues were flagged: duplicated helpers, suboptimal caching, and missing test paths. These are all P3 but contribute to maintainability.

**Job:** Deduplicate test helpers, optimize venv caching, and add coverage for the probe-fail-repair path.

**Done looks like:** No duplicated test functions. One shared cache key. The probe-fail-repair path has test coverage.

**Beads:**
- `fuf5.11` — Deduplicate _site_packages_dir in bootstrap proof test (P3, no deps)
- `fuf5.12` — Consolidate shadow finder sitecustomize bodies (P3, no deps)
- `fuf5.13` — Optimize test venv sharing with unified cache keys (P3, no deps)
- `fuf5.14` — Add test coverage for probe-fail-repair path (P3, no deps)

**Story order rationale:** All P3, all independent. Can run in parallel with everything else.

---

## Story 5: Input Validation Hardening

**Why now:** Module name validation accepts non-identifier characters. Low risk but easy to fix.

**Job:** Restrict `clean_module_name` to valid Python identifier characters.

**Done looks like:** `clean_module_name("ids-console")` raises ValueError.

**Beads:**
- `fuf5.9` — Validate Python identifier characters in clean_module_name (P3, no deps)

**Story order rationale:** Independent. Can run anytime.

---

## Parallelism Map

```
Time -->

Story 1: [fuf5.1] -----> [fuf5.4, fuf5.5, fuf5.7, fuf5.8, fuf5.15]
Story 2: [fuf5.2] -----> [fuf5.6]
Story 3: [fuf5.3] -----> [fuf5.10]
Story 4: [fuf5.11, fuf5.12, fuf5.13, fuf5.14]  (all parallel)
Story 5: [fuf5.9]  (independent)
```

Stories 1-5 can all start in parallel (their Layer 1 beads have no inter-story dependencies).

---

## File Scope Matrix (for reservation planning)

| Bead | Production Files | Test Files |
|------|-----------------|------------|
| fuf5.1 | `ids/ops/module_validation.py` | `tests/ops/test_ids_operator_console_preflight.py`, `tests/ops/test_ids_same_host_stack_manage.py` |
| fuf5.2 | `ids/ops/same_host_stack.py` | `tests/ops/test_ids_same_host_stack_manage.py` |
| fuf5.3 | — | `tests/ops/test_ids_module_validation.py` (new) |
| fuf5.4 | `ids/ops/module_validation.py` | tests (same as fuf5.1) |
| fuf5.5 | — | `tests/ops/test_ids_module_validation.py` (new) |
| fuf5.6 | `ids/ops/operator_console_preflight.py` | `tests/ops/test_ids_operator_console_preflight.py` |
| fuf5.7 | `ids/ops/module_validation.py` | tests |
| fuf5.8 | `ids/ops/module_validation.py` | tests |
| fuf5.9 | `ids/ops/module_validation.py` | tests |
| fuf5.10 | `ids/ops/module_validation.py` | `tests/ops/test_ids_module_validation.py` |
| fuf5.11 | — | `tests/ops/test_ids_repo_installable_bootstrap_proof.py` |
| fuf5.12 | — | `tests/ops/repo_installable_proof_support.py`, `tests/ops/test_ids_repo_installable_bootstrap_proof.py` |
| fuf5.13 | — | `tests/ops/test_ids_operator_console_preflight.py`, `tests/ops/test_ids_same_host_stack_manage.py` |
| fuf5.14 | — | `tests/ops/test_ids_repo_installable_surface.py` |
| fuf5.15 | `ids/ops/module_validation.py` | — |

**Collision note:** `ids/ops/module_validation.py` is touched by fuf5.1, fuf5.4, fuf5.7, fuf5.8, fuf5.9, fuf5.10, fuf5.15. The dependency graph already serializes these (fuf5.4/7/8/10/15 all depend on fuf5.1). fuf5.9 is independent but small enough to merge or sequence.
