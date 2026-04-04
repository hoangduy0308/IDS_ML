# Discovery Report: Telegram Settings UI & Deploy Readiness

**Date**: 2026-04-04
**Feature**: ids-console-telegram-settings-and-deploy-readiness
**Mode**: review follow-up replanning
**CONTEXT.md reference**: `history/ids-console-telegram-settings-and-deploy-readiness/CONTEXT.md`

---

## Institutional Learnings

### Critical Patterns (Always Applied)

- **Use exact deploy/runtime contracts, not inferred ones (20260328)**: systemd, preflight, and runtime must agree on the same worker and config surface.
- **Split runtime verification from operator mutation (20260329)**: review follow-up should preserve the current boundary where runtime reads and verifies while explicit admin or install paths mutate state.
- **Proxy-facing behavior must honor explicit `root_path` and public origin (20260329)**: a page that renders behind a reverse proxy but posts to the wrong path is still broken.
- **Packaging proof must be scrubbed and artifact-real, not warmed-worktree friendly (20260403)**: deploy closure is not real unless the shipped surface is the one being verified.
- **Notification ownership stays outside the web process (20260329)**: the notify worker is a first-class supervised runtime, so deploy fixes must treat it like one.

### Strong Domain Matches

| File | Key Insight | How It Applies Here |
|------|-------------|---------------------|
| `history/learnings/20260329-operator-console-production-hardening.md` | Preflight must consume the same secret/proxy contract as runtime. | The reopened settings/UI follow-up cannot let runtime, `/settings`, and preflight disagree about what “configured” means. |
| `history/learnings/20260329-notification-runtime-contracts.md` | Optional Telegram config is a drift trap unless loader, systemd, docs, and tests share one exact contract. | The review beads are mostly that drift surfacing again in the UI and installer. |
| `history/learnings/20260403-packaging-contract-proof.md` | Packaging closure requires proving the real shipped artifact surface, not a dirty developer tree. | The blocking review bead is precisely an artifact-surface leak in `ops/build_release.sh`. |
| `history/learnings/20260329-operator-console-production-hardening.md` | Reverse-proxied services must use explicit `root_path` and public-origin-aware behavior. | The new Settings save/test flow currently violates that contract. |

### New Candidates Already Flagged In This Session

- `safe-export-surface-release-bundles`
- `harden-preseeded-secret-files-during-install`

These live in `.khuym/findings/learnings-candidates.md` and should be revisited after the follow-up phase closes.

---

## Review-Triggered Scope

The original three execution phases landed, but review reopened the feature with four concrete follow-up beads:

| Bead | Severity | Plain-language problem |
|------|----------|------------------------|
| `ids_ml_new-i7oa.1` | P1 | `ops/build_release.sh` archives the live working tree, so ignored or untracked local files can leak into release tarballs. |
| `ids_ml_new-fhlz` | P2 | `/settings` and `/settings/test` only look at DB-backed Telegram config, even though D1 says env values remain the fallback. |
| `ids_ml_new-yw5l` | P2 | Settings form/test/redirect paths are hardcoded to `/settings...`, so the feature breaks under a non-empty `root_path`. |
| `ids_ml_new-fsoc` | P2 | The installer leaves a pre-seeded env file at its existing permissions and does not enable the notify worker with the rest of the runtime surface. |

In practical terms, the codebase is not in “new feature planning” mode anymore. It is in “review closure planning” mode for a smaller, sharper phase that makes the already-built feature actually safe to ship.

---

## Architecture Snapshot

### Affected Runtime Surfaces

| Area | Why It Matters In The Follow-Up |
|------|---------------------------------|
| `ids/console/web.py` | Must stop giving operators a false “not configured” answer and must generate settings URLs that survive reverse-proxy mounting. |
| `ids/console/notification_runtime.py` | Already contains the effective `DB > env fallback` behavior; likely becomes the canonical config-resolution source. |
| `ids/ops/operator_console_preflight.py` | Must stay aligned with runtime and should not drift into a second interpretation of Telegram enablement. |
| `ops/build_release.sh` | Holds the blocking packaging leak: it stages from the raw working tree instead of a safe export surface. |
| `ops/install.sh` | Needs installer hardening for pre-seeded env files and must enable the notify worker as part of the supported runtime surface. |
| `ops/README-deploy.md`, `docs/current/operations/deployment_quickstart.md` | Must describe the corrected release/install/runtime contract after the fixes land. |

### Existing Good Patterns Worth Reusing

- `ids/console/notification_runtime.py::_resolve_telegram_config()` already expresses the intended precedence rule at runtime.
- FastAPI/Starlette already support `root_path`; the bug is in the new settings links and redirects, not in the platform choice.
- The repo already has proof-oriented packaging learnings and tests around scrubbed installs; the follow-up should reuse that mindset instead of inventing a weaker “just exclude one more folder” workaround.

---

## Pattern Analysis

### 1. Safe Release Export Surface

Current release staging is tar-based and hand-maintained. Review exposed that this is not a trustworthy packaging boundary once local-only files exist in the checkout. The new plan must treat the export surface itself as a product contract: either tracked-only or explicitly allowlisted.

### 2. One Effective Telegram Config Story

The runtime already knows how to answer “what Telegram config is active right now?” The reopened UI and preflight issues happened because the answer was reimplemented in adjacent layers. The follow-up should collapse those competing interpretations into one shared story:

- DB values override env values
- env values still count when DB values are absent
- worker, UI, preflight, docs, and tests all tell the same story

### 3. Root-Path-Aware Settings Interactions

The app-level proxy contract is not broken globally. The regression is local to the new settings surface because the form action, fetch URL, and redirect are hardcoded to leading-slash paths. This is a focused repair with focused proof.

### 4. Installer Closure Means More Than “Files Were Copied”

The installer already seeds config, creates a venv, and installs units. Review showed that “install script exists” was weaker than “install path is actually safe and leaves the advertised worker/runtime surface enabled.” That means install closure has to include file-mode hardening and service-enable correctness, not just docs.

---

## Constraints Analysis

### Product Constraints From CONTEXT.md

- **D1** still governs the follow-up: DB overrides env, but env remains fallback.
- **D2** still governs the UI: the Settings page should give operators a truthful view/test path for Telegram without exposing the token.
- **D3** is the reason this follow-up exists at all: release readiness is not satisfied while the artifact surface can leak local files or while supported deploy shapes still break.
- **D4** stays locked: fix the existing tarball + install.sh model; do not replace it with Docker or a new installer model.

### Technical Constraints

- No new dependencies are needed.
- The work crosses Python, Jinja2/JS, shell scripts, service units, and docs, so planning must keep write scope deliberate.
- Packaging proof and installer hardening carry real blast radius because they affect the shipped artifact, not just developer ergonomics.

---

## Summary For Synthesis

The feature is not being re-planned from scratch. The first three phases remain historically correct, but review proved they did not fully close the ship-readiness contract. The next plan needs one follow-up phase that makes four things true together:

1. Release bundles cannot leak local checkout junk.
2. Telegram config has one truthful meaning across runtime, UI, and preflight.
3. The Settings surface works behind a supported reverse-proxy path prefix.
4. The installer leaves the notify worker and operator env-file permissions in a genuinely production-ready state.

That is the smallest believable “feature is really ready now” slice left.
