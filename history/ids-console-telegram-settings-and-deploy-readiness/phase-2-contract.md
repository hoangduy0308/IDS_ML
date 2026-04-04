# Phase Contract: Phase 2 - Settings UI and Preflight Integration

**Date**: 2026-04-04
**Feature**: ids-console-telegram-settings-and-deploy-readiness
**Phase Plan Reference**: `history/ids-console-telegram-settings-and-deploy-readiness/phase-plan.md`

---

## 1. What This Phase Changes

After this phase lands, an admin logged into the operator console sees a "Settings" link in the sidebar. Clicking it opens a settings page with the current Telegram configuration status. If Telegram is configured, the bot token is shown masked (e.g., `••••••BCDEF`). The admin can enter a new bot token and chat ID, click "Save", and see the masked token appear with a "Configured" status. They can click "Test" to send a real test message to Telegram and see inline success/failure feedback. They can also clear both fields and save to disable DB-based notifications. The preflight validator now opens the database and accepts DB-stored Telegram config as a valid configuration source.

---

## 2. Why This Phase Exists Now

Phase 1 created the database foundation (console_settings table, get/set methods, hot-reload). This phase builds the user-facing UI that lets operators actually use that foundation. Without this phase, the only way to write settings to the DB would be via Python shell — not acceptable for production operators.

---

## 3. Entry State

- Schema v3 with `console_settings` table, `get_setting()`/`set_setting()` methods on OperatorStore
- Notification worker hot-reloads from DB each cycle via `_resolve_telegram_config()`
- 156 console tests pass
- No `/settings` route exists in web.py
- No `settings.html` template exists
- Preflight only validates env-file Telegram config
- `PRIMARY_NAV` has 7 items (no Settings entry)

---

## 4. Exit State

- `PRIMARY_NAV` has 8 items including `{"key": "settings", "label": "Settings", "href": "/settings"}`
- GET `/settings` renders `settings.html` with masked token (last 4 chars) or "Not configured" status, auth-protected
- POST `/settings` saves bot_token and chat_id to `console_settings` via `set_setting()`, CSRF-protected. Empty values clear settings.
- POST `/settings/test` sends a real test Telegram message using DB-stored credentials and returns JSON `{success: true/false, detail: "..."}`, auth+CSRF protected. Test button JS uses `esc()` before innerHTML.
- Full token is NEVER returned in any GET response — server-side masking only
- `operator_console_preflight.py` opens the DB (via `--database-path`) and checks `console_settings` for Telegram credentials. If DB has valid token+chat_id, preflight considers Telegram configured. Backward-compatible with env-only deployments.
- New tests cover: auth redirect, CSRF enforcement, save to DB, masked display, clear/empty behavior, test-send with mock, preflight DB-only, preflight env-only, preflight both
- All existing 156 tests still pass

---

## 5. Demo Walkthrough

Log into the dashboard. Click "Settings" in the sidebar. See "Telegram: Not configured". Enter bot token `123:ABCDEF` and chat ID `-100999`. Click "Save". See "Configured" with masked token `••••••BCDEF`. Click "Test". See "Test message sent successfully" (or error details). Navigate away and back — token stays masked. Clear both fields and save — status returns to "Not configured".

### Demo Checklist

- [ ] Unauthenticated GET /settings → redirect to /login
- [ ] Authenticated GET /settings → 200 with form
- [ ] POST /settings without CSRF → 403
- [ ] POST /settings with token+chat_id → saves, shows masked token
- [ ] POST /settings with empty fields → clears settings
- [ ] POST /settings/test → sends real message, returns success/failure
- [ ] Token never appears in GET response HTML
- [ ] Preflight with DB-only config → passes
- [ ] Settings nav item visible in sidebar

---

## 6. Story Sequence At A Glance

| Story | What Happens | Why Now | Unlocks Next | Done Looks Like |
|-------|--------------|---------|--------------|-----------------|
| Story 1: Settings routes + template + nav | Admin can see, save, clear, and test Telegram settings in the UI | This is the user-facing feature | Story 2 (preflight can validate DB config) | All route tests pass, masked token works, test button works |
| Story 2: Preflight DB-settings integration | Preflight accepts DB-stored Telegram config as valid | Service won't warn about missing env config when settings are in DB | Phase 3 (deploy audit) | Preflight tests pass for DB-only, env-only, and both scenarios |

---

## 7. Out Of Scope

- config.py changes — stays env-only (critical pattern)
- Token encryption — decided against in approach.md
- Deploy audit — Phase 3
- Multi-user settings — single admin model

---

## 8. Success Signals

- Settings page renders correctly with dark theme CSS variables
- Token masking is server-side only — full token never in HTTP response
- Test button sends real Telegram message and handles errors gracefully
- Preflight backward-compatible — existing env-only deployments unaffected

---

## 9. Failure / Pivot Signals

- If XSS is found in test button response rendering — stop and fix before continuing
- If preflight changes break existing env-only deployments — revert and redesign
- If the template inheritance pattern from base.html doesn't work for settings — investigate before forcing
