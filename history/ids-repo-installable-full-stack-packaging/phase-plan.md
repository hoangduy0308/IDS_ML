# Phase Plan: IDS Repo-Installable Full Stack Packaging

**Feature:** ids-repo-installable-full-stack-packaging
**Date:** 2026-04-02

---

## Phase History

### Phases 1-3 (complete)
The original packaging feature was executed across multiple phases covering:
- repo-root install metadata and canonical entrypoint mapping
- production-path normalization and runtime alignment
- deploy asset convergence, docs canonicalization, final bootstrap proof

All phases are complete. The feature shipped and passed review.

### Phase 4: First Review Follow-up (complete)
Epic `ids_ml_new-4of7` addressed 4 review findings (1 P1, 2 P2, 1 P3) from the initial post-execution review. All beads closed:
- `ids_ml_new-oupo` — side-effect-safe module validation (P1)
- `ids_ml_new-n4cg` — portable console README links (P3)
- `ids_ml_new-ogbn` — rekey editable proof cache (P2)
- `ids_ml_new-grin` — caller-environment contamination regressions (P2)

### Phase 5: Second Review Follow-up (current)
Epic `ids_ml_new-fuf5` addresses 15 findings (6 P2, 9 P3) from the review of Phase 4 changes. This is the current phase awaiting validation.

---

## Phase 5 Overview

**Name:** Module Validation Trust Boundary Hardening
**Epic:** `ids_ml_new-fuf5`
**Entry state:** Phase 4 code is merged. 87 tests pass. No P1 findings remain.
**Exit state:** All P2 findings are resolved. Module validation has atomic subprocess execution, full-chain trusted-root verification, unified trust derivation, and comprehensive unit test coverage.

**Stories:**
1. Atomic validation pipeline (fuf5.1 + dependents)
2. Trust boundary fail-closed behavior (fuf5.2 + fuf5.6)
3. Scrubbing contract verification (fuf5.3 + fuf5.10)
4. Test infrastructure cleanup (fuf5.11, fuf5.12, fuf5.13, fuf5.14)
5. Miscellaneous hardening (fuf5.9)

**P3 beads** are included for completeness but are not required for the phase exit state.
