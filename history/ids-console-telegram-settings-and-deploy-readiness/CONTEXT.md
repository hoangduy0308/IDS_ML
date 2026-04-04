# Telegram Settings UI & Deploy Readiness — Context

**Feature slug:** ids-console-telegram-settings-and-deploy-readiness
**Date:** 2026-04-04
**Exploring session:** complete
**Scope:** Standard

---

## Feature Boundary

This feature delivers two things: (1) a settings screen in the operator console dashboard where admins can view, edit, and test the Telegram bot token and chat ID without restarting the service, and (2) a full system readiness audit with fixes to ensure the entire IDS stack is ready for real-world Linux deployment.

**Domain type(s):** SEE + CALL + RUN + READ

---

## Locked Decisions

### Telegram Settings — Persistence
- **D1** Bot token and chat ID are stored in SQLite (new settings table in the console DB). DB values take priority over env file/secret file values. Changes take effect immediately without service restart. Env file/secret file remains as fallback when DB has no value.
  *Rationale: Consistent with existing SQLite-based architecture. Eliminates operator friction of editing files + restarting services.*

### Telegram Settings — Security & Display
- **D2** Token is masked in the UI (`••••••last4chars`). Full token is only visible immediately after entry, before page reload. A "Test" button sends a test message to confirm the token and chat ID work. After reload, token is masked again.
  *Rationale: Token is sensitive (controls the bot). Masking prevents shoulder-surfing and accidental exposure. Test button provides confidence without revealing the token.*

### Deploy Readiness — Audit Scope
- **D3** Full readiness audit before build: code quality, test coverage, all CLI commands functional, systemd units correct, preflight checks pass, docs complete. Create a comprehensive checklist, fix all blockers before declaring release-ready.
  *Rationale: System is being prepared for real-world use. Partial audit risks production incidents.*

### Deploy Readiness — Build & Install Flow
- **D4** Keep the existing deployment flow (tarball via `build_release.sh` + `install.sh` on target). Focus on fixing bugs, ensuring idempotency, and clear documentation. No Docker, no curl|bash installer.
  *Rationale: Bare-metal systemd deployment with direct NIC access is the correct model for a host-based IDS. Docker adds unnecessary complexity. Current flow is already best practice — just needs polish.*

### Agent's Discretion
- Settings table schema design (column names, types)
- Exact UI layout of the settings screen (must fit existing dark-theme console style)
- Order and grouping of readiness checklist items
- Which test failures are blockers vs non-blockers

---

## Specific Ideas & References

- User wants the settings screen to be part of the existing dashboard — not a separate admin panel
- "Test" button should send a real Telegram message and show success/failure feedback in the UI
- The readiness audit should answer "can a new operator install and use this system on a fresh Linux box end-to-end?"

---

## Existing Code Context

### Reusable Assets
- `ids/console/config.py` — Current config loader with `_load_secret()` helper (lines 108-125) and Telegram env var parsing (lines 283-289). New DB-based settings must integrate with this.
- `ids/console/db.py` — SQLite schema with migrations. New settings table goes here.
- `ids/console/notifications.py` — `TelegramNotifierConfig` dataclass (lines 36-54) and `send_telegram_message()` function (lines 155-231). Test button reuses this.
- `ids/console/notification_runtime.py` — `NotificationRuntimeConfig.from_operator_console_config()` (lines 41-64). Must be updated to check DB settings.
- `ids/console/web.py` — FastAPI routes (581 lines). New settings routes added here.
- `ids/console/templates/` — Jinja2 templates following base.html inheritance with `{% block content %}`.
- `ids/console/static/console.css` — 49 CSS variables dark theme. Settings screen must use these.
- `ids/console/static/console.js` — Client-side JS with `esc()` XSS helper (critical pattern from learnings).
- `ids/console/auth.py` — Admin authentication with CSRF tokens. Settings routes must be auth-protected.

### Established Patterns
- **TDD with foundation-first phases** (critical pattern from learnings): Phase 1 = foundation/schema, Phase 2 = UI + routes, Phase 3 = integration + audit
- **XSS escaping in JS**: All innerHTML injection must use `esc()` helper (critical pattern)
- **Service entrypoint wiring**: Must verify the real app factory serves new routes, not just test stubs (critical pattern)
- **Preflight validation**: `ids/ops/operator_console_preflight.py` validates config at startup

### Integration Points
- `ids/console/web.py` — Add new `/settings` route (GET for page, POST for save, POST for test)
- `ids/console/db.py` — Add `console_settings` table and getter/setter functions
- `ids/console/config.py` — Add method to check DB settings before falling back to env vars
- `ids/ops/operator_console_manage.py` — CLI management commands may need settings awareness
- `ops/build_release.sh` — Audit and fix for release readiness
- `ops/install.sh` — Audit and fix for installation smoothness
- `deploy/systemd/` — Verify service units are correct and complete

---

## Canonical References

- `history/learnings/critical-patterns.md` — Mandatory pre-planning read. Contains XSS, foundation-first, entrypoint wiring, and preflight patterns.
- `ops/README-deploy.md` — Current deployment guide (134 lines). Must be updated if install flow changes.
- `ops/ids-operator-console.env.example` — Env template. Must remain valid even with DB-based settings.
- `docs/current/operations/deployment_quickstart.md` — Quick deploy guide. Must be updated for completeness.

---

## Outstanding Questions

### Resolve Before Planning
(none — all product decisions locked)

### Deferred to Planning
- [ ] Exact migration strategy for settings table — planner investigates existing migration patterns in `ids/console/migrations.py`
- [ ] How notification_runtime hot-reloads DB settings without restart — planner investigates current config refresh patterns
- [ ] Full readiness checklist items — planner audits each subsystem to discover what's broken/missing
- [ ] Whether `install.sh` is currently idempotent — planner tests the flow

---

## Deferred Ideas

- Docker/container-based deployment — deferred, not needed for single-host IDS
- Multi-user role-based settings access — deferred, current single-admin model is sufficient
- Web-based Telegram bot setup wizard (BotFather integration) — deferred, out of scope

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2, D3, D4) are stable. Reference them by ID in all downstream artifacts.
