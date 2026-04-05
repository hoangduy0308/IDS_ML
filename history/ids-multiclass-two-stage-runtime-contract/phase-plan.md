# Phase Plan: Two-Stage Runtime Family Contract

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-runtime-contract`
**Based on**:
- `history/ids-multiclass-two-stage-runtime-contract/CONTEXT.md`
- `history/ids-multiclass-two-stage-runtime-contract/discovery.md`
- `history/ids-multiclass-two-stage-runtime-contract/approach.md`

---

## 1. Feature Summary

This feature makes the production IDS runtime do more than say "Attack" or "Benign". After it lands, a composite active bundle can keep the existing binary alert contract and also attach a best-known attack family when the family signal is strong enough, while clearly returning `unknown` or `benign` in the other cases. The work is phased because the system has to learn one new production contract first, then carry that contract safely through the realtime daemon and lifecycle surfaces, and only then harden packaging and rollout behavior around it.

---

## 2. Why This Breakdown

- Phase 1 must happen first because nothing else is safe until one composite bundle can be resolved and one inference path can produce the new family fields without breaking today's binary contract.
- Later phases stay separate because the live sensor, preflight, health, and packaging surfaces are operational amplifiers; extending them before the core contract is stable would spread ambiguity instead of containing it.
- This breakdown contains the highest risk in one place early: the composite manifest and two-stage runtime semantics. Once that contract is believable, the remaining phases are mostly propagation and hardening.

---

## 3. Phase Overview Table

| Phase | What Changes In Real Life | Why This Phase Exists Now | Demo Walkthrough | Unlocks Next |
|-------|----------------------------|---------------------------|------------------|--------------|
| Phase 1: Make One Composite Bundle Score Safely | One inference entrypoint can read a composite bundle, keep the binary fields, and add family enrichment with `known / unknown / benign` semantics. Legacy binary bundles still keep working. | This is the first believable slice of the feature; without it, there is no production contract to propagate anywhere else. | Point batch inference or realtime scoring at a composite bundle and see binary fields plus family enrichment; point the same runtime at a legacy binary bundle and see the old binary-only output. | Preflight, lifecycle, health, and daemon wiring can now trust one concrete composite contract. |
| Phase 2: Make The Live Runtime Respect That Contract | The realtime daemon path, preflight, lifecycle commands, and health/status surfaces all understand the composite bundle and fail closed when it is broken. | Once one scoring path works, the next real-world question is whether the actual daemon and ops path can run it safely. | Promote a composite bundle, pass preflight, run the realtime pipeline or live sensor path, and see composite-aware runtime/health evidence. | Packaging and rollout hardening can now be done against a real operational contract rather than a lab-only path. |
| Phase 3: Make Promotion And Rollback Operationally Safe | Packaging, promotion, rollback, and regression coverage support composite bundles as a normal production artifact. | This closes the rollout loop so the feature is shippable rather than just technically possible. | Build the composite artifact, verify it, promote it, fail a bad candidate without disturbing the active bundle, and roll back successfully. | Review / ship / later console-family lane. |

---

## 4. Phase Details

### Phase 1: Make One Composite Bundle Score Safely

- **What Changes In Real Life**: one runtime path can use the selected stage-2 checkpoint and emit family enrichment without changing the existing binary alert meaning.
- **Why This Phase Exists Now**: this is the smallest believable slice of the whole feature and the place where the highest design risk lives.
- **Stories Inside This Phase**:
  - Story 1: Define the composite contract - decide how a bundle declares stage 1, stage 2, and abstention thresholds while preserving legacy-binary compatibility.
  - Story 2: Teach inference to use it - extend the runtime config and scoring path so composite bundles append family enrichment and legacy bundles remain binary-only.
  - Story 3: Prove the output semantics - add regression coverage that pins `known`, `unknown`, `benign`, and fail-closed behavior.
- **Demo Walkthrough**: create a composite bundle fixture, run `ids-inference` or the runtime helper on a sample frame, and see `attack_score`, `predicted_label`, `is_alert`, `threshold`, plus `attack_family`, `attack_family_confidence`, `attack_family_margin`, and `family_status`. Then rerun against a legacy binary bundle and confirm the old binary shape still works.
- **Unlocks Next**: the live runtime and operational lifecycle surfaces can now extend a concrete, test-proven composite contract instead of guessing at one.

### Phase 2: Make The Live Runtime Respect That Contract

- **What Changes In Real Life**: the actual realtime pipeline, live-sensor preflight, activation lifecycle, and health/status path all treat the composite bundle as the production truth.
- **Why This Phase Exists Now**: after Phase 1 proves one scoring seam, the next risk is whether the supervised daemon path and operator lifecycle path honor the same contract.
- **Stories Inside This Phase**:
  - Story 1: Carry family enrichment through the realtime event path.
  - Story 2: Make preflight and lifecycle commands composite-aware and fail closed on bad candidates.
  - Story 3: Surface composite bundle readiness and active-state visibility through health/runtime evidence.
- **Demo Walkthrough**: verify a composite bundle, activate it, run preflight successfully, score a realtime JSONL sample through the pipeline, and inspect a health/runtime payload that shows the active composite bundle and its readiness.
- **Unlocks Next**: packaging and rollout hardening can now target the real daemon path rather than a standalone inference-only experiment.

### Phase 3: Make Promotion And Rollback Operationally Safe

- **What Changes In Real Life**: composite family enrichment becomes a normal deployable production artifact with packaging, verify/promote/rollback, and regression protection.
- **Why This Phase Exists Now**: only after the runtime and ops paths understand the composite contract does it make sense to harden release and rollback around it.
- **Stories Inside This Phase**:
  - Story 1: Package the selected stage-2 checkpoint into one deployable composite bundle.
  - Story 2: Prove failed promotion leaves the last known-good bundle untouched.
  - Story 3: Pin wrapper, packaging, and migration regressions so rollout does not silently narrow supported surfaces.
- **Demo Walkthrough**: build the composite bundle artifact, verify it, activate it, reject a deliberately corrupted candidate without changing the active bundle, then roll back successfully and keep runtime health consistent.
- **Unlocks Next**: final review and the later console-family lane, which can now consume a stable runtime contract instead of designing against a moving target.

---

## 5. Phase Order Check

- [x] Phase 1 is obviously first
- [x] Each later phase depends on or benefits from the one before it
- [x] No phase is just a technical bucket with no user/system meaning

---

## 6. Approval Summary

- **Current phase to prepare next**: `Phase 1 - Make One Composite Bundle Score Safely`
- **What the user should picture after that phase**: one active composite bundle can score traffic and add family enrichment with `known / unknown / benign` semantics while old binary bundles still work unchanged.
- **What will not happen until later phases**: the live sensor/preflight/health path and production packaging/rollback story are not wired yet.
