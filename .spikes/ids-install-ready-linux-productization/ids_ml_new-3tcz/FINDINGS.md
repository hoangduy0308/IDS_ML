# Spike Findings: ids_ml_new-3tcz

**Feature**: `ids-install-ready-linux-productization`
**Phase**: `Phase 1 - Make Install Modes And Host Config Real`
**Question**: Can one live-sensor host env contract carry extractor tokenization cleanly through systemd `EnvironmentFile`, `ids-stack` / same-host preflight, and daemon startup without manual unit edits or shell-specific hacks?
**Result**: `NO`
**Validated at**: `2026-04-05T23:07:58.3308122+07:00`

## Why

The Python-side contract already preserves extractor prefixes as token lists once execution is inside the application surfaces, but the deployed Linux path is not yet an env-file-driven contract. The shipped live-sensor unit still hardcodes critical values with `Environment=` and starts the daemon through `bash -lc`, while `ops/install.sh` installs that unit without seeding a live-sensor host env file. That means a multi-token extractor prefix cannot yet survive end-to-end without shell-sensitive startup assumptions or manual unit edits.

## Evidence

- `deploy/systemd/ids-live-sensor.service` has no `EnvironmentFile=` and still starts through `/usr/bin/bash -lc`.
- `ops/install.sh` forwards extractor information into bootstrap paths but does not seed a live-sensor host env contract.
- `ids/ops/live_sensor_preflight.py`, `ids/runtime/live_sensor.py`, and `ids/runtime/live_flow_bridge.py` preserve token lists only after the caller has already preserved token boundaries.

## Constraints To Fold Into Replanning

- Story 2 must own the host-owned live-sensor env file contract and unit wiring as one deploy seam, not as separate incidental edits.
- Story 2 must also eliminate shell-wrapper dependence in the packaged sensor start path; `EnvironmentFile=` alone is not enough if startup still round-trips through `bash -lc`.
- Story 3 verification must include executable round-trip coverage for multi-token prefixes, missing-token failure, and env-file-to-daemon parity.

## Recommended Bead Impacts

- `ids_ml_new-1u8h.3`: explicitly own host env file creation plus `EnvironmentFile=` unit wiring so token lists survive startup unchanged.
- `ids_ml_new-1u8h.4`: own removal of shell-wrapper dependence and align install/runtime readers around the seeded live-sensor env file.
- `ids_ml_new-1u8h.5`: own round-trip regression proof for multi-token prefixes, missing-token failure, and env-file-to-daemon startup parity.
