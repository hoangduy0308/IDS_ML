# Review-Fix Story Map: Runtime Contract Review Pass 2

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-runtime-contract`
**Contract**: `history/ids-multiclass-two-stage-runtime-contract/review-fix-2-contract.md`

---

## Story Table

| Story | What Happens | File Scope | Bead |
|-------|--------------|------------|------|
| Story 1: Gate stage-2 feature alignment to attack rows | runtime composite scoring aligns and scores stage-2 features only for attack rows and pins the mixed benign/attack regression in inference tests | `ids/runtime/inference.py`, `tests/runtime/test_ids_inference_composite_contract.py` | `ids_ml_new-d90e.14` |

---

## Shape

- This pass contains one blocking runtime bug fix.
- The bead is self-contained and should be implemented before any further review or epic closure.
