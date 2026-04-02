# Phase 3 Story Map — The expanded console surface is live

**Feature:** ids-console-ui-pencil-rebuild
**Phase:** 3 of 3

---

## Story 3.1 — System Health screen (TDD)

**What happens:** Tests for `/system-health` are written first and fail. Then the route handler and `system_health.html` template are implemented to make them pass. The system health screen renders the full readiness component breakdown: config state, schema state, admin bootstrap count, data path health per stream, active bundle state, and notification component state.

**Why now:** System Health is the simplest of the three new Phase 3 screens — pure read-only, no forms, no POST handlers, no polling JS. It reuses `build_readiness_payload(config, include_sensitive=True)` which is already imported in `web.py` and already validated by the Phase 2 Overview and Operations tests. Starting with the simplest screen validates the template inheritance pattern for Phase 3 before the more complex screens are built.

**IMPORTANT — D6a correction:** CONTEXT.md D6a references `_prepare_health_snapshot()`. This function does NOT exist in `ids/console/health.py`. Use `build_readiness_payload(config, include_sensitive=True)` instead. It is already imported in `web.py`. Do not search for `_prepare_health_snapshot`.

**Pencil frame:** `ibfMx` — open with `mcp__pencil__batch_get` to inspect the layout before writing the template.

**Contributes to phase exit state:**
- `GET /system-health` → 200 (not 501)
- `test_ids_operator_console_system_health.py` tests passing
- `test_ids_operator_console_web.py` 501 assertion for `/system-health` changed to 200

**Creates:**
- `tests/console/test_ids_operator_console_system_health.py` (written first, failing, then passing)
- `ids/console/templates/system_health.html` (extends base.html, uses `{% block content %}`)
- `ids/console/web.py` — `/system-health` route handler replacing the 501 stub

**Data contract this story must honor:**
```python
# Already imported in web.py:
from .health import build_liveness_payload, build_readiness_payload

# In the route handler (config is closure variable, not from request):
readiness = build_readiness_payload(config, include_sensitive=True)
# readiness["components"] contains: config, schema, admin_bootstrap, data_paths, active_bundle, notification
# readiness["status"] is "ok" or "degraded"
# readiness["ready"] is bool

# Template context:
return render_template(request, "system_health.html", readiness=readiness)
```

**Pattern — replace only the 501 line:**
The 501 stub already has the auth guard. Keep it. Replace only `raise HTTPException(status_code=501, detail="Not yet implemented")`:
```python
@app.get("/system-health", response_class=HTMLResponse)
def system_health_page(request: Request) -> Response:
    redirect = require_authenticated_redirect(request, login_path="/login")
    if redirect is not None:
        return redirect
    # ↓ replace the raise below with:
    readiness = build_readiness_payload(config, include_sensitive=True)
    return render_template(request, "system_health.html", readiness=readiness)
```

**Unlocks:** Story 3.2 can proceed — the web.py modification pattern and template inheritance are validated for Phase 3.

**Done looks like:**
- `pytest tests/console/test_ids_operator_console_system_health.py` passes (~10 tests)
- `pytest tests/console/test_ids_operator_console_web.py -k system_health` passes (200, not 501)
- All 96 Phase 1+2 tests still pass
- `GET /system-health` in a live app renders component status badges (config ✓, schema ✓, admin bootstrap ✓, data paths, active bundle, notification)

---

## Story 3.2 — Suppression Rules screen (TDD)

**What happens:** Tests for `GET /suppression-rules` (active rules table), `POST /suppression-rules` (add rule, CSRF), and `POST /suppression-rules/{rule_id}/deactivate` (deactivate, CSRF) are written first and fail. Then the route handlers and `suppression_rules.html` are implemented to make them pass. This includes expanding the `POST /suppression-rules` stub signature to accept the form fields.

**Why now:** Suppression Rules has no dependency on Live Logs. It reuses the established CSRF + redirect pattern from Phase 2 (Alerts notes/status). The DB methods (`list_active_suppression_rules`, `create_suppression_rule`, `deactivate_suppression_rule`) all exist and are tested from Phase 1. Starting here while the CSRF pattern is fresh and before the more complex Live Logs JS work locks web.py is the right ordering.

**Pencil frame:** `i7RHe` — open with `mcp__pencil__batch_get` to inspect the layout before writing the template.

**Contributes to phase exit state:**
- `GET /suppression-rules` → 200, renders active rules table + add rule form
- `POST /suppression-rules` (CSRF) → adds rule, 303 redirect
- `POST /suppression-rules/{rule_id}/deactivate` (CSRF) → deactivates rule, 303 redirect; 404 if rule_id not found
- `test_ids_operator_console_suppression_rules.py` tests passing
- `test_ids_operator_console_web.py` 501 assertions for these routes changed to 200/303

**Creates:**
- `tests/console/test_ids_operator_console_suppression_rules.py` (written first, failing, then passing)
- `ids/console/templates/suppression_rules.html` (extends base.html, active rules table with deactivate button, add rule form)
- `ids/console/web.py` — 3 route handlers replacing 501 stubs

**Data contracts this story must honor:**

```python
# Store is a closure variable — _open_store() takes NO arguments:
runtime_store = _open_store()

# List active rules:
rules = runtime_store.list_active_suppression_rules(sensor_id=DEFAULT_SENSOR_ID)
# → list[dict] with keys: id, sensor_id, rule_name, match_field, match_value, applies_to, is_active, created_at, updated_at

# Create new rule (POST /suppression-rules):
new_id = runtime_store.create_suppression_rule(
    rule_name=rule_name,
    match_field=match_field,
    match_value=match_value,
    applies_to=applies_to,
    sensor_id=DEFAULT_SENSOR_ID,
)
# → int (new rule ID)

# Deactivate (POST /suppression-rules/{rule_id}/deactivate):
deactivated = runtime_store.deactivate_suppression_rule(rule_id=rule_id)
# → True if found and deactivated, False if not found (rule_id: int)
# Return 404 if deactivated is False
```

**POST /suppression-rules stub expansion (critical):**
The existing 501 stub has only `csrf_token: str = Form("")`. The worker must expand the function signature:
```python
@app.post("/suppression-rules")
async def suppression_rules_create(
    request: Request,
    csrf_token: str = Form(""),
    rule_name: str = Form(""),
    match_field: str = Form(""),
    match_value: str = Form(""),
    applies_to: str = Form("model_alert"),
) -> Response:
    validate_csrf_form(request, {"csrf_token": csrf_token})
    require_authenticated_api(request)
    runtime_store = _open_store()
    runtime_store.create_suppression_rule(
        rule_name=rule_name,
        match_field=match_field,
        match_value=match_value,
        applies_to=applies_to,
        sensor_id=DEFAULT_SENSOR_ID,
    )
    return RedirectResponse(url="/suppression-rules", status_code=303)
```

**CSRF + redirect — same pattern as Phase 2 alert POST handlers:**
- POST success → `RedirectResponse(url="/suppression-rules", status_code=303)`
- CSRF rejection → `validate_csrf_form` raises automatically (already pre-wired in stub)
- Both POST stubs already have `validate_csrf_form` + `require_authenticated_api` — keep them

**Acceptance criteria for tests:**
1. `GET /suppression-rules` → 200
2. Active rules list renders (rule_name, match_field, match_value, applies_to visible)
3. Empty state renders when no rules exist
4. Add rule form present in HTML (rule_name, match_field, match_value inputs, csrf_token hidden field)
5. `POST /suppression-rules` with valid CSRF → 303 redirect to `/suppression-rules`
6. `POST /suppression-rules` with invalid/missing CSRF → 400 or 403
7. `POST /suppression-rules/{id}/deactivate` with valid CSRF → 303 redirect
8. `POST /suppression-rules/{id}/deactivate` with invalid/missing CSRF → 400 or 403
9. `POST /suppression-rules/{id}/deactivate` with unknown rule_id → 404

**Unlocks:** Story 3.3 can proceed — POST handler pattern + template pattern for Phase 3 fully validated.

**Done looks like:**
- `pytest tests/console/test_ids_operator_console_suppression_rules.py` passes
- `pytest tests/console/test_ids_operator_console_web.py -k suppression` passes (200/303, not 501)
- All 96 Phase 1+2 tests still pass
- `GET /suppression-rules` in a live app renders the active rules table and add form
- Adding a rule redirects back and the new rule appears in the table
- Deactivating a rule redirects back and the rule is gone from the active list

---

## Story 3.3 — Live Logs screen + polling JS (TDD)

**What happens:** Tests for `/live-logs` HTML render are written first and fail. Then the route handler, `live_logs.html` template, and polling JS in `console.js` are implemented to make them pass. The page renders a server-side initial feed and carries a `data-live-logs-poll` attribute. `console.js` gains `initLiveLogsPoller()` — a `setInterval` that fetches `/api/v1/alerts` and `/api/v1/anomalies` every 7 seconds and re-renders the log list.

**Why now:** Live Logs is last among the three new screens because it has the most moving parts: a new template, a web.py route change, AND a `console.js` update. The JS polling does not depend on any Phase 3 story being done first, but the route pattern for the initial render benefits from System Health and Suppression Rules confirming the Phase 3 template inheritance works correctly. Placing it last also means the worker doesn't need to worry about other stories touching `console.js`.

**Pencil frame:** `rJIYx` — open with `mcp__pencil__batch_get` to inspect the layout before writing the template.

**Contributes to phase exit state:**
- `GET /live-logs` → 200, terminal-style feed, `data-live-logs-poll` attribute present, initial events visible
- `test_ids_operator_console_live_logs.py` tests passing
- `test_ids_operator_console_web.py` 501 assertion for `/live-logs` changed to 200
- `console.js` updated with `initLiveLogsPoller()` (no JS tests required — attribute contract is sufficient)

**Creates:**
- `tests/console/test_ids_operator_console_live_logs.py` (written first, failing, then passing)
- `ids/console/templates/live_logs.html` (extends base.html, log area, data-live-logs-poll on container)
- `ids/console/static/console.js` — add `initLiveLogsPoller()` function, call from `init()`
- `ids/console/web.py` — `/live-logs` route handler replacing the 501 stub

**Data contract this story must honor:**

```python
# GET /live-logs handler:
runtime_store = _open_store()
# Server-render initial feed — recent events, newest first:
alerts = list_alerts_for_triage(runtime_store, limit=50, include_suppressed=True)
anomalies = runtime_store.list_anomalies(limit=50)
# Note: anomalies list items may need _with_decoded_payload() treatment for payload field
return render_template(request, "live_logs.html", alerts=alerts, anomalies=anomalies)
```

**Template contract:**
- Extends `base.html`, uses `{% block content %}`
- Log area container: `<div id="live-logs-feed" data-live-logs-poll="7000">...</div>`
- Initial server-rendered rows for both alerts and anomalies
- Each event row shows: timestamp, event type (alert/anomaly), key identifier, severity or score

**console.js polling contract:**
```javascript
function initLiveLogsPoller() {
  var container = document.getElementById('live-logs-feed');
  if (!container) { return; }
  var interval = parseInt(container.getAttribute('data-live-logs-poll'), 10) || 7000;
  setInterval(function() {
    // fetch /api/v1/alerts?include_suppressed=true and /api/v1/anomalies
    // merge, sort newest first, re-render rows
  }, interval);
}
// Add to init(): initLiveLogsPoller();
```

**Polling endpoints (already exist and are tested from Phase 1):**
- `GET /api/v1/alerts?include_suppressed=true` → `{"sensor_id": "...", "alerts": [...]}`
- `GET /api/v1/anomalies` → `{"sensor_id": "...", "anomalies": [...]}`

**Test scope — DO NOT add flaky JS timer tests:**
Tests verify server-rendered HTML only:
1. `GET /live-logs` → 200
2. `#live-logs-feed` container present in HTML
3. `data-live-logs-poll` attribute present on the container
4. At least one initial event row rendered (alert or anomaly) when test fixture has data
5. Base shell present (sidebar, nav items)

Do not test `setInterval` behavior, fetch calls, or DOM re-render — these are not testable in the FastAPI TestClient. The polling contract is proven by the attribute presence + the existing `/api/v1/*` tests from Phase 1.

**Unlocks:** Story 3.4 (Verification) — all three new screens are live, the full suite can now be run.

**Done looks like:**
- `pytest tests/console/test_ids_operator_console_live_logs.py` passes
- `pytest tests/console/test_ids_operator_console_web.py -k live_logs` passes (200, not 501)
- All 96 Phase 1+2 tests still pass
- `GET /live-logs` in a live app renders recent events; the feed refreshes every 7s without a page reload
- `console.js` has `initLiveLogsPoller()` function that reads `data-live-logs-poll` from the container

---

## Story 3.4 — Verification: full suite, entrypoint wiring, legacy smoke

**What happens:** The full test suite is run. Any gaps or regressions introduced during Phase 3 are fixed. An entrypoint wiring regression test is added — this was called out in `critical-patterns.md` as a lesson from the v1 console feature. `STATE.md` is updated to mark Phase 3 complete.

**Why now:** Verification is always last. It can only run after all three new screens are implemented and their tests pass. It also catches cross-story regressions that weren't visible in individual story test runs.

**Contributes to phase exit state:**
- Full test suite passes (all Phase 1 + 2 + 3 tests green)
- Entrypoint wiring regression test passes
- Legacy redirects confirmed passing
- STATE.md updated to swarming-complete + phase-3-complete

**Creates / modifies:**
- `tests/console/test_ids_operator_console_web.py` or `test_ids_operator_console_config.py` — adds entrypoint wiring regression test
- `.khuym/STATE.md` — updated to phase-3-complete

**Entrypoint wiring regression test (from `critical-patterns.md` [20260328]):**

The v1 console had a split where `web.py` had all routes but `server.py` launched a different app. The regression test must prove this cannot happen again:

```python
# In test_ids_operator_console_config.py (or test_ids_operator_console_web.py):
def test_entrypoint_wiring_exposes_real_routes():
    """Regression: server.py:create_operator_console_app must expose real routes, not just /healthz."""
    from ids.console.server import create_operator_console_app
    app = create_operator_console_app()
    route_paths = [getattr(r, "path", None) for r in app.routes]
    assert "/overview" in route_paths, (
        "server.py entrypoint must expose /overview — not just /healthz or a stub root"
    )
    assert "/system-health" in route_paths, (
        "server.py entrypoint must expose /system-health (Phase 3 route)"
    )
```

**Legacy smoke:**
- `GET /dashboard` → 307/302 redirect to `/overview`
- `GET /anomalies` → 307/302 redirect to `/operations`
These should already pass from Phase 1 — re-verify they still pass after all Phase 3 web.py changes.

**Done looks like:**
- `pytest tests/console/` — all pass (96 Phase 1+2 baseline + all Phase 3 new tests)
- `pytest tests/console/test_ids_operator_console_config.py` (or `_web.py`) — entrypoint wiring test passes
- Legacy redirect tests pass
- `.khuym/STATE.md` updated to `STATUS: swarming-complete`, `PHASE: phase-3-complete`
- Phase 3 commits recorded in `STATE.md`

---

## Story Ordering Rationale

```
3.1 (System Health) → simplest read-only screen, validates Phase 3 template pattern
3.2 (Suppression Rules) → full CRUD + CSRF, builds on proven web.py edit pattern
3.3 (Live Logs + polling JS) → most moving parts, placed last to avoid console.js conflicts
3.4 (Verification) → full suite run, entrypoint regression, STATE.md close
```

All four stories modify `web.py` and `test_ids_operator_console_web.py`. These shared files require serial ownership — **single-worker, sequential execution** (same model as Phases 1 and 2). The bead dependency chain enforces this: wnnq-style chain (3.1 → 3.2 → 3.3 → 3.4).

Story 3.3 additionally modifies `console.js` — no other Phase 3 story touches this file, so there is no conflict.

---

## Shared Implementation Notes (all Phase 3 stories)

- All 3 templates extend `base.html` using `{% extends "base.html" %}` and override `{% block content %}` — do NOT override `{% block page_wrapper %}` (reserved for login layout)
- All GET route handlers get the store via `_open_store()` (no arguments — closure variable)
- `config` is a closure variable in the factory — not from the request
- CSRF tokens are injected by `render_template()` and validated on all POST handlers via `validate_csrf_form(request, {"csrf_token": csrf_token})`
- Both POST stubs (`/suppression-rules` and `/suppression-rules/{id}/deactivate`) already have `validate_csrf_form` + `require_authenticated_api` pre-wired — keep them, just add form field params and replace the 501 raise
- `DEFAULT_SENSOR_ID` is defined in `web.py` — use it for store calls, do not hardcode

---

## Story-To-Bead Mapping

*(To be filled after bead creation)*

| Story | Bead ID |
|-------|---------|
| 3.1 — System Health screen (TDD) | `ids_ml_new-cnh3` |
| 3.2 — Suppression Rules screen (TDD) | `ids_ml_new-7vke` |
| 3.3 — Live Logs screen + polling JS (TDD) | `ids_ml_new-ut75` |
| 3.4 — Verification full suite | `ids_ml_new-bui4` |

Epic: `ids_ml_new-k8c1`

---

## Phase 3 → Feature Complete Handoff Condition

All Phase 3 stories passing (96 Phase 1+2 tests + all Phase 3 tests) + entrypoint wiring regression passing → feature `ids-console-ui-pencil-rebuild` is swarming-complete. Invoke `khuym:reviewing` for the final review pass.
