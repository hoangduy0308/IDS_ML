STATUS: complete
EPIC: ids_ml_new-d90e (CLOSED)
HANDOFF: none

## Outcome

- Feature: ids-multiclass-two-stage-runtime-contract
- Review status: clean after review-fix pass 2
- Targeted verification: 127 passed, 0 failed
- Review-fix commits:
  - `107f9e3` realtime composite path preserves stage-2-only source fields
  - `284d74c` composite manifest rejects external override flags
  - `08e160b` stage-2 feature alignment and scoring now run only on attack rows

## Final Contract

- Binary runtime fields remain the primary contract.
- Composite bundles add `attack_family`, `attack_family_confidence`, `attack_family_margin`, and `family_status`.
- `family_status` semantics are `benign`, `unknown`, `known`.
- Composite activation remains fail-closed and legacy binary bundles still load in transition mode.
- Mixed benign/attack batches no longer require stage2-only columns on benign rows.

## Learnings

- Learnings file: `history/learnings/20260405-composite-runtime-review-contracts.md`
- Critical promotions: 2
