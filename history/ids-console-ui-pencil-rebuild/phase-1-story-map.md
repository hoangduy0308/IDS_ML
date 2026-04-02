# Phase 1 Story Map — Shell, tokens, and auth

**Feature:** ids-console-ui-pencil-rebuild
**Phase:** 1 of 3

---

## Story 1.1 — Delete old UI and extend the DB

**What happens:** The old UI files are removed. The new `deactivate_suppression_rule()` DB method is added and passes its test.

**Why now:** Workers can't write new files while old conflicting files exist. The DB method is a standalone change with no dependencies — doing it first means Phase 3 workers never hit a missing method.

**Contributes to phase exit state:** Old files gone (entry state cleared). DB extension tested.

**Creates:** Deleted files + new `OperatorStore.deactivate_suppression_rule()` + passing DB test.

**Unlocks:** Story 1.2 can safely create new template files without conflict.

**Done looks like:**
- `git status` shows all old templates and static files as deleted
- `pytest tests/console/test_ids_operator_console_db.py -k deactivate` passes
- `OperatorStore.deactivate_suppression_rule(rule_id=<id>)` sets `is_active=0`, returns `True`; calling again returns `False`

**Files written:** `ids/console/db.py` (extend), `tests/console/test_ids_operator_console_db.py` (extend)
**Files deleted:** `ids/console/web.py`, `ids/console/templates/*`, `ids/console/static/console.css`, `ids/console/static/console.js`

---

## Story 1.2 — CSS token system and shared shell

**What happens:** The dark-mode CSS token layer is live. `base.html` and the sidebar partial render the correct shell.

**Why now:** Every screen inherits from `base.html` and `console.css`. Without this, Story 1.3 cannot render any page — the app factory needs templates to return responses.

**Contributes to phase exit state:** CSS variables live, shared shell works.

**Creates:** `console.css` (token layer + shell styles), `base.html`, `partials/app_sidebar.html`, `partials/top_utility_bar.html`.

**Unlocks:** Story 1.3 can write the app factory and login template knowing what CSS classes and Jinja2 blocks are available.

**Done looks like:**
- `console.css` contains all 40 CSS variables matching CONTEXT.md token table (dark values)
- `base.html` renders a valid HTML document with font CDN links, `class="dark"` on `<html>`, sidebar include, and `{% block content %}` slot
- Sidebar partial contains exactly 9 nav items: Overview, Alerts, Operations, Reports, Live Logs, Suppression Rules, System Health — plus Login/Logout affordance
- `top_utility_bar.html` has title slot + action slot

**Files written:** `ids/console/static/console.css`, `ids/console/templates/base.html`, `ids/console/templates/partials/app_sidebar.html`, `ids/console/templates/partials/top_utility_bar.html`

---

## Story 1.3 — New web.py skeleton + login/logout (TDD)

**What happens:** Tests for auth, redirects, and app factory are written first and fail. Then the new `web.py` is written to make them pass. `login.html` is implemented.

**Why now:** Shell and CSS exist. The app factory can now register all routes against real templates. Login must work before any authenticated route can be exercised by tests.

**Contributes to phase exit state:** All routes registered, login/logout implemented, tests passing, `render_template()` injects correct nav with 9 items.

**Creates:** `ids/console/web.py` (full rewrite), `ids/console/templates/login.html`, `ids/console/static/console.js` (sidebar toggle + timestamp), updated tests.

**Unlocks:** Phase 2 workers can start immediately on individual screen templates — all shared infrastructure is stable.

**Done looks like:**
- Tests written first (failing), then passing:
  - `test_ids_operator_console_auth.py`: login valid/invalid, logout CSRF, unauthenticated redirect
  - `test_ids_operator_console_web.py`: legacy redirects (`/dashboard`, `/anomalies`), app factory exposes all routes
  - `test_ids_operator_console_config.py`: app factory registers `/live-logs`, `/suppression-rules`, `/system-health`
- `create_operator_console_web_app()` registers all 9+3 HTML routes + JSON APIs + legacy redirects
- `render_template()` injects `primary_nav` with 9 items
- Phase 2/3 unimplemented routes return HTTP 501 (not 500, not crash)
- `login.html` matches Pencil screen 07: centered card, VIGIL IDS branding, error state works
- `console.js`: sidebar toggle (hamburger on mobile), timestamp formatter
- `server.py` import still resolves — `create_operator_console_web_app` callable from factory

**Files written:** `ids/console/web.py`, `ids/console/templates/login.html`, `ids/console/static/console.js`, updated `tests/console/test_ids_operator_console_auth.py`, `tests/console/test_ids_operator_console_web.py`, `tests/console/test_ids_operator_console_config.py`

---

## Story Ordering Rationale

```
1.1 (delete + DB) → must clear old files before writing new ones
1.2 (CSS + shell) → templates needed before app factory can render
1.3 (web.py + login, TDD) → all dependencies ready
```

Stories 1.1 and 1.2 can be partially parallelized (DB extension in 1.1 is independent of CSS work in 1.2) but the file deletions in 1.1 must complete before 1.2 writes new files in `templates/`.

---

## Story-To-Bead Mapping

*(To be filled after bead creation)*

| Story | Bead IDs |
|-------|---------|
| 1.1 — Delete + DB extension | `ids_ml_new-o9gb` |
| 1.2 — CSS token layer + shell | `ids_ml_new-8kka` |
| 1.3 — web.py skeleton + login (TDD) | `ids_ml_new-bpwm` |

Epic: `ids_ml_new-k8c1`

---

## Phase 1 → Phase 2 Handoff Condition

All Phase 1 tests passing + `console.css` + `base.html` + sidebar present + login works → Phase 2 workers can pick up screen templates immediately without coordination overhead.
