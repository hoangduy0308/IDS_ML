# Two-Stage Runtime Family Contract - Context

**Feature slug:** ids-multiclass-two-stage-runtime-contract
**Date:** 2026-04-05
**Exploring session:** complete
**Scope:** Standard

---

## Feature Boundary

This feature adds stage-2 family enrichment to the production runtime and bundle activation contract while keeping the existing binary alert contract intact; console storage, console UI, notifications, and reporting are explicitly out of scope.

**Domain type(s):** CALL | RUN | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Scope & Rollout
- **D1** This session only covers runtime scoring plus bundle activation/validation for stage-2 family enrichment; console storage/display is a separate future lane.
  *Rationale: keep the foundational runtime contract independent from operator-surface changes.*

- **D11** Phase 2 scope stops at runtime scoring path and bundle activation/validation. Console DB, alerts page, reporting, and notifications remain out of scope.
  *Rationale: prevent cross-subsystem coupling during the first production-facing rollout.*

### Family Semantics
- **D2** Stage 2 only predicts within the known closed set; any low-confidence or out-of-closed-set-looking case must become `unknown` rather than being forced into a known family.
  *Rationale: the user wants known families classified when possible and everything else routed to `unknown`.*

- **D3** If stage 1 says `Benign`, runtime returns `family_status="benign"` and does not populate `attack_family`.
  *Rationale: `Benign` is not an attack family and must stay distinct from `unknown`.*

- **D8** The production closed set remains `DDoS / DoS / Mirai / Spoofing / Web-Based`, but weak predictions, especially around `Web-Based`, must be allowed to fall back to `unknown`.
  *Rationale: keep parity with the trained stage-2 label space while avoiding forced family assignment on weak evidence.*

### Runtime Output Contract
- **D4** When stage 1 says `Attack` and stage 2 is confident enough, runtime keeps all existing binary output fields unchanged and only adds family enrichment fields.
  *Rationale: preserve backward compatibility for current consumers.*

- **D10** Runtime adds these enrichment fields: `attack_family`, `attack_family_confidence`, `attack_family_margin`, and `family_status`, where `family_status` is one of `known`, `unknown`, or `benign`.
  *Rationale: downstream systems need explicit semantics rather than inferring state from binary labels.*

- **D12** If stage 2 is enabled and a runtime scoring call for stage 2 fails, that batch/request must fail clearly; runtime must not silently fall back to binary-only behavior.
  *Rationale: silent fallback would hide contract drift and produce misleading outputs.*

### Bundle & Activation Contract
- **D5** Production uses one composite bundle that contains both stage 1 and stage 2 and is activated in one step.
  *Rationale: follow the repo's single activation contract pattern and avoid stage drift.*

- **D6** A composite bundle is valid only when both stage 1 and stage 2 are compatible; if stage 2 is missing or incompatible, activation/startup must fail closed.
  *Rationale: production should not silently degrade into an unintended mixed contract.*

- **D7** Stage-2 abstention thresholds (`top1_confidence` and `runner_up_margin`) live inside the versioned composite bundle contract, not runtime config.
  *Rationale: threshold calibration is model behavior and must travel with the selected checkpoint.*

- **D9** Runtime must stay compatible with legacy binary bundles during transition; family enrichment is only active when the activation record points at the new composite bundle.
  *Rationale: rollout should support staged migration without breaking current installs.*

### Agent's Discretion
- Planning may choose the exact composite manifest shape, versioning details, and startup validation flow as long as they implement D5-D9 exactly.
- Planning may decide how runtime code is decomposed internally as long as D2-D4 and D10-D12 remain externally true.

---

## Specific Ideas & References

- The intended runtime meaning is: classify into known families when the family signal is strong enough; otherwise emit `unknown`.
- `Benign` must stay separate from `unknown`.
- The currently selected stage-2 checkpoint is the imported full-data family classifier with `iterations=500` and `class_weight_exponent=0.5`, recorded in the Phase 1 acceptance summary.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `ids/runtime/inference.py` - current binary inference contract, bundle resolution path, and output frame assembly. This is the main extension point for family enrichment.
- `ids/runtime/realtime_pipeline.py` - current realtime event payload builder that emits `attack_score`, `predicted_label`, and `is_alert`. This is where runtime enrichment fields must be appended without breaking current output.
- `ids/core/model_bundle.py` - current bundle manifest validation and compatibility rules. It currently enforces `ids_binary_classifier.v1` and is the main place that must evolve into a composite contract.
- `ids/core/model_bundle_activation.py` - existing active-bundle resolution path used by runtime and ops. Planning should reuse this rather than inventing a parallel activation seam.
- `ml_pipeline/training/train_iot_diad_family_classifier.py` - current stage-2 family classifier training/report contract, including confidence and margin evidence that will feed abstention thresholds.
- `artifacts/modeling/cic_iot_diad_2024_family_views/family_classifier/reports/oracle_family_eval.json` - imported full-data stage-2 report selected as the current best checkpoint.

### Established Patterns
- Single activation contract: production bundle selection already flows through `active_bundle.json` and manifest validation rather than loose model/schema overrides.
- Fail-closed bundle validation: `ids/core/model_bundle.py` already rejects incompatible bundle metadata and should remain the enforcement point.
- Runtime binary contract preservation: `ids/runtime/inference.py` and `ids/runtime/realtime_pipeline.py` currently expose a stable binary scoring shape that downstream consumers already expect.

### Integration Points
- `ids/runtime/inference.py` - extend scoring so stage 1 still produces binary outputs while stage 2 attaches family enrichment and abstention status.
- `ids/runtime/realtime_pipeline.py` - carry the new enrichment fields into emitted JSONL alert events.
- `ids/core/model_bundle.py` - define and validate the new composite bundle contract plus legacy compatibility behavior.
- `ids/ops/model_bundle_lifecycle.py` and `ids/ops/live_sensor_preflight.py` - ensure activation/preflight continue to validate the production contract through the canonical path.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `history/ids-multiclass-two-stage-classification/phase-1-acceptance-summary.md` - records the imported Kaggle evidence, selected stage-2 checkpoint, and why direct multiclass remains comparison-only.
- `history/ids-multiclass-two-stage-classification/CONTEXT.md` - original feature context that locked the overall two-stage direction and OOD/unknown intent.
- `history/learnings/critical-patterns.md` - repository-level critical patterns, especially the single activation contract rule and fail-closed runtime lessons.

---

## Outstanding Questions

### Deferred to Planning
- [ ] What exact composite manifest schema and versioning scheme should replace or extend `ids_binary_classifier.v1` while preserving D9? - requires codebase-level contract design against current bundle/activation helpers.
- [ ] Where should the selected stage-2 threshold values come from inside the imported family report, and how should they be encoded into the bundle manifest? - requires reading the full report contract and deciding how calibration metadata becomes runtime metadata.
- [ ] How should runtime surface stage-2 failures so batch/request callers get a clear contract-level failure without introducing a hidden binary-only fallback path? - requires inspection of current CLI/service error handling paths.

---

## Deferred Ideas

- Console alert storage, alert detail pages, notifications, and reporting for family enrichment - explicitly deferred to a separate lane after runtime contract work lands.
- Any attempt to replace the binary gate with direct multiclass inference - deferred because the imported Kaggle evidence still does not justify deployment.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
