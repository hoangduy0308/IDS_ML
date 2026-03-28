# Critical Patterns

Promoted learnings from completed features. Read this file at the start of every
planning Phase 0 and every exploring Phase 0. These are the lessons that cost the
most to learn and save the most by knowing.

---

## [20260328] Never Use Copy-Based Fallbacks In Filesystem Rollback
**Category:** failure
**Feature:** ids-structured-record-adapter
**Tags:** [rollback, security, filesystem]

The adapter rollback path originally tried to recover from a failed `replace()` by copying the backup back into place. Review exposed that this is unsafe when the destination can be redirected through a symlink or junction, because a recovery step becomes an arbitrary overwrite primitive. Future work should keep rollback on atomic rename/replace only and fail closed if restore cannot be completed safely.

**Full entry:** history/learnings/20260328-adapter-rollback-contract.md

## [20260328] Validate Write Scope And High-Risk Spikes Before Swarming
**Category:** failure
**Feature:** ids-structured-record-adapter
**Tags:** [validation, swarming, bead-decomposition]

This feature's first validation pass failed because concurrent beads overlapped in file scope and HIGH-risk assumptions had not been spiked yet. Catching that before execution prevented a bad swarm start and forced the plan into a shape the workers could actually execute safely. Future validation passes should explicitly reject shared write scopes and missing spikes before approving execution.

**Full entry:** history/learnings/20260328-adapter-rollback-contract.md
