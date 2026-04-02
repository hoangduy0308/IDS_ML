# Approach — ids-console-ui-pencil-rebuild

---

## Gap Analysis

| Gap | Current state | Required state |
|-----|--------------|----------------|
| HTML templates | 9 old Jinja2 templates (light mode, old design) | 9 new templates matching Pencil dark-mode design |
| CSS | `console.css` — no token layer, old design | CSS variables from Pencil + component-based dark-mode CSS |
| JS | `console.js` — only timestamp formatter | New `console.js`: sidebar toggle, polling for Live Logs |
| `web.py` | 6 HTML screens, 4 JSON APIs, 2 legacy redirects | Full rewrite + 3 new routes + suppression CRUD |
| DB method | No `deactivate_suppression_rule()` in `OperatorStore` | Add soft-deactivate method to `db.py` |
| Route `/live-logs` | Does not exist | New route serving alerts+anomalies event feed |
| Route `/suppression-rules` | Does not exist | New GET + POST + POST deactivate routes |
| Route `/system-health` | Does not exist | New route serving readyz/healthz + health snapshot |
| Tests | Tests for 6 screens only | Tests for all 9 screens + suppression CRUD + DB extension |

---

## Recommended Approach

**Three-phase sequential delivery, TDD throughout.**

### Phase 1 — Shell, tokens, and auth (foundation first)
Delete all old UI files. Build the shared foundation that every screen depends on:
- CSS token layer (`console.css`) with all Pencil CSS variables in dark mode
- `base.html` with sidebar partial, top-bar slot, footer
- Sidebar partial with all 9 navigation items (including 3 new ones)
- New `web.py` with all routes registered (most returning 501 stubs) and login/logout fully implemented
- `deactivate_suppression_rule()` added to `db.py`
- Tests for login, logout, auth redirects, legacy redirects written first

**Why first:** Every screen inherits from `base.html` and `console.css`. Without the shared shell landing correctly, no page can be correctly implemented. Login/logout must work before any authenticated page can be tested.

### Phase 2 — Existing 6 screens
Implement the 6 original screens with full Pencil fidelity, one story per screen group:
- Overview, Alerts, Alert Detail, Operations, Reports
- Each screen: write failing test → implement template → test passes

**Why second:** Foundation exists. Backend data contracts are unchanged. These screens have existing test patterns to model against.

### Phase 3 — New 3 screens + verification
Implement the 3 new routes with real data wiring:
- System Health: simple read-only view from readyz/healthz
- Suppression Rules: full CRUD with add/deactivate forms
- Live Logs: event feed with client-side polling JS
- Verification: full test suite, entrypoint wiring test, legacy redirect smoke

**Why third:** Requires foundation + core screens to exist. Live Logs polling JS also benefits from having the base JS patterns established.

---

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| Incremental patch of existing web.py | D2 locks full rewrite; existing CSS is not token-based and cannot be systematically extended to dark mode |
| Tailwind CSS | D4 locks no-framework; adds build step dependency |
| SSE for Live Logs | D8 locks polling; SSE adds streaming endpoint complexity inconsistent with server-rendered approach |
| Phase the new screens before existing screens | Existing screens have established test patterns — doing them first lets new screen tests model after |
| Alpine.js for interactivity | Deferred to planning — pure vanilla JS is sufficient for sidebar toggle and polling |

---

## Risk Map

| Risk | Level | Mitigation |
|------|-------|-----------|
| Sidebar nav registration must include all 9 items (3 new routes not yet in primary_nav helper) | MEDIUM | `render_template()` injects `primary_nav` — update this helper in Phase 1 to include all 9 items |
| `deactivate_suppression_rule()` not atomic under concurrent requests | LOW | SQLite single-writer model; same-host deployment means no real concurrency risk |
| Geist + JetBrains Mono fonts require CDN availability | LOW | Add to `base.html` via Google Fonts/Bunny; fallback to system-ui / monospace in CSS |
| Live Logs polling hits `/api/v1/alerts` + `/api/v1/anomalies` — existing JSON endpoints | LOW | These endpoints are unchanged; polling is read-only |
| Legacy redirect tests must pass after full rewrite | LOW | `/dashboard` and `/anomalies` redirects are simple 303 routes — include in Phase 1 test suite |
| `server.py` entrypoint wiring might drift during rewrite | LOW | Verified: `server.py` imports `create_operator_console_web_app` — keep this import intact; add regression test in Phase 3 |
| CSS variable naming must match Pencil exactly | LOW | Full token list is locked in CONTEXT.md with exact hex values — map 1:1 in Phase 1 |
| Suppression CRUD POST forms need CSRF | MEDIUM | Established pattern: copy from existing `/alerts/{id}/notes` CSRF handler pattern |

---

## Proposed File Structure

```
ids/console/
  web.py                         ← full rewrite (all 9+3 routes)
  db.py                          ← extend only (add deactivate_suppression_rule)
  templates/
    base.html                    ← dark-mode shell, sidebar include, nav
    login.html                   ← centered card, no sidebar
    overview.html                ← screen 01
    alerts.html                  ← screen 02
    alert_detail.html            ← screen 03
    operations.html              ← screen 04
    reports.html                 ← screen 05
    live_logs.html               ← screen 06 (NEW)
    suppression_rules.html       ← screen 08 (NEW)
    system_health.html           ← screen 09 (NEW)
    partials/
      app_sidebar.html           ← sidebar with all 9 nav items
      top_utility_bar.html       ← top bar (title, search slot, action slot)
  static/
    console.css                  ← CSS variables + component styles (dark mode)
    console.js                   ← sidebar toggle, Live Logs polling, timestamps

tests/console/
  test_ids_operator_console_web.py      ← update for new routes + new screens
  test_ids_operator_console_auth.py     ← update for new login/logout template
  test_ids_operator_console_config.py   ← update for 3 new routes
  test_ids_operator_console_db.py       ← extend for deactivate_suppression_rule
  (all other test files unchanged)
```

---

## Institutional Learnings Applied

| Learning | How applied |
|----------|-------------|
| Split UI redesigns into foundation/route/surface/verification beads | Phase structure: P1=foundation+auth, P2=6 screens, P3=3 new screens+verification |
| Keep service entrypoint wired to real app factory | Verify server.py import stays intact; add regression test in P3 |
| Split runtime verification from operator mutation paths | Suppression CRUD uses OperatorStore methods only; no raw SQL in web.py |
| Use live bead state to rescue stalled swarms | Worker coordination: time-box silent workers; recover from br show + git log |
