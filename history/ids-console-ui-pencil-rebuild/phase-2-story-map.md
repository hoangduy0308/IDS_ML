# Phase 2 Story Map — The core product surface is live

**Feature:** ids-console-ui-pencil-rebuild
**Phase:** 2 of 3

---

## Story 2.1 — Overview screen (TDD)

**What happens:** Tests for `/overview` are written first and fail. Then the route handler and `overview.html` template are implemented to make them pass. The overview renders real system data: readiness health badges, an alert queue preview (≤8 rows), and an anomaly preview table.

**Why now:** Overview is the landing page after login — the first thing a security analyst sees. It has no dependencies on any other Phase 2 story. It exercises the three most common data access patterns (readiness payload, alert list, anomaly list) which every other screen also uses, so validating them here first catches data contract issues early.

**Contributes to phase exit state:**
- `GET /overview` → 200 with real data (not 501)
- `test_ids_operator_console_overview.py` tests passing
- `test_ids_operator_console_web.py` 501 assertion for `/overview` changed to 200

**Creates:**
- `tests/console/test_ids_operator_console_overview.py` (written first, failing, then passing)
- `ids/console/templates/overview.html` (extends base.html, uses `{% block page_wrapper %}` pattern)
- `ids/console/web.py` — `/overview` route handler (replaces 501 stub)

**Data contracts this story must honor:**
- `build_readiness_payload(config, include_sensitive=True)` → readiness dict with component statuses
- `store.list_alerts()` → filter in Python to get queue preview (≤8 rows, newest first)
- `store.list_anomalies()` → anomaly preview rows

**Unlocks:** Stories 2.2–2.4 can all proceed in parallel after this — the data access pattern is validated. Story 2.1 also confirms that `overview.html` correctly uses `{% block content %}` inside the base shell (not `{% block page_wrapper %}`).

**Done looks like:**
- `pytest tests/console/test_ids_operator_console_overview.py` passes
- `pytest tests/console/test_ids_operator_console_web.py -k overview` passes (200, not 501)
- All 43 Phase 1 tests still pass
- `GET /overview` in a live app renders readiness badges, ≤8 alert rows, and anomaly preview rows
- No `_prepare_health_snapshot` call anywhere — only `build_readiness_payload()`

---

## Story 2.2 — Alerts and Alert Detail screens (TDD)

**What happens:** Tests for `/alerts` (triage queue, status filter, suppressed row visibility) and `/alerts/{alert_id}` (identifiers, status timeline, notes timeline, triage form, note form) are written first and fail. The route handlers and two templates (`alerts.html`, `alert_detail.html`) are implemented to make them pass. The POST handlers for notes and status update are implemented and tested for CSRF + redirect behavior.

**Why now:** Alerts is the primary daily workflow for a security analyst — the highest-value screen pair. Alert Detail is tightly coupled to Alerts (it shares the same DB access path: `list_alerts()` filtered by ID), so implementing them together avoids a gap where Alerts links to a 501 stub.

**Contributes to phase exit state:**
- `GET /alerts` → 200 with full triage queue (≤200 rows), filter parameter working, suppressed rows visible and marked
- `GET /alerts/{alert_id}` → 200 with full event context, status history, notes, triage form, note form
- `POST /alerts/{id}/notes` (CSRF) → adds note, 303 redirect to detail page
- `POST /alerts/{id}/status` (CSRF) → updates triage status, 303 redirect to detail page
- `test_ids_operator_console_alerts.py` tests passing (queue + filter + suppressed + detail + note POST + status POST)
- `test_ids_operator_console_web.py` 501 assertions for these routes changed to 200/303

**Creates:**
- `tests/console/test_ids_operator_console_alerts.py` (written first, failing, then passing — includes queue, filter, detail, POST note, POST status)
- `ids/console/templates/alerts.html` (extends base.html, status filter form, triage queue table, suppressed row styling)
- `ids/console/templates/alert_detail.html` (extends base.html, identifiers panel, status history timeline, notes timeline, triage form, note form)
- `ids/console/web.py` — 4 route handlers replacing 501 stubs: `GET /alerts`, `GET /alerts/{id}`, `POST /alerts/{id}/notes`, `POST /alerts/{id}/status`

**Data contracts this story must honor:**
- `store.list_alerts()` → full list, filter by `status` param in Python (no `.filter()` on DB side)
- No `get_alert_by_id()` exists — use `list_alerts()` and filter by ID in Python; return 404 if not found
- `store.update_alert_status(alert_id, status, updated_by)` → updates status
- `store.add_alert_note(alert_id, note, added_by)` → adds note
- `store.list_alert_notes(alert_id)` → ordered note records
- `store.list_alert_status_history(alert_id)` → ordered status change records
- CSRF token must be validated on both POST routes (same pattern as existing logout POST)
- POST success → `RedirectResponse(url=f"/alerts/{id}", status_code=303)`

**Unlocks:** Stories 2.3 and 2.4 have no dependency on Alerts/Detail — they can execute before, after, or concurrently. This story completing closes the largest interactive surface of Phase 2.

**Done looks like:**
- `pytest tests/console/test_ids_operator_console_alerts.py` passes (queue renders, status filter works, suppressed row visible, detail renders, note POST redirects, status POST redirects)
- `pytest tests/console/test_ids_operator_console_web.py -k "alerts or alert"` passes (200/303, not 501)
- All 43 Phase 1 tests still pass
- Filtering `/alerts?status=acknowledged` in a live app returns only acknowledged rows
- Clicking an alert opens its detail with IP identifiers, severity badge, status history, and existing notes
- Adding a note redirects back to the detail with the new note visible

---

## Story 2.3 — Operations screen (TDD)

**What happens:** Tests for `/operations` are written first and fail. Then the route handler and `operations.html` are implemented. The operations screen renders the anomaly table (≤200 rows) and the readiness component matrix (schema, admin, data paths, bundle state).

**Why now:** Operations has no dependency on Alerts or Reports. It reuses the same data contracts as Overview (`list_anomalies()` and `build_readiness_payload()`) but presents a deeper view — the full anomaly table instead of a preview, and the full readiness breakdown instead of just badges. After Overview validates these data patterns, Operations builds on proven ground.

**Contributes to phase exit state:**
- `GET /operations` → 200 with anomaly table and readiness component breakdown (not 501)
- `test_ids_operator_console_operations.py` tests passing
- `test_ids_operator_console_web.py` 501 assertion for `/operations` changed to 200

**Creates:**
- `tests/console/test_ids_operator_console_operations.py` (written first, failing, then passing)
- `ids/console/templates/operations.html` (extends base.html, anomaly table, readiness component matrix)
- `ids/console/web.py` — `/operations` route handler (replaces 501 stub)

**Data contracts this story must honor:**
- `store.list_anomalies()` → full anomaly list (≤200 rows); most recent first
- `build_readiness_payload(config, include_sensitive=True)` → component breakdown dict; same call as Overview
- Template context: `anomalies`, `readiness` (both injected by route handler)

**Unlocks:** Stories 2.2 and 2.4 are independent. This story being small and self-contained means it is a good candidate to run concurrently with Story 2.2 if multiple workers are available.

**Done looks like:**
- `pytest tests/console/test_ids_operator_console_operations.py` passes
- `pytest tests/console/test_ids_operator_console_web.py -k operations` passes (200, not 501)
- All 43 Phase 1 tests still pass
- `GET /operations` in a live app renders an anomaly table with rows and a readiness component matrix with status indicators

---

## Story 2.4 — Reports screen (TDD)

**What happens:** Tests for `/reports` are written first and fail. Then the route handler and `reports.html` are implemented. The reports screen renders rollup totals (alert counts by status and severity, anomaly count) and a summary history table of recent reporting windows.

**Why now:** Reports is the final screen and has no dependency on Alerts or Operations stories. It uses a different data source (`build_report_bundle()` / `build_report_rollup()`) that has not been touched in Phase 2 yet, so it is isolated. It makes sense to implement it last so all data contract patterns are well-understood before tackling this distinct one.

**Contributes to phase exit state:**
- `GET /reports` → 200 with rollup summary and summary history table (not 501)
- `test_ids_operator_console_reporting.py` (extended) tests passing
- `test_ids_operator_console_web.py` 501 assertion for `/reports` changed to 200

**Creates:**
- `tests/console/test_ids_operator_console_reporting.py` (extended — new rollup and summary table assertions written first, failing, then passing)
- `ids/console/templates/reports.html` (extends base.html, rollup counters, summary history table)
- `ids/console/web.py` — `/reports` route handler (replaces 501 stub)

**Data contracts this story must honor:**
- `build_report_bundle()` → full reporting data (summary windows, rollup by status/severity, anomaly count)
- `build_report_rollup()` → aggregate totals for the rollup counters section
- `store.list_recent_summaries()` → recent summary records for the history table
- If `build_report_bundle()` raises unexpectedly, stop and investigate before continuing (signal from phase-2-contract.md)

**Unlocks:** After this story closes, all 5 Phase 2 screen templates exist. The combined exit state of stories 2.1–2.4 satisfies the full Phase 2 exit state in `phase-2-contract.md`. Phase 3 workers can immediately start on Live Logs, Suppression Rules, and System Health.

**Done looks like:**
- `pytest tests/console/test_ids_operator_console_reporting.py` passes (rollup totals render, summary table renders)
- `pytest tests/console/test_ids_operator_console_web.py -k reports` passes (200, not 501)
- All 43 Phase 1 tests still pass
- `GET /reports` in a live app renders rollup counter cards (by status, by severity, anomaly count) and a history table of recent reporting windows

---

## Story Ordering Rationale

```
2.1 (Overview) → first because it validates all three core data access patterns
2.2 (Alerts + Detail) → highest-value interactive surface, built while patterns are fresh
2.3 (Operations) → read-only, reuses patterns from 2.1, builds on sequential file ownership
2.4 (Reports) → distinct data source (report bundle), runs last to close the phase
```

All four stories modify `web.py` and `test_ids_operator_console_web.py`. These shared files require serial ownership — no concurrent execution. The bead dependency chain (wnnq→ibzr→egf5→6g24) enforces this. Phase 2 uses a single-worker sequential swarm (same model as Phase 1).

Story 2.1 must complete before 2.2 because it validates that the template inheritance pattern (`{% block content %}`, not `{% block page_wrapper %}`) works correctly in child templates — catching any base.html issues before the larger screens are built.

---

## Shared Implementation Notes (all stories)

- All 5 templates extend `base.html` using `{% extends "base.html" %}` and override `{% block content %}` — do NOT override `{% block page_wrapper %}` (that is reserved for the login layout)
- All route handlers get the store via `_open_store(request)` and inject context via `render_template()`
- CSRF tokens are already injected by `render_template()` and must be validated on all POST handlers (match the existing logout pattern)
- Suppressed alerts (`is_suppressed=True`) must remain visible in the alerts queue but be clearly marked — do not filter them out

---

## Story-To-Bead Mapping

*(To be filled after bead creation)*

| Story | Bead IDs |
|-------|---------|
| 2.1 — Overview screen (TDD) | `ids_ml_new-wnnq` |
| 2.2 — Alerts + Alert Detail (TDD) | `ids_ml_new-ibzr` |
| 2.3 — Operations screen (TDD) | `ids_ml_new-egf5` |
| 2.4 — Reports screen (TDD) | `ids_ml_new-6g24` |

Epic: `ids_ml_new-k8c1`

---

## Phase 2 → Phase 3 Handoff Condition

All Phase 2 stories passing (43 Phase 1 tests + all Phase 2 tests) → Phase 3 workers can pick up Live Logs, Suppression Rules, and System Health immediately. All shared infrastructure (web.py route patterns, template inheritance, data access patterns) is proven and stable.
