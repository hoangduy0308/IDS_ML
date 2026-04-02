# Phase Plan — ids-console-ui-pencil-rebuild

---

## Feature Summary

Replace the entire IDS operator console UI — all templates, CSS, JS, and route logic — with a new 9-screen dark-mode design taken from the Pencil design file at `design/UI`. The backend data layer, auth model, and DB schema are unchanged (except adding one soft-deactivate method for suppression rules). Three screens that don't exist yet (Live Logs, Suppression Rules, System Health) get real backend routes wired to existing infrastructure. All implementation follows TDD: failing tests first, then implementation.

---

## Phase 1 — Shell, tokens, and auth: the app looks right and lets you in

**What changes for real people and systems after this phase lands:**

An operator opens the browser and immediately sees the new dark-mode interface. The login screen is the new Pencil design. After logging in, the sidebar shows all 9 navigation items (including the 3 new ones). Logging out works. The CSS token system is live with the full dark-mode palette. All old UI files are gone. Routes that aren't implemented yet return a clean 404 or stub — the app does not crash.

**Why this is Phase 1:**
Every screen inherits from `base.html` and `console.css`. The sidebar is shared by 8 of 9 screens. Without the shared shell working correctly, no screen can be correctly built or tested. Login/logout must work before any authenticated route can be opened.

**Simplest demo:**
1. Open the app. See the new dark-mode login screen (VIGIL IDS branding, centered card).
2. Log in. See the dark sidebar with 9 nav items, the Overview stub page.
3. Log out. Return to the login screen.

**Stories:**

### Story 1.1 — Delete old UI and extend the DB
Old files go away. The new `deactivate_suppression_rule()` DB method is added and tested.
- Delete: `web.py`, all `templates/`, `static/console.css`, `static/console.js`
- Add to `db.py`: `deactivate_suppression_rule(rule_id: int) -> bool` (soft-deactivate via `is_active = 0`)
- Add test: `test_ids_operator_console_db.py` — deactivate method + verify soft-delete behavior

### Story 1.2 — CSS token system and shared shell
The dark-mode design token layer is live. `base.html` and the sidebar partial work.
- Write `console.css`: all 40 CSS variables (dark mode values), layout primitives, sidebar styles, top-bar styles, card/table base styles
- Write `base.html`: dark-mode html shell, sidebar include, main slot, CDN font links (Geist, JetBrains Mono)
- Write `partials/app_sidebar.html`: 280px sidebar with logo, 9 nav items (Overview, Alerts, Alert Detail link, Operations, Reports, Live Logs, Suppression Rules, System Health), user footer
- Write `partials/top_utility_bar.html`: title slot + action slot

### Story 1.3 — New web.py skeleton + login/logout (TDD)
The app factory is rewritten. All routes are registered. Login and logout work with new templates.
- Write failing tests first: auth redirects, login, logout, legacy redirects, app factory exposes all 9 routes
- Write new `web.py`: app factory, all routes registered (Phase 2/3 screens return HTTP 501 until implemented), full login/logout implementation
- Write `login.html`: centered card, VIGIL IDS branding, form, error state
- Tests pass

**Phase 1 exit state:**
- `ids/console/web.py` is a complete rewrite — all routes registered, login/logout implemented
- `console.css` has all dark-mode CSS variables and shared component styles
- `base.html` + sidebar partial render correctly with 9 nav items
- Login/logout works with new templates
- Legacy redirects pass (`/dashboard → /overview`, `/anomalies → /operations`)
- `deactivate_suppression_rule()` added and tested in db.py
- All old UI files are deleted
- Tests: auth, redirects, DB extension, app factory — all passing

---

## Phase 2 — Existing 6 screens: the core product surface is live

**What changes for real people and systems after this phase lands:**

A security analyst can open the app and do their full job. The Overview shows system status and alert pressure. The Alerts queue lists active alerts with filtering. Clicking an alert opens the detail view where the analyst can update triage status and add investigation notes. The Operations screen shows anomalies and readiness. Reports shows historical summaries. All screens match the Pencil dark-mode design.

**Why this is Phase 2:**
The foundation exists. The backend data contracts for these screens are unchanged — it's implementation work against known data, not new infrastructure. These screens also have the most established test patterns, making TDD straightforward.

**Simplest demo:**
1. Log in. Overview shows real alert counts, readiness badges, and anomaly preview.
2. Click into Alerts. Filter by "new" status. See filtered results.
3. Click an alert. See raw identifiers, severity, status history. Update the triage status.
4. Navigate to Operations. See anomaly table and readiness component breakdown.
5. Navigate to Reports. See summary rollup tables.

**Stories:**

### Story 2.1 — Overview screen (TDD)
Write test for `/overview` rendering hero metrics, alert snapshot, readiness matrix. Implement `overview.html`. Test passes.

### Story 2.2 — Alerts and Alert Detail screens (TDD)
Write tests for `/alerts` (filter, suppressed rows, queue counts) and `/alerts/{alert_id}` (identifiers, timeline, note/status forms). Implement both templates. Tests pass.

### Story 2.3 — Operations screen (TDD)
Write test for `/operations` (anomaly table, health sidebar, readiness components). Implement `operations.html`. Test passes.

### Story 2.4 — Reports screen (TDD)
Write test for `/reports` (summary table, rollup counts by status/severity, anomaly history). Implement `reports.html`. Test passes.

**Phase 2 exit state:**
- All 6 original screens render with Pencil fidelity and real data
- Tests for all 6 screens pass (including suppressed alert visibility, triage state filtering, timeline rendering)
- No regression on Phase 1 tests

---

## Phase 3 — New 3 screens: the expanded console surface is live

**What changes for real people and systems after this phase lands:**

The operator can now access three new capabilities directly in the browser. Live Logs shows a scrolling terminal-style feed of recent alerts and anomalies that refreshes every 5–10 seconds. Suppression Rules shows all active rules and lets the operator add new rules or deactivate existing ones — with immediate effect on the alert queue. System Health shows a single-page summary of all readiness components, health snapshot, and active bundle state.

**Why this is Phase 3:**
These routes need the foundation shell and shared CSS patterns established in Phase 1 to build on. Live Logs polling JS also benefits from the base JS patterns that are established. Suppression Rules needs the `deactivate_suppression_rule()` DB method from Phase 1 to already exist.

**Simplest demo:**
1. Navigate to `/live-logs`. See a scrolling dark terminal with recent alert and anomaly events. Watch new entries appear without a page reload.
2. Navigate to `/suppression-rules`. See the active rules table. Click "Add rule", fill the form, submit — new rule appears. Click "Deactivate" on a rule — it disappears from the active list.
3. Navigate to `/system-health`. See a full breakdown of readiness components, active bundle status, notification state, and data paths.
4. Run the full test suite — all pass including entrypoint wiring regression.

**Stories:**

### Story 3.1 — System Health screen (TDD)
Write test for `/system-health` (readiness components, health snapshot, active bundle visibility). Implement `system_health.html`. Test passes.
This is simplest of the three new screens — pure read-only from existing endpoints.

### Story 3.2 — Suppression Rules screen (TDD)
Write tests for `/suppression-rules` GET (table of active rules), POST (add rule, CSRF), POST `/suppression-rules/{id}/deactivate` (CSRF, returns deactivated). Implement `suppression_rules.html` with add form and deactivate buttons. Tests pass.

### Story 3.3 — Live Logs screen + polling JS (TDD)
Write test for `/live-logs` HTML render (filter bar, log area, detail panel) and for the polling API contract (`/api/v1/alerts` + `/api/v1/anomalies` endpoints are tested in Phase 1 already). Implement `live_logs.html` + polling JS in `console.js`. Test passes.

### Story 3.4 — Verification: full suite, entrypoint wiring, legacy smoke
Run the full test suite. Fix any gaps. Add regression test: `server.py` import of `create_operator_console_web_app` exposes `/overview` (not just `/healthz`). Confirm legacy redirects pass. Update `.khuym/STATE.md`.

**Phase 3 exit state:**
- All 9 screens render with Pencil fidelity
- All 3 new routes have tests and implementation
- Suppression CRUD (add + deactivate) works with CSRF
- Live Logs polling JS refreshes the feed every 5–10s
- Full test suite passes (all existing + all new)
- Entrypoint wiring regression test passes
- Legacy redirects pass
- STATE.md updated to execution-complete

---

## Phase Ordering Rationale

```
Phase 1 (Foundation) → required before any screen can be built
Phase 2 (Core screens) → established data contracts, known patterns, parallel-friendly
Phase 3 (New screens + verification) → needs foundation + patterns + DB extension from P1
```

The bead decomposition within Phase 2 (stories 2.1–2.4) supports parallel execution by different workers since each screen maps to disjoint template files.

---

## What Phase 1 Unlocks

Approving Phase 1 lets workers start immediately on the highest-risk shared files (`web.py`, `console.css`, `base.html`) without conflicting with page-level work.

**Prepare Phase 1 next.**
