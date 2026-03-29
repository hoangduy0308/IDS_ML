# Spike Findings: Bead Write-Scope Decomposition

## Question

Does the revised bead decomposition keep write scopes sufficiently disjoint and context-bounded for swarming, especially around shared stack-manager files and docs?

## Decision

YES.

The current graph is safe enough for swarming because the only concurrent implementation beads are disjoint, and all shared stack-manager files are now serialized by explicit dependencies.

## Evidence

- `br ready --json` now surfaces only:
  - `ids_ml_new-x8y.1`
  - `ids_ml_new-x8y.2`
  - spikes `ids_ml_new-x8y.6/.7/.8`
- `ids_ml_new-x8y.1` writes the sensor health helper and its tests.
- `ids_ml_new-x8y.2`, `ids_ml_new-x8y.4`, `ids_ml_new-mwh`, `ids_ml_new-x8y.3`, and `ids_ml_new-x8y.5` all touch the shared stack-manager surface, but they are serialized by the dependency chain:
  - `ids_ml_new-x8y.2 -> ids_ml_new-x8y.4 -> ids_ml_new-mwh -> ids_ml_new-x8y.3 -> ids_ml_new-x8y.5`
- `bv --robot-plan` confirms only `.1` and `.2` are actionable implementation beads while the downstream shared-file beads remain blocked.
- The final plan-check report passed all 8 dimensions after this serialization change.

## Constraints For The Future Execution

- Swarming should keep `.1` and `.2` as separate workers first.
- The shared stack-manager beads must continue to be claimed in dependency order; do not manually bypass blockers.
- If `ids_ml_new-x8y.5` needs regression edits in `tests/test_ids_same_host_stack_manage.py`, it must stay after `.3` and `ids_ml_new-mwh`.

## Conclusion

The revised graph is execution-safe. The decomposition is no longer blocked by write-scope collisions, provided workers respect the declared dependency order.
