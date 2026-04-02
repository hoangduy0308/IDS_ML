# Phase 1 Contract — Shell, tokens, and auth

**Feature:** ids-console-ui-pencil-rebuild
**Phase:** 1 of 3

---

## What Changes In Real Life When This Phase Lands

An operator opens the browser and sees the new dark-mode VIGIL IDS login screen. They log in, land on a dark shell with a sidebar listing all 9 navigation destinations (including the 3 new ones). They can navigate, log out, and land back at login. The CSS token system is live with the full dark-mode palette from the Pencil design. All old UI files are permanently gone.

---

## Entry State

- Old `ids/console/web.py`, `ids/console/templates/`, `ids/console/static/console.css`, `ids/console/static/console.js` still exist
- No `deactivate_suppression_rule()` method in `OperatorStore`
- No dark-mode CSS token layer
- No `base.html` with sidebar listing 9 nav items

---

## Exit State (observable, not aspirational)

- `ids/console/web.py` is a complete rewrite: all routes registered, login + logout implemented, authenticated page routes return HTTP 501 stub (will be filled in Phase 2–3)
- `ids/console/static/console.css` has all 40 CSS variables from the Pencil design file in dark-mode values, plus shared layout + shell component styles
- `ids/console/templates/base.html` renders a dark-mode shell with correct font CDN links, sidebar include, and main content slot
- `ids/console/templates/partials/app_sidebar.html` contains 9 nav items including Live Logs, Suppression Rules, System Health
- `ids/console/templates/login.html` matches the Pencil screen 07 design
- `ids/console/static/console.js` contains sidebar toggle and timestamp formatter (polling added in Phase 3)
- `ids/console/db.py` has `deactivate_suppression_rule(rule_id: int) -> bool` added and tested
- All old templates and CSS are deleted
- **Tests passing:**
  - Auth redirects (unauthenticated → /login)
  - Login form (valid credentials → /overview, invalid → error)
  - Logout (CSRF form → /login)
  - Legacy redirects (`/dashboard → /overview`, `/anomalies → /operations`)
  - App factory exposes all 9+3 routes
  - `deactivate_suppression_rule()` soft-deactivates and returns bool

---

## Demo Walkthrough

1. `pytest tests/console/test_ids_operator_console_auth.py` — all pass
2. `pytest tests/console/test_ids_operator_console_web.py -k "redirect or login or logout"` — all pass
3. `pytest tests/console/test_ids_operator_console_db.py -k "deactivate"` — passes
4. Start the app locally. Open browser. Login screen is dark-mode centered card.
5. Log in with admin credentials. See dark sidebar with 9 items.
6. Check that navigating to unimplemented screens returns a clean stub (not a crash).
7. Log out. Return to login screen.

---

## What This Phase Unlocks

Phase 2 workers can immediately start on individual screen templates (`overview.html`, `alerts.html`, etc.) without touching `web.py` or `console.css` — the shared shell is stable and locked.

---

## Out Of Scope For This Phase

- Any authenticated page template beyond `login.html` (those are Phase 2–3)
- Live Logs polling JS (Phase 3)
- Suppression Rules form handling (Phase 3)
- System Health template (Phase 3)

---

## Signals That Would Force A Pivot

- `render_template()` helper in the new `web.py` fails to inject `primary_nav` with all 9 items → fix before Phase 2 starts
- CSS variable names don't match Pencil token names exactly → cross-check with CONTEXT.md token table before marking Phase 1 done
- `server.py` import breaks after `web.py` rewrite → fix immediately, this is the entrypoint wiring risk
