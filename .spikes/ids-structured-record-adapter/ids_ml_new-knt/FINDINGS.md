# Spike Findings: ids_ml_new-knt

## Question

Can adapter output feed `ids_realtime_pipeline.py` directly without extra translation?

## Result

**YES**

## What was tested

- Created one synthetic record with all `72` canonical feature names plus passthrough metadata (`adapter_profile`, `flow_id`)
- Fed that record directly into `run_pipeline_stream()` using the existing `RealtimePipelineRunner` and `FlowFeatureContract`
- Used a dummy inferencer to isolate the question to runtime compatibility, not model behavior

## Evidence

Observed result from the spike check:

```json
{"summary":{"input_mode":"stdin","total_records":1,"valid_records":1,"quarantined_records":0,"schema_anomaly_records":0,"alert_records":1,"batch_flushes":1},"alert_count":1,"quarantine_count":0,"alert_passthrough":{"adapter_profile":"primary","flow_id":"flow-1"}}
```

This proves the downstream handoff assumption:
- a direct `72`-feature adapted record is already consumable by the runtime
- non-feature metadata survives as passthrough
- no intermediate schema or additional translation layer is required

## Constraints learned

- Adapted output should stay flat at the feature boundary; metadata can remain as extra top-level keys that the runtime strips into `passthrough`.
- The adapter must not emit a nested intermediate payload if the goal is direct composition with the current runtime.
- End-to-end verification in execution should include at least one adapter-to-runtime dry-run, not only unit tests.

## Implication for plan

Keep `ids_ml_new-f4w.3` and `ids_ml_new-f4w.4` on the current path:
- CLI handoff should emit runtime-ready JSONL
- tests should include at least one direct adapter -> runtime compatibility path
