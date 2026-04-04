# Phase Plan: Telegram Settings UI & Deploy Readiness

**Date**: 2026-04-04
**Feature**: ids-console-telegram-settings-and-deploy-readiness
**Based on**:
- `history/ids-console-telegram-settings-and-deploy-readiness/CONTEXT.md`
- `history/ids-console-telegram-settings-and-deploy-readiness/discovery.md`
- `history/ids-console-telegram-settings-and-deploy-readiness/approach.md`

**Planning revision**: The original three phases executed, but review reopened the feature with one blocking ship-readiness defect and three non-blocking follow-ups. This revision adds a final review-closure phase instead of pretending the earlier plan already closed the feature.

---

## 1. Feature Summary

This feature started as “let operators manage Telegram settings in the dashboard and verify the whole Linux deploy path is ready.” Most of that product is already built: the DB settings table exists, the settings page exists, the notification worker reloads DB values, and the deploy docs/scripts were updated.

Review proved the feature is not fully shippable yet. The release bundle can still leak ignored local files, the Settings page can disagree with the runtime about whether Telegram is configured, the new settings flow breaks under a mounted proxy path, and the installer does not fully close the advertised worker/secret-file contract. The next plan therefore adds one final review-closure phase that makes the feature actually ready, not just mostly implemented.

---

## 2. Why This Breakdown

- Phases 1-3 still make sense historically: schema/hot-reload had to exist before the UI, and the UI had to exist before a deploy-readiness pass was even possible.
- The review findings are not random cleanup. Together they show that the original “deploy readiness” phase proved too much too early, so the remaining work deserves its own explicit closure phase.
- Keeping the review follow-up as Phase 4 is clearer than rewriting history. It lets everyone see what already landed and what still blocks a real ship decision.

---

## 3. Phase Overview Table

| Phase | What Changes In Real Life | Why This Phase Exists Now | Demo Walkthrough | Unlocks Next |
|-------|----------------------------|---------------------------|------------------|--------------|
| Phase 1: Settings schema and notification hot-reload `(completed)` | The database can store Telegram settings and the worker can pick them up without restart. | Nothing user-facing could be truthful until DB-backed runtime behavior existed. | Write DB settings, run a worker cycle, see the worker use them. | Phase 2 |
| Phase 2: Settings UI and preflight integration `(completed)` | An admin can use `/settings`, save/test credentials, and preflight accepts DB-backed config. | This is the visible operator feature and depends on Phase 1. | Log in, save settings, click Test, see the UI respond. | Phase 3 |
| Phase 3: Initial deploy-readiness pass `(completed but not sufficient)` | Deploy scripts, service units, and docs were audited and updated against the new settings feature. | The feature needed a readiness pass after the code existed end-to-end. | Build the tarball, inspect scripts/docs, see the new deploy surfaces wired. | Phase 4 after review |
| Phase 4: Review closure and release-proof hardening `(current)` | The shipped artifact is safe, Settings tells the truth in every supported config shape, mounted proxy paths work, and install/runtime closure is real. | Review proved the feature still has ship-blocking seams. This is now the smallest believable “ready to ship” slice left. | Build a release bundle that cannot include local junk, verify env-only Telegram truth in `/settings`, exercise mounted `/console/settings`, and confirm the installer leaves the notify worker and env file in a production-ready state. | Final validation, execution, and then reviewing again for closure |

---

## 4. Phase Details

### Phase 1: Settings schema and notification hot-reload `(completed)`

- **What Changes In Real Life**: Telegram settings can live in SQLite and the worker can pick them up on its normal poll cycle.
- **Why This Phase Exists Now**: The UI and later deploy work had nothing stable to stand on until runtime behavior existed.
- **Stories Inside This Phase**:
  - Story 1: Add `console_settings` storage and migration
  - Story 2: Reload effective Telegram config in the worker each cycle
- **Demo Walkthrough**: Seed settings in the DB, run one maintenance cycle, and see the worker consume them without a restart.
- **Unlocks Next**: Phase 2 can now be a real operator surface instead of a stub.

### Phase 2: Settings UI and preflight integration `(completed)`

- **What Changes In Real Life**: The dashboard exposes a Settings page where an admin can save/test Telegram config, and preflight understands DB-backed settings.
- **Why This Phase Exists Now**: The user asked for a visible, in-dashboard management path, and it depends on the runtime/storage work from Phase 1.
- **Stories Inside This Phase**:
  - Story 1: Add `/settings` page, save flow, test flow, and nav entry
  - Story 2: Teach preflight to recognize DB-backed Telegram config
- **Demo Walkthrough**: Log in, save token/chat, click Test, and see the page return success with masked token display.
- **Unlocks Next**: Phase 3 can audit the full feature instead of an incomplete one.

### Phase 3: Initial deploy-readiness pass `(completed but not sufficient)`

- **What Changes In Real Life**: The deployment scripts, service units, and docs were updated to include the new settings feature and the supported same-host workflow.
- **Why This Phase Exists Now**: A readiness pass still had to happen once the feature existed end-to-end.
- **Stories Inside This Phase**:
  - Story 1: Audit build/install helpers
  - Story 2: Audit systemd and CLI wiring
  - Story 3: Refresh deployment docs
- **Demo Walkthrough**: Run the build helper, inspect the staged deploy surfaces, and read the updated docs as an operator would.
- **Unlocks Next**: Review has enough concrete surfaces to decide whether the feature is actually ready.

### Phase 4: Review closure and release-proof hardening `(current)`

- **What Changes In Real Life**: Operators can trust that the release tarball contains only intended product files, the Settings page tells the truth whether Telegram is coming from DB or env fallback, the page still works behind `/console/...`, and a fresh install leaves the notify worker and env-file permissions in a genuinely production-ready state.
- **Why This Phase Exists Now**: Review found the remaining gaps only after the earlier three phases landed. Shipping without this phase would mean calling the feature done while a P1 security flaw and several real deployment/runtime drifts remain open.
- **Stories Inside This Phase**:
  - Story 1: Repair the shipped deploy surface  
    `ops/build_release.sh` stops packaging the raw working tree, and `ops/install.sh` closes the env-file permission and notify-worker enablement gaps.
  - Story 2: Make Telegram config mean one thing everywhere  
    Runtime, `/settings`, `/settings/test`, preflight, and docs all use the same effective `DB > env fallback` story instead of parallel interpretations.
  - Story 3: Make the new settings surface work in real deployment topology and prove closure  
    The settings flow becomes root-path aware, and focused tests/proof close the mounted-path and release/install contract seams that review exposed.
- **Demo Walkthrough**: Build a release bundle while a local ignored directory exists and confirm it is absent from the archive. Start from env-only Telegram config and see `/settings` show a truthful configured state and allow Test. Exercise the settings flow under `/console/settings`. Verify the installer leaves the notify worker enabled and the operator env file hardened.
- **Unlocks Next**: Final execution and a clean review pass that can actually close the feature.

---

## 5. Phase Order Check

- [x] Phase 1 is obviously first
- [x] Each later phase depends on or benefits from the one before it
- [x] No phase is just a technical bucket with no user/system meaning

---

## 6. Approval Summary

- **Current phase to prepare next**: `Phase 4 - Review closure and release-proof hardening`
- **What the user should picture after that phase**: the Telegram settings feature is no longer “implemented but still risky”; it is truthful, proxy-safe, installer-safe, and artifact-safe enough to ship.
- **What will not happen until later phases**: no new product capability is being added here; this is the final follow-up phase that closes the release/readiness contract.

### Proposed Stories For Phase 4

- Story 1: Repair the shipped deploy surface
- Story 2: Make Telegram config mean one thing everywhere
- Story 3: Make the settings surface work in real deployed topology and prove closure

### High-Risk Items To Flag For Validating

- release export-surface strategy in `ops/build_release.sh`
- final closure-proof shape for the repaired packaging/install lane
