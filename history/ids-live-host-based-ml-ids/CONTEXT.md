# IDS Live Host-Based ML Sensor - Context

**Feature slug:** ids-live-host-based-ml-ids
**Date:** 2026-03-28
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature defines the first live, host-based Linux IDS sensor that continuously captures local network traffic, extracts TCP/UDP flow records, adapts them into the frozen 72-feature contract, runs the existing ML inference path in near-realtime, and writes local alert/quarantine outputs; it does not implement multi-environment deployment, network-mirror sensing, webhook/SIEM delivery, or IPS-style automated response.

**Domain type(s):** RUN | CALL | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Deployment Shape
- **D1** The next IDS feature starts from live traffic immediately, not from `PCAP replay` or an offline-first collector.
  *Rationale: The fastest path to a real IDS is validating the full runtime boundary on actual traffic rather than optimizing around replay fixtures.*

- **D2** v1 targets one concrete Linux host and one explicitly configured network interface.
  *Rationale: Generalizing across environments too early would turn the feature into a deployment framework instead of a working IDS sensor.*

- **D3** v1 must run end-to-end as `live packets -> flow records -> adapter -> realtime ML inference -> alert/quarantine`.
  *Rationale: A machine-learning IDS is not complete if it stops at traffic collection without producing model-driven detection output.*

- **D4** v1 runs as a continuously running sensor process, not as a manual demo/test command.
  *Rationale: The feature is meant to behave like a real monitoring component on the protected host.*

### Failure Handling
- **D5** Malformed records and recoverable per-record issues continue through quarantine/logging, but fatal capture/runtime failures must fail fast and rely on supervisor restart.
  *Rationale: A process that stays alive while capture is broken creates a false sense of protection; fail-fast is safer for infrastructure-level faults.*

### Detection Scope
- **D6** v1 is pure `IDS`, meaning detection plus alert/log output only; `IPS` or automated response is deferred to a later feature.
  *Rationale: Detection and enforcement have different operational risk profiles, and enforcement should not be coupled into the first live ML sensor.*

- **D7** v1 writes alert/quarantine outputs locally via `JSONL` and `journald`; Telegram notifications, webhooks, and SIEM delivery are deferred.
  *Rationale: Local durable outputs are the safest source of truth while the sensor boundary is still being proven on live traffic.*

- **D8** v1 only scores `TCP/UDP flow traffic`; non-flow-friendly traffic classes are outside the model path and should be handled via telemetry/logging rather than forced into inference.
  *Rationale: The trained model and current runtime are flow-feature-based, so widening to all traffic types would risk semantic drift and scope explosion.*

- **D9** v1 is a `host-based` sensor on the Linux machine being protected, not a separate network sensor consuming `SPAN/mirror port` traffic.
  *Rationale: Host-based capture is the simplest path to a working live deployment and avoids introducing distributed network-sensor concerns in the first version.*

- **D10** v1 persists only `positive alerts` and `quarantine events` as full local records; benign predictions are aggregated into counters/telemetry rather than stored as full events by default.
  *Rationale: Persisting all benign predictions would create unnecessary volume and operational noise for a continuously running host sensor.*

### Agent's Discretion
- The planner/implementer may choose the concrete Linux packet-capture and flow-assembly mechanism as long as it preserves the locked host-based, live, single-interface boundary.
- The planner/implementer may choose the exact local file layout, rotation strategy, and journald field structure as long as alert/quarantine outputs remain local-first and operationally inspectable.
- The planner/implementer may choose the exact runtime packaging shape (`single script`, `module + service wrapper`, or similar) as long as it behaves as a continuously running Linux sensor process.

---

## Specific Ideas & References

- User intent: move from the already-built structured-record runtime into a real machine-learning IDS that operates on live host traffic.
- Explicit product direction: finish the IDS first, then extend later toward Telegram notification sinks and eventually IPS behavior.
- Scope discipline matters here because the repo already has the downstream ML pipeline; the missing subsystem is the live host-side capture/flow stage, not another round of model selection.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py` - current adapter that turns CICFlowMeter-like structured records into the runtime-ready 72-feature shape plus adapter quarantine output.
- `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` - current runtime that validates canonical records, micro-batches valid inputs, runs ML inference, and emits alert/quarantine JSONL.
- `F:/Work/IDS_ML_New/scripts/ids_feature_contract.py` - strict frozen-schema contract used by the runtime for alias-safe validation and quarantine behavior.
- `F:/Work/IDS_ML_New/scripts/ids_inference.py` - reusable inferencer and bundled model loading path for the finalized CatBoost classifier.

### Established Patterns
- Strict quarantine over guessing: malformed inputs are quarantined instead of being imputed or silently repaired.
- Local JSONL-first operations: the current runtime and adapter already use JSONL-friendly file/stream boundaries, which is a good fit for local-first v1 sensor outputs.
- Fixed model-facing contract: the 72-feature schema and thresholded CatBoost bundle are treated as frozen deployment contracts, not dynamically inferred runtime metadata.

### Integration Points
- `F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1/feature_columns.json` - canonical model input contract that the live flow-extraction path must ultimately satisfy.
- `F:/Work/IDS_ML_New/history/ids-structured-record-adapter/CONTEXT.md` - latest completed feature that locked the adapter boundary immediately upstream of the runtime.
- `F:/Work/IDS_ML_New/history/ids-pre-model-realtime-pipeline/CONTEXT.md` - prior feature that locked the runtime boundary and near-realtime micro-batch model path.
- `F:/Work/IDS_ML_New/docs/ids_record_adapter_architecture.md` - documents the adapter handoff and clarifies that live packet capture is the next upstream subsystem.
- `F:/Work/IDS_ML_New/docs/ids_realtime_pipeline_architecture.md` - documents the current runtime expectation of structured flow records and the split between model alerts and schema anomalies.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `F:/Work/IDS_ML_New/docs/final_model_decision.md` - final locked model choice and operating threshold for deployment.
- `F:/Work/IDS_ML_New/docs/experiment_progress_checkpoint.md` - project checkpoint showing that the next major step after model/runtime work is IDS system design and deployment integration.
- `F:/Work/IDS_ML_New/docs/ids_inference_architecture.md` - current model-layer responsibilities and the explicit assumption that upstream flow extraction is separate.
- `F:/Work/IDS_ML_New/docs/ids_realtime_pipeline_architecture.md` - current runtime boundary, micro-batch behavior, and alert/quarantine semantics.
- `F:/Work/IDS_ML_New/docs/ids_record_adapter_architecture.md` - current structured-record adapter boundary and output contract.
- `F:/Work/IDS_ML_New/history/ids-structured-record-adapter/CONTEXT.md` - latest locked adapter decisions that this live sensor must feed into, not replace.

---

## Outstanding Questions

### Deferred to Planning
- [ ] What concrete packet-capture and flow-assembly approach best fits a single Linux host while keeping feature semantics as close as possible to the CICFlowMeter-like training contract? - Planning should compare realistic implementation options without violating the locked v1 boundary.
- [ ] How should TCP/UDP flows be keyed, timed out, and flushed into structured records for near-realtime inference? - Planning should choose a flow-lifecycle strategy that balances semantic fidelity with a continuously running sensor process.
- [ ] Should the live sensor emit raw extracted flow records into an intermediate local sink before adaptation, or compose extraction directly into the adapter/runtime pipeline? - Planning should decide the safest observability boundary for v1.
- [ ] What Linux service packaging should own restart policy, permissions, and configuration (`systemd`, capability setup, log rotation, path layout)? - Planning should define the operational envelope for a continuously running host sensor.
- [ ] What counters and periodic summaries should be written for benign traffic, skipped non-TCP/UDP traffic, and fatal restart reasons? - Planning should define the minimal telemetry set needed for operations without persisting every benign prediction.

---

## Deferred Ideas

- Telegram notification delivery - deferred because the first live sensor should prove local detection durability before adding best-effort outbound notifications.
- Webhook/SIEM alert shipping - deferred because transport/integration is a separate subsystem from core sensor detection.
- Multi-host or multi-environment collector abstraction - deferred because v1 is intentionally constrained to one Linux host and one configured NIC.
- `SPAN/mirror port` network sensing - deferred because the first deployment target is host-based rather than a separate network sensor.
- IPS or automated blocking/response - deferred because v1 is detection-only.
- Full all-protocol coverage beyond TCP/UDP flow traffic - deferred because the deployed model contract is flow-based and should not be stretched across incompatible traffic classes in v1.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
