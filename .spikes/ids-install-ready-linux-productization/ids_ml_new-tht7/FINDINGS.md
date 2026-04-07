# Spike Findings: ids_ml_new-tht7

**Feature**: `ids-install-ready-linux-productization`
**Phase**: `Phase 1 - Make Install Modes And Host Config Real`
**Question**: Does the replanned Phase 1 now contain the live-sensor startup blocker cleanly enough to execute, with Story 2 owning the exact `EnvironmentFile` + direct startup seam and Story 3 owning one exact packaged replacement-extractor helper path?
**Result**: `YES`
**Validated at**: `2026-04-05T23:26:00+07:00`

## Why

The prior blocker was not that the repo lacked the needed runtime primitives; it was that the old phase shape treated the env file and extractor default as if they were enough on their own while the deployed service still depended on hardcoded `Environment=` values and `bash -lc`. The replanned Phase 1 now isolates that exact risk in Story 2 and narrows Story 3 to one exact helper-path default on top of the hardened seam.

The current codebase already supports the core runtime contract once arguments are explicit:

- `ids/ops/live_sensor_preflight.py` accepts `--extractor-command-prefix` and validates the executable first token.
- `ids/runtime/live_sensor.py` carries `extractor_command_prefix` into `LiveFlowBridge`.
- `ids/runtime/live_flow_bridge.py` appends `<pcap-path>` and `<output-dir>` to the configured prefix, so one exact helper executable is a natural steady-state contract.
- `ids/ops/same_host_stack.py` already has env-file parsing and a validated preflight builder pattern for host-owned config.

That means the remaining work is concentrated in the files already owned by Phase 1 beads:

- `deploy/systemd/ids-live-sensor.service`
- `ops/install.sh`
- new `ops/ids-live-sensor.env.example`
- `ids/ops/live_sensor_preflight.py`
- `ids/runtime/live_sensor.py`
- `ids/ops/same_host_stack.py`
- `tests/ops/*`
- `tests/runtime/*`

No hidden Phase 2 dependency is required to make this seam exact.

## Evidence

- `deploy/systemd/ids-live-sensor.service` still hardcodes critical runtime settings with `Environment=` and still starts through `/usr/bin/bash -lc`, so the blocker is real and local to the service/startup contract.
- `ops/install.sh` still seeds only operator-console host config and has no `ops/ids-live-sensor.env.example`, so the missing host-owned live-sensor contract is also local to this phase.
- `ids/ops/live_sensor_preflight.py` already validates `extractor_command_prefix` as a concrete executable-first contract.
- `ids/runtime/live_sensor.py` and `ids/runtime/live_flow_bridge.py` already support carrying a concrete extractor prefix into runtime execution.
- `ids/ops/same_host_stack.py` already proves the repo has a host env parsing pattern that can be reused for live-sensor convergence.
- Existing tests already cover multi-token preflight parsing, which means Story 2 can harden the startup seam while Story 3 intentionally narrows the packaged default to one exact helper path.

## Validation Decision

Phase 1 is now shaped correctly for execution:

- Story 2 owns the deploy seam that caused the original NO result.
- Bead `ids_ml_new-1u8h.4` explicitly owns removal of shell-wrapped startup drift, so the risk is not hidden.
- Story 3 no longer tries to solve arbitrary multi-token env transport as the normal product path; it pins one exact packaged helper path, which is much safer and matches the runtime contract.

## Constraints To Keep During Execution

- Story 2 must leave one direct packaged startup contract for both preflight and daemon startup; `bash -lc` cannot remain the normal path.
- Story 3 must make the packaged default extractor one exact helper path; arbitrary multi-token prefixes should remain compatibility override paths, not the default product story.
- Verification must prove env-file to preflight to daemon parity for the exact helper path before the phase can claim success.
