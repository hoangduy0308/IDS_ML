# Review-Fix Story Map: Operator Surfaces Review Pass 1

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-operator-surfaces`
**Contract**: `history/ids-multiclass-two-stage-operator-surfaces/review-fix-1-contract.md`

---

## Story Table

| Story | What Happens | File Scope | Bead |
|-------|--------------|------------|------|
| Story 1: Tighten family semantics and route proof | align benign and unknown detail semantics with locked decisions and pin them through the canonical app-factory route tests | `ids/console/alerts.py`, `ids/console/templates/alert_detail.html`, `tests/console/test_ids_operator_console_alerts.py`, `tests/console/test_ids_operator_console_alerts_web.py`, `tests/console/test_ids_operator_console_web.py` | `ids_ml_new-3rc7.9` |

---

## Shape

- This review-fix pass is intentionally single-story and sequential.
- The bead is blocking because it closes the only accepted P1 review finding for this feature slice.
- Duplicate reviewer claims about the detail path bypassing the helper were checked against the live code and rejected because `/alerts/{id}` already loads through `list_alerts_for_triage()`.
