# Approach: Two-Stage Runtime Family Contract

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-runtime-contract`
**Based on**:
- `history/ids-multiclass-two-stage-runtime-contract/discovery.md`
- `history/ids-multiclass-two-stage-runtime-contract/CONTEXT.md`

---

## 1. Gap Analysis

> What exists vs. what the feature requires.

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Runtime scoring config | `ids/runtime/inference.py` only knows one binary model, one threshold, and one output contract | a composite runtime config that can resolve stage 1 plus optional stage 2 family scoring and abstention thresholds | Medium |
| Runtime output shape | binary fields only in `ids/runtime/inference.py` and `ids/runtime/realtime_pipeline.py` | additive family enrichment fields with explicit `family_status` semantics | Medium |
| Bundle contract | `ids/core/model_bundle.py` validates only `ids_binary_classifier.v1` with one model/schema/threshold bundle | composite bundle validation plus explicit legacy-binary compatibility path | High |
| Activation / lifecycle | `ids/core/model_bundle_activation.py` and `ids/ops/model_bundle_lifecycle.py` manage one active bundle cleanly | same lifecycle semantics for composite bundles without reopening split override seams | Medium |
| Preflight / health | preflight and health prove only the binary bundle is valid and visible | composite-aware verify-only startup and health/status surfaces that expose the enriched contract | Medium |
| Packaging / promotion surface | `ml_pipeline/packaging/package_final_model.py` packages only the binary production bundle | a production packaging flow that assembles the selected stage-2 artifact into a composite deployable bundle | High |
| Regression coverage | strong tests for binary bundle, activation, preflight, realtime pipeline, and health | matching composite + legacy-binary transition tests, including failed promotion and stage-2 runtime failure behavior | High |

---

## 2. Recommended Approach

Keep the production cutover model exactly as it works today: one active bundle chosen through one activation record, verified before runtime starts. Instead of inventing a second family-model config seam, extend the bundle manifest into a composite production contract that contains the existing binary stage plus a second stage-2 family block with its model path, feature schema path, and abstention thresholds. Then teach `ids.runtime.inference` to resolve that richer contract, preserve the existing binary output fields, and append family enrichment fields only when the active bundle is composite and the stage-2 signal clears the bundled thresholds. Finally, fan that contract through the realtime pipeline, lifecycle verification, preflight, health, and packaging surfaces so the daemon path, not just offline scripts, is using the same deployable artifact.

### Why This Approach

- It follows the existing production pattern at `ids/core/model_bundle.py` and `ids/core/model_bundle_activation.py` instead of reopening raw override seams.
- It honors D4, D5, D6, D7, D9, and D10 from `CONTEXT.md` without forcing a consumer migration to a brand-new runtime payload.
- It avoids the known failure mode from `20260329-model-bundle-promotion-hardening.md`: model, schema, and threshold drift across multiple inputs.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Production selection contract | one composite bundle activated through the existing activation record | locked by D5 and reinforced by the critical activation-contract learning |
| Legacy rollout behavior | keep old binary bundle validation path alive; only composite bundles enable family enrichment | locked by D9 and lowers rollout risk |
| Runtime output compatibility | preserve `attack_score`, `predicted_label`, `is_alert`, `threshold`; add family fields alongside them | locked by D4 and D10 |
| Abstention control | bundle-calibrated `top1_confidence` + `runner_up_margin` thresholds, evaluated inside runtime scoring | locked by D2 and D7 |
| Failure behavior | if composite stage 2 is active and scoring fails, propagate a clear runtime failure instead of binary-only fallback | locked by D12 and matches fail-closed repo patterns |
| Visibility path | reuse activation status / live sensor health surfaces rather than inventing console-owned state | aligns with existing runtime summary pattern and keeps D1/D11 intact |

---

## 3. Alternatives Considered

### Option A: Add a second runtime config seam for the family model

- Description: keep the existing binary bundle as-is and let runtime load a separate stage-2 model and thresholds from another file or config path.
- Why considered: looks smaller than evolving the production manifest and activation contract.
- Why rejected: directly violates the single-activation-contract pattern and recreates the exact drift seam the repo already hardened away.

### Option B: Replace the binary runtime contract with direct multiclass output

- Description: drop binary-first runtime behavior and let the new family model become the only prediction contract.
- Why considered: superficially simpler because there is only one model output.
- Why rejected: conflicts with locked decisions D2-D4, does not provide trustworthy `unknown` behavior, and is contradicted by the imported Kaggle evidence.

### Option C: Hide stage 2 behind runtime config and silently fall back on failure

- Description: opportunistically add family enrichment when available, but revert to binary-only behavior if stage 2 breaks.
- Why considered: lowers short-term operational friction.
- Why rejected: violates D6 and D12, makes contract drift invisible, and would be hard to reason about in production incidents.

---

## 4. Risk Map

> Every component that is part of this feature must appear here.

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Composite bundle manifest contract in `ids/core/model_bundle.py` | **HIGH** | core production contract, blast radius across runtime, ops, and packaging | Spike in validating: can one manifest shape preserve legacy-binary compatibility and fail-closed composite validation cleanly? |
| Runtime two-stage inference path in `ids/runtime/inference.py` | **HIGH** | scoring semantics change in a core runtime surface and must preserve additive compatibility | Spike in validating: can stage 2 append family fields without breaking current CLI/output contract? |
| Realtime pipeline propagation in `ids/runtime/realtime_pipeline.py` | **MEDIUM** | extends current event payload but follows established pattern | targeted tests |
| Activation / lifecycle handling in `ids/ops/model_bundle_lifecycle.py` and `ids/core/model_bundle_activation.py` | **MEDIUM** | extends existing lifecycle behavior, but still on a proven pattern | targeted tests for failed promote and legacy/composite coexistence |
| Preflight / health contract updates | **MEDIUM** | verify-only surfaces already exist, but new composite rules must be visible and strict | targeted tests |
| Composite bundle packaging flow | **HIGH** | new production artifact assembly path touching deployment semantics | Spike in validating: can packaging build one deployable composite artifact without disturbing existing binary packaging? |
| Legacy-binary compatibility path | **MEDIUM** | not novel but easy to regress while evolving manifest validation | regression tests |

### Risk Classification Reference

```
Pattern in codebase?        -> YES = LOW base
External dependency?        -> YES = HIGH
Blast radius > 5 files?     -> YES = HIGH
Otherwise                   -> MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `Composite bundle manifest contract`: prove the manifest/versioning shape can support composite + legacy validation without a split override seam.
- `Runtime two-stage inference path`: prove the additive output contract and fail-closed stage-2 behavior can coexist with current binary callers.
- `Composite bundle packaging flow`: prove the selected stage-2 checkpoint can be assembled into one deployable production artifact and activated through the existing lifecycle.

---

## 5. Proposed File Structure

> Where new files will live. Workers use this to plan their work.

```
ids/
  core/
    model_bundle.py                 # Extend manifest validation to composite + legacy-binary
    model_bundle_activation.py      # Reuse active-bundle resolution path for composite status
  runtime/
    inference.py                    # Add two-stage runtime config + scoring + family fields
    realtime_pipeline.py            # Emit family enrichment in realtime JSONL events
    live_sensor_health.py           # Report composite bundle readiness/visibility
  ops/
    model_bundle_lifecycle.py       # Verify/promote/rollback composite bundles
    live_sensor_preflight.py        # Composite-aware verify-only startup
ml_pipeline/
  packaging/
    package_final_model.py          # Extend or companion-pack composite bundle artifact
tests/
  runtime/
    test_ids_inference.py
    test_ids_realtime_pipeline.py
    test_ids_live_sensor_health.py
  ops/
    test_ids_live_sensor_preflight.py
    test_ids_model_bundle_manage.py
```

---

## 6. Dependency Order

> Dependency order for bead creation. This is planning guidance, not a runtime wave scheduler.

```
Layer 1: Composite contract definition
  - model bundle schema, manifest validation, packaging expectations

Layer 2: Runtime scoring behavior
  - inference config, stage-2 scoring, additive output contract

Layer 3: Runtime propagation and operational gates
  - realtime pipeline, preflight, lifecycle, health/status

Layer 4: Compatibility and hardening proofs
  - legacy-binary coverage, failed-promotion regressions, wrapper smokes
```

### Parallelizable Groups

- Group A: contract design and packaging design can be researched together, but runtime implementation must wait for the chosen manifest shape.
- Group B: realtime pipeline and health/preflight work can run in parallel after the runtime scoring contract is fixed.
- Group C: compatibility tests and wrapper smokes can expand once the core implementation stabilizes.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | one activation contract must own production model selection | composite bundle is defined as an extension of the existing active-bundle path, not as a sidecar config seam |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | preflight and runtime should fail closed rather than degrade silently | stage-2 contract and scoring failures are planned as explicit failures, not binary-only fallback |
| `history/learnings/20260403-packaging-contract-proof.md` | validation and execution must stay bound to the same contract | preflight, lifecycle, runtime, and packaging all point at the same composite bundle artifact |
| `history/learnings/20260331-repo-structure-wrapper-contracts.md` | wrappers are executable contracts and must be tested directly | wrapper-smoke and canonical module help surfaces remain part of the verification plan |

---

## 8. Open Questions for Validating

- [ ] Is a new `manifest_version` or a new nested `inference_contract.version` the cleaner way to represent a composite bundle while preserving legacy-binary reads? - matters because it defines how much branching workers need to introduce across runtime and ops.
- [ ] What exact runtime failure surface should represent stage-2 scoring errors once composite mode is active? - matters because D12 forbids silent fallback but the codebase has several entrypoints that may need consistent error semantics.
- [ ] Should composite bundle packaging extend `package_final_model.py` directly or land as a companion packager first? - impacts blast radius and how much deployment behavior changes in one phase.
