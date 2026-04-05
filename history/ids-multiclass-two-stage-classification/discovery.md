# Discovery Report: IDS Multiclass Two-Stage Classification

**Date**: 2026-04-04
**Feature**: `ids-multiclass-two-stage-classification`
**CONTEXT.md reference**: `history/ids-multiclass-two-stage-classification/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- Keep production model selection on one activation contract. If stage 2 ships, it must travel through the same promoted bundle/activation path as stage 1 rather than reintroducing independent runtime overrides.
- Treat compatibility wrappers as executable contracts. Any new `scripts/*` entrypoint for multiclass preparation, training, or packaging must get smoke coverage in the same lane.
- Keep canonical modules independent from wrappers. New runtime or bundle logic belongs under `ids/*` or `ml_pipeline/*`, with `scripts/*` remaining thin shims only.
- Publish durable daemon outputs during runtime, not only at shutdown. Family enrichment has to appear in the live JSONL records as they are emitted, not only in a summary step.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | `ids.core.model_bundle`, activation flow | The safe deployment seam is one versioned bundle plus one activation record. Two-stage rollout must not split binary and family state across separate runtime knobs. | high |
| `history/learnings/20260331-repo-structure-wrapper-contracts.md` | `scripts/*`, `ids/*`, `ml_pipeline/*` | New CLI surfaces must stay wrapper-thin and be tested directly. Canonical code must not import back through wrappers. | high |
| `history/learnings/20260403-packaging-contract-proof.md` | packaging/install surface | Packaging claims are not real unless scrubbed install and wrapper behavior are proven outside a warmed tree. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | realtime JSONL pipeline | Realtime enrichment has to publish durable fields in the emitted alert stream during runtime. | medium |

---

## Agent A: Architecture Snapshot

> Source: code reading, repo topology, bundle/runtime contract inspection

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `ml_pipeline/data_prep` | Builds frozen parquet datasets and manifests from raw CIC-IoT-DIAD CSVs. | `ml_pipeline/data_prep/preprocess_iot_diad.py` |
| `ml_pipeline/training` | Trains current binary baselines and writes evaluation reports. | `ml_pipeline/training/train_iot_diad_binary.py` |
| `ml_pipeline/packaging` | Assembles deployable model bundles and model cards. | `ml_pipeline/packaging/package_final_model.py` |
| `ids/core` | Owns bundle contract parsing, schema metadata, and activation compatibility. | `ids/core/model_bundle.py` |
| `ids/runtime` | Loads the active bundle, scores records, and emits realtime alert JSONL. | `ids/runtime/inference.py`, `ids/runtime/realtime_pipeline.py` |
| `ids/console` | Persists alerts/anomalies and renders operator surfaces. | `ids/console/db.py`, `ids/console/templates/alerts.html` |

### Entry Points

- **Preprocessing wrapper**: `scripts/preprocess_iot_diad.py` -> `ml_pipeline.data_prep.preprocess_iot_diad.main`
- **Binary training wrapper**: `scripts/train_iot_diad_binary.py` -> `ml_pipeline.training.train_iot_diad_binary`
- **Packaging wrapper**: `scripts/package_final_model.py` -> `ml_pipeline.packaging.package_final_model.main`
- **Offline inference CLI**: `ids/runtime/inference.py`
- **Realtime scoring pipeline**: `ids/runtime/realtime_pipeline.py`
- **Operator store/UI**: `ids/console/db.py` and Jinja templates under `ids/console/templates/`

### Key Files to Model After

- `ml_pipeline/data_prep/preprocess_iot_diad.py` — demonstrates the repo's frozen-artifact + manifest/report pattern.
- `ml_pipeline/training/train_iot_diad_binary.py` — demonstrates split loading, sampling, evaluation, and report-writing conventions for large parquet datasets.
- `ml_pipeline/packaging/package_final_model.py` — demonstrates how deployment metadata is assembled from upstream reports into a promoted bundle.
- `ids/core/model_bundle.py` — demonstrates the fail-closed bundle contract boundary that the two-stage lane must extend instead of bypassing.
- `ids/runtime/realtime_pipeline.py` — demonstrates the append-oriented JSONL emission path that new family fields must preserve.

---

## Agent B: Pattern Search

> Source: code reading and targeted symbol/file search

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Frozen processed dataset | `ml_pipeline/data_prep/preprocess_iot_diad.py` | Deterministic parquet splits + manifests + cleaning report | Yes |
| Binary classifier training | `ml_pipeline/training/train_iot_diad_binary.py` | Large-parquet streaming, sampled train subset, full-split eval | Yes |
| Production model bundle | `ml_pipeline/packaging/package_final_model.py` + `ids/core/model_bundle.py` | One manifest carrying model/schema/threshold compatibility metadata | Yes |
| Realtime alert emission | `ids/runtime/realtime_pipeline.py` | Additive prediction fields emitted per record to durable JSONL | Yes |
| Alert persistence with extensible payload | `ids/console/db.py` | Narrow query columns + full `payload_json` blob for full-fidelity record storage | Yes |

### Reusable Utilities

- **Bundle schema metadata**: `ids/core/model_bundle.py` — `build_feature_schema_metadata(...)`
- **Bundle inference metadata**: `ids/core/model_bundle.py` — `build_inference_contract_metadata(...)`
- **Atomic JSON writes**: `ids/core/model_bundle.py` — `write_json_atomic(...)`
- **Operator payload persistence**: `ids/console/db.py` — `OperatorStore.upsert_alert(...)` already stores the full alert payload as JSON, which reduces immediate schema pressure for stage-2 fields.

### Naming Conventions

- Dataset/training tasks use explicit domain names such as `preprocess_iot_diad.py`, `train_iot_diad_binary.py`.
- Bundle contract types are explicit and versioned, for example `ids_binary_classifier.v1`.
- Runtime prediction fields are simple flat keys such as `attack_score`, `predicted_label`, `is_alert`, `threshold`.

---

## Agent C: Constraints Analysis

> Source: processed dataset manifests, current runtime/bundle contract, console schema

### Runtime & Model Contract

- **Current production contract**: binary only
- **Bundle manifest version**: `2`
- **Inference contract version**: `ids_binary_classifier.v1`
- **Prediction type**: `binary_classifier`
- **Primary production model**: `CatBoostClassifier`

### Existing Dependencies (Relevant to This Feature)

| Package / Asset | Purpose |
|-----------------|---------|
| `catboost` | Current production binary classifier and strongest tabular baseline already in repo |
| `pyarrow` / parquet | Large-scale dataset IO for frozen artifacts |
| `pandas` / `numpy` | Dataset derivation, streaming eval, report generation |
| SQLite operator store | Current persistence surface for alerts and payload JSON |

### Dataset Constraints

- The frozen dataset artifact is binary by task, but it retains `attack_family`, `attack_scenario`, and `derived_label_family` metadata in the clean parquet files.
- `BruteForce` and `Recon` are intentionally held out as `ood_attack_holdout`; they should remain unknown-family probes for the first stage-2 rollout.
- Family distribution is highly imbalanced. `DoS` dominates heavily, `DDoS` is also very large, while `Web-Based` is tiny.
- Some scenario coverage is too sparse for a credible first scenario-classifier rollout. `Web-Based` scenarios are split across single files and are not a stable closed-set scenario target.

### Runtime / UI Constraints

- `ids/runtime/inference.py` assumes `predict_proba(... )[:, 1]` and emits only binary outputs.
- `ids/runtime/realtime_pipeline.py` writes flat JSONL events with `attack_score`, `predicted_label`, `is_alert`, and `threshold`.
- `ids/console/templates/alerts.html` renders only event id, severity, source/destination, protocol, status, and time. There is no family column yet.
- `ids/console/db.py` stores queryable alert columns plus a full `payload_json` blob. That means stage-2 values can be persisted immediately without an invasive schema expansion, while indexed columns can be added later if justified.

### Build / Quality Requirements

The repo pattern implies the multiclass lane must ship with:

```powershell
pytest
python -m scripts.<new_or_changed_wrapper> --help
```

Plus focused offline proofs for:

- derived artifact manifests and split counts
- bundle contract validation
- runtime replay showing additive family fields

---

## Agent D: External Research

> Guided by locked decisions in CONTEXT.md

No external library or novel infrastructure is required for the first planning pass. The codebase already has the core building blocks needed for a first two-stage tabular implementation, so planning should stay grounded in local contracts and dataset reality instead of adding new dependencies.

---

## Open Questions

> Items that were not fully settled by research alone.

- [ ] Whether the optional family-enrichment metadata should fit inside the existing bundle manifest version `2` or require a manifest version bump while keeping the primary binary inference fields stable.
- [ ] Whether stage-2 abstention should be calibrated by top-1 confidence only, confidence-plus-margin, or a dedicated OOD heuristic using the validation and OOD holdout sets.
- [ ] Whether the alerts list should show family fields in the first UI slice, or whether alert detail should land first and the table column follow after operator feedback.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a frozen binary dataset artifact, a strong binary CatBoost production lane, a fail-closed model-bundle contract, and an operator/runtime path that already handles additive prediction payloads.

**What we need**: a derived family-view artifact, a stage-2 multiclass family classifier with unknown/abstain behavior, and one promoted two-stage deployment contract that enriches live alerts without breaking the current binary gate.

**Key constraints from research**:
- `BruteForce` and `Recon` must remain OOD unknown-family probes in the first rollout.
- The production runtime cannot regress from one activation contract into split model/schema/threshold wiring.
- Severe family imbalance means stage-2 evaluation has to report both closed-set quality and unknown-handling behavior.

**Institutional warnings to honor**:
- Do not split stage 1 and stage 2 into separate production overrides.
- Do not create new wrapper seams without smoke coverage.
- Do not rely on shutdown-only or summary-only publication for new family fields.
