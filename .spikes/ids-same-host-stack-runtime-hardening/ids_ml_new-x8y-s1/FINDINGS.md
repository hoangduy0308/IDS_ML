# Spike Findings: Live Sensor Runtime Health Seam

## Question

Can the stack use one read-only sensor health seam that proves real runtime health from activation state plus durable summary evidence, without inventing a second source of truth or relying on systemd-only assumptions in tests?

## Decision

YES.

The stack can use a narrow read-only health helper built from:

- the activation contract returned by `build_bundle_status_payload()`
- the latest durable live sensor summary event from `ids_live_sensor_summary.jsonl`

This is strong enough for same-host `status` and `smoke` as long as the helper treats missing, stale, or mismatched runtime evidence as degraded instead of guessing.

## Evidence

- `scripts/ids_live_sensor.py` initializes the sink's active bundle state from `build_bundle_status_payload(config.activation_path)` before the daemon loop starts.
- `scripts/ids_live_sensor_sinks.py` persists summary events durably during runtime via `capture_summary()`, not only on graceful shutdown.
- Runtime summaries already carry `active_bundle`, queue depth, extractor runtime, processed window count, and extractor failure metadata.
- `tests/test_ids_live_sensor.py` proves summary events are emitted while the daemon is processing windows and that fatal capture failure still writes a final summary with `reason="capture-failure"`.
- `tests/test_ids_live_sensor_sinks.py` proves summary JSONL append semantics survive restart and include `active_bundle` metadata.
- `history/learnings/20260328-live-sensor-runtime-contracts.md` explicitly rejects shutdown-only publication and systemd-only health inference for daemon contracts.

## Constraints For The Future Implementation

- The helper must remain read-only. No service control, no mutation, no ownership drift away from `ids_live_sensor.py` and `ids-live-sensor.service`.
- Health must compare summary `active_bundle` against the activation record. Mismatch means degraded.
- Missing summary evidence must not be reported as healthy just because the activation record exists.
- Stale summary evidence must be explicit. The stack layer needs a freshness window instead of assuming old JSONL means current health.
- The helper should use JSONL summary evidence directly; journald may be supplemental, but not the primary truth source.

## Conclusion

The validating spike supports bead `ids_ml_new-x8y.1` exactly as planned: add one small read-only sensor-domain status helper that composes activation state with durable summary evidence and fails closed on stale or inconsistent runtime signals.
