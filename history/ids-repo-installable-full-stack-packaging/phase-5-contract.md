# Phase 5 Contract: Module Validation Trust Boundary Hardening

**Feature:** ids-repo-installable-full-stack-packaging
**Phase:** 5 of 5
**Epic:** `ids_ml_new-fuf5`

---

## Entry State

- Phase 4 review-followup code is committed (commits a7941e2, 8224788, ecd20a7, b456d12).
- 87 tests pass across the full ops/docs test suite.
- Module validation uses a two-phase subprocess pattern (origin resolution + import proof in separate calls).
- Trusted-root containment checks only the leaf module origin.
- `_build_import_env()` scrubs 3 specific PYTHON* vars; `-I` flag provides overlapping coverage.
- No P1 review findings remain.

## Exit State

When this phase is complete, the following must be true:

1. **Module validation is atomic**: origin resolution, trusted-root containment, and import proof happen in a single subprocess call with no TOCTOU gap.
2. **Trust boundary is fail-closed**: module checks fail explicitly when the repo_root directory is invalid, rather than silently skipping containment.
3. **All dotted segments are checked**: intermediate package origins (e.g., `ids/__init__.py`) are verified against the trusted root, not just the leaf module.
4. **Trust derivation is consistent**: both preflight surfaces (operator console and stack) derive the trusted root from the same source.
5. **Scrubbing contract is directly tested**: `_build_import_env()` has its own unit test that fails if scrubbing is removed, independent of the `-I` flag.
6. **Error path coverage exists**: `resolve_importable_module()` error paths have direct unit tests.

## Demo

Run the full test suite and point to:
- The single merged validation subprocess script
- The unit test for `_build_import_env()` that directly asserts env dict contents
- The intermediate-origin test that rejects a hostile `__init__.py` outside trusted root
- The fail-closed test where module checks fail when repo_root is invalid

## Phase Unlocks

This is the final phase. Completing it means the module validation trust boundary is hardened to the standard identified by the 4-agent review panel. No further phases are planned.

## Beads

6 P2 (required for exit state) + 9 P3 (optional hardening).
