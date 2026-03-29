# Discovery Report: IDS Same-Host Stack Runtime Hardening

**Date**: 2026-03-29
**Feature**: `ids-same-host-stack-runtime-hardening`
**CONTEXT.md reference**: `history/ids-same-host-stack-runtime-hardening/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md` — keep startup verify-only, keep exact-path preflight contracts, keep one activation contract for production model selection, and treat entrypoint/runtime wiring as a mandatory `WIRED` check.
- `history/learnings/critical-patterns.md` — validate write scopes and HIGH-risk spikes before swarming; this feature must decompose into disjoint runtime/deploy/docs slices.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | live sensor runtime | Preflight must use exact absolute paths and the daemon must keep durable runtime evidence independent from shutdown. | high |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | operator console runtime | Review must verify `EXISTS / SUBSTANTIVE / WIRED`; real routes and runtime entrypoint must stay aligned. | high |
| `history/learnings/20260329-operator-console-production-hardening.md` | operator console ops/proxy | Runtime startup must remain verify-only; migration/bootstrap/recovery stay on explicit operator commands; proxy inputs and secret contract must be wired through runtime + preflight + deploy artifacts together. | high |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | model bundle activation | Production model selection must stay on one activation record; no reintroduction of split path overrides at stack level. | high |
| `history/learnings/20260329-notification-runtime-contracts.md` | notification runtime | Notification ownership must stay outside the web process, long-running by default under systemd, and restore verification must include redrive/status rather than visibility alone. | high |

---

## Agent A: Architecture Snapshot

> Source: file tree analysis, targeted code reading

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts/ids_model_bundle*.py` | Activation-record verify/promote/rollback contract for the live model bundle | `scripts/ids_model_bundle.py`, `scripts/ids_model_bundle_manage.py` |
| `scripts/ids_live_sensor*.py` | Live sensor daemon and exact-path preflight | `scripts/ids_live_sensor.py`, `scripts/ids_live_sensor_preflight.py` |
| `scripts/ids_operator_console*.py` | Console runtime entrypoint, manage CLI, verify-only preflight | `scripts/ids_operator_console_server.py`, `scripts/ids_operator_console_manage.py`, `scripts/ids_operator_console_preflight.py` |
| `scripts/ids_operator_console/` | Console config, readiness, backup/restore, notification runtime, web app factory | `scripts/ids_operator_console/config.py`, `scripts/ids_operator_console/health.py`, `scripts/ids_operator_console/ops.py`, `scripts/ids_operator_console/web.py` |
| `deploy/systemd/` | Linux same-host service contracts | `deploy/systemd/ids-live-sensor.service`, `deploy/systemd/ids-operator-console.service`, `deploy/systemd/ids-operator-console-notify.service` |
| `deploy/nginx/` | Reverse-proxy seam for operator-console edge | `deploy/nginx/ids-operator-console.conf.example` |
| `docs/` | Shipped architecture and operations runbooks for component-level contracts | `docs/ids_live_sensor_operations.md`, `docs/ids_operator_console_operations.md`, `docs/final_model_bundle.md` |
| `tests/` | Existing verification surfaces for bundle lifecycle, sensor preflight/runtime, console preflight/ops/web, notification runtime | `tests/test_ids_model_bundle_manage.py`, `tests/test_ids_live_sensor_preflight.py`, `tests/test_ids_live_sensor.py`, `tests/test_ids_operator_console_preflight.py`, `tests/test_ids_operator_console_ops.py`, `tests/test_ids_operator_console_notifications.py`, `tests/test_ids_operator_console_web.py` |

### Entry Points

- **CLI / lifecycle**
  - `scripts/ids_model_bundle_manage.py` — bundle `status|verify|promote|rollback`
  - `scripts/ids_operator_console_manage.py` — console `status|migrate|bootstrap-admin|backup|restore|smoke|notify-*`
  - `scripts/ids_live_sensor_preflight.py` — sensor deploy gate
  - `scripts/ids_operator_console_preflight.py` — console/worker deploy gate
- **Server**
  - `scripts/ids_operator_console_server.py` — canonical app launcher wired to `create_operator_console_web_app`
- **Workers / daemons**
  - `scripts/ids_live_sensor.py` — live sensor daemon
  - `scripts/ids_operator_console_manage.py notify-worker` — notification worker loop
- **Linux deployment**
  - `deploy/systemd/*.service` — current supervisor entrypoints
  - `deploy/nginx/ids-operator-console.conf.example` — edge proxy sample

### Key Files to Model After

- `scripts/ids_operator_console_manage.py` — already exposes a thin orchestration CLI over lower-level ops helpers; good precedent for a stack manager that composes instead of owning runtime logic.
- `scripts/ids_operator_console/ops.py` — shows how to build smoke/backup/restore wrappers that return machine-readable payloads.
- `scripts/ids_operator_console/health.py` — shows per-component readiness payloads with explicit non-gating degraded states.
- `scripts/ids_model_bundle_manage.py` — shows the expected JSON-first lifecycle UX for activation state and failure-closed errors.
- `deploy/systemd/ids-live-sensor.service` and `deploy/systemd/ids-operator-console*.service` — show the current environment/source-of-truth split that the stack layer must preserve, not duplicate semantically.

---

## Agent B: Pattern Search

> Source: targeted implementation and test review

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Bundle lifecycle CLI | `scripts/ids_model_bundle_manage.py` | Thin argparse CLI over strict domain helpers, JSON payloads, fail-closed contract errors | Yes |
| Console lifecycle CLI | `scripts/ids_operator_console_manage.py` | One management surface wrapping status, bootstrap, backup/restore, smoke, and notification flows | Yes |
| Console smoke wrapper | `scripts/ids_operator_console/ops.py::run_smoke_checks` | In-process smoke via canonical app factory + readiness payload | Yes |
| Console readiness payload | `scripts/ids_operator_console/health.py::build_readiness_payload` | Componentized health with top-level `ready` plus named subcomponents | Yes |
| Sensor preflight | `scripts/ids_live_sensor_preflight.py::validate_preflight` | Exact-path contract validation against Linux/runtime requirements | Yes |
| Console preflight | `scripts/ids_operator_console_preflight.py::validate_preflight` | Verify-only startup gate that checks secret, proxy, schema, admin bootstrap, and optional notification pairing | Yes |
| Console restore path | `scripts/ids_operator_console/ops.py::restore_backup` | Offline-only restore with explicit operator confirmation and post-restore inspection | Yes |

### Reusable Utilities

- **Activation status**: `scripts/ids_model_bundle.py::build_bundle_status_payload` — current machine-readable source for “active bundle runtime-ready or not”.
- **Bundle resolution**: `scripts/ids_model_bundle.py::resolve_active_model_bundle` — fail-closed active bundle verifier used by sensor preflight/runtime.
- **Console config loading**: `scripts/ids_operator_console/config.py::load_operator_console_config` — one source of truth for env/secret/path resolution.
- **Console smoke + restore helpers**: `scripts/ids_operator_console/ops.py` — existing wrappers that a stack orchestrator can call instead of duplicating behavior.
- **Notification status/redrive**: `scripts/ids_operator_console_manage.py notify-status|notify-redrive` — existing recovery semantics for the outbound worker domain.
- **Readiness detail**: `scripts/ids_operator_console/health.py::build_readiness_payload` — already distinguishes active bundle and notification states.

### Naming Conventions

- Runtime/lifecycle CLIs use `ids_<domain>_manage.py` or `ids_<domain>_preflight.py`.
- Subcommands are verb-first and operational: `status`, `verify`, `promote`, `rollback`, `migrate`, `bootstrap-admin`, `smoke`, `notify-worker`, `notify-redrive`.
- Deploy artifacts are named after systemd service identity: `ids-live-sensor.service`, `ids-operator-console.service`, `ids-operator-console-notify.service`.
- Tests are seam-specific and file-aligned: `tests/test_<artifact>.py`.

---

## Agent C: Constraints Analysis

> Source: codebase layout, deploy files, tests, config loader

### Runtime & Framework

- **Language/runtime**: Python CLI/services
- **Web framework**: FastAPI + Uvicorn for the operator console
- **Persistent store**: SQLite for the console/notification runtime
- **Supervisor assumption**: systemd-managed same-host Linux services
- **Edge assumption**: reverse proxy terminates TLS and forwards trusted headers to the console app

### Existing Dependencies (Relevant to This Feature)

| Package / Surface | Purpose |
|-------------------|---------|
| `argparse`-style CLIs | Existing operational entrypoints are all Python CLI driven |
| FastAPI + Starlette `TestClient` | Console app factory and smoke verification |
| SQLite | Console DB, notification state, summary-backed visibility |
| systemd unit contracts | Production runtime wiring for sensor, console, worker |
| Nginx sample config | Production-facing proxy seam for the console |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None required by current discovery | The feature can be built by composing existing Python/runtime/deploy surfaces | LOW |

### Build / Quality Requirements

The repo currently relies on direct pytest execution against seam-specific modules rather than a root build system:

```bash
python -m pytest -q tests/test_ids_model_bundle_manage.py
python -m pytest -q tests/test_ids_live_sensor_preflight.py tests/test_ids_live_sensor.py
python -m pytest -q tests/test_ids_operator_console_preflight.py tests/test_ids_operator_console_ops.py tests/test_ids_operator_console_notifications.py tests/test_ids_operator_console_web.py
```

For this feature, new verification will almost certainly need:

```bash
python -m pytest -q tests/test_ids_same_host_stack_*.py
python -m pytest -q <existing seam tests above>
```

### Filesystem / Deployment Constraints

- Sensor runtime currently expects:
  - `/var/lib/ids-live-sensor/active_bundle.json`
  - `/var/lib/ids-live-sensor` writable spool/state root
  - `/var/log/ids-live-sensor` writable output/log root
- Console/runtime currently expects:
  - `/var/lib/ids-operator-console/operator_console.db`
  - `/etc/ids-operator-console/ids-operator-console.env`
  - `/etc/ids-operator-console/console.secret`
  - optional Telegram secret-file inputs
- App checkout and scripts are assumed at `/opt/ids_ml_new`
- Current preflight surfaces validate exact files/dirs, not abstract resources; the stack layer should preserve that style.

### Testability Constraints

- `build_bundle_status_payload()` is testable in isolation and already returns `runtime_ready`.
- Sensor preflight is testable in-repo, but “runtime health” beyond preflight is not currently exposed as a separate canonical status command; planning must choose a seam that does not invent a fake source of truth.
- Console smoke/readiness is already machine-readable and unit-tested.
- Notification status, worker, and redrive are already machine-readable and unit-tested.
- Reverse proxy seam is documented/config-based only today; any stack-level proxy check must stay optional and bounded.

---

## Agent D: External Research

> Source: skipped intentionally

No external research required for planning. Discovery indicates this feature can and should be implemented by composing existing repo-local patterns and deploy/runtime contracts rather than introducing a new library, framework, or external integration.

### Known Gotchas / Anti-Patterns

- Do not turn the stack orchestrator into a new owner of runtime or mutation logic; that would violate locked decisions D1-D3.
- Do not create a second source of truth for active bundle state; reuse activation-record and summary-backed visibility seams.
- Do not make proxy availability erase the distinction between internal runtime health and operator-edge degradation.
- Do not reintroduce startup mutation of console schema/bootstrap just because a stack bootstrap helper exists.

---

## Open Questions

> Items that were not resolvable through research alone.

- [ ] What is the narrowest reliable “live sensor runtime health” seam the stack manager can use for status/smoke without needing a new long-running control-plane concept?
- [ ] Should stack backup/restore expose thin wrapper commands or remain verification-only while docs orchestrate the mutation flow across bundle + console state?
- [ ] What is the minimal optional reverse-proxy verification that is real enough for production rollout but still non-gating and easy to test?

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: the repo already ships hardened component-level contracts for model activation, live sensor preflight/runtime, operator console preflight/smoke/backup/restore, and notification worker lifecycle, all with matching tests and deployment artifacts.

**What we need**: one same-host stack contract that composes those existing pieces into canonical host-level bootstrap, preflight, smoke/status, restart/recovery, and post-restore verification paths without smearing ownership across failure domains.

**Key constraints from research**:
- The stack layer should be another thin Python management surface, not a new runtime/control-plane.
- Live sensor lacks a standalone runtime `status/smoke` command today, so the approach must choose a testable health seam carefully.
- Console and notification already expose machine-readable lifecycle/status surfaces; the stack plan should reuse them directly.
- Reverse proxy remains a production-facing seam but not a top-level readiness gate.

**Institutional warnings to honor**:
- Keep verify-only startup separate from operator mutation paths.
- Keep production model selection on one activation contract.
- Treat entrypoint/deploy/runtime wiring as a first-class review target.
- Force validation to spike any plan choice that risks shared write scopes or an invented sensor-health source.
