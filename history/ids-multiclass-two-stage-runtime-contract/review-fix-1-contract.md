# Review-Fix Contract: Runtime Contract Review Pass 1

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-runtime-contract`
**Reason**: review uncovered one blocking runtime regression and one composite-manifest hardening gap

---

## 1. What This Pass Changes

This pass fixes the concrete review findings from the first full-feature review:

- realtime composite scoring must not fail when the stage-2 feature schema is a strict superset of the stage-1 schema
- composite bundle validation must reject any attempt to declare external stage-1/stage-2/abstention override seams

---

## 2. Entry State

- All three planned phases are implemented and the targeted test matrix is green.
- Review found:
  - a P1 runtime regression in the realtime path when stage-2 requires extra columns beyond stage 1
  - a P2 hardening gap where composite manifests validate boolean override flags but do not reject `true`

---

## 3. Exit State

- The realtime pipeline can supply the full feature frame required by composite stage-2 scoring, including stage-2-only columns, without breaking the legacy binary path.
- Tests prove that realtime composite scoring works with the real `IDSInferencer`, not only a dummy inferencer.
- Composite manifest validation fails closed if any external stage-1/stage-2/abstention override flag is `true`.

---

## 4. Stories

| Story | Done Looks Like |
|-------|-----------------|
| Story 1: Fix realtime composite feature alignment | composite realtime scoring no longer fails when stage 2 needs extra columns; targeted runtime tests prove it |
| Story 2: Tighten composite manifest override rejection | composite manifests with any external override flag set to `true` are rejected explicitly by validation tests |

---

## 5. Success Signal

The exact review findings can no longer be reproduced, and the targeted regression tests fail if either contract drifts again.
