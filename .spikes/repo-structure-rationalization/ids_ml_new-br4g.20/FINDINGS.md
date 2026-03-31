# Spike Findings: ids_ml_new-br4g.20

## Question
What runtime migration sequence keeps live sensor, inference, bridge, adapter, and extractor entrypoints stable while code moves behind `ids.runtime`?

## Evidence
- `scripts/ids_live_sensor.py` is the composition root. It imports `FlowFeatureContract`, `IDSInferencer`, `LiveFlowBridge`, `RollingDumpcapCaptureManager`, `LiveSensorLocalSink`, and `RealtimePipelineRunner`, then wires them into `LiveSensorDaemon`.
- `tests/test_ids_live_sensor.py` locks the external surface: the daemon must keep activation-path wiring, and the service unit must continue to reference `ids_live_sensor_preflight.py`, `--interface`, `--dumpcap-binary`, `--extractor-command-prefix`, and `--activation-path`.
- `scripts/ids_realtime_pipeline.py` depends on `FlowFeatureContract` and `IDSInferencer` only, and `tests/test_ids_realtime_pipeline.py` locks CLI help, stdin/file behavior, and flush timing.
- `scripts/ids_inference.py` is a standalone CLI/runtime boundary for bundle loading and scoring, and `tests/test_ids_inference.py` locks bundle/config resolution plus CLI output shape.
- `scripts/ids_live_flow_bridge.py` depends on `ClosedCaptureWindow` and `adapt_record`; `tests/test_ids_live_flow_bridge.py` proves it must keep the extractor command shape and the `*_Flow.csv` bridge contract.
- `scripts/ids_offline_window_extractor.py` and `scripts/ids_offline_window_serializer.py` form the extractor side of that same contract; `tests/test_ids_offline_window_extractor.py` verifies the CSV is bridge-consumable and adapter-consumable.
- `scripts/ids_record_adapter.py` is the normalization seam between extractor output and runtime features; `tests/test_ids_record_adapter.py` locks explicit profile selection, quarantine behavior, and streaming/file-mode behavior.
- `scripts/ids_live_capture.py` and `scripts/ids_live_sensor_sinks.py` are leaf support modules. Their tests only validate local contracts and do not require early composition-root changes.

## Decision
YES. This migration is safe if the repo keeps `scripts.*` entrypoints as thin compatibility wrappers in phase 1 and moves implementation in dependency order.

## Recommended migration order
1. Move shared contracts out of the runtime path first: `ids_feature_contract` and `ids_model_bundle` belong in `ids.core`, not in `ids.runtime`.
2. Move `ids_inference` and `ids_realtime_pipeline` together behind `ids.runtime`. They are one scoring slice: realtime pipeline depends on the inferencer API and the `FlowFeatureContract` contract.
3. Move `ids_record_adapter`, `ids_offline_window_serializer`, and `ids_offline_window_extractor` together behind `ids.runtime`. This is one extractor/adapter slice with one CSV contract.
4. Move `ids_live_flow_bridge` after the extractor/adapter slice is settled. It consumes the extractor command output and the adapter profile contract.
5. Move `ids_live_capture` and `ids_live_sensor_sinks` after the bridge slice. They are leaf support modules, but live sensor should not be rewritten until they already exist behind the new package.
6. Move `ids_live_sensor` last. It is the composition root, so it should become a thin wrapper over `ids.runtime` only after every dependency it wires has already moved.

## Coupling constraints
- `ids_inference` and `ids_realtime_pipeline` must move together or in the same bead. Splitting them creates a temporary import gap because the pipeline is built around `IDSInferencer.predict()`.
- `ids_record_adapter`, `ids_offline_window_serializer`, and `ids_offline_window_extractor` must move together. The extractor emits the source rows the adapter consumes, and the serializer defines the exact CSV shape the bridge expects.
- `ids_live_flow_bridge` must not move before the adapter/extractor slice. Its tests hard-code the `*_Flow.csv` handoff and the adapter quarantine behavior.
- `ids_live_sensor` must remain the final move in this runtime wave. It is the only module that depends on every other runtime component and on the active bundle activation contract.
- `FlowFeatureContract` and model-bundle activation logic are prerequisite shared contracts, not runtime internals. They should not be buried inside `ids.runtime`.
- Phase 1 must preserve `python -m scripts.*` and direct service entrypoints unchanged. Any module move without a wrapper is a contract break.

## Recommended rules to embed into affected beads
- Keep every current `scripts.*` CLI and systemd entrypoint stable in phase 1; move code behind wrappers only.
- Treat `ids_live_sensor` as the last runtime bead, not a starting point.
- Group `ids_live_flow_bridge`, `ids_record_adapter`, and `ids_offline_window_extractor` into one dependency chain bead set; do not split the CSV contract across separate moves.
- Keep `ids_live_capture` and `ids_live_sensor_sinks` as leaf-support beads with no CLI signature changes.
- Add or preserve tests that assert CLI help, runtime wrapper args, bridge CSV shape, and service-unit command lines before and after each move.
- Do not place shared contracts into `ids.runtime`; reserve that package for runtime implementation only.
