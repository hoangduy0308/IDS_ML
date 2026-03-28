# Discovery Report: IDS Operator Console V1

**Date**: 2026-03-28
**Feature**: `ids-operator-console-v1`
**CONTEXT.md reference**: `history/ids-operator-console-v1/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md`: do not use copy-based rollback when promoting or restoring durable files; prefer atomic rename/replace and fail closed.
- `history/learnings/critical-patterns.md`: validating must reject overlapping write scopes and require spikes for HIGH-risk items before swarming.
- `history/learnings/critical-patterns.md`: daemon-style/operator-facing evidence must be durable during runtime, not only on graceful shutdown.
- `history/learnings/critical-patterns.md`: Linux service packaging should use one config source plus exact-path preflight checks instead of duplicated literals or loose PATH lookup.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | live sensor runtime / operator evidence | Any operator-facing alert/anomaly/summary surface must treat runtime durability as the contract; the dashboard backend must not depend on shutdown-only publishing. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | same-host service deployment | A same-host service should centralize config and validate exact paths in preflight instead of scattering path assumptions. | high |
| `history/learnings/20260328-adapter-rollback-contract.md` | multi-output publishing | Features that publish more than one durable sink should stage/promote outputs transactionally and test rollback as one contract. | medium |
| `history/learnings/20260328-adapter-rollback-contract.md` | anomaly/redaction handling | Export and artifact handling must assume sensitive payloads can leak; default-safe output posture matters. | medium |

---

## Agent A: Architecture Snapshot

> Source: file tree analysis, direct code/doc reads

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts/ids_live_sensor.py` | Long-running same-host producer that composes capture, bridge, runtime, and sink layers. | `scripts/ids_live_sensor.py` |
| `scripts/ids_live_sensor_sinks.py` | Defines durable local outputs: alert JSONL, quarantine JSONL, summary JSONL, journald summary formatting. | `scripts/ids_live_sensor_sinks.py` |
| `scripts/ids_realtime_pipeline.py` | Defines the `model_prediction` and `schema_anomaly` event surface and the JSONL-first runtime boundary. | `scripts/ids_realtime_pipeline.py` |
| `docs/ids_live_sensor_architecture.md` | Documents the current sensor boundary and explicitly lists deferred operator-product features. | `docs/ids_live_sensor_architecture.md` |
| `docs/ids_live_sensor_operations.md` | Documents same-host systemd operation, local output paths, and operator-facing traces. | `docs/ids_live_sensor_operations.md` |
| `deploy/systemd/ids-live-sensor.service` | Concrete same-host Linux deployment shape for the existing producer side. | `deploy/systemd/ids-live-sensor.service` |
| `history/ids-live-host-based-ml-ids/CONTEXT.md` | Locked upstream decisions the new operator platform must wrap, not override. | `history/ids-live-host-based-ml-ids/CONTEXT.md` |

### Entry Points

- **Existing producer daemon**: `F:/Work/IDS_ML_New/scripts/ids_live_sensor.py`
- **Existing runtime CLI**: `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py`
- **Existing deployment**: `F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service`
- **Existing tests**: `F:/Work/IDS_ML_New/tests/test_ids_live_sensor.py`, `F:/Work/IDS_ML_New/tests/test_ids_live_sensor_sinks.py`, `F:/Work/IDS_ML_New/tests/test_ids_realtime_pipeline.py`
- **No existing UI/API/admin service**: the repo currently has no web app, no frontend bundle, no API server, no user database, and no dashboard routes

### Key Files to Model After

- `F:/Work/IDS_ML_New/scripts/ids_live_sensor_sinks.py` — demonstrates the repo’s output-contract discipline, path validation, runtime append behavior, and summary/event formatting to preserve.
- `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` — demonstrates the signal split between `model_prediction` and `schema_anomaly`, plus the repo’s current JSONL-first event model.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service` — demonstrates how same-host services are currently packaged and configured.

---

## Agent B: Pattern Search

> Source: `rg`, direct code reading, prior feature artifacts

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Durable append-only event writing | `scripts/ids_live_sensor_sinks.py` | append JSONL records during runtime, summarize separately | Yes |
| Operational-vs-security signal separation | `scripts/ids_realtime_pipeline.py`, `docs/ids_realtime_pipeline_architecture.md` | `model_prediction` vs `schema_anomaly` are separate event classes | Yes |
| Same-host service configuration | `deploy/systemd/ids-live-sensor.service` | env-driven config + preflight + systemd restart model | Yes |
| Script-first explicit configuration | all `scripts/ids_*.py` entrypoints | `argparse`, local dataclasses, direct file paths | Yes |
| Narrow pytest regression tests | `tests/test_ids_live_sensor*.py`, `tests/test_ids_realtime_pipeline.py` | focused unit/integration tests around one module or contract at a time | Yes |

### Reusable Utilities

- **Event contract**: `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` — already defines the current shape of attack alerts and schema anomalies.
- **Summary formatting**: `F:/Work/IDS_ML_New/scripts/ids_live_sensor_sinks.py` — already defines the sensor summary record and journald line conventions.
- **Path/config discipline**: `F:/Work/IDS_ML_New/scripts/ids_live_sensor_preflight.py` and `F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service` — useful pattern for a future operator-console service preflight and deployment.

### Naming Conventions

- Python modules live under `scripts/` and are imported as `scripts.<module>`.
- Feature docs use `docs/ids_<capability>_architecture.md` or `history/<feature>/...`.
- Tests use `tests/test_ids_<capability>.py`.
- Data carriers and summaries commonly use explicit `@dataclass` models rather than loose untyped state.

---

## Agent C: Constraints Analysis

> Source: local environment, imports scan, file tree, existing docs/tests

### Runtime & Framework

- **Python version**: `3.11.9`
- **Test runner**: `pytest 8.3.5`
- **Repo style**: Python CLI/script-first; no existing web framework or frontend build chain found
- **Dependency manifests at repo root**: none found (`pyproject.toml`, `requirements*.txt`, `package.json`, lockfiles absent)

### Existing Dependencies (Relevant to This Feature)

| Package | Evidence | Purpose |
|---------|----------|---------|
| `pandas` | `scripts/ids_inference.py`, `scripts/ids_realtime_pipeline.py` | runtime data shaping and current IDS event pipeline |
| `catboost` | `scripts/ids_inference.py` | deployed ML model runtime |
| `pytest` | `tests/*` | test execution |
| stdlib `sqlite3` | available in Python 3.11 runtime | candidate same-host embedded storage with no extra service |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| `fastapi` | same-process API + server-rendered/admin-friendly web backend on top of existing Python repo | HIGH — new application framework for this repo |
| `uvicorn` | ASGI app serving for the new backend/dashboard service | HIGH — new runtime server |
| `jinja2` | server-rendered dashboard templates without introducing a full JS toolchain | MEDIUM — new dependency, but directly supported by FastAPI/Starlette docs |
| `python-multipart` | FastAPI form parsing for login/admin form posts | MEDIUM — required if the UI uses standard form submissions |

### Build / Quality Requirements

```bash
# Existing verifiable style in this repo
python -m pytest -q

# Current targeted verification anchors
python -m pytest -q tests/test_ids_realtime_pipeline.py
python -m pytest -q tests/test_ids_live_sensor.py
python -m pytest -q tests/test_ids_live_sensor_sinks.py

# Likely quality gates for this feature
python -m py_compile <new backend/dashboard files>
python -m pytest -q <new operator-console tests>
```

### Storage / Deployment Constraints

- The current producer side is same-host and local-file-based, so v1 backend ingest must respect file-path and process-level operational realities rather than assume a broker or remote event bus.
- The feature is explicitly `single-host / single-admin` in v1, which makes an embedded database viable and keeps deployment aligned with the current Linux systemd model.
- The anomaly/export surface must preserve the repo’s redaction-first posture by default; the product layer should not assume raw source payloads are safe to expose.

---

## Agent D: External Research

> Source: official docs only, because this feature introduces a new web/application layer

### Library Documentation

| Library / Platform | Key Docs | Relevant Point |
|--------------------|----------|----------------|
| FastAPI templates | https://fastapi.tiangolo.com/advanced/templates/ | FastAPI supports server-rendered Jinja templates via Starlette’s templating utilities, which fits a dashboard without a separate SPA toolchain. |
| FastAPI static files | https://fastapi.tiangolo.com/tutorial/static-files/ | Static assets can be mounted directly in the same app, which fits a same-host admin console. |
| FastAPI form handling | https://fastapi.tiangolo.com/tutorial/request-forms/ | Standard HTML form handling is supported, but requires `python-multipart`. |
| Starlette middleware | https://www.starlette.io/middleware/ | The middleware layer includes session-oriented building blocks suitable for same-host signed-cookie admin sessions. |
| Starlette authentication | https://www.starlette.io/authentication/ | Starlette exposes request-level auth/permission hooks if the console later needs stronger route protection. |
| Python `sqlite3` | https://docs.python.org/3.12/library/sqlite3.html | SQLite is built into Python as a lightweight disk-based database, which matches the locked same-host, single-admin deployment shape. |
| Jinja templates | https://github.com/pallets/jinja/blob/main/docs/templates.rst | Template inheritance (`extends`, `block`) is a straightforward way to build a shared operator-console layout. |

### Community / Platform Patterns

- **Pattern**: use a server-rendered admin console first when a Python repo has no existing frontend toolchain.
  - Why it applies: this repo has no React/Vite/Node baseline to reuse, but does have a strong Python/systemd base.
  - Reference: FastAPI templates + static-files docs above.

- **Pattern**: keep same-host operational dashboards on an embedded database before introducing a separate DB service.
  - Why it applies: locked v1 scope is one host, one admin, one sensor-aware schema, with no fleet management yet.
  - Reference: Python `sqlite3` docs.

### Known Gotchas / Anti-Patterns

- **Gotcha**: FastAPI form parsing depends on `python-multipart`.
  - Why it matters: a login or admin-form workflow will fail at runtime if this dependency is omitted.
  - How to avoid: treat form support as an explicit dependency in planning rather than a hidden transitive assumption.

- **Gotcha**: templating/static support solves delivery, not product semantics.
  - Why it matters: the hard part is still the operator data model, ingest loop, status history, suppression semantics, and anomaly redaction boundary.
  - How to avoid: keep the plan centered on domain/storage/ingest first, not just “make pages render”.

- **Anti-pattern**: introducing a separate SPA/frontend toolchain for v1.
  - Common mistake: adding React/Vite/Node package management to a repo that currently has no web stack at all.
  - Correct approach: start with a Python-native server-rendered console and leave a future split frontend as a later option if product needs outgrow it.

- **Anti-pattern**: tying the new dashboard directly into sensor control or config mutation in the first release.
  - Common mistake: collapsing operator console and control plane into one feature.
  - Correct approach: keep v1 read/triage/monitoring-only and consume the existing producer outputs.

---

## Open Questions

> Items not fully resolvable through research alone.

- [ ] Should the same FastAPI app own both HTML dashboard routes and JSON API routes, or should JSON endpoints be kept minimal and internal-only in v1? — this affects file structure and future extensibility.
- [ ] What exact ingest strategy is safest for same-host file outputs: line-tail polling with persisted offsets, directory watcher semantics, or explicit import runs? — this is the main reliability question for the backend service.
- [ ] How should suppression rules be keyed so they reduce alert noise without accidentally hiding distinct future attack alerts? — this affects operator trust in the console.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a solid same-host IDS producer already exists. It emits local `alerts`, `quarantine`, and `summary` outputs, has a clear distinction between security alerts and operational anomalies, and already runs under a systemd-managed Linux deployment model.

**What we need**: a separate same-host operator platform that ingests those outputs into centralized local storage, authenticates a single admin user, exposes dashboard/API routes, supports triage/status-history/notes/reporting/suppression, and sends Telegram notifications without mutating the existing sensor boundary.

**Key constraints from research**:
- The repo is Python-first and currently has no frontend or web-framework baseline.
- A same-host embedded DB and server-rendered web app fit the locked v1 scope better than a distributed service stack.
- The anomaly path must remain distinct from attack alerts and preserve redaction-first handling.
- Login forms and server-rendered templates are easy to support in FastAPI, but require explicit dependency choices.

**Institutional warnings to honor**:
- Keep operator-facing evidence durable during runtime rather than assuming graceful shutdown.
- Keep deployment values centralized and validate exact paths/preconditions for same-host services.
- Treat any multi-output/export workflow transactionally and fail closed on unsafe restore paths.
- Flag ingest reliability, auth, and new framework introduction as HIGH-risk for validating.
