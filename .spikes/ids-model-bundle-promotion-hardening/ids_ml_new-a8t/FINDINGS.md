# Spike Findings: ids_ml_new-a8t

**Question:** Can active bundle promotion and rollback use an atomic activation record without copy-based restore fallback?
**Result:** YES
**Date:** 2026-03-29

## Evidence

- [`scripts/ids_live_sensor_sinks.py`](F:/Work/IDS_ML_New/scripts/ids_live_sensor_sinks.py) already contains a transactional replace-based promotion pattern with backup staging and restore-by-`replace()` only.
- [`history/learnings/20260328-adapter-rollback-contract.md`](F:/Work/IDS_ML_New/history/learnings/20260328-adapter-rollback-contract.md) and [`history/learnings/critical-patterns.md`](F:/Work/IDS_ML_New/history/learnings/critical-patterns.md) explicitly prohibit copy-based rollback fallbacks.

## Conclusion

The repo already has the filesystem safety pattern needed for this feature. The safe design is to store host-local activation state in a small JSON activation record/current pointer, update it through staged temp file + atomic `Path.replace()`, and record the previous known-good bundle in that activation state. Rollback should rewrite the activation record back to the previous bundle, not copy bundle directories.

## Locked Constraints For Execution

- Keep activation state separate from bundle contents so promotion/rollback only swaps a small activation record.
- Activation state must record at least: active bundle identity/root, previous known-good bundle identity/root, promoted or activated timestamp, and verification status needed for operator visibility.
- Rollback must use the same atomic replace path as promotion; no copy/unlink fallback is allowed if restore fails.
- If activation-record restore fails, the system must fail closed and preserve diagnostic state rather than attempting a broader filesystem rewrite.

## Beads Affected

- `ids_ml_new-hup.1`
- `ids_ml_new-hup.2`
