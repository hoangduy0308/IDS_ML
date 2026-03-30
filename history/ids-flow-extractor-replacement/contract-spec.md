# Extractor Contract

## Scope

This artifact defines the exact current extractor contract for `ids-flow-extractor-replacement` from repo evidence.

Per `D4`, code and tests win when docs are broader than the executable surface.

## Current Contract

| Contract layer | Current requirement | Source of truth |
|---|---|---|
| Input boundary | The extractor consumes a closed `pcap` window produced by the live capture manager. It is not wired directly to the live NIC stream. | `scripts/ids_live_sensor.py`, `tests/test_ids_live_sensor.py`, `docs/ids_live_sensor_architecture.md` |
| Invocation shape | The bridge runs `extractor_command_prefix + <pcap-path> + <output-dir>`. The prefix is configurable, but the current default is `Cmd`. | `scripts/ids_live_flow_bridge.py`, `tests/test_ids_live_flow_bridge.py`, `history/ids-flow-extractor-replacement/dependency-map.md` |
| Output file discovery | The bridge currently discovers one CSV at `<window-stem>_Flow.csv`. Missing output or invalid CSV is a window-stage failure. | `scripts/ids_live_flow_bridge.py`, `tests/test_ids_live_flow_bridge.py` |
| Row transport format | The bridge requires a CSV header row readable by `csv.DictReader` and hands each row to the adapter one record at a time. | `scripts/ids_live_flow_bridge.py`, `tests/test_ids_live_flow_bridge.py` |
| Adapter profile boundary | The live path currently defaults to `cicflowmeter_primary_v1`. The adapter itself remains explicit-profile-only and rejects unknown or hybrid payloads. | `scripts/ids_live_flow_bridge.py`, `scripts/ids_record_adapter.py`, `tests/test_ids_record_adapter.py` |
| Accepted upstream record surface | A record is accepted only if its keys belong to the selected profile's declared feature aliases, metadata aliases, or controlled extras. Unmapped or colliding fields quarantine. | `scripts/ids_record_adapter.py`, `tests/test_ids_record_adapter.py` |
| Adapted output shape | Successful adaptation emits one flat record containing all 72 canonical features plus `adapter_profile`, normalized source metadata, and controlled extras. | `scripts/ids_record_adapter.py`, `docs/ids_record_adapter_architecture.md`, `tests/test_ids_record_adapter.py` |
| Model-facing runtime contract | `FlowFeatureContract` requires the exact 72 bundle feature names with numeric coercion. Missing values, non-numeric values, and alias collisions quarantine before scoring. | `artifacts/final_model/catboost_full_data_v1/feature_columns.json`, `scripts/ids_feature_contract.py`, `scripts/ids_realtime_pipeline.py` |
| Bundle activation contract | Live runtime resolves the model artifact and feature schema through the activation record. Extractor work must not introduce independent model/schema/threshold overrides. | `scripts/ids_live_sensor.py`, `scripts/ids_model_bundle.py`, `docs/ids_live_sensor_operations.md`, `tests/test_ids_live_sensor.py` |
| Live deployment contract | Current live startup still requires exact helper paths for `dumpcap`, `java`, extractor binary, `jnetpcap`, activation record, and writable output roots. | `scripts/ids_live_sensor_preflight.py`, `docs/ids_live_sensor_operations.md`, `docs/ids_same_host_stack_operations.md`, `tests/test_ids_live_sensor_preflight.py`, `tests/test_ids_same_host_stack_manage.py` |

## The Hard Production Boundary

The strongest production contract today is:

1. closed-window `pcap` input
2. extractor output discoverable by the bridge
3. explicit adapter profile normalization
4. exact 72 canonical numeric features from `feature_columns.json`
5. active-bundle model/schema/threshold resolution

Anything that weakens steps 3 to 5 is a production contract change, not a compatibility tweak.

## Failure Contract

The current repo already defines stable failure categories that replacement work must preserve or replace explicitly:

- extractor process failure -> `window_stage_error` at stage `extractor`
- extractor runner exception -> `window_stage_error` at stage `extractor`
- missing output file -> `window_stage_error` at stage `output`
- invalid CSV/header -> `window_stage_error` at stage `output`
- unknown adapter profile -> `window_stage_error` at stage `adapter`
- bad row shape or values -> `adapter_quarantine`
- missing/non-numeric model features -> runtime quarantine before scoring

These categories matter because later beads and spikes must preserve observability while changing the extractor seam.

## Existing Golden Evidence

The repo already contains the strongest current evidence set for this contract:

- `tests/test_ids_live_flow_bridge.py` for bridge command, output, and failure behavior
- `tests/test_ids_record_adapter.py` for explicit profile surfaces and quarantine rules
- `tests/test_ids_live_sensor.py` for staged live composition and activation-record runtime wiring
- `tests/test_ids_live_sensor_preflight.py` for exact-path live startup gating
- `artifacts/demo/ids_record_adapter_primary_sample.jsonl` as a representative current primary-profile row

These are the right references for later implementation and validating spikes. No new production contract should be invented without reconciling against them first.

## Out Of Contract

The following are not the deepest model-facing invariants even though they are live-path facts today:

- literal `Cmd` naming
- literal `_Flow.csv` naming
- CICFlowMeter branding language
- Java and `jnetpcap` as permanent requirements

Those remain current deployment facts, but they live above the model-facing contract and can only change through explicit bridge/preflight migration work.
