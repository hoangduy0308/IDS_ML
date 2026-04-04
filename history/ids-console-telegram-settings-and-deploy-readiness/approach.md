# Approach: Telegram Settings UI & Deploy Readiness

**Date**: 2026-04-04
**Feature**: ids-console-telegram-settings-and-deploy-readiness
**Mode**: review follow-up replanning
**Based on**:
- `history/ids-console-telegram-settings-and-deploy-readiness/CONTEXT.md`
- `history/ids-console-telegram-settings-and-deploy-readiness/discovery.md`

---

## 1. Gap Analysis

| Surface | Have Now | Need Next | Gap Size |
|---------|----------|-----------|----------|
| Release bundle export surface | `ops/build_release.sh` archives the raw working tree with a manual exclude list | A tracked or allowlisted export surface that cannot include ignored/untracked local files | High |
| Effective Telegram config story | Runtime uses `DB > env fallback`; `/settings` and `/settings/test` only read DB; preflight has its own resolution path | One shared interpretation of Telegram enablement across runtime, UI, preflight, docs, and tests | Medium |
| Settings path behavior under proxy mount | New settings links and redirects are hardcoded to `/settings...` | Root-path-aware settings form/test/redirect behavior with mounted-path coverage | Medium |
| Installer closure | Installer creates/seeds files and installs units, but does not re-harden a pre-seeded env file and does not enable the notify worker | A production-ready install path that secures the operator env file and leaves the worker surface enabled | Medium |
| Deployment proof | Current checks are strong on strings and focused tests, but weak on final release/install closure for this reopened lane | Focused proof that the repaired export surface, installer contract, and settings/runtime contract now hold together | High |

---

## 2. Recommended Approach

Treat the follow-up as one review-closure phase with three tightly related stories instead of four unrelated patchlets.

### Story A: Repair the shipped deploy surface

Close the blocking packaging gap first. `ops/build_release.sh` should stop treating the developer checkout as the product and instead build from a safe export surface. In the same story, harden `ops/install.sh` so it applies secure ownership/mode to an already-seeded operator env file and enables the notify worker with the rest of the supported runtime surface.

Why together: these are both “what actually lands on the target host” problems. Fixing only one still leaves deploy readiness false.

### Story B: Collapse Telegram config drift into one contract

Promote one effective Telegram config story across the system:

- DB values override env values
- env values still count when DB is absent
- UI status and test behavior match worker behavior
- preflight does not silently interpret enablement differently from runtime

The simplest credible way to do that is to reuse or extract the runtime precedence logic rather than keep parallel interpretations in `web.py` and preflight.

### Story C: Make the settings flow work in real deployed topology and prove closure

Fix root-path-aware settings interactions, then add focused proof for:

- mounted `/console/...` settings save/test flow
- env-only fallback surfaced truthfully in UI/tests
- release export surface excluding local ignored files
- install/runtime contract for worker enablement and env-file hardening

Why last: once the deploy surface and config meaning are fixed, the proof can validate the final intended contract instead of re-proving an intermediate shape.

---

## 3. Why This Approach

- It respects **D4** by fixing the existing tarball + install.sh deployment model instead of replacing it.
- It respects **D1/D2** by making the UI tell the truth about the same Telegram config the worker is actually using.
- It keeps the follow-up small enough to reason about as a closure lane rather than reopening the entire feature.
- It uses the strongest existing institutional guidance: packaging proof must be real, proxy-facing paths must be explicit, and deploy/runtime/preflight contracts must not drift.

---

## 4. Alternatives Considered

### Option A: Patch the four review beads independently with no shared phase design

- **Why considered**: fastest apparent path
- **Why rejected**: these are not isolated bugs in practice. The UI fallback issue, installer hardening, and preflight/runtime alignment are all symptoms of one contract drift problem. Treating them as unrelated increases the chance of another review rerun.

### Option B: Only expand the manual tar exclude list

- **Why considered**: smallest code change for the P1 blocker
- **Why rejected**: brittle. It solves the currently visible ignored directory and leaves the release surface unsafe the next time another local-only path appears.

### Option C: Narrow the docs instead of fixing behavior

- **Why considered**: some P2 issues could be “documented away”
- **Why rejected**: D3 is explicit about real deploy readiness. A settings page that lies about configured state, a mounted path that breaks on submit, or an installer that leaves secrets loose are behavior problems, not documentation nits.

---

## 5. Risk Map

| Component | Risk Level | Reason | Validation Need |
|-----------|------------|--------|-----------------|
| Safe export-surface change in `ops/build_release.sh` | **HIGH** | Security-sensitive packaging boundary; easy to fix shallowly and still miss artifact leakage paths | Validate with focused proof or spike if the export strategy is ambiguous |
| Installer hardening + notify worker enablement | **MEDIUM** | Small code surface, but directly affects shipped runtime behavior on target hosts | Validate with focused contract checks |
| Effective Telegram config unification across runtime/UI/preflight | **MEDIUM** | Cross-cutting behavioral contract drift across multiple modules | Validate that one source of truth is being used |
| Root-path-aware settings interactions | **MEDIUM** | Proxy-mounted apps often look fine until a redirect or POST path is exercised | Validate with mounted-path tests |
| Final proof coverage for the closure lane | **HIGH** | Review already proved that “looks done” is weaker than “artifact/runtime contract is closed” | Validate with explicit closure-oriented checks, not broad optimism |

### HIGH-Risk Summary

Two items are high enough that validating should inspect them carefully before execution approval:

- release export-surface strategy
- final proof shape for the repaired deploy/packaging lane

These may not require a separate spike if the plan/checker finds the execution shape clear, but they should not be treated as routine low-risk cleanup.

---

## 6. Proposed File Structure

```
ops/
  build_release.sh                    # MODIFY: safe export surface, not raw working tree
  install.sh                          # MODIFY: harden pre-seeded env file, enable notify worker
  README-deploy.md                    # MODIFY: reflect corrected install/runtime story
  ids-operator-console.env.example    # MODIFY if wording or permission guidance needs tightening

ids/console/
  web.py                              # MODIFY: effective-config truth in UI + root-path-aware redirects
  notification_runtime.py             # MODIFY or EXTRACT: canonical effective Telegram config resolver
  templates/settings.html             # MODIFY: root-path-aware form action / data hooks
  static/console.js                   # MODIFY: root-path-aware test endpoint call

ids/ops/
  operator_console_preflight.py       # MODIFY: consume the same effective Telegram config contract

tests/console/
  test_ids_operator_console_web.py    # MODIFY: env-fallback truth + root_path flow coverage
  test_ids_operator_console_notifications.py
                                     # MODIFY if canonical resolver moves or broadens

tests/ops/
  test_ids_operator_console_preflight.py
                                     # MODIFY: keep preflight aligned with the effective config contract
  test_deploy_helper_contract.py      # MODIFY: closure-oriented checks for export/install contract

docs/current/operations/
  deployment_quickstart.md            # MODIFY: corrected release/install/runtime flow
  README.md                           # MODIFY if operator-facing guidance changes
```

---

## 7. Dependency Order

```
Layer 1: Decide and implement the safe release/install contract
Layer 2: Unify the effective Telegram config story across runtime/UI/preflight
Layer 3: Make the settings surface root-path aware against the final contract
Layer 4: Add focused closure proof and documentation updates
```

### Why This Order Makes Sense

- There is no point proving settings/UI behavior against a release path that still leaks local files.
- There is no point writing final mounted-path tests before the config contract itself is truthful.
- Documentation should be updated against the repaired runtime/deploy story, not the pre-fix story.

---

## 8. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied Here |
|-----------------|-------------|------------------|
| `20260403-packaging-contract-proof.md` | Packaging closure must prove the real shipped artifact surface | The follow-up treats the release export surface as a first-class contract, not a tar implementation detail |
| `20260329-operator-console-production-hardening.md` | Proxy-facing services need explicit `root_path` / public-origin-aware behavior | Settings save/test/redirect paths are planned as a root-path-aware repair, not a local-only fix |
| `20260329-notification-runtime-contracts.md` | Optional Telegram config must be wired everywhere to one exact contract | The UI, worker, preflight, installer, and docs are planned as one config-story repair |
| `20260329-notification-runtime-contracts.md` | Notify worker is its own supervised runtime surface | Installer follow-up includes enabling the worker as part of the supported runtime set |

---

## 9. Open Questions For Validating

- Is the safest export-surface implementation obvious enough to execute directly, or does validating need a short spike to choose between tracked-only export and explicit allowlist staging?
- Can the current runtime resolver be reused directly by UI/preflight, or does the phase need one extracted helper to avoid another drift seam?

These are execution-shaping questions, not product questions. They should be settled in validating before code is written.
