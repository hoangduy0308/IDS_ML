# IDS Multiclass Two-Stage Classification - Context

**Feature slug:** ids-multiclass-two-stage-classification
**Date:** 2026-04-04
**Exploring session:** complete
**Scope:** Standard

---

## Feature Boundary

This feature defines the dataset, model, runtime, and evaluation direction for extending the current binary IDS into a two-stage system that keeps binary attack detection as the production gate and adds attack-family classification as a second-stage enrichment step.

**Domain type(s):** RUN | ORGANIZE | CALL

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Runtime Architecture
- **D1** Keep the current `Attack/Benign` detector as the primary production decision point.
  *Rationale: the repo's current bundle, inference contract, realtime pipeline, and console all assume binary alerting. Replacing that contract in one step would create a much larger blast radius than necessary.*

- **D2** Add attack-family classification as a second-stage classifier that only runs on records already classified as `Attack` by stage 1.
  *Rationale: this preserves the existing alert gate while letting the system enrich alerts with more specific family information.*

- **D3** Stage 2 must support `unknown/abstain` behavior instead of forcing every detected attack into a known family.
  *Rationale: the processed dataset currently keeps `BruteForce` and `Recon` out of train as OOD holdout families, and some other families/scenarios are too sparse to justify forced closed-set predictions.*

- **D4** The first rollout must keep the current binary bundle/runtime contract intact and extend outputs, not replace them.
  *Rationale: the current contract is explicitly binary in the model bundle metadata and runtime code. The safer path is additive output fields such as family, confidence, and family-status rather than a breaking contract flip.*

### Labeling Strategy
- **D5** Stage 2 target labels are attack families, not attack scenarios.
  *Rationale: family-level labels already exist in the processed dataset, while scenario coverage is too sparse and uneven for a credible first multiclass rollout.*

- **D6** The initial recommended closed-set family space is the in-distribution families already present in train/val/test: `DDoS`, `DoS`, `Mirai`, `Spoofing`, and `Web-Based`.
  *Rationale: these are the families with actual supervised training signal in the current processed artifact.*

- **D7** `BruteForce` and `Recon` stay out of the initial stage-2 supervised training set and remain evaluation probes for unknown-family behavior.
  *Rationale: each currently comes from a single source file in the processed dataset, and the repo's current preprocessing protocol deliberately uses them as OOD holdout families.*

### Dataset and Evaluation
- **D8** Planning must treat the current processed binary dataset as a baseline artifact, not mutate it in place.
  *Rationale: the repo already depends on the frozen binary artifact and its manifests. Multiclass work should produce new artifacts or a new preprocessing mode instead of silently redefining existing ones.*

- **D9** The multiclass lane must be evaluated both as an oracle classifier on attack-only rows and as an end-to-end two-stage pipeline after stage-1 gating.
  *Rationale: stage-2 quality alone is not enough. The real system quality also depends on what stage 1 lets through.*

- **D10** Planning must include a direct multiclass baseline for offline comparison, but that baseline is not the default deployment target.
  *Rationale: we need a real comparison point, but the default production direction remains the two-stage system because the current runtime and dataset protocol favor that shape.*

### Agent's Discretion
- Model family for stage 2 is delegated. Planning may recommend CatBoost, one-vs-rest, calibrated tree models, or another strong tabular multiclass baseline.
- Calibration method, abstention rule, thresholding, class weighting, and resampling strategy are delegated.
- Planning may recommend a new preprocessing mode or a separate packaging lane for stage 2, as long as it does not silently overwrite the current binary artifact.

---

## Specific Ideas & References

- The user explicitly delegated the architectural choice after a careful dataset review instead of asking for a predetermined answer.
- The user asked for the decision to be grounded in the processed dataset before choosing the multiclass direction.
- The working direction chosen from that review is: `binary detector -> attack-family classifier with unknown/abstain`.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `ml_pipeline/data_prep/preprocess_iot_diad.py` - current preprocessing pipeline; derives `derived_label_binary`, preserves `attack_family` metadata, and assigns `BruteForce`/`Recon` to `ood_attack_holdout`.
- `ml_pipeline/training/train_iot_diad_binary.py` - current binary training lane; hard-codes `LABEL_MAP = {"Benign": 0, "Attack": 1}` and defines the current train/eval assumptions.
- `ml_pipeline/packaging/package_final_model.py` - current model packaging lane; planning should inspect how to add or parallel a second-stage bundle without breaking the existing binary package.
- `ids/runtime/inference.py` - current production inference path; emits `attack_score`, `predicted_label`, `is_alert`, and assumes binary `predict_proba(... )[:, 1]`.
- `ids/runtime/realtime_pipeline.py` - current realtime scoring and alert emission path; planning must inspect how additive stage-2 enrichment would attach to emitted alerts.
- `ids/core/model_bundle.py` - current bundle compatibility layer; explicitly declares `ids_binary_classifier.v1`.

### Established Patterns
- Frozen dataset artifact pattern: the repo treats `artifacts/cic_iot_diad_2024_binary` as a canonical processed dataset with manifests and reports, not an ad hoc scratch output.
- Additive runtime enrichment pattern: current alert JSONL already carries model fields plus passthrough metadata, which makes it plausible to add family fields without replacing the binary decision contract.
- OOD evaluation pattern: the preprocessing protocol intentionally holds out `BruteForce` and `Recon` from train to test generalization on unseen attack families.

### Integration Points
- `artifacts/cic_iot_diad_2024_binary/manifests/file_manifest.csv` - source-file-level family/scenario/split truth for dataset review.
- `artifacts/cic_iot_diad_2024_binary/manifests/cleaning_report.json` - row counts, family targets, and current OOD family policy.
- `artifacts/final_model/catboost_full_data_v1/model_bundle.json` - current production bundle metadata showing binary contract assumptions.
- `artifacts/final_model/catboost_full_data_v1/metrics.json` - current binary metrics, including the OOD recall limitation that matters for two-stage error propagation.
- `history/audit-2026-04-04-findings/BACKLOG.md` - audit item H1 motivating multiclass extension.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `docs/current/ml/dataset_preprocessing_protocol.md` - defines how the current processed dataset was built and why `BruteForce`/`Recon` were held out.
- `artifacts/cic_iot_diad_2024_binary/manifests/cleaning_report.json` - the canonical processed-dataset summary used during this exploring pass.
- `artifacts/cic_iot_diad_2024_binary/manifests/file_manifest.csv` - the canonical per-source-file split/family/scenario manifest.
- `docs/current/ml/final_model_decision.md` - explains why the current production lane was optimized as binary IDS.
- `artifacts/final_model/catboost_full_data_v1/model_bundle.json` - current deployment contract metadata.
- `artifacts/final_model/catboost_full_data_v1/metrics.json` - current binary performance baseline.

---

## Outstanding Questions

### Resolve Before Planning

None.

### Deferred to Planning

- [ ] Should stage 2 ship as a separate model bundle resolved by the binary bundle, or as a composite two-stage bundle contract? - Planning needs to inspect the packaging and activation code paths.
- [ ] Should stage-2 training use family-balanced sampling, per-class weighting, or a calibrated one-vs-rest setup? - Planning needs actual modeling and class-imbalance analysis.
- [ ] What exact abstention rule should define `unknown_attack_family`? - Planning needs to compare confidence-threshold, margin-based, and OOD-specific options.
- [ ] Should the repo add a new preprocessing mode for multiclass/family training, or derive stage-2 data from the existing processed artifact? - Planning needs to weigh reproducibility against implementation blast radius.
- [ ] Where should the console surface family predictions first: alert detail only, alerts table, or both? - Planning should inspect UI scope and current alert schema consumers.

---

## Deferred Ideas

- Scenario-level classification inside each family - deferred because scenario coverage is too sparse and uneven for a credible first multiclass rollout.
- Replacing the binary detector with a direct multiclass production contract - deferred until an offline baseline proves it beats or meaningfully simplifies the two-stage design.
- Training `BruteForce` and `Recon` as ordinary stage-2 supervised classes in the first iteration - deferred because the current processed dataset gives each only one source file and uses them as OOD probes.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
