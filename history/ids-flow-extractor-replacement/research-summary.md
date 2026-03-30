# Research Summary

## Scope

This note records what the repo currently expects from the flow-extractor layer for `ids-flow-extractor-replacement`.

Per locked decision `D4`, code and tests are treated as the source of truth when docs drift.

## Core Finding

The repo does not actually depend on CICFlowMeter branding as the model-serving contract. The hard contract is a staged pipeline:

1. produce a closed `pcap` window
2. invoke an extractor command on that window
3. load one CSV output from the extractor
4. adapt each row into the canonical runtime record shape
5. validate all 72 canonical numeric features before scoring
6. load model/schema/threshold through the active bundle activation contract

The current live deployment still packages that pipeline around a CICFlowMeter-like shell, but the strongest enforced boundary is the adapter/runtime/model contract, not the legacy tool name.

## Current Extractor Contract

| Layer | Repo expectation now | Evidence |
|------|-----------------------|----------|
| Closed-window input | The extractor runs on a closed `pcap` window, not directly on the live NIC stream. | `docs/ids_live_sensor_architecture.md`, `scripts/ids_live_sensor.py`, `tests/test_ids_live_sensor.py` |
| Process invocation | The bridge builds `extractor_command_prefix + <pcap-path> + <output-dir>`. The prefix is configurable, but defaults to `Cmd`. | `scripts/ids_live_flow_bridge.py`, `tests/test_ids_live_flow_bridge.py` |
| Output discovery | The bridge expects one CSV at `<window-stem>_Flow.csv` by default. Missing or invalid output becomes a `window_stage_error`. | `scripts/ids_live_flow_bridge.py`, `tests/test_ids_live_flow_bridge.py` |
| Row format | The bridge only requires a CSV header row readable by `csv.DictReader`, then hands each row to the adapter. | `scripts/ids_live_flow_bridge.py`, `tests/test_ids_live_flow_bridge.py` |
| Adapter handoff | The default live path uses adapter profile `cicflowmeter_primary_v1`. Bad rows are quarantined; unknown profiles become adapter-stage window errors. | `scripts/ids_live_flow_bridge.py`, `tests/test_ids_live_flow_bridge.py`, `tests/test_ids_record_adapter.py` |
| Adapted record shape | Successful adaptation must yield the 72 canonical feature columns plus adapter-owned metadata such as `adapter_profile`, `source_flow_id`, `source_collector_id`, and `source_timestamp`. | `docs/ids_record_adapter_architecture.md`, `scripts/ids_record_adapter.py`, `tests/test_ids_record_adapter.py` |
| Runtime scoring boundary | The runtime validates every required feature, rejects missing or non-numeric fields, and only scores records that pass `FlowFeatureContract`. There is no runtime imputation path. | `scripts/ids_feature_contract.py`, `scripts/ids_realtime_pipeline.py`, `docs/ids_record_adapter_architecture.md` |
| Bundle activation boundary | Live runtime wiring resolves model artifact and feature schema through the activation record, not through extractor-specific overrides. | `scripts/ids_live_sensor.py`, `scripts/ids_model_bundle.py`, `tests/test_ids_live_sensor.py`, `docs/ids_live_sensor_operations.md` |
| Live deployment gate | Current same-host live deployment still enforces exact helper paths for `dumpcap`, `java`, extractor binary, `jnetpcap`, activation record, and writable output roots before startup. | `docs/ids_live_sensor_operations.md`, `scripts/ids_live_sensor_preflight.py`, `tests/test_ids_live_sensor_preflight.py`, `docs/ids_same_host_stack_operations.md` |

## What The Extractor Must Preserve

### Must-have now

- Accept closed-window `pcap` input and produce deterministic per-window output.
- Produce rows that can be adapted into the 72 canonical numeric features required by the active bundle.
- Preserve the staged seam `capture -> extractor -> adapter -> realtime pipeline -> sink`.
- Keep model bundle selection on the activation-record contract.

### Adapter-recoverable or configurable

- The exact process prefix is configurable even though `Cmd` is the current default.
- The exact adapter profile can change if the bridge config changes and a matching explicit profile exists.
- Legacy field spelling differences can be absorbed by the adapter profile layer when they are explicitly declared.

### Current packaging residue, not the strongest model boundary

- Java requirement
- `jnetpcap` requirement
- CICFlowMeter command-wrapper naming
- `_Flow.csv` naming convention

Those are live-path facts today, but the repo enforces them above the model-serving boundary, mainly in bridge defaults, preflight, systemd wiring, and same-host stack orchestration.

## Practical Reading Of The Contract

For later implementation beads, the safest interpretation is:

- Do not redesign the runtime or model bundle boundary.
- Treat the bridge shell and preflight package surface as changeable only after the extractor still feeds the adapter/runtime contract correctly.
- Use docs as orientation, but let code and tests decide what is actually enforced today.
