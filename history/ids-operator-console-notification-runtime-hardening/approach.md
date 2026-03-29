# Approach: IDS Operator Console Notification Runtime Hardening

**Date**: 2026-03-29
**Feature**: `ids-operator-console-notification-runtime-hardening`
**Based on**:
- `history/ids-operator-console-notification-runtime-hardening/discovery.md`
- `history/ids-operator-console-notification-runtime-hardening/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Notification domain logic | `scripts/ids_operator_console/notifications.py` already queues, dispatches, retries, and persists Telegram delivery state | A real operator-owned runtime contract that invokes this logic outside tests/modules | Medium |
| Queue source | `scripts/ids_operator_console/ingest.py` can refresh alerts from JSONL into SQLite on demand | An explicit owner for the `ingest -> queue` seam so notifications reflect real runtime alerts | Medium |
| Operator surface | `scripts/ids_operator_console_manage.py` exposes migrate/bootstrap/backup/restore/smoke only | Notification `status`, `test-send`, `run-once/drain`, long-running worker mode, and redrive actions | New |
| Observability | `/readyz` covers config/schema/admin/data-path/active-bundle only | Non-gating notification health with backlog/retry/disabled/degraded visibility across readiness/status/journald/smoke | New |
| Deploy wiring | `deploy/systemd/ids-operator-console.service` plus preflight validate only web-service startup | A real worker deploy contract, preflight alignment, and runbook coverage for notification operations | New |
| Backup/restore semantics | SQLite backup already preserves the DB file, including `notification_deliveries` | Explicit verification and operator guidance that restored delivery state remains meaningful and recoverable | Medium |

---

## 2. Recommended Approach

Implement this feature as a same-host notification maintenance subsystem centered on one new runtime/orchestration module plus explicit `ids_operator_console_manage.py` subcommands, while keeping the web service itself verify-only. The worker contract must own one full maintenance cycle on every explicit run: refresh sensor outputs into the console store first, queue notification candidates from persisted alerts second, dispatch due Telegram deliveries with existing retry logic third, then emit an operator-facing status snapshot for backlog/failure visibility. Add notification status helpers to the store/health surfaces so `/readyz`, `status`, `smoke`, and journald can report `enabled/disabled/degraded` state without making notification degradation block the core console runtime. Wire that contract through preflight, a dedicated same-host worker service artifact, backup/restore verification, and docs/runbooks so the Telegram path is truly operable rather than merely present in code.

### Why This Approach

- It reuses the existing strongest patterns in the repo: explicit maintenance CLI from `scripts/ids_model_bundle_manage.py`, supervisor-managed daemon behavior from `scripts/ids_live_sensor.py`, and same-host exact-path preflight from `scripts/ids_operator_console_preflight.py`.
- It honors locked decisions `D3`-`D5` by keeping notification ownership out of the web process and preserving verify-only startup for the console itself.
- It honors `D6`-`D10` by basing queueing on persisted alerts, keeping delivery state in SQLite, and making retry/recovery resume from local state after restart rather than from transient memory.
- It honors `D11`-`D14` by making notification health explicit and non-gating, then wiring the same contract through manage CLI, health, preflight, systemd, and docs.
- It closes the real production gap discovered in research: not missing Telegram logic, but missing ownership of the `ingest -> queue -> dispatch` flow and missing operator surfaces around that flow.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime owner | Add a dedicated notification maintenance entrypoint outside `ids_operator_console_server.py` | Satisfies `D3`-`D5` and preserves the web app’s failure boundary |
| Cycle shape | `ingest refresh -> queue notifications -> dispatch due deliveries -> emit status snapshot` | Ensures notifications are wired to fresh runtime alerts without inventing a second producer path |
| CLI surface | Extend `scripts/ids_operator_console_manage.py` with notification subcommands rather than inventing a second operator UX | Matches existing repo lifecycle CLI conventions and keeps operator workflow discoverable |
| Runtime module shape | Introduce a focused orchestration module that wraps existing `ingest.py` + `notifications.py` + status aggregation helpers | Reuses proven primitives while isolating new runtime behavior in one place |
| Health strategy | Add a notification component that reports `enabled`, `configured`, backlog, due oldest age, retry count, failed count, and last error summary, but does not flip overall core readiness by itself | Directly implements `D11` and preserves failure isolation |
| Disabled-mode semantics | If Telegram is not configured, treat notifications as explicitly disabled and skip queue accumulation by default while still surfacing disabled state to operators | Implements `D8` without creating silent infinite backlog |
| Recovery strategy | Persist queue/retry state in existing `notification_deliveries`, add an explicit redrive path for failed terminal rows, and keep worker startup resume-only | Implements `D7`, `D10`, and `D15` without manual DB surgery |
| Deploy strategy | Ship a dedicated worker service artifact for long-running mode, but wire it only to the command contract finalized in `ids_operator_console_manage.py` for `run-once`, `status`, `test-send`, and `redrive` | Prevents deploy/preflight drift from racing ahead of the surfaced operator/runtime contract |

---

## 3. Alternatives Considered

### Option A: Embed the notification loop inside the FastAPI web process

- Description: start a background task/thread from `ids_operator_console_server.py` that periodically queues and dispatches Telegram deliveries.
- Why considered: minimal new files and no second service unit.
- Why rejected: violates locked decisions `D3`-`D5`, couples notification failure to the dashboard process, and repeats the exact category of runtime-wiring ambiguity this repo has already been burned by.

### Option B: Provide only manual `manage` commands with no long-running worker

- Description: expose `queue`, `drain`, and `status` commands and require operators to run them manually or via ad hoc cron.
- Why considered: smaller implementation surface and explicit lifecycle control.
- Why rejected: does not reach the “production-ready same-host runtime” target in `D16`, leaves scheduling/ownership ambiguous, and pushes operational correctness into undocumented external automation.

### Option C: Build a notification-only worker that assumes ingest is handled elsewhere

- Description: create a worker that only reads persisted alerts from SQLite and never refreshes from sensor JSONL.
- Why considered: keeps the worker narrowly scoped to Telegram delivery.
- Why rejected: current repo evidence shows no always-on ingest owner for the console, so this would still leave the runtime path partially unwired and alerts potentially stale.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Notification maintenance cycle (`ingest -> queue -> dispatch`) | **HIGH** | New runtime ownership across multiple existing modules, must preserve ordering and failure isolation, and blast radius spans `ingest`, `notifications`, `manage`, and tests | Spike (handled by khuym:validating skill) |
| Worker entrypoint + systemd/preflight wiring | **HIGH** | New supervised runtime surface with deploy/artifact implications and a history of wiring drift in this repo | Spike (handled by khuym:validating skill) |
| Notification health/readiness contract | **HIGH** | Cross-cuts `health.py`, `ops.py`, `web.py`, CLI output, and docs; correctness depends on non-gating semantics that are easy to get subtly wrong | Spike (handled by khuym:validating skill) |
| Disabled-mode and backlog semantics | **MEDIUM** | Variation on existing queue logic, but behavior must be explicit enough to avoid silent operator confusion | Focused tests |
| Redrive/retry visibility | **MEDIUM** | Extends existing retry primitives, but introduces operator-facing mutation paths that need careful test coverage | Focused tests |
| Backup/restore + post-restore queue meaning | **MEDIUM** | Existing backup primitive covers the table, but operator-facing semantics and runbook expectations must stay correct | Focused tests |
| CLI UX and JSON/text payloads | **LOW** | Strong precedent exists in current manage scripts and bundle lifecycle commands | Proceed |

### Risk Classification Reference

```text
Pattern in codebase?        -> YES = LOW base
External dependency?        -> YES = HIGH
Blast radius > 5 files?     -> YES = HIGH
Otherwise                   -> MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `Notification maintenance cycle`: prove the chosen cycle ordering keeps ingest durable, queueing suppression-aware, and dispatch failures isolated from ingest/triage/dashboard readiness.
- `Worker entrypoint + systemd/preflight wiring`: prove the worker can be supervised on the same host with one explicit runtime contract and no hidden startup side effects.
- `Notification health/readiness contract`: prove notification degradation is operator-visible and actionable without incorrectly making the whole console unready.

---

## 5. Proposed File Structure

```text
scripts/
  ids_operator_console/
    notifications.py                 # existing queue/dispatch/retry primitives, extended for status/redrive helpers
    db.py                            # existing delivery persistence, extended with notification status aggregations
    ingest.py                        # existing refresh seam reused by worker run-once cycle
    health.py                        # add non-gating notification component
    ops.py                           # extend smoke/status helpers with notification visibility
    notification_runtime.py          # NEW: maintenance cycle + worker loop orchestration
  ids_operator_console_manage.py     # add notification status/test-send/run-once/worker/redrive commands
  ids_operator_console_preflight.py  # validate notification-enabled worker contract when configured
deploy/
  systemd/
    ids-operator-console.service
    ids-operator-console-notify.service   # NEW: dedicated same-host worker unit
docs/
  ids_operator_console_architecture.md
  ids_operator_console_operations.md
tests/
  test_ids_operator_console_notifications.py
  test_ids_operator_console_ops.py
  test_ids_operator_console_web.py
  test_ids_operator_console_db.py
  test_ids_operator_console_ingest.py
  test_ids_operator_console_notification_runtime.py   # NEW: runtime-cycle/worker-focused coverage
```

---

## 6. Dependency Order

```text
Layer 1 (sequential): runtime foundations
  - notification runtime module shape
  - DB/status aggregation helpers
  - disabled-mode and redrive semantics

Layer 2 (parallel): operator-facing integration
  - manage CLI notification subcommands
  - health/ops/web notification visibility

Layer 3 (parallel): deploy and verification integration
  - preflight + systemd worker artifact
  - docs/runbook + restore expectations

Layer 4 (sequential): end-to-end wired regression pass
  - cycle ordering
  - failure isolation
  - restart/restore visibility
```

### Parallelizable Groups

- Group A: runtime core (`notification_runtime.py`, `notifications.py`, `db.py`) must land first because every other bead depends on the status and cycle contract.
- Group B: CLI surface and health/ops surface can proceed in parallel once Group A defines the runtime/status contract.
- Group C: deploy/preflight can proceed only after both Group A and the CLI portion of Group B are stable, because service/preflight wiring must bind to the finalized command names and config semantics.
- Group D: docs/runbook can proceed after deploy/preflight and health/CLI surfaces are stable enough to document exact shipped behavior.
- Group E: final regression and polish depends on Groups A-D being stable enough to verify `EXISTS / SUBSTANTIVE / WIRED`.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | Runtime/deploy paths must be reviewed as `EXISTS / SUBSTANTIVE / WIRED` | The plan includes a dedicated worker entrypoint, service artifact, preflight, and regression coverage instead of stopping at module functions |
| `history/learnings/20260329-operator-console-production-hardening.md` | Keep verify-only runtime separate from maintenance/mutation paths | The plan keeps notification work out of `ids_operator_console_server.py` and moves it into explicit operator/worker entrypoints |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Long-running daemons must publish durable operator evidence during runtime | The worker plan emits persisted queue state and operator status snapshots during runtime rather than relying on shutdown/manual inspection |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Exact-path preflight and one config source reduce deploy drift | The worker is planned as a same-host supervised service with matching preflight/unit/runtime contract |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | Restore verification must preserve operator-facing visibility, not only storage integrity | The plan explicitly includes post-restore queue/delivery-state semantics in smoke/runbook and validating questions |

---

## 8. Open Questions for Validating

- [ ] Is the proposed non-gating notification component expressive enough for operators to detect disabled/misconfigured/backlogged states without misreading the whole console as unhealthy? — if wrong, readiness semantics will stay operationally confusing.
- [ ] Does a dedicated `ids-operator-console-notify.service` give the cleanest same-host deploy contract, or does validating show that a timer + `run-once` model is safer with the same explicit ownership? — if wrong, the deploy artifact could still be more ambiguous than necessary.
