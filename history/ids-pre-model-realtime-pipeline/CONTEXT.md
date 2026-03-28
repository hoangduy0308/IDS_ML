# IDS Pre-Model Realtime Pipeline — Context

**Feature slug:** ids-pre-model-realtime-pipeline
**Date:** 2026-03-27
**Exploring session:** complete
**Scope:** Standard

---

## Feature Boundary

This feature defines the v1 IDS path from realtime structured flow events into validated 72-feature model input, micro-batch inference, and alert/quarantine outputs; it does not implement raw packet sniffing or replace the upstream flow extractor.

**Domain type(s):** RUN | CALL | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Ingest Boundary
- **D1** The canonical model input for IDS v1 is `flow records`, not raw `PCAP` packets and not free-form network logs.
  *Rationale: The finalized model was trained on flow-based features, and the frozen `72`-column schema already matches CICFlowMeter-style flow statistics rather than packets or text logs.*

- **D2** IDS v1 will be a service that receives realtime `structured flow records` from an upstream collector/extractor; this service does not sniff raw packets itself.
  *Rationale: Separating `collector/flow extraction` from `inference service` keeps the deployment contract simple, reduces train/deploy feature drift, and avoids turning this work into both a packet-processing project and an inference project at the same time.*

### Runtime Behavior
- **D3** IDS v1 will process realtime input using `micro-batches`, and emit alerts immediately after each short batch completes rather than waiting for large offline batches.
  *Rationale: This preserves near-realtime behavior while fitting the current DataFrame/batch-oriented inference code and gives better throughput/backpressure behavior than one-record-at-a-time scoring.*

### Schema Failure Handling
- **D4** If an incoming realtime record cannot be aligned cleanly to the exact `72`-feature schema, it must not be passed to the model; instead it is quarantined and produces a separate schema/pipeline anomaly alert while the rest of the batch continues.
  *Rationale: Silent dropping creates an evasion path, while forcing malformed rows into the model would corrupt inference. Record-level quarantine preserves service continuity without hiding suspicious ingest failures.*

### Agent's Discretion
- The planner/implementer may choose the concrete transport and envelope for realtime `structured flow records` as long as the payload can be validated against the exact `72`-feature contract before inference.
- The planner/implementer may choose the concrete micro-batch trigger policy (`batch size`, `flush interval`, or both) as long as it remains near-realtime and does not depend on large offline files.

---

## Specific Ideas & References

- User intent: build the next stage of the IDS around the already-finalized model, focusing on the layer before the model rather than reopening dataset/model selection.
- User phrasing: wants something that can “nhận thông tin”, turn it into structured records in realtime, and push those records into the model immediately.
- Clarified interpretation: “log realtime” for this feature means a realtime stream of `structured flow events/records`, not free-form log text.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `F:/Work/IDS_ML_New/scripts/ids_inference.py` — current inference entry point; loads the model bundle, loads feature columns, aligns inputs to the frozen schema, coerces numeric types, runs `predict_proba`, and emits `attack_score`, `predicted_label`, `is_alert`, and `threshold`.
- `F:/Work/IDS_ML_New/scripts/package_final_model.py` — packages the finalized model bundle and records the selected threshold, labels, and feature count. This is the existing source of truth for bundle-level metadata.
- `F:/Work/IDS_ML_New/scripts/preprocess_iot_diad.py` — strongest local reference for data hygiene and schema enforcement; it removes leakage columns, sanitizes numeric values, quarantines malformed source files, and writes the frozen `feature_columns.json`.

### Established Patterns
- Exact-schema enforcement: `ids_inference.py` fails fast when required feature columns are missing or non-numeric. The new pre-model layer must preserve this strictness at the schema boundary.
- Quarantine instead of guessing: `preprocess_iot_diad.py` already quarantines malformed dataset files and schema mismatches. IDS v1 should mirror that mindset for malformed realtime records.
- Frozen feature contract: the bundle and manifests both point to the same `72`-feature schema. New work must treat that contract as fixed, not inferred dynamically.

### Integration Points
- `F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1/feature_columns.json` — canonical list of the `72` required model features.
- `F:/Work/IDS_ML_New/artifacts/cic_iot_diad_2024_binary/manifests/feature_columns.json` — training-time frozen schema; currently matches the bundled schema and should be kept consistent.
- `F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1/model_bundle.json` — canonical bundle config including threshold `0.5`, label names, and feature count `72`.
- `F:/Work/IDS_ML_New/CIC-IoT-DIAD-2024/Anomaly Detection - Flow Based features/README.txt` — dataset-local reference that the original features come from CICFlowMeter-style biflow extraction from PCAP.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `F:/Work/IDS_ML_New/docs/final_model_decision.md` — final locked model choice and operating threshold.
- `F:/Work/IDS_ML_New/docs/experiment_progress_checkpoint.md` — current project state and explicit note that the next phase is feature extraction, inference runtime, and IDS integration.
- `F:/Work/IDS_ML_New/docs/ids_inference_architecture.md` — current inference-layer boundaries and the already-documented flow `feature extraction -> schema alignment -> model inference -> alert`.
- `F:/Work/IDS_ML_New/docs/final_model_bundle.md` — current model packaging assumptions and bundle structure.
- `F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1/feature_columns.json` — exact model input contract.
- `F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1/model_bundle.json` — exact threshold/label/bundle metadata.

---

## Outstanding Questions

### Deferred to Planning
- [ ] What exact runtime interface should carry realtime structured flow events into the IDS service? — Planning should choose a practical v1 interface that is easy to demo and test locally without changing the locked ingest boundary.
- [ ] What event envelope should exist around the `72` model features? — Planning should define which non-model fields are kept for tracing, observability, and alert payloads without leaking them into model inference.
- [ ] How should the service emit quarantine records and schema anomaly alerts? — Planning should choose the simplest sink(s) for v1 while preserving forensic visibility for malformed inputs.
- [ ] How should upstream collectors that produce CICFlowMeter-like but not perfectly identical records be adapted to the frozen schema? — Planning should define aliasing/mapping rules that never silently invent missing model features.

---

## Deferred Ideas

- Implement raw `PCAP` sniffing and packet-to-flow extraction inside the IDS service — deferred because it is a separate subsystem and would expand scope far beyond the current pre-model integration layer.
- Accept free-form network log text directly as model input — deferred because the current model contract is flow-feature-based, not text/log-event-based.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2, D3, D4) are stable. Reference them by ID in all downstream artifacts.
