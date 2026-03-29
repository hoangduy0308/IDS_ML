# Validation Report: IDS Operator Console Notification Runtime Hardening

**Date**: 2026-03-29
**Feature**: `ids-operator-console-notification-runtime-hardening`
**Phase**: `khuym:validating`

---

## Phase 1: Plan Verification

```text
PLAN VERIFICATION REPORT
Feature: ids-operator-console-notification-runtime-hardening
Beads reviewed: 7
Date: 2026-03-29

DIMENSION 1 — Requirement Coverage: PASS
Locked decisions D1-D16 map cleanly onto the bead set. Same-host and Telegram-only scope are enforced across the epic and all child beads; D3-D10 land in ids_ml_new-wx1.1, D11-D13 land in ids_ml_new-wx1.2, D8/D14 land in ids_ml_new-wx1.3, and D13-D16 land in ids_ml_new-wx1.4. No locked decision remained bead-less after the validation pass.

DIMENSION 2 — Dependency Correctness: PASS
The execution graph remains acyclic and matches the intended build order: runtime core first, operator surface second, deploy/preflight third, docs/recovery last. The previously missing ids_ml_new-wx1.3 -> ids_ml_new-wx1.2 dependency was already fixed before validating, and no invalid bead references were found. The only remaining bv suggestion for ids_ml_new-wx1.4 -> ids_ml_new-wx1.1 was evaluated and rejected because ids_ml_new-wx1.4 already depends transitively on ids_ml_new-wx1.1 through ids_ml_new-wx1.3.

DIMENSION 3 — File Scope Isolation: PASS
File overlaps are serialized by the dependency graph. ids_ml_new-wx1.2 and ids_ml_new-wx1.3 both touch tests/test_ids_operator_console_ops.py, but ids_ml_new-wx1.3 depends on ids_ml_new-wx1.2. ids_ml_new-wx1.4 shares scripts/ids_operator_console/ops.py and tests/test_ids_operator_console_notification_runtime.py with earlier beads, but ids_ml_new-wx1.4 sits after ids_ml_new-wx1.2 and ids_ml_new-wx1.3, which already forces sequential ownership of those files.

DIMENSION 4 — Context Budget: PASS
Each execution bead stays within one agent-sized concern: runtime core, operator surface, deploy/preflight, and docs/recovery. None of the execution beads requires a cross-repo rewrite or an uncontrolled number of subsystems. The three spike beads are analysis-only and bounded to one output artifact each under .spikes/.

DIMENSION 5 — Test Coverage: PASS
Every execution bead now carries explicit runnable acceptance criteria, not just generic verification language. ids_ml_new-wx1.1, ids_ml_new-wx1.2, ids_ml_new-wx1.3, and ids_ml_new-wx1.4 each name the concrete pytest surface that must pass plus the contract behavior that those tests must prove.

DIMENSION 6 — Gap Detection: PASS
Completing the full bead set would close the production gaps identified in CONTEXT.md: explicit runtime ownership, operator commands, non-gating visibility, deploy/preflight wiring, restart/recovery semantics, and runbook coverage. No uncovered non-functional requirement remained after checking observability, failure isolation, disabled-mode behavior, and backup/restore expectations.

DIMENSION 7 — Risk Alignment: PASS
All three HIGH-risk items from approach.md now have specific spike beads with YES/NO questions: ids_ml_new-xpl for the maintenance cycle, ids_ml_new-lyk for deploy/preflight ownership, and ids_ml_new-uj1 for health/readiness semantics. Each spike writes to its own .spikes output path and closes with a definitive decision plus constraints.

DIMENSION 8 — Completeness: PASS
If all execution beads land as written, the shipped feature will include the runtime worker, CLI surface, health/readiness visibility, deploy/service wiring, and operational docs/tests needed to satisfy D16. The bead set covers both implementation and proof that the runtime is EXISTS / SUBSTANTIVE / WIRED rather than module-only.

OVERALL: PASS

PRIORITY FIXES (if FAIL):
1. None.
```

**Iterations used**: 1

### Validation-only bead polish applied

- Added explicit acceptance criteria to `ids_ml_new-wx1.1`, `ids_ml_new-wx1.2`, `ids_ml_new-wx1.3`, and `ids_ml_new-wx1.4` so verification is runnable rather than implied.
- Created three spike beads for the HIGH-risk items in `approach.md`.
- Evaluated `bv --robot-suggest` dependency noise against the epic only. One high-confidence suggestion (`ids_ml_new-wx1.4 -> ids_ml_new-wx1.1`) was intentionally rejected because the dependency is already enforced transitively via `ids_ml_new-wx1.3`.

---

## Phase 2: Spike Results

### ids_ml_new-xpl

- Result: `YES`
- Question: Can one explicit same-host notification worker own `ingest -> queue -> dispatch` without breaking failure isolation?
- Why YES:
  - `ingest.py` already exposes a restart-safe, persisted-offset ingest seam via `ingest_sensor_outputs_once()`.
  - `alerts.py` already narrows notification candidates through suppression filtering and terminal triage exclusion.
  - `notifications.py` already persists deduped deliveries, dispatches due rows only, and isolates retryable/non-retryable failures into `retry` and `failed` delivery states.
  - Current tests already prove retry-state persistence and that alert rows survive dispatch failure.
- Constraints:
  - Do not use `queue_and_dispatch_notifications()` as the final runtime contract because it skips ingest and does not model disabled-mode/status snapshot semantics.
  - The new runtime seam must own explicit phase ordering and emit per-phase summaries so dispatch failure cannot collapse the whole worker path into an opaque crash.

### ids_ml_new-lyk

- Result: `YES`
- Question: Can deploy and preflight share one explicit notification worker contract on the same host?
- Why YES:
  - The current web service already demonstrates the repo pattern: one env contract, one preflight command, one explicit systemd unit.
  - `ids_operator_console_preflight.py` already validates absolute paths, secrets, schema/admin bootstrap, and Telegram token/chat pairing.
  - `tests/test_ids_operator_console_preflight.py` already proves this contract can be verified locally without network dependency.
  - `ids_operator_console_manage.py` already establishes the explicit operator-command pattern that the worker can extend.
- Constraints:
  - Add a dedicated worker entrypoint or finalized manage subcommand and make systemd/preflight point to that exact surface.
  - Keep notification ownership outside `ids_operator_console_server.py`; the web unit remains verify-only.
  - Preflight should only require worker-specific seams when notifications are explicitly enabled, not in disabled mode.

### ids_ml_new-uj1

- Result: `YES`
- Question: Can notification health become operator-visible while staying non-gating for core readiness?
- Why YES:
  - `health.py` already separates `components` from the top-level `ready` boolean.
  - `web.py` uses `payload["ready"]` alone to decide `/readyz` HTTP 200 vs 503, so a new component can be surfaced without forcing readiness failure.
  - `ops.py` and the dashboard already reuse the same readiness payload, which makes one component model fan out to smoke and UI visibility.
- Constraints:
  - Preserve the core-ready calculation for config/schema/data-path/admin/runtime essentials; notification state must not be folded into that boolean.
  - Surface notification state with explicit fields such as `enabled`, `configured`, `backlog`, `retrying`, `failed`, `oldest_due`, and `last_error`.
  - The CLI `status` view and smoke output should reuse the same component snapshot so operators do not get conflicting stories.

---

## Phase 3: Bead Polishing

### Round 1: Dependency Completeness

- `bv --robot-suggest` on the full repo returned many unrelated historical suggestions.
- Focused dependency checks were run against the current epic only.
- Outcome:
  - `0` real dependencies added during this round.
  - `1` relevant suggestion rejected intentionally:
    - `ids_ml_new-wx1.4 -> ids_ml_new-wx1.1`
    - Reason: already transitively enforced by `ids_ml_new-wx1.4 -> ids_ml_new-wx1.3 -> ids_ml_new-wx1.1`

### Round 2: Graph Health

- `bv --robot-insights` for the current graph reported:
  - no dependency cycles
  - one clean critical path through `ids_ml_new-wx1.1 -> ids_ml_new-wx1.2 -> ids_ml_new-wx1.3 -> ids_ml_new-wx1.4`
  - no epic-local articulation or orphan issue that blocks this feature plan
- Outcome:
  - `0` critical graph issues fixed

### Round 3: Priority Sanity

- `bv --robot-priority` suggested de-prioritizing some beads, but only `ids_ml_new-wx1.1` had high confidence and it remains correctly at the top of the implementation chain already.
- Outcome:
  - `0` priority changes made
  - existing ordering remains acceptable for this feature's critical path

### Deduplication Check

- No duplicate execution beads found inside this epic.
- The noisy duplicate suggestions from `bv --robot-suggest` belonged to old unrelated issues and were ignored.

### Fresh-Eyes Review

Because no explicit delegation/subagent permission was granted in this session, the fresh-eyes pass was performed locally as a cold-read review against the bead content itself.

```text
BEAD REVIEW REPORT
Epic: ids_ml_new-wx1
Beads reviewed: 8
Date: 2026-03-29

CRITICAL FLAGS (0 total)
None.

MINOR FLAGS (0 total)
None after the validation pass tightened acceptance criteria.

CLEAN BEADS (8 total)
ids_ml_new-wx1, ids_ml_new-wx1.1, ids_ml_new-wx1.2, ids_ml_new-wx1.3, ids_ml_new-wx1.4, ids_ml_new-xpl, ids_ml_new-lyk, ids_ml_new-uj1

SUMMARY
The execution beads are now specific enough for a fresh worker to know what to build, where to build it, and how to verify completion. The main ambiguity that existed before validating was verification specificity; that has been resolved by adding runnable acceptance criteria.
```

Note: the clean bead count above covers all beads reviewed; the list is the authoritative source.

### Tooling Note

- During validation, `br` emitted transient SQLite rebuild warnings and `br list --status open --json` duplicated `ids_ml_new-wx1.4` in output.
- Source-of-truth check against `.beads/issues.jsonl` confirmed only one canonical `ids_ml_new-wx1.4` record exists, and `br show ids_ml_new-wx1.4 --json` resolves to that single bead.
- Treat this as a non-blocking beads CLI display artifact for this session, not as an epic-structure defect.

---

## Validation Conclusion

- Plan verification: `PASS`
- HIGH-risk spikes: `3/3 YES` and closed with recorded constraints
- Dependency/graph review: `PASS`
- Fresh-eyes review: `0 CRITICAL`
- Overall confidence before execution: `HIGH`

No blocker was found that requires returning to `khuym:planning`.
