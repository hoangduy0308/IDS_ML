STATUS: complete
EPIC: ids_ml_new-d90e (CLOSED)
HANDOFF: none

## Outcome

- Feature: ids-multiclass-two-stage-runtime-contract
- Review status: clean after review-fix pass 1
- Targeted verification: 126 passed, 0 failed
- Review-fix commits:
  - `107f9e3` realtime composite path preserves stage-2-only source fields
  - `284d74c` composite manifest rejects external override flags

## Final Contract

- Binary runtime fields remain the primary contract.
- Composite bundles add `attack_family`, `attack_family_confidence`, `attack_family_margin`, and `family_status`.
- `family_status` semantics are `benign`, `unknown`, `known`.
- Composite activation remains fail-closed and legacy binary bundles still load in transition mode.

## Learnings

- Learnings file: `history/learnings/20260405-composite-runtime-review-contracts.md`
- Critical promotions: 2
