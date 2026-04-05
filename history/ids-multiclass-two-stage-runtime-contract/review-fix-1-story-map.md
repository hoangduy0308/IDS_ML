# Review-Fix Story Map: Runtime Contract Review Pass 1

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-runtime-contract`
**Contract**: `history/ids-multiclass-two-stage-runtime-contract/review-fix-1-contract.md`

---

## Story Table

| Story | What Happens | File Scope | Bead |
|-------|--------------|------------|------|
| Story 1: Fix realtime composite feature alignment | realtime batching carries the full composite feature frame and proves it with a real inferencer-backed regression test | `ids/runtime/realtime_pipeline.py`, `tests/runtime/test_ids_realtime_pipeline.py` | `ids_ml_new-d90e.12` |
| Story 2: Tighten composite manifest override rejection | composite manifest validation rejects any `true` external override flag and proves it in contract tests | `ids/core/model_bundle.py`, `tests/core/test_ids_model_bundle.py` | `ids_ml_new-d90e.13` |

---

## Shape

- The two stories are independent and may run in parallel.
- Story 1 is blocking for review cleanliness because it is a P1 runtime regression.
- Story 2 is a hardening follow-up from review and should land in the same review-fix pass.
