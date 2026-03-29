# Spike Findings: ids_ml_new-d85

**Question:** Can live sensor runtime, preflight, and systemd share one active-bundle contract and fail closed consistently?
**Result:** YES
**Date:** 2026-03-29

## Evidence

- [`scripts/ids_live_sensor.py`](F:/Work/IDS_ML_New/scripts/ids_live_sensor.py) currently mixes `FlowFeatureContract.from_feature_file(config.feature_columns_path)` with independent inference inputs, which is exactly the seam this feature must close.
- [`scripts/ids_live_sensor_preflight.py`](F:/Work/IDS_ML_New/scripts/ids_live_sensor_preflight.py) already provides a dedicated preflight contract that can be upgraded to resolve the same active bundle as runtime.
- [`deploy/systemd/ids-live-sensor.service`](F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service) already centralizes environment variables and uses the same values in both `ExecStartPre=` and `ExecStart=`, so replacing split model/schema env vars with one active-bundle input is operationally straightforward.
- [`history/learnings/20260328-live-sensor-runtime-contracts.md`](F:/Work/IDS_ML_New/history/learnings/20260328-live-sensor-runtime-contracts.md) and [`history/learnings/20260329-operator-console-production-hardening.md`](F:/Work/IDS_ML_New/history/learnings/20260329-operator-console-production-hardening.md) require one config source plus verify-only runtime startup.

## Conclusion

The existing runtime, preflight, and unit-file shape already supports a single-source contract. The correct production path is to wire all three surfaces to one active-bundle input, resolve the canonical bundle contract there, and fail closed on missing or incompatible bundles. Separate production `MODEL_PATH`, `FEATURE_COLUMNS_PATH`, and threshold env wiring should be removed from the systemd/service contract rather than kept as parallel truth sources.

## Locked Constraints For Execution

- Runtime, preflight, and systemd must all consume the same active-bundle contract input.
- Production service wiring must stop passing separate model/schema/threshold inputs.
- Dev-only fallback flags may remain in generic inference tooling, but not in the production service contract.
- Preflight and runtime must share the same compatibility semantics so readiness cannot claim a narrower contract than execution.

## Beads Affected

- `ids_ml_new-hup.1`
- `ids_ml_new-hup.3`
- `ids_ml_new-hup.4`
- `ids_ml_new-hup.5`
