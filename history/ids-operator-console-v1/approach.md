# Approach: IDS Operator Console V1

**Date**: 2026-03-28
**Feature**: `ids-operator-console-v1`
**Based on**:
- `history/ids-operator-console-v1/discovery.md`
- `history/ids-operator-console-v1/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Producer-side event generation | `scripts/ids_live_sensor.py`, `scripts/ids_live_sensor_sinks.py` emit durable local `alerts`, `quarantine`, and `summary` outputs | A consumer-facing service that ingests those outputs into a queryable store | Medium |
| Alert/event semantics | `model_prediction` and `schema_anomaly` are already distinct in runtime/docs | Persisted operator-facing data model that preserves this split while adding triage state, notes, history, suppression, and export | New |
| User-facing product surface | No UI, no API, no auth, no admin workflow | Combined console with login, dashboard pages, triage flows, reporting/export, Telegram notifications | New |
| Storage | Filesystem JSONL + journald only | Embedded same-host operational store for alerts, anomalies, summaries, offsets, notes, suppression rules, and admin state | New |
| Deployment | Existing producer has same-host `systemd` unit and preflight | Separate same-host operator-console service with aligned config and deployment pattern | Medium |

---

## 2. Recommended Approach

Implement `ids-operator-console-v1` as a new Python-native operator service layered on top of the current sensor outputs: a `FastAPI` application serving both HTML dashboard routes and minimal JSON endpoints, using server-rendered `Jinja2` templates, and persisting operator data into a same-host `sqlite3` database. The service should run separately from `ids_live_sensor`, ingest the existing `alerts/quarantine/summary` JSONL files via a background importer that tracks file identity + offsets and tolerates partial appended lines, and expose an authenticated single-admin console for combined alert triage and sensor-health visibility. Alert triage state, notes, status history, suppression rules, Telegram delivery state, and export/report history all live in the operator datastore, while raw detection remains owned by the sensor pipeline. Login/session handling should use a simple same-host admin model with signed cookies, explicit password-hash storage, and CSRF-aware form actions rather than a heavyweight multi-user auth subsystem. This keeps the architecture aligned with the repo’s current Python/systemd/file-first shape, honors the locked IDS-not-IPS boundary, and avoids introducing a Node frontend toolchain or a separate database server for a one-host v1.

### Why This Approach

- It matches the repo’s existing strengths at `scripts/ids_live_sensor.py` and `scripts/ids_live_sensor_sinks.py`: Python modules, explicit configs, same-host operation, and local durable outputs.
- It honors locked decisions `D2`, `D5`, `D8`, `D10`, `D14`, `D17`, and `D20` from `CONTEXT.md` by keeping the sensor as producer, the console as separate service, and the UI as read/triage/monitoring only.
- It preserves the current semantic split already documented in `docs/ids_realtime_pipeline_architecture.md`, which is critical for `D9` and the redaction-first anomaly boundary.
- It minimizes new infrastructure by choosing a Python-native web layer and embedded storage instead of adding a SPA toolchain or a remote DB service to a repo that currently has neither.
- It directly incorporates discovery gotchas: explicit form dependency, exact-path same-host packaging, and durable operator evidence that does not depend on graceful shutdown.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Web stack | `FastAPI` + `Jinja2` + mounted static assets in one process | Best fit for a Python-first repo with no existing frontend toolchain; supports both HTML console and future JSON endpoints |
| Storage | stdlib `sqlite3` embedded DB with app-managed schema bootstrap and explicit offset/state tables | Matches same-host single-admin v1 without adding a separate DB service or ORM migration burden |
| Ingest | Background importer tails current `alerts/quarantine/summary` JSONL files using persisted file identity + offsets and partial-line protection | Honors `D8`, keeps producer boundary intact, and avoids changing the sensor contract |
| Auth | Single-admin login with server-side protected routes, signed session cookies, password-hash storage, and CSRF-aware form handling | Satisfies `D6`/`D14` without opening multi-user/role complexity |
| Alert workflow | Persist triage state, notes, status history, and suppression in operator DB, separate from source alert payloads | Satisfies `D7`, `D16`, `D18`, and `D19` without mutating sensor outputs |
| Anomaly handling | Store and display anomalies in a separate operational lane with redaction-first defaults | Satisfies `D9` and `D11` |
| Notifications | Telegram notifier driven from persisted alert events after suppression evaluation | Satisfies `D12`/`D13` while keeping notification failures isolated from sensor ingest |
| Deployment | Separate same-host `systemd` service with centralized env config and preflight checks | Reuses the proven deployment posture from the live sensor work |

---

## 3. Alternatives Considered

### Option A: Separate SPA frontend plus REST backend

- Description: add a new JS frontend stack (for example React/Vite) and a separate Python API.
- Why considered: richer UI flexibility and cleaner long-term separation between frontend and backend.
- Why rejected: the repo currently has no Node/package-manager baseline, no frontend build chain, and no webapp conventions. For v1 this would create a second toolchain, increase operational overhead, and delay delivery of the first operator console.

### Option B: Read JSONL directly from the dashboard with no database

- Description: serve pages that query the live JSONL files directly and compute state on the fly.
- Why considered: avoids introducing an embedded datastore and keeps the first slice extremely thin.
- Why rejected: the locked workflow requires notes, status history, suppression, export, login state, and notification bookkeeping. Those operator concerns need persistent relational state beyond raw JSONL files.

### Option C: External DB/service stack from day one

- Description: introduce PostgreSQL plus a more distributed backend shape for the console.
- Why considered: stronger path for future multi-host growth.
- Why rejected: `D3` and `D20` intentionally lock v1 to one host/sensor and same-host deployment. An external DB adds infrastructure without solving the immediate product gap.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| FastAPI/Jinja operator service foundation | **HIGH** | New application framework and app structure for this repo, plus blast radius across new package layout, entrypoint, and templates | Spike in validating |
| JSONL ingest with persisted offsets | **HIGH** | No existing precedent for a long-running consumer that tails producer files, handles partial lines and possible file replacement/rotation, and recovers cleanly after restart | Spike in validating |
| Admin auth/session boundary | **HIGH** | Security-sensitive and novel to this repo; bad choices around cookie/session/CSRF handling could expose the console or create brittle login behavior | Spike in validating |
| Alert/anomaly relational data model | **MEDIUM** | New schema, but a straightforward translation of locked workflow and existing event types | Plan review + tests |
| Alert triage + suppression service layer | **MEDIUM** | New domain logic, but no external integrations beyond the local DB | Proceed with focused tests |
| Combined console UI | **MEDIUM** | No prior UI pattern in repo, but server-rendered pages are conventional once the backend contract exists | Proceed with UI/route tests |
| Telegram notification delivery | **HIGH** | External integration, retry/failure semantics, and suppression interaction are all new | Spike in validating |
| Reporting/export surfaces | **MEDIUM** | New output path that must respect anomaly redaction and operator filters | Proceed with focused tests |
| Same-host deployment unit + preflight | **MEDIUM** | Strong precedent exists from the sensor service, but the new service adds its own config/env paths and secret handling | Validate with deployment-focused tests |

### Risk Classification Reference

```
Pattern in codebase?        → YES = LOW base
External dependency?        → YES = HIGH
Blast radius > 5 files?    → YES = HIGH
Otherwise                   → MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `FastAPI/Jinja operator service foundation`: prove the selected Python web stack integrates cleanly into this repo without forcing a separate frontend toolchain or awkward script imports.
- `JSONL ingest with persisted offsets`: prove the importer handles append-only runtime files, restart recovery, partial/duplicate line boundaries, and file replacement safely.
- `Admin auth/session boundary`: prove the single-admin session/login approach is secure and practical for same-host deployment, including cookie/session and CSRF behavior.
- `Telegram notification delivery`: prove outbound delivery failure does not block local persistence or triage workflow and that suppression semantics are applied at the right layer.

---

## 5. Proposed File Structure

```text
scripts/
  ids_operator_console/
    __init__.py
    config.py                    # env/config loading for same-host console
    db.py                        # sqlite bootstrap, connections, schema helpers
    ingest.py                    # JSONL importer + offset tracking
    auth.py                      # single-admin auth/session utilities
    alerts.py                    # triage, notes, status history, suppression logic
    reporting.py                 # export/report helpers
    notifications.py             # Telegram delivery hooks and retry bookkeeping
    web.py                       # FastAPI app factory and route registration
    templates/
      base.html
      login.html
      dashboard.html
      alert_detail.html
      anomalies.html
      reports.html
    static/
      console.css
      console.js
  ids_operator_console_server.py # service entrypoint / uvicorn launcher
  ids_operator_console_preflight.py
tests/
  test_ids_operator_console_config.py
  test_ids_operator_console_db.py
  test_ids_operator_console_ingest.py
  test_ids_operator_console_auth.py
  test_ids_operator_console_alerts.py
  test_ids_operator_console_web.py
  test_ids_operator_console_reporting.py
  test_ids_operator_console_notifications.py
docs/
  ids_operator_console_architecture.md
deploy/systemd/
  ids-operator-console.service
```

---

## 6. Dependency Order

```text
Layer 1 (sequential): Foundation — config, sqlite bootstrap, app/service scaffold
Layer 2 (parallel): Ingest pipeline + auth/session boundary
Layer 3 (parallel): Triage/suppression domain + reporting/notification support
Layer 4 (sequential): Combined console UI/routes plus minimal sensor-aware JSON endpoints
Layer 5 (sequential): Deployment unit/preflight/docs and end-to-end integration hardening
```

### Parallelizable Groups

- Group A: foundation scaffold — must land first because every other bead depends on the new package/config/store shape.
- Group B: ingest pipeline and auth/session boundary — can proceed in parallel after foundation because their write scopes can stay isolated.
- Group C: triage/suppression domain and reporting/notification logic — can begin once foundation exists; they consume the store/auth contracts but do not need the final UI.
- Group D: combined console UI/routes — depends on ingest + auth + triage contracts being stable.
- Group E: deployment unit/docs and end-to-end fit-and-finish — depends on app entrypoint and core routes existing.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Operator-facing evidence must be durable during runtime | The console ingests persisted sensor outputs as the source of truth instead of relying on transient in-memory hooks |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Same-host Linux services should centralize config and validate exact paths in preflight | The plan includes a separate operator-console service with env-driven config and explicit deployment/preflight work |
| `history/learnings/20260328-adapter-rollback-contract.md` | Multi-output/export flows should be treated as one contract | Reporting/export work is isolated and should verify safe multi-output behavior instead of ad hoc file writes |
| `history/learnings/20260328-adapter-rollback-contract.md` | Validation must enforce disjoint write scopes and spike HIGH-risk items | Bead decomposition is layered and the risk map explicitly flags the items validating must spike before execution |

---

## 8. Open Questions for Validating

- [ ] Is line-tail ingest with persisted offsets robust enough for the current sensor outputs, including partial writes and future file replacement/rotation, or does validating discover a better same-host ingest seam? — if wrong, the whole data flow into the console becomes brittle.
- [ ] Is the planned single-admin session approach secure and simple enough without adding a heavier auth library, especially around CSRF and cookie handling? — if wrong, v1 either ships an unsafe console or takes on unexpected dependency/complexity.
- [ ] Should Telegram notification delivery live inside the app process or behind a local async job loop once validating inspects failure modes more deeply? — if wrong, notifier failures could leak into request or ingest paths.
