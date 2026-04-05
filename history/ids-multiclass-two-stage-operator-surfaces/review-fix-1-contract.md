# Review-Fix Contract: Operator Surfaces Review Pass 1

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-operator-surfaces`
**Reason**: review uncovered one blocking contract gap in benign and abstention semantics on the real alert-detail surface

---

## 1. What This Pass Changes

This pass closes the review findings that matter to the shipped operator contract:

- benign alerts must not preserve or render attack-family label fields
- unknown alerts must expose the runtime abstention context completely enough for operators to interpret the state
- the canonical app-factory route tests must prove known, unknown, benign, and legacy family semantics on `/alerts/{id}`

---

## 2. Entry State

- Phase 1 implementation is complete and the targeted console suite is green.
- Review found:
  - a blocking test-contract gap: benign family semantics are not pinned on the real route despite locked decision `D8`
  - a visible semantics gap: the unknown branch drops abstention margin even though runtime emits it
  - the shared helper still preserves stray family fields for benign rows

---

## 3. Exit State

- `build_alert_family_view()` clears family label and numeric family fields when the normalized state is `benign`.
- The alert detail page exposes `unknown` abstention context completely enough to include runtime margin when present.
- The canonical `/alerts/{id}` route tests prove known, unknown, benign, and legacy behavior, including:
  - benign rows show no family label/confidence/margin
  - unknown rows keep explicit unknown semantics and their visible support fields
  - known rows keep the visible confidence/margin contract

---

## 4. Stories

| Story | Done Looks Like |
|-------|-----------------|
| Story 1: Tighten family semantics and route proof | benign rows cannot leak family labels, unknown rows show full abstention context, and the real alert-detail route tests pin all four visible states |

---

## 5. Success Signal

The review finding in `ids_ml_new-3rc7.9` can no longer be reproduced, and the targeted console tests fail if benign/no-label behavior or visible abstention semantics drift again.
