# Spike Findings: ids_ml_new-s80

## Question

Can explicit CICFlowMeter-like profiles normalize safely without inventing features?

## Result

**YES**

## What was tested

- Reused the frozen `72`-feature schema from `artifacts/final_model/catboost_full_data_v1/feature_columns.json`
- Constructed an explicit one-to-one alias map using the same short-form naming precedent already present in `scripts/ids_feature_contract.py`
- Validated one synthetic record where several canonical keys were replaced by CICFlowMeter-like short-form aliases
- Validated a second record with one required mapped feature missing

## Evidence

Observed result from the spike check:

```json
{"valid_type":"ValidatedFlowRecord","missing_type":"QuarantinedFlowRecord","missing_reason":"missing_required_features","passthrough_keys":["collector_id"],"renamed_fields_used":["DstPort","FlowDuration","Init Bwd Win Byts","Init Fwd Win Byts","Pkt Len Max"],"feature_count":72}
```

This proves the key property needed for the adapter plan:
- explicit one-to-one profile mappings can normalize renamed upstream fields into the frozen schema
- passthrough metadata remains outside model features
- missing fields still fail closed into quarantine instead of being invented

## Constraints learned

- The primary profile must contain real CICFlowMeter-like naming differences; it cannot just mirror canonical feature names or the adapter will not be meaningfully exercised.
- Profile maps must remain explicit and one-to-one. No derived features, no many-to-one semantic rewrites, no default filling.
- Final acceptance should still go through `FlowFeatureContract` so the adapter does not fork the model contract.

## Implication for plan

Keep `ids_ml_new-f4w.1` and `ids_ml_new-f4w.2` exactly on the current path:
- profile registry first
- final canonical validation delegated to `FlowFeatureContract`
