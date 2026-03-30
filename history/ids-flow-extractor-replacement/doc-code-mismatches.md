# Doc vs Code Mismatches

Per locked decision `D4`, the entries below treat code and tests as the source of truth when prose and executable behavior diverge.

## Mismatch Log

| Topic | Docs say | Code and tests say | Source-of-truth call |
|------|----------|--------------------|----------------------|
| Bridge output framing | `docs/ids_live_sensor_architecture.md` describes the bridge as producing "CICFlowMeter-compatible flow records". | The bridge only enforces a configurable command prefix, a per-window CSV output path, a readable CSV header, and successful adapter handoff. No code or test asserts broader CICFlowMeter brand fidelity. | Treat `scripts/ids_live_flow_bridge.py` and `tests/test_ids_live_flow_bridge.py` as the contract. |
| Preflight validation depth | `docs/ids_live_sensor_operations.md` says startup verifies `dumpcap`, Java, and the CICFlowMeter wrapper are "installed and runnable". | `validate_preflight()` checks absolute-path existence, executable bits, activation-record resolution, and writable destinations. It does not execute Java or the extractor wrapper as a smoke step. | Treat `scripts/ids_live_sensor_preflight.py` and `tests/test_ids_live_sensor_preflight.py` as the actual preflight scope. |
| Adapter profile explicitness across the whole live path | `docs/ids_record_adapter_architecture.md` says profile selection is explicit and there is no silent default profile. | That is true for the adapter API and CLI, but the live bridge and live sensor wrap the adapter with a default `cicflowmeter_primary_v1` profile unless callers override it. | Treat adapter explicitness as true inside `scripts/ids_record_adapter.py`, but note the repo-level live path defaults in `scripts/ids_live_flow_bridge.py` and `scripts/ids_live_sensor.py`. |
| Hard runtime boundary vs packaging boundary | The live-sensor docs present Java, the CICFlowMeter wrapper, and `jnetpcap` as part of the sensor's required runtime pieces. | The model-serving hard stop is narrower: records must satisfy `FlowFeatureContract`, and live runtime must resolve the active bundle contract. Java and `jnetpcap` are currently enforced in preflight and stack packaging, not in the scoring boundary itself. | Treat `scripts/ids_feature_contract.py`, `scripts/ids_realtime_pipeline.py`, `scripts/ids_live_sensor.py`, and the related tests as the hard runtime contract. |
| Writable output wording | `docs/ids_live_sensor_operations.md` says "the spool and log directories are writable". | Preflight checks one writable `spool_dir` plus writable parent directories for `alerts_output_path`, `quarantine_output_path`, and `summary_output_path`. The outputs do not have to share one log root. | Treat `scripts/ids_live_sensor_preflight.py` as the exact path contract. |

## Planning Implications

- Do not assume a replacement extractor must impersonate CICFlowMeter beyond the shell points the bridge and tests actually enforce.
- Do not assume preflight already proves extractor executability beyond path and permission checks.
- Do not treat adapter-profile explicitness as globally true across the live path until bridge defaults are addressed deliberately.
- Keep the distinction between packaging dependencies and the model-facing runtime boundary explicit in later planning and implementation beads.
