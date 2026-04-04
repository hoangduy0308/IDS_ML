# Phase Contract: Phase 3 - Deploy Readiness Audit and Fixes

**Date**: 2026-04-04
**Feature**: ids-console-telegram-settings-and-deploy-readiness
**Phase Plan Reference**: `history/ids-console-telegram-settings-and-deploy-readiness/phase-plan.md`

---

## 1. What This Phase Changes

After this phase lands, an operator reading the deployment docs gets a complete, accurate picture of how to install the IDS operator console on a fresh Linux box, including the new Settings UI for Telegram configuration. The systemd service units work correctly with the env file (no more hardcoded overrides that silently ignore admin customization). The docs explain both configuration approaches (env file for initial bootstrap, Settings UI for ongoing management) and their precedence. The deployment quickstart walks through the real end-to-end flow from tarball to first notification.

---

## 2. Why This Phase Exists Now

Phases 1-2 added DB-based settings and a Settings UI, but all the deployment documentation, env file examples, and systemd units still describe only the old env-file-only approach. An operator deploying today would hit confusing inconsistencies between what the docs say and what the system actually does. This phase closes that gap.

---

## 3. Entry State

- Phase 1 complete: console_settings table, get/set methods, notification hot-reload from DB
- Phase 2 complete: /settings UI routes, template, test button, preflight DB awareness
- 164 console tests + 23 preflight tests pass
- Systemd units have hardcoded `Environment=` lines that override `EnvironmentFile=` values (including clearing Telegram vars to empty)
- All deployment docs describe only env-file Telegram config — no mention of Settings UI or DB approach
- ops/ids-operator-console.env.example lacks notes about DB-based settings
- docs/current/operations/deployment_quickstart.md and README.md are incomplete

---

## 4. Exit State

- Systemd service units (`ids-operator-console.service`, `ids-operator-console-notify.service`) use `EnvironmentFile=` as the primary config source. Hardcoded `Environment=` lines removed (defaults live in the env example file instead).
- `ops/ids-operator-console.env.example` documents all variables with comments explaining DB-settings precedence
- `docs/current/operations/deployment_quickstart.md` has a complete golden-path walkthrough including Settings UI usage
- `docs/current/operations/README.md` updated to reflect the complete operations story
- `ops/README-deploy.md` updated with Telegram configuration section explaining both approaches
- Existing deploy contract tests updated to match the new systemd unit structure
- All existing tests still pass

---

## 5. Demo Walkthrough

Read `deploy/systemd/ids-operator-console.service` — no hardcoded `Environment=` lines, only `EnvironmentFile=-/etc/ids-operator-console/ids-operator-console.env`. Read `ops/ids-operator-console.env.example` — see comments explaining "DB settings take precedence over these values when configured via Settings UI at /settings." Read `docs/current/operations/deployment_quickstart.md` — see complete golden-path from build to first notification, including "Step 5: Configure Telegram via Settings UI."

### Demo Checklist

- [ ] ids-operator-console.service has no hardcoded Environment= lines
- [ ] ids-operator-console-notify.service has no hardcoded Environment= lines
- [ ] env.example has comments about DB precedence and Settings UI
- [ ] deployment_quickstart.md mentions Settings UI at /settings
- [ ] deployment_quickstart.md has complete walkthrough
- [ ] ops/README-deploy.md Telegram section updated
- [ ] docs/current/operations/README.md updated
- [ ] Existing deploy contract tests pass (updated for new service structure)
- [ ] All 164 console tests still pass

---

## 6. Story Sequence At A Glance

| Story | What Happens | Why Now | Unlocks Next | Done Looks Like |
|-------|-------------|---------|--------------|-----------------|
| Story 1: Fix systemd units and env example | Service units use EnvironmentFile only. Env example has all defaults with comments. | Hardcoded Environment= overrides break admin customization | Story 2 (docs need to describe the correct config flow) | Deploy contract tests pass with new structure |
| Story 2: Update all deployment documentation | Docs describe complete deployment flow including Settings UI | Docs currently describe only the old env-file approach | Feature complete | Quickstart, README-deploy, operations README all accurate |

---

## 7. Out Of Scope

- Live sensor service (`ids-live-sensor.service`) — separate feature, different component
- Docker deployment — D4 locks existing tarball flow
- install.sh idempotency improvements — desirable but not blocking for this feature
- Build pipeline changes — build_release.sh works as-is
- Nginx config improvements — works as-is

---

## 8. Success Signals

- An operator reading the docs can understand the full config story without confusion
- Systemd services respect env file customization
- Env example serves as the complete reference for all configurable variables
- No inconsistency between what docs say and what code does

---

## 9. Failure / Pivot Signals

- If changing systemd units breaks existing deploy contract tests and the fix is non-obvious — investigate before forcing
- If docs changes require understanding deployment flows we haven't audited — scope down to what we know
