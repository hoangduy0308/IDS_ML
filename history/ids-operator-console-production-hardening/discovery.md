# Discovery Report: IDS Operator Console Production Hardening

**Date**: 2026-03-29
**Feature**: `ids-operator-console-production-hardening`
**CONTEXT.md reference**: `history/ids-operator-console-production-hardening/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md`: service entrypoints must stay wired to the canonical app factory; runtime/deployment verification must check `EXISTS / SUBSTANTIVE / WIRED`, not just module presence.
- `history/learnings/critical-patterns.md`: Linux services in this repo are safer when they use one exact-path config source plus dedicated preflight validation rather than duplicated literals or shell lookup.
- `history/learnings/critical-patterns.md`: validation must reject overlapping write scopes and require spikes for every HIGH-risk planning assumption before execution.
- `history/learnings/critical-patterns.md`: rollback and restore flows must fail closed and avoid copy-based recovery that broadens the write surface.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | operator console runtime | Keep the service entrypoint wired to the real FastAPI app factory and add regression coverage that proves the runnable entrypoint exposes real feature routes. | high |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | review/integration | Review production-facing service work with the three-layer check `EXISTS / SUBSTANTIVE / WIRED`, especially around entrypoints, units, background jobs, and deployment artifacts. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | systemd/preflight | Same-host Linux services should use centralized config plus exact-path preflight instead of duplicated or implicit runtime discovery. | high |
| `history/learnings/20260328-adapter-rollback-contract.md` | rollback/restore | Multi-output publish/rollback must be treated as one contract, and restore should stay on atomic rename/replace paths rather than copy-based fallback. | high |

---

## Agent A: Architecture Snapshot

> Source: file tree analysis, local code reading, existing docs

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts.ids_operator_console.config` | runtime config loading for host/port/paths/session secret | `scripts/ids_operator_console/config.py` |
| `scripts.ids_operator_console.auth` | password hashing, session bootstrap, CSRF validation | `scripts/ids_operator_console/auth.py` |
| `scripts.ids_operator_console.db` | SQLite bootstrap, operator store primitives, notification/admin/session tables | `scripts/ids_operator_console/db.py` |
| `scripts.ids_operator_console.ingest` | JSONL ingest with persisted offsets and parse-error anomaly capture | `scripts/ids_operator_console/ingest.py` |
| `scripts.ids_operator_console.alerts` | triage workflow, suppression evaluation, combined-console snapshot helpers | `scripts/ids_operator_console/alerts.py` |
| `scripts.ids_operator_console.reporting` | export/report bundle generation for alerts/anomalies/summaries | `scripts/ids_operator_console/reporting.py` |
| `scripts.ids_operator_console.notifications` | Telegram queue/dispatch, retry bookkeeping, failure isolation | `scripts/ids_operator_console/notifications.py` |
| `scripts.ids_operator_console.web` | canonical FastAPI app factory, dashboard/auth/API routes, current `/healthz` surface | `scripts/ids_operator_console/web.py` |
| `scripts.ids_operator_console_server` | uvicorn launcher and canonical service entrypoint | `scripts/ids_operator_console_server.py` |
| `scripts.ids_operator_console_preflight` | exact-path startup contract validation for systemd | `scripts/ids_operator_console_preflight.py` |
| deployment surface | same-host unit packaging | `deploy/systemd/ids-operator-console.service` |

### Entry Points

- **Server**: `F:/Work/IDS_ML_New/scripts/ids_operator_console_server.py`
- **Web app factory**: `F:/Work/IDS_ML_New/scripts/ids_operator_console/web.py`
- **Preflight**: `F:/Work/IDS_ML_New/scripts/ids_operator_console_preflight.py`
- **Systemd unit**: `F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service`
- **Regression anchors**:
  - `F:/Work/IDS_ML_New/tests/test_ids_operator_console_config.py`
  - `F:/Work/IDS_ML_New/tests/test_ids_operator_console_auth.py`
  - `F:/Work/IDS_ML_New/tests/test_ids_operator_console_ingest.py`
  - `F:/Work/IDS_ML_New/tests/test_ids_operator_console_notifications.py`
  - `F:/Work/IDS_ML_New/tests/test_ids_operator_console_web.py`

### Key Files to Model After

- `F:/Work/IDS_ML_New/scripts/ids_live_sensor_preflight.py` - demonstrates the existing repo pattern for a dedicated exact-path preflight gate before a systemd service starts.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service` - demonstrates the current same-host unit shape and operational hardening baseline reused elsewhere in the repo.
- `F:/Work/IDS_ML_New/tests/test_ids_live_sensor_preflight.py` - demonstrates how runtime-contract preflight logic is verified with targeted regression tests.
- `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py` - demonstrates the repo’s stricter rollback/backup expectations for atomic promotion and surviving backup artifacts after restore failure.

---

## Agent B: Pattern Search

> Source: grep, local file reads, existing feature history

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Canonical app factory wiring | `scripts/ids_operator_console_server.py`, `scripts/ids_operator_console/web.py` | single real app factory launched by service entrypoint | Yes - must be preserved and extended |
| Exact-path service preflight | `scripts/ids_operator_console_preflight.py`, `scripts/ids_live_sensor_preflight.py` | dedicated Python preflight script invoked by `ExecStartPre=` | Yes - expand rather than replace |
| Same-host systemd packaging | `deploy/systemd/ids-operator-console.service`, `deploy/systemd/ids-live-sensor.service` | env-driven unit with state/log directories and preflight gate | Yes |
| File-tail ingest with restart safety | `scripts/ids_operator_console/ingest.py` | persisted file identity + offset tracking with partial-line protection | Yes - likely base for data-path readiness checks |
| Notification failure isolation | `scripts/ids_operator_console/notifications.py` | local persistence first, outbound retry bookkeeping after | Yes - informs backup/retention scope |
| Redaction-first anomaly export | `scripts/ids_operator_console/reporting.py`, `tests/test_ids_operator_console_reporting.py` | anomaly exports default to redacted output unless payload is explicitly requested | Yes |

### Reusable Utilities

- **Config parsing**: `F:/Work/IDS_ML_New/scripts/ids_operator_console/config.py` - existing env/path resolution and runtime directory creation, but currently too thin for production secrets/proxy settings.
- **Auth helpers**: `F:/Work/IDS_ML_New/scripts/ids_operator_console/auth.py` - password hashing, CSRF validation, and signed-cookie session bootstrap already exist.
- **Exact-path validators**: `F:/Work/IDS_ML_New/scripts/ids_operator_console_preflight.py` - reusable file/directory/parent-path checks for expanded deployment contract validation.
- **Store primitives**: `F:/Work/IDS_ML_New/scripts/ids_operator_console/db.py` - existing operator DB wrapper can host schema versioning, migration verification, retention, and backup metadata.
- **Operator-console regression shape**: `F:/Work/IDS_ML_New/tests/test_ids_operator_console_*.py` - tests are already script-first and can be extended without a new framework.

### Naming Conventions

- Python modules live under `scripts/` and are imported as `scripts.<module>`.
- Service-adjacent helper scripts follow `scripts/ids_<capability>_<purpose>.py`.
- Docs follow `docs/ids_<capability>_<topic>.md` or `history/<feature>/...`.
- Tests follow `tests/test_ids_<capability>*.py`.
- Runtime data surfaces use explicit dataclasses and plain stdlib/sqlite primitives rather than ORMs or heavy framework abstractions.

---

## Agent C: Constraints Analysis

> Source: local environment, imports scan, file reads, current unit/test surfaces

### Runtime & Framework

- **Python version**: `3.11.9`
- **SQLite runtime**: `3.45.1`
- **Test runner**: `pytest 8.3.5`
- **Installed web stack already in environment**:
  - `fastapi 0.115.12`
  - `starlette 0.46.2`
  - `uvicorn 0.34.0`
  - `jinja2 3.1.6`
  - `multipart 0.0.20`
- **Repo style**: script-first Python repo; no package manifest at root (`pyproject.toml`, `requirements*.txt`, `setup.cfg`, `setup.py`, `Pipfile`, `poetry.lock` all absent)

### Existing Dependencies (Relevant to This Feature)

| Package | Version / Evidence | Purpose |
|---------|--------------------|---------|
| `fastapi` | installed; used in `scripts/ids_operator_console/web.py` | operator web routes and HTML/API surface |
| `starlette` | installed; used for `SessionMiddleware` and `TestClient` | session middleware and testing |
| `uvicorn` | installed; used in `scripts/ids_operator_console_server.py` | ASGI service runtime |
| `jinja2` | installed; templates referenced in web app | server-rendered console views |
| `multipart` | installed; implied by FastAPI `Form(...)` usage | login/logout/form POST parsing |
| stdlib `sqlite3` | Python runtime + `has_backup=True` | operator DB, explicit migration path, backup primitive |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None required at planning time | current hardening scope can be implemented on top of existing FastAPI/Starlette/Uvicorn/Jinja2/sqlite3/systemd patterns | LOW |

### Build / Quality Requirements

```bash
# Existing proven verification anchors
python -m py_compile scripts/ids_operator_console_server.py scripts/ids_operator_console_preflight.py scripts/ids_operator_console/*.py
python -m pytest -q tests/test_ids_operator_console_config.py tests/test_ids_operator_console_auth.py tests/test_ids_operator_console_db.py
python -m pytest -q tests/test_ids_operator_console_ingest.py tests/test_ids_operator_console_notifications.py tests/test_ids_operator_console_reporting.py tests/test_ids_operator_console_web.py

# Full-suite regression anchor already used by the previous feature
python -m pytest -q
```

### Deployment / Storage Constraints

- Current operator-console unit still hardcodes `IDS_OPERATOR_CONSOLE_SECRET_KEY=change-me` in `deploy/systemd/ids-operator-console.service`; production hardening must remove placeholder-secret deployment as a valid default path.
- `SessionMiddleware` is currently configured with `https_only=False` in `scripts/ids_operator_console/web.py`, which is acceptable for local/dev but not as the default production posture behind HTTPS termination.
- Current runtime has only `/healthz`, and it reports basic liveness plus database path; there is no richer readiness/config/schema/data-path health contract yet.
- `scripts/ids_operator_console_server.py` currently passes only `host`, `port`, `log_level`, and `reload` into `uvicorn.run()`. There is no explicit proxy-header trust or root-path configuration surface yet.
- `scripts/ids_operator_console/db.py` bootstraps schema idempotently but has no schema version table, migration registry, retention policy, backup metadata, or restore verification primitive.
- `scripts/ids_operator_console_preflight.py` validates exact paths and placeholder secret rejection, but not admin bootstrap state, schema version readiness, secret-file references, reverse-proxy assumptions, or restore-related contracts.
- Current runtime has no operator CLI/script for admin bootstrap, password rotation, migration, backup, restore, retention, or smoke checks.
- `scripts/ids_operator_console/auth.py` persists authenticated state only in the signed session cookie; although the DB has `admin_sessions`, current request auth does not consult or expire them, so production session hardening is a real gap rather than a cosmetic improvement.
- There is no operator-console production runbook or reverse-proxy example yet; docs only contain architecture narrative at `docs/ids_operator_console_architecture.md`.

### Database / Storage

- **Store**: stdlib `sqlite3` with WAL mode and explicit SQL bootstrap in `scripts/ids_operator_console/db.py`
- **Current bootstrap mode**: `CREATE TABLE IF NOT EXISTS` schema creation only; no versioned migrations
- **Current source-of-truth split**:
  - operator-owned state lives in SQLite
  - upstream sensor evidence remains in JSONL producer outputs
- **Implication for hardening**: backup/restore should center on operator-owned DB + config/reference metadata, while preserving the upstream-producer boundary locked in CONTEXT.md

---

## Agent D: External Research

> Source: official docs only
> Guided by locked decisions in CONTEXT.md

### Library / Platform Documentation

| Library / Platform | Key Docs | Relevant Point |
|--------------------|----------|----------------|
| FastAPI behind a proxy | https://fastapi.tiangolo.com/advanced/behind-a-proxy | FastAPI expects trusted proxy headers to be explicitly enabled; this affects redirect URLs, HTTPS awareness, and any reverse-proxied deployment. |
| Uvicorn settings | https://www.uvicorn.org/settings/ | `--proxy-headers`, `--forwarded-allow-ips`, and `--root-path` are the runtime knobs that control trusted forwarded headers and subpath deployment. |
| systemd execution environment | https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html | systemd exposes a read-only `$CREDENTIALS_DIRECTORY` for `LoadCredential=`/`SetCredential=` and fails with `EXIT_CREDENTIALS` if credential setup fails, which is useful for fail-closed secret handling. |
| Python sqlite3 | https://docs.python.org/3/library/sqlite3.html | `sqlite3` is the recommended built-in DB API and exposes `Connection.backup()` in the Python runtime, giving a first-party backup primitive without adding another database layer. |

### Known Gotchas / Anti-Patterns

- **Gotcha**: FastAPI/Uvicorn will not safely trust `X-Forwarded-*` headers unless trusted proxy IPs are configured.
  - Why it matters: redirects and generated URLs can point at `http://127.0.0.1:...` instead of the public HTTPS URL if proxy trust is left implicit.
  - How to avoid: make trusted proxy/header settings part of the production config contract and smoke it explicitly.

- **Gotcha**: `root_path` is required if the reverse proxy strips a path prefix.
  - Why it matters: docs, redirects, and route assumptions drift if the app is mounted under a subpath and the runtime never receives that prefix.
  - How to avoid: expose `root_path` or equivalent proxy contract in config and test it as part of deployment readiness.

- **Gotcha**: systemd credentials are version-sensitive platform features.
  - Why it matters: `LoadCredential=`/`$CREDENTIALS_DIRECTORY` are excellent for hardened deployments, but not every target host may run a recent-enough systemd.
  - How to avoid: plan for file-path based secrets as the baseline contract and make credential-style paths an additive, supported deployment mode.

- **Anti-pattern**: implement SQLite “backup” by copying the live DB file directly.
  - Common mistake: filesystem copy of the WAL-backed DB path while the app is live, then assuming the artifact is consistent.
  - Correct approach: use a first-party SQLite backup primitive or an explicit offline contract, then wrap artifact promotion/restore in atomic file handling and fail-closed checks.

---

## Open Questions

> Items that will be resolved in synthesis/approach, not by more raw discovery.

- [ ] Should the production secret contract be `file-path first with optional systemd credential examples`, or should planning require `LoadCredential=` as the canonical deployment mode? - this changes deployment portability and test surface.
- [ ] Should migration, backup, restore, retention, and smoke actions live behind one operator CLI (`manage`) or several single-purpose scripts? - this affects operator ergonomics and bead boundaries.
- [ ] Should reverse-proxy readiness ship as one concrete `nginx` example plus a proxy-agnostic contract, or docs-only with no repo artifact? - this affects whether review can verify `WIRED` at the deploy-artifact level.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a working same-host operator console on `FastAPI + Jinja2 + sqlite3` with ingest, triage, reporting, notifications, preflight, and a canonical app entrypoint already fixed to the real app factory.

**What we need**: a production-hardening layer around that baseline: proxy-aware runtime/deploy config, fail-closed secret handling, explicit migration/upgrade workflow, backup/restore/retention operations, richer readiness/smoke surfaces, and operator-facing deployment/runbook artifacts.

**Key constraints from research**:
- The repo already has the needed Python/web/runtime dependencies installed, but there is still no package manifest, so planning should avoid unnecessary new dependencies.
- Reverse-proxy correctness depends on explicit Uvicorn/FastAPI forwarded-header and optional `root_path` handling; leaving proxy trust implicit is not acceptable.
- systemd credential directories are useful but platform-dependent; file-path secret references remain the most portable baseline.
- SQLite already provides an in-runtime backup primitive, so planning can avoid unsafe file-copy backup schemes.

**Institutional warnings to honor**:
- Preserve canonical app-factory wiring and add deployment/runtime verification that proves the real production surface is served.
- Treat backup/restore as a transactional contract and fail closed on restore ambiguity instead of using copy-based recovery.
- Keep service config centralized and exact-path validated through preflight.
