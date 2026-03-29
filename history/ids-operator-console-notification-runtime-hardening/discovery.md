# Discovery Report: IDS Operator Console Notification Runtime Hardening

**Date**: 2026-03-29
**Feature**: `ids-operator-console-notification-runtime-hardening`
**CONTEXT.md reference**: `history/ids-operator-console-notification-runtime-hardening/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md`: service entrypoints and deploy artifacts must pass `EXISTS / SUBSTANTIVE / WIRED`; module-level notification code alone is not enough.
- `history/learnings/critical-patterns.md`: same-host Linux services in this repo are safer when they use one exact-path config source plus dedicated preflight validation rather than implicit shell/runtime discovery.
- `history/learnings/critical-patterns.md`: validating must reject overlapping write scopes and must spike every HIGH-risk assumption before execution starts.
- `history/learnings/critical-patterns.md`: supervised daemon outputs must become durable during runtime, not only at shutdown or after an external happy-path step.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | operator console runtime | Keep the runnable surface wired to the real app/service contract and verify background/runtime paths with `EXISTS / SUBSTANTIVE / WIRED`, not just module tests. | high |
| `history/learnings/20260329-operator-console-production-hardening.md` | operator console operations | Split verify-only web startup from operator mutation and maintenance paths; do not hide state-changing or background work inside normal runtime startup. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | daemon durability | Long-running workers must publish durable operator-facing state during runtime and classify failure domains clearly enough for supervisor restart behavior. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | systemd/preflight | Same-host services should keep centralized env/path config and exact-path preflight checks aligned with the actual runtime contract. | high |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | restore/visibility | Failed mutations must preserve last known-good state, and backup/restore verification must include the operator-facing visibility path rather than only happy-path mutation success. | medium |

---

## Agent A: Architecture Snapshot

> Source: local file analysis, targeted code reads, existing feature history

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts.ids_operator_console.notifications` | Telegram queue/dispatch/retry/backoff domain logic | `scripts/ids_operator_console/notifications.py` |
| `scripts.ids_operator_console.db` | SQLite persistence for alerts, offsets, admin state, and `notification_deliveries` | `scripts/ids_operator_console/db.py` |
| `scripts.ids_operator_console.alerts` | suppression and triage filtering for notification candidates | `scripts/ids_operator_console/alerts.py` |
| `scripts.ids_operator_console.ingest` | same-host JSONL ingest with persisted offsets and restart-safe partial-line handling | `scripts/ids_operator_console/ingest.py` |
| `scripts.ids_operator_console.health` | `/healthz` and `/readyz` payload builders for the console | `scripts/ids_operator_console/health.py` |
| `scripts.ids_operator_console.ops` | backup/restore/retention/smoke utilities | `scripts/ids_operator_console/ops.py` |
| `scripts.ids_operator_console_manage` | current explicit operator CLI surface for migrate/bootstrap/backup/restore/smoke | `scripts/ids_operator_console_manage.py` |
| `scripts.ids_operator_console_server` | canonical web-service entrypoint that launches the real FastAPI app | `scripts/ids_operator_console_server.py` |
| `scripts.ids_operator_console_preflight` | exact-path preflight contract for the current console service | `scripts/ids_operator_console_preflight.py` |
| deployment surface | same-host systemd packaging for the console | `deploy/systemd/ids-operator-console.service` |

### Entry Points

- **Web service**: `F:/Work/IDS_ML_New/scripts/ids_operator_console_server.py`
- **Canonical app factory**: `F:/Work/IDS_ML_New/scripts/ids_operator_console/web.py`
- **Operator CLI**: `F:/Work/IDS_ML_New/scripts/ids_operator_console_manage.py`
- **Preflight gate**: `F:/Work/IDS_ML_New/scripts/ids_operator_console_preflight.py`
- **Current systemd unit**: `F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service`
- **Missing runtime seam today**: there is no explicit notification worker entrypoint or dedicated service/timer/loop owning `ingest -> queue -> dispatch`.

### Key Files to Model After

- `F:/Work/IDS_ML_New/scripts/ids_model_bundle_manage.py` — demonstrates this repo’s preferred explicit-operator CLI shape for `status/verify/promote/rollback` style lifecycle commands.
- `F:/Work/IDS_ML_New/scripts/ids_live_sensor.py` — demonstrates a same-host long-running daemon loop that owns runtime work outside the web app and persists operational state during runtime.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service` — demonstrates how this repo wires a supervisor-managed daemon with centralized env config and exact-path preflight.
- `F:/Work/IDS_ML_New/tests/test_ids_operator_console_ingest.py` — proves the existing ingest seam is restart-safe and newline/rotation aware, which matters if the notification worker refreshes alerts before queueing.

---

## Agent B: Pattern Search

> Source: code reads, grep, prior feature artifacts

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Explicit lifecycle CLI | `scripts/ids_model_bundle_manage.py` | one script with subcommands for inspect/verify/mutate lifecycle | Yes |
| Verify-only web startup | `scripts/ids_operator_console_server.py`, `scripts/ids_operator_console/web.py` | canonical app factory with no hidden background worker | Yes - must be preserved |
| Runtime ingest with persisted offsets | `scripts/ids_operator_console/ingest.py` | `run_once()` importer that tolerates append/restart/partial lines/file replace | Yes |
| Notification persistence first, outbound second | `scripts/ids_operator_console/notifications.py` | queue in SQLite, then attempt provider dispatch with retry bookkeeping | Yes |
| Non-destructive operational smoke | `scripts/ids_operator_console/ops.py` | local smoke checks against the wired runtime contract | Yes |
| Exact-path preflight | `scripts/ids_operator_console_preflight.py`, `scripts/ids_live_sensor_preflight.py` | preflight validates runtime contract before `ExecStart` | Yes |
| Same-host service packaging | `deploy/systemd/ids-operator-console.service`, `deploy/systemd/ids-live-sensor.service` | env-driven systemd unit with `ExecStartPre` and journald output | Yes |

### Reusable Utilities

- **Candidate filtering**: `F:/Work/IDS_ML_New/scripts/ids_operator_console/alerts.py` — `list_alerts_for_notification()` already applies suppression and excludes terminal triage states.
- **Delivery persistence**: `F:/Work/IDS_ML_New/scripts/ids_operator_console/db.py` — `save_notification_delivery()`, `mark_notification_attempt()`, `list_pending_notification_deliveries()` already model pending/retry/failed/sent.
- **Message formatting + retry logic**: `F:/Work/IDS_ML_New/scripts/ids_operator_console/notifications.py` — `build_alert_notification_text()`, `dispatch_pending_telegram_notifications()`, and exponential/retry-after handling already exist.
- **Health payload style**: `F:/Work\IDS_ML_New/scripts/ids_operator_console/health.py` — component-based readiness payload can be extended with a non-gating notification section.
- **Ops command output style**: `F:/Work/IDS_ML_New/scripts/ids_operator_console_manage.py` and `F:/Work/IDS_ML_New/scripts/ids_model_bundle_manage.py` — repo favors JSON-or-text payloads from explicit CLI subcommands rather than hidden admin endpoints.

### Naming Conventions

- Script-first Python modules under `scripts/`.
- Service and maintenance entrypoints are plain Python scripts named `ids_<capability>_<purpose>.py`.
- Deploy artifacts live in `deploy/systemd/`.
- Docs live in `docs/ids_<capability>_<topic>.md`.
- Tests live in `tests/test_ids_<capability>*.py`.
- Operational contracts prefer explicit dataclasses, stdlib/sqlite primitives, and JSON payloads over heavyweight abstractions.

---

## Agent C: Constraints Analysis

> Source: local environment, current imports, unit/test surfaces

### Runtime & Framework

- **Python version**: `3.11.9`
- **SQLite runtime**: `3.45.1`
- **FastAPI**: `0.115.12`
- **Starlette**: `0.46.2`
- **Uvicorn**: `0.34.0`
- **Jinja2**: `3.1.6`
- **Pytest**: `8.3.5`
- **Repo packaging reality**: no root `pyproject.toml`, `requirements*.txt`, `setup.cfg`, or `setup.py`; planning should avoid introducing new dependencies unless truly necessary.

### Existing Dependencies (Relevant to This Feature)

| Package | Version / Evidence | Purpose |
|---------|--------------------|---------|
| `fastapi` | imported by `scripts/ids_operator_console/web.py` | web routes and HTML/API surface |
| `starlette` | imported for `SessionMiddleware` and `TestClient` | session middleware and testing |
| `uvicorn` | imported by `scripts/ids_operator_console_server.py` | ASGI runtime |
| stdlib `sqlite3` | used in `db.py` and `ops.py` | operator persistence and backup primitives |
| stdlib `urllib` | used in `notifications.py` | Telegram HTTP transport without extra SDK dependency |
| `pytest` | current repo test runner | targeted regression coverage |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None required at planning time | the feature can build on existing Python/FastAPI/sqlite/systemd patterns and the current `urllib`-based Telegram path | LOW |

### Build / Quality Requirements

```bash
python -m py_compile scripts/ids_operator_console_manage.py scripts/ids_operator_console_server.py scripts/ids_operator_console_preflight.py scripts/ids_operator_console/*.py
python -m pytest -q tests/test_ids_operator_console_notifications.py tests/test_ids_operator_console_ops.py tests/test_ids_operator_console_web.py tests/test_ids_operator_console_db.py tests/test_ids_operator_console_ingest.py
```

### Deployment / Storage Constraints

- `scripts/ids_operator_console_server.py` currently only launches the web app; it does not own notification dispatch or even explicit ingest refresh.
- `deploy/systemd/ids-operator-console.service` currently wires only one web service process plus preflight; there is no worker unit or timer for notifications.
- `scripts/ids_operator_console_preflight.py` validates Telegram token/chat pairing but does not validate any notification-worker entrypoint or enabled/disabled runtime ownership contract.
- `scripts/ids_operator_console/health.py` has no notification component in `/readyz`, so operators cannot distinguish “console ready but notifications degraded/disabled” from “feature absent”.
- `scripts/ids_operator_console_manage.py` has no notification `status`, `test-send`, `run-once`, `worker`, or `redrive` subcommands.
- `notification_deliveries` already persists delivery state, but the current code has no aggregate status helper for backlog/retry/oldest due item/operator diagnostics.
- SQLite backup already covers the full operator DB, so delivery-state preservation is structurally possible; the missing gap is runtime semantics, surface area, and verification rather than a brand-new storage engine.

### Database / Storage

- **Operator source of truth**: `notification_deliveries` in SQLite plus alert rows and ingest offsets.
- **Upstream producer boundary**: live sensor still owns `alerts/quarantine/summary` JSONL outputs; notification planning must not mutate producer-side runtime.
- **Important implication**: if the worker needs fresh alerts before queueing, it should reuse `ingest_sensor_outputs_once()` or an equivalent explicit refresh step rather than inventing a second producer interface.

---

## Agent D: External Research

> Source: intentionally skipped
> Guided by locked decisions in CONTEXT.md

### Why External Research Was Skipped

- The feature does not introduce a new library or outbound provider beyond the already implemented Telegram HTTP path.
- The repo already contains the relevant patterns for explicit CLI lifecycle management, same-host daemon wiring, exact-path preflight, SQLite backup/restore, and componentized readiness payloads.
- Planning value is higher in composing existing repo patterns into one runtime contract than in searching for generic community examples.

### Known Gotchas / Anti-Patterns From Existing Evidence

- **Anti-pattern**: embedding the notification loop inside `ids_operator_console_server.py`.
  - Why it matters: it violates the repo’s verify-only web startup posture and blurs the failure boundary between dashboard service and outbound delivery.
  - How to avoid: keep a separate maintenance/worker entrypoint and supervisor contract.

- **Anti-pattern**: treating Telegram config presence in `config.py`/`preflight.py` as proof that runtime wiring exists.
  - Why it matters: current code already passes config pairing checks while still lacking any actual worker ownership surface.
  - How to avoid: plan review must require a real worker/CLI/service path plus runtime verification.

- **Anti-pattern**: assuming dispatch can be hardened without considering how fresh alerts enter the local store.
  - Why it matters: if no process owns the `ingest -> queue` seam, dispatch remains technically correct but operationally stale.
  - How to avoid: make the worker contract explicit about whether it performs ingest refresh, and verify that ordering during validation.

---

## Open Questions

> Items that will be closed in synthesis/approach.

- [ ] What exact CLI contract best fits repo conventions: all notification actions under `ids_operator_console_manage.py`, or a new dedicated worker script plus thin manage wrappers? — this affects operator ergonomics and deploy wiring.
- [ ] How should disabled Telegram mode avoid unbounded backlog while still preserving clear operator visibility and fail-closed misconfiguration behavior? — this affects correctness of D8 and D11.
- [ ] Should production deployment surface a separate `ids-operator-console-notify.service`, a timer + oneshot pattern, or both? — this affects same-host operability and WIRED verification.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: the repo already contains strong notification domain primitives: suppression-aware candidate selection, SQLite-backed delivery state, Telegram dispatch/retry logic, restart-safe alert ingest, explicit operator CLI patterns, and same-host preflight/systemd conventions.

**What we need**: a real runtime ownership contract that turns those primitives into an operable notification subsystem with an explicit worker entrypoint owning the full `ingest refresh -> queue -> dispatch` cycle, plus non-gating health visibility, operator commands, deploy/preflight wiring, and restore/runbook semantics.

**Key constraints from research**:
- No new dependency is required; the right plan should reuse current Python/FastAPI/sqlite/systemd patterns.
- The web app must remain verify-only and must not silently own notification background work.
- The notification path is only truly wired if the shipped worker owns the `ingest -> queue -> dispatch` cycle explicitly, not just dispatch in isolation.
- Delivery-state preservation is already structurally possible through SQLite backup, so planning should focus on operator-facing semantics and verification.

**Institutional warnings to honor**:
- Preserve canonical entrypoints and prove background/runtime paths are actually wired.
- Keep maintenance work out of normal web startup.
- Treat worker output, queue state, and restore visibility as durable runtime evidence, not as shutdown-only or happy-path-only artifacts.
