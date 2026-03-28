# IDS Structured Record Adapter - Context

**Feature slug:** ids-structured-record-adapter
**Date:** 2026-03-27
**Exploring session:** complete
**Scope:** Standard

---

## Feature Boundary

This feature defines the v1 adapter that sits between upstream structured flow records and the existing IDS realtime runtime. It accepts CICFlowMeter-like upstream records, applies explicit profile-based field mapping and numeric coercion, emits a 72-feature model-ready record plus controlled passthrough metadata, and sends unmappable records to a separate adapter-stage quarantine stream.

This feature does **not** implement raw `PCAP` or live packet capture, packet-to-flow assembly, flow timeout/sessionization logic, or a generic multi-source mapping framework.

**Domain type(s):** RUN | CALL | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Scope Boundary
- **D1** The current feature covers only the `structured record adapter`. Raw `PCAP/live packet -> flow extractor` is a separate future feature and is out of scope here.
  *Rationale: Combining adapter work with packet processing would create two independent subsystems in one session and blur the planning/execution boundary.*

### Upstream Source Shape
- **D2** Adapter v1 targets `one primary upstream format plus one similar secondary profile` to demonstrate extensibility. It does not attempt generic free-form mapping across arbitrary sources.
  *Rationale: v1 should prove one strong path without over-generalizing the contract layer.*

- **D3** The upstream schema family is `CICFlowMeter-like structured records`.
  *Rationale: This keeps deploy-time semantics as close as possible to the flow-statistics semantics used during training.*

### Transformation Rules
- **D4** Adapter v1 performs only `field mapping / rename / numeric coercion / validation`. It does not derive new features and does not impute or default missing model features.
  *Rationale: The adapter must not invent feature semantics that were not present in the upstream record.*

- **D5** Adapter v1 outputs a direct `72-feature structured flow record` that can feed the existing realtime runtime without another schema translation layer.
  *Rationale: The adapter boundary should end at the actual model-facing contract, not an intermediate schema.*

### Error Handling
- **D6** If an upstream record cannot be mapped cleanly into the adapter output contract, the adapter emits that record to a separate `quarantine/error stream` while valid records continue flowing.
  *Rationale: This preserves forensic visibility without failing the full process or silently dropping suspicious records.*

### Metadata Handling
- **D7** Adapter output keeps `fixed metadata plus a controlled extra bag`; it does not preserve the full upstream record in the normal adapted output.
  *Rationale: The output should remain traceable without turning into the original source record disguised as model input.*

### Profile Selection
- **D8** The adapter profile is selected explicitly by the caller, for example via `--profile`; there is no auto-detection in v1.
  *Rationale: Auto-detection creates avoidable ambiguity and hidden mis-mapping risk at the contract boundary.*

### Runtime Interface
- **D9** The adapter CLI supports both `stdin/stdout` and file-path-based I/O.
  *Rationale: This keeps the adapter usable in streaming pipelines while still supporting local demos and batch dry-runs.*

### Extensibility Proof
- **D10** The secondary profile differs from the primary profile in `field names and some metadata-envelope fields` such as timestamps, source IDs, or flow IDs, while preserving the same CICFlowMeter-like semantics.
  *Rationale: v1 should demonstrate limited extensibility without widening into semantic translation between different flow systems.*

### Quarantine Contract
- **D11** Adapter errors use an `adapter-specific quarantine schema` with shared minimum fields such as `reason`, `record_index`, `profile`, and `source_record`.
  *Rationale: Downstream systems need common observability fields, but adapter-stage failures should still be distinguishable from runtime-stage schema anomalies.*

### Agent's Discretion
- The planner/implementer may choose the exact names and file layout for the primary and secondary profiles as long as both remain CICFlowMeter-like and differ only in field naming/envelope metadata, not in feature semantics.
- The planner/implementer may choose the exact fixed passthrough metadata keys as long as they remain minimal, stable, and useful for tracing records through adapter and inference stages.
- The planner/implementer may choose the exact adapter CLI flags and output sink layout as long as the adapter remains usable in both pipeline-style streaming and local file-based dry-runs.

---

## Specific Ideas & References

- User intent: move from the already-built realtime runtime to the next upstream layer that normalizes structured flow records before they hit the model-facing pipeline.
- Clarified adapter role: this component does not replace the runtime; it produces inputs that [ids_realtime_pipeline.py](F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py) can consume.
- Explicit scope split: packet capture / flow assembly remains a separate future work item after this adapter.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `F:/Work/IDS_ML_New/scripts/ids_feature_contract.py` - current strict contract layer for the frozen 72-feature model schema, including alias mapping, numeric coercion, passthrough handling, and quarantine results.
- `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` - current runtime entrypoint that consumes structured JSONL records, validates/quarantines records, micro-batches valid inputs, and emits model/quarantine outputs.
- `F:/Work/IDS_ML_New/scripts/ids_inference.py` - reusable inferencer and bundle loading path for the finalized CatBoost model.
- `F:/Work/IDS_ML_New/docs/ids_realtime_pipeline_architecture.md` - current documented boundary for `structured flow record -> runtime -> model`.

### Established Patterns
- Strict schema boundary already exists in `ids_feature_contract.py`: missing or non-numeric required features are quarantined, not guessed.
- The runtime already expects JSONL-friendly records and supports both `stdin` and file-path execution; the adapter should match that operational shape.
- Current quarantine behavior separates malformed records from valid scoring flow. The adapter should preserve that pattern one stage earlier.

### Integration Points
- `F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1/feature_columns.json` - canonical 72-feature output target for the adapter.
- `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` - immediate downstream consumer for adapted records.
- `F:/Work/IDS_ML_New/scripts/ids_feature_contract.py` - reference for canonical field names and safe one-to-one aliasing patterns.
- `F:/Work/IDS_ML_New/docs/ids_inference_architecture.md` - current explanation of the model-facing runtime boundary that the adapter must feed cleanly.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `F:/Work/IDS_ML_New/history/ids-pre-model-realtime-pipeline/CONTEXT.md` - prior feature context that locked the runtime boundary, quarantine behavior, and flow-record input assumptions.
- `F:/Work/IDS_ML_New/docs/ids_realtime_pipeline_architecture.md` - current runtime architecture and JSONL input/output behavior.
- `F:/Work/IDS_ML_New/scripts/ids_feature_contract.py` - current model-facing schema contract and alias constraints.
- `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` - current downstream runtime implementation.
- `F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1/feature_columns.json` - exact target feature schema.

---

## Outstanding Questions

### Deferred to Planning
- [ ] What exact field list defines the primary CICFlowMeter-like upstream profile? Planning should choose a concrete sample shape for v1.
- [ ] What exact differences define the secondary profile beyond metadata-envelope fields? Planning should keep the difference narrow and explicit.
- [ ] What exact fixed passthrough metadata keys should be standardized in the adapted output? Planning should keep them minimal and stable.
- [ ] What exact adapter-specific quarantine schema should be emitted on the error stream beyond the minimum shared fields locked in D11?
- [ ] Should the adapter live as a new standalone script or as a reusable module plus script wrapper under `scripts/`? Planning should choose the concrete file layout.

### Deferred Ideas
- Add raw `PCAP/live packet` ingestion and flow assembly in this same component - deferred because it is a separate subsystem.
- Build a generic multi-source profile/config framework - deferred because v1 is intentionally limited to one primary format plus one nearby profile.
- Auto-detect adapter profiles from source payload shape - deferred because v1 requires explicit profile selection.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1-D11) are stable. Reference them by ID in all downstream artifacts.
