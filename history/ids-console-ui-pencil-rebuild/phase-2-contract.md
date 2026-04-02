# Phase 2 Contract — The core product surface is live

**Feature:** ids-console-ui-pencil-rebuild
**Phase:** 2 of 3

---

## What Changes In Real Life When This Phase Lands

A security analyst opens the app and can do their full job. Overview shows real system status — how many alerts are queued, what the readiness score looks like, and whether the active bundle is current. Alerts shows the full triage queue with filtering by status. Clicking any alert opens the detail view where the analyst can read the full event context, review the status timeline and investigation notes, update the triage status, and add a note. Operations shows the anomaly table and readiness component breakdown. Reports shows historical summaries with rollup counts by status, severity, and window.

All screens match the Pencil dark-mode design and render real data from the database.

---

## Entry State

- All Phase 1 beads closed: `console.css`, `base.html`, sidebar, `web.py` rewrite, and `login.html` all exist
- 5 authenticated screen routes return `HTTP 501` (not crash, not 404): `/overview`, `/alerts`, `/alerts/{id}`, `/operations`, `/reports`
- 2 mutation POST routes return `HTTP 501`: `POST /alerts/{id}/notes`, `POST /alerts/{id}/status`
- No template files for the 5 new screens exist yet
- Existing page tests assert `501` for these routes (updated in Phase 1)

---

## Exit State (observable, not aspirational)

- `GET /overview` → 200, renders readiness health, alert queue preview (≤8 rows), anomaly preview
- `GET /alerts` → 200, renders triage queue (≤200 rows), status filter working, suppressed rows visible and marked
- `GET /alerts/{alert_id}` → 200, renders full alert context, notes timeline, status timeline, triage form, note form
- `GET /operations` → 200, renders anomaly table (≤200 rows), readiness component matrix
- `GET /reports` → 200, renders rollup summary (alerts by status, by severity, anomaly count, summary table)
- `POST /alerts/{id}/notes` (CSRF) → adds note, redirects back to detail page (303)
- `POST /alerts/{id}/status` (CSRF) → updates triage status, redirects back to detail page (303)
- All 5 templates use `base.html` and inherit the dark shell with sidebar (7 nav items)
- **Tests passing (TDD — tests written first):**
  - `test_ids_operator_console_overview.py` — overview renders, real data visible
  - `test_ids_operator_console_alerts.py` (extended) — queue renders, filter works, suppressed row visible
  - Alert detail renders with notes and status history; note add and status update redirect correctly
  - `test_ids_operator_console_operations.py` — operations renders with anomaly table
  - `test_ids_operator_console_reporting.py` (extended) — reports page renders rollup data
  - `test_ids_operator_console_web.py` updated: 501 assertions for Phase 2 routes changed to 200
- **No regressions on Phase 1 tests** (43 tests still pass)

---

## Demo Walkthrough

1. `pytest tests/console/` — all pass (includes both Phase 1 and Phase 2 tests)
2. Start the app. Log in. Overview page renders with real data (not 501).
3. Navigate to Alerts. See the triage queue. Apply a filter by "acknowledged" status. See filtered results.
4. Click an alert. See its IP addresses, severity, score, status history, and notes. Add a note. See it appear without reload (page redirects back to detail). Change triage status.
5. Navigate to Operations. See the anomaly table and readiness component matrix (schema, admin, data paths, bundle state).
6. Navigate to Reports. See rollup totals and the summary history table.
7. All Phase 1 routes still work: login, logout, sidebar nav, legacy redirects.

---

## What This Phase Unlocks

Phase 3 workers can immediately start on Live Logs, Suppression Rules, and System Health templates — all shared infrastructure (shell, CSS, nav, web.py) is stable and all data patterns are established.

---

## Out Of Scope For This Phase

- Live Logs screen (Phase 3)
- Suppression Rules screen (Phase 3)
- System Health screen (Phase 3)
- Live Logs polling JS (Phase 3)
- Suppression rule mutation forms (Phase 3)
- Alert detail note/status forms may render the form but only the POST handlers make them functional

---

## Signals That Would Force A Pivot

- `build_readiness_payload()` or `build_report_bundle()` raises unexpectedly — investigate before continuing
- No method on `OperatorStore` to fetch a single alert by ID — worker must use `list_alerts()` and filter in Python, or add a thin wrapper
- Jinja2 template inheritance breaks (e.g. `{% block page_wrapper %}` override fails in a child template) — check `base.html` pattern and fix before writing all 5 templates
- Existing Phase 1 tests regress after any web.py change — fix immediately, do not merge a broken Phase 1 regression
