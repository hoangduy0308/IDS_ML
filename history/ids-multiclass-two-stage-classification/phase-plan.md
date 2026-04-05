# Phase Plan: IDS Multiclass Two-Stage Classification

**Date**: 2026-04-04
**Feature**: `ids-multiclass-two-stage-classification`
**Based on**:
- `history/ids-multiclass-two-stage-classification/CONTEXT.md`
- `history/ids-multiclass-two-stage-classification/discovery.md`
- `history/ids-multiclass-two-stage-classification/approach.md`

---

## 1. Feature Summary

The goal is to keep the current IDS behavior that decides `Attack` versus `Benign`, but stop there only for alert gating. Once a row is already considered an attack, the system should enrich that alert with a best-known attack family such as `DoS` or `Mirai`, or explicitly say it does not know the family yet. The work is phased because the repo first needs believable offline evidence and a safe deployment contract before it touches the live runtime and operator console.

---

## 2. Why This Breakdown

- Phase 1 has to come first because the repo does not yet have a reproducible family-view artifact or calibrated evidence that a family classifier with `unknown` behavior is worth shipping.
- Runtime and bundle changes are separate from offline modeling because the deployment seam is the riskiest part; we should only touch it after the data shape and evaluation rules are concrete.
- UI/operator changes are last because they are only meaningful once the live runtime fields and bundle contract are stable.

---

## 3. Phase Overview Table

| Phase | What Changes In Real Life | Why This Phase Exists Now | Demo Walkthrough | Unlocks Next |
|-------|----------------------------|---------------------------|------------------|--------------|
| Phase 1: Prove Family Classification Offline | The repo can reproducibly derive family-focused datasets and show whether a two-stage classifier plus `unknown` handling is credible on the processed data in both oracle and stage-1-gated form. | Nothing should touch production contracts until offline evidence is good enough to justify the rollout shape. | Run one derivation command, offline baseline commands, and a gated replay command, then inspect reports showing oracle family metrics, gated behavior, OOD unknown behavior, and direct-multiclass comparison. | A concrete model/package target instead of a speculative idea. |
| Phase 2: Wire One Safe Two-Stage Runtime Contract | A promoted bundle can drive the existing binary gate and, on attack rows only, add family prediction fields without breaking the current alert contract. | This is the smallest believable production slice after the offline evidence exists. | Activate a candidate bundle, replay flow records, and observe `attack_score`/`is_alert` unchanged plus new family enrichment fields on attack alerts. | Operator-facing visibility and adoption. |
| Phase 3: Make Family Predictions Usable For Operators | Operators can actually see and reason about the family prediction in the console and docs, not just in raw JSONL. | Visibility, docs, and wrapper proofs only matter after the runtime contract is stable. | Open the console, inspect alerts/detail, and see family/confidence/status fields that match the live payloads and runbook docs. | Review, rollout, and future family/scenario improvements. |

---

## 4. Phase Details

### Phase 1: Prove Family Classification Offline

- **What Changes In Real Life**: the repo gains a deterministic way to produce family-labeled training/eval views from the frozen binary dataset and can show whether stage 2 actually works on known families while abstaining on unknown ones.
- **Why This Phase Exists Now**: without this phase, later work would be guessing at class targets, calibration, and whether the unknown-family requirement is even achievable with the current data.
- **Stories Inside This Phase**:
  - Story 1: Derive family views from the frozen artifact — create reproducible attack-only and direct-multiclass views plus manifests and count reports.
  - Story 2: Train and compare offline baselines — train the stage-2 family classifier, measure it after stage-1 gating, and compare it to the direct multiclass baseline from the same derived source.
  - Story 3: Lock the acceptance rule — define how `unknown` is assigned and what offline evidence is strong enough to justify runtime work.
- **Demo Walkthrough**: Run the derived-data command against `artifacts/cic_iot_diad_2024_binary`, then run the stage-2 and direct-multiclass training commands, then run the gated two-stage evaluation. The result is a set of reports that clearly show oracle family confusion on in-distribution test data, what changes after stage-1 gating, unknown-family behavior on `BruteForce` and `Recon`, and whether the two-stage lane beats or at least justifies itself against the direct multiclass baseline.
- **Unlocks Next**: a concrete packaging target, concrete runtime fields, and a justified phase-2 contract.

### Phase 2: Wire One Safe Two-Stage Runtime Contract

- **What Changes In Real Life**: the active IDS runtime can still make the same binary alerting decision it makes today, but attack alerts now carry a family label, family confidence, and a family status such as `known` or `unknown`.
- **Why This Phase Exists Now**: phase 1 tells us what the stage-2 artifact looks like and how unknown-family behavior should work, which is the minimum needed before changing deployment/runtime code.
- **Stories Inside This Phase**:
  - Story 1: Promote one composite bundle — package binary and family artifacts under one manifest and one activation path.
  - Story 2: Extend inference without breaking the gate — keep `attack_score`, `predicted_label`, `is_alert`, and `threshold` stable while adding family enrichment on attack rows only.
  - Story 3: Prove replay and wrapper safety — show that CLI/runtime wrappers and bundle validation still work under the new additive contract.
- **Demo Walkthrough**: Promote a test bundle, point the replay or realtime pipeline at it, and score a sample JSONL stream. Alert rows still show the same binary gating fields, and attack rows additionally show family prediction fields with `unknown` on low-confidence or OOD-like samples.
- **Unlocks Next**: console surfaces and operator docs can now depend on a stable live payload shape.

### Phase 3: Make Family Predictions Usable For Operators

- **What Changes In Real Life**: operators stop reading family predictions out of raw JSONL and can inspect them in the console, with documentation and proofs that explain what `known` versus `unknown` means.
- **Why This Phase Exists Now**: until the runtime payload is stable, UI and documentation would keep changing underfoot.
- **Stories Inside This Phase**:
  - Story 1: Persist and expose the new fields cleanly — ensure the operator store and alert views can read family enrichment from the durable payload path.
  - Story 2: Surface the result where operators triage — add family/confidence/status to the appropriate alert views.
  - Story 3: Close the operational contract — update docs, wrapper smoke tests, and packaging/runtime proofs for the new lane.
- **Demo Walkthrough**: Load the console after replaying enriched alerts. The alerts surface shows the family prediction and its status, and the runbook/test surfaces show how the new two-stage lane is packaged, activated, and verified.
- **Unlocks Next**: review/ship for the first multiclass rollout, plus later work on scenario-level classification or richer unknown handling.

---

## 5. Phase Order Check

- [x] Phase 1 is obviously first
- [x] Each later phase depends on or benefits from the one before it
- [x] No phase is just a technical bucket with no user/system meaning

---

## 6. Approval Summary

- **Current phase to prepare next**: `Phase 1 - Prove Family Classification Offline`
- **What the user should picture after that phase**: the repo can generate family-focused datasets and reports that prove whether two-stage family classification with `unknown` behavior is credible on this dataset.
- **What will not happen until later phases**: no runtime bundle switch, no live alert enrichment, and no console changes yet.
