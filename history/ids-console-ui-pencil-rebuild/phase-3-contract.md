# Phase 3 Contract — The expanded console surface is live

**Feature:** ids-console-ui-pencil-rebuild
**Phase:** 3 of 3

---

## What Changes In Real Life When This Phase Lands

The operator can now access three new capabilities directly in the browser. Live Logs shows a scrolling terminal-style feed of recent alerts and anomalies that refreshes every 7 seconds without a page reload. Suppression Rules shows all active rules in a table and lets the operator add new rules or deactivate existing ones — with CSRF-protected forms and immediate DB effect. System Health shows a single-page breakdown of every readiness component (config, schema, admin bootstrap, data paths, active bundle, notification state) using the same `build_readiness_payload()` data source as Overview and Operations.

All three screens match the Pencil dark-mode design (frames `rJIYx`, `i7RHe`, `ibfMx` in `design/UI`). After this phase, all 9 screens are live and the full console surface is complete.

---

## Entry State

- 96 tests passing across Phase 1 and Phase 2 (`pytest tests/console/` — all green)
- Phase 3 routes return HTTP 501 (not crash, not 404):
  - `GET /live-logs` (auth guard pre-wired)
  - `GET /suppression-rules` (auth guard pre-wired)
  - `POST /suppression-rules` (CSRF + auth pre-wired, `csrf_token: str = Form("")`)
  - `POST /suppression-rules/{rule_id}/deactivate` (CSRF + auth pre-wired, `rule_id: int`)
  - `GET /system-health` (auth guard pre-wired)
- No Phase 3 template files exist yet
- `deactivate_suppression_rule(*, rule_id: int) -> bool` exists in `OperatorStore` (added in Phase 1 / Story 1.1)
- `create_suppression_rule(*, rule_name, match_field, match_value, applies_to, sensor_id)` exists in `OperatorStore`
- `list_active_suppression_rules(*, sensor_id, applies_to)` exists in `OperatorStore`
- `build_readiness_payload(config, *, include_sensitive=True)` exists in `ids/console/health.py:191`
- JSON polling endpoints exist and are tested: `GET /api/v1/alerts`, `GET /api/v1/anomalies`
- Existing Phase 1/2 test assertions for Phase 3 routes: 501 — these will be updated to 200 in Phase 3

---

## Critical Correction: D6a vs. Reality

CONTEXT.md D6a says System Health is built from `_prepare_health_snapshot()`. **This function does not exist in `ids/console/health.py`.** It was never implemented. The Phase 3 System Health story must use:

```python
build_readiness_payload(config, include_sensitive=True)
# → already imported in web.py: from .health import build_liveness_payload, build_readiness_payload
```

The `build_readiness_payload()` return dict contains all fields needed for the System Health screen:
- `status`, `ready`, `service`, `environment`, `proxy`
- `components.config` (config ok, session cookie settings, secret source)
- `components.schema` (ok, state, version, detail)
- `components.admin_bootstrap` (ok, admin_count)
- `components.data_paths` (ok, per-stream path health)
- `components.active_bundle` (ok, state dict)
- `components.notification` (notification component state)

Use this. Do not look for `_prepare_health_snapshot()`.

---

## Exit State (observable, not aspirational)

- `GET /system-health` → 200, renders full readiness component breakdown (config, schema, admin bootstrap, data paths, active bundle, notification)
- `GET /suppression-rules` → 200, renders active rules table + add rule form
- `POST /suppression-rules` (CSRF) → creates new rule, 303 redirect to `/suppression-rules`
- `POST /suppression-rules/{rule_id}/deactivate` (CSRF) → deactivates rule, 303 redirect; 404 if rule not found
- `GET /live-logs` → 200, renders terminal-style feed with recent alerts + anomalies; page container carries `data-live-logs-poll` attribute and polling JS initializes a 7s `setInterval`
- All 3 templates use `base.html` → `{% block content %}` pattern (same as Phase 2)
- **Tests passing (TDD — tests written first):**
  - `test_ids_operator_console_system_health.py` — new
  - `test_ids_operator_console_suppression_rules.py` — new
  - `test_ids_operator_console_live_logs.py` — new
  - `test_ids_operator_console_web.py` updated: 501 assertions for Phase 3 routes changed to 200/303
- **No regressions on Phase 1 or Phase 2 tests** (96 tests still pass)
- Entrypoint wiring regression test passes: `create_operator_console_app()` exposes `/overview` (real route, not placeholder)

---

## Demo Walkthrough

1. `pytest tests/console/` — all pass (Phase 1 + 2 + 3 baseline = 96 + new Phase 3 tests)
2. Start the app. Log in. Navigate to `/system-health`. See readiness badges for all components: config ✓, schema ✓, admin ✓, data paths ✓/⚠, active bundle ✓/✗, notification state.
3. Navigate to `/suppression-rules`. See the active rules table (or empty state). Click Add Rule, fill rule_name, match_field, match_value, submit. Rule appears in table.
4. Click Deactivate on an existing rule. It disappears from the active list.
5. Navigate to `/live-logs`. See recent alerts and anomalies in a scrolling terminal view. Wait 7 seconds. The feed refreshes automatically (no page reload).
6. All Phase 1 routes still work: login, logout, sidebar nav, legacy redirects.
7. All Phase 2 routes still work: overview, alerts, alert detail, operations, reports.

---

## What This Phase Unlocks

This is the final phase. After Phase 3 lands, all 9 screens are live. The full console surface is stable for operator use. No further UI rebuild phases remain.

Post-Phase-3 options: hardening, new feature screens, or live-sensor data feed upgrades — but these are out of scope for this feature.

---

## Out Of Scope For This Phase

- Multi-sensor selector in HTML pages (deferred — JSON API supports it but HTML pages don't)
- Light mode / theme toggle (deferred — dark mode is locked for this feature)
- Report export action (deferred)
- Model promotion / rollback UI (remains CLI-only)
- Fleet / multi-host views (out of scope for same-host console)
- WebSocket or SSE for live logs (locked as D8: polling only)

---

## Suppression Rules Form Contract

The `POST /suppression-rules` stub currently has only `csrf_token: str = Form("")`. The worker must expand the signature to include all form fields:

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
    # → create, redirect
```

`rule_id` is typed as `int` in the deactivate stub — the store call must use `rule_id=rule_id` (keyword arg).

---

## Polling Architecture for Live Logs

The Live Logs page:
1. Server-renders initial feed (≤50 recent alerts + ≤50 recent anomalies) into the template at page load time.
2. Template includes a container element with `data-live-logs-poll="7000"` (interval in ms).
3. `console.js` adds `initLiveLogsPoller()` — called during `init()`. It reads `data-live-logs-poll` from the container, starts a `setInterval` that fetches `/api/v1/alerts?include_suppressed=true` and `/api/v1/anomalies`, then re-renders the log list.
4. Tests verify: GET /live-logs → 200, `data-live-logs-poll` attribute present, initial feed rows present.
5. No test mocks the `setInterval` — the JS contract is tested via attribute presence and initial render. Worker must NOT add flaky JS timer tests.

---

## Signals That Would Force A Pivot

- `build_readiness_payload()` raises unexpectedly — investigate before continuing (same signal as Phase 2 contract)
- `create_suppression_rule()` or `list_active_suppression_rules()` signature has changed since Phase 1 — verify before writing tests
- Jinja2 template inheritance breaks in any Phase 3 template — check `base.html` pattern and fix before implementing remaining templates
- Existing Phase 1 or Phase 2 tests regress after any `web.py` change — fix immediately, do not merge a broken regression
- Worker expands the `POST /suppression-rules` signature incorrectly — tests will catch mismatched Form fields; fix before closing the bead
