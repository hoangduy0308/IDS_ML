# Review-Fix Contract: Runtime Contract Review Pass 2

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-runtime-contract`
**Reason**: follow-up review found one remaining runtime correctness bug in stage-2 gating

---

## 1. What This Pass Changes

This pass fixes the remaining concrete review finding from follow-up review:

- composite stage-2 feature alignment must only run on rows that stage 1 already classified as `Attack`

---

## 2. Entry State

- All planned phase beads plus review-fix pass 1 are implemented.
- Follow-up review revalidated the feature and found one remaining runtime bug:
  - `IDSInferencer.score_frame()` aligns stage-2 feature columns against the full batch before it narrows to stage-1 attack rows
  - a benign row missing a stage2-only feature can therefore fail the whole composite batch even though family enrichment should not apply to benign traffic

---

## 3. Exit State

- Composite runtime scoring only aligns and scores stage-2 features for rows that stage 1 marked as `Attack`.
- Mixed benign/attack batches with stage2-only columns present only on attack rows no longer fail.
- Tests prove the bug reproduces on the old path and stays fixed on the new path.

---

## 4. Stories

| Story | Done Looks Like |
|-------|-----------------|
| Story 1: Gate stage-2 feature alignment to attack rows | stage-2 alignment/scoring only touches attack rows and regression tests prove benign rows no longer need stage2-only columns |

---

## 5. Success Signal

The reproduced bug can no longer be triggered, and composite runtime semantics now match the locked decision that family classification only applies after the binary `Attack/Benign` gate.
