---
date: 2026-04-04
feature: ids-console-telegram-settings-and-deploy-readiness
categories: [pattern, failure]
severity: critical
tags: [release, packaging, security, install, settings, config, sqlite, deploy]
---

# Learning: Build Release Bundles From A Safe Export Surface

**Category:** failure
**Severity:** critical
**Tags:** [release, packaging, git, security]
**Applicable-when:** Building any release/deploy artifact from a source repository

## What Happened

`ops/build_release.sh` built the release tarball by running `tar -cf - .` from the repo root with a manual exclude list. This meant untracked and gitignored files (credentials, `.claude/`, local review artifacts) could silently leak into the shipped tarball. The review flagged this as a P1 security issue — anyone with access to the artifact could extract leaked secrets.

## Root Cause / Key Insight

A manual exclude list is a deny-list approach: it only excludes what you remember to exclude. Every new local-only directory or secret file requires a new exclusion entry. The safe approach is an allow-list: only tracked files are included by construction. `git archive HEAD` achieves this — it exports exactly the committed tree, ignoring everything else.

## Recommendation for Future Work

Always use `git archive` or `git checkout-index` to build release artifacts. Never archive the raw working tree with tar exclusions. Treat `wheelhouse/` or similar build outputs as post-export layers added to the staged clean checkout. Add a regression test that creates an ignored sentinel file and proves it is absent from the produced archive.

---

# Learning: Harden Pre-Seeded Secret Files During Install

**Category:** failure
**Severity:** critical
**Tags:** [install, permissions, secrets, security]
**Applicable-when:** Writing an installer that accepts a pre-seeded configuration or secret file as a supported input path

## What Happened

`ops/install.sh` applied secure permissions (`0640 root:ids-operator`) when creating the operator env file, but left an already-existing file untouched. The documented workflow tells operators to `cp` the env example before running the installer, which means the file arrives with the caller's default umask — often world-readable. The Telegram bot token lives in that file.

## Root Cause / Key Insight

Installers often have two code paths: "create new" and "skip existing." The skip-existing path assumed the file was already safe, but the documented pre-seed workflow produces files at default permissions. Any installer that accepts a pre-seeded secret file must re-harden it regardless of who created it.

## Recommendation for Future Work

When an installer discovers an existing secret/config file at the expected path, always re-apply the canonical ownership and mode (`chmod 0640`, `chown root:<service-group>`). Document this behavior so operators know the installer will fix permissions. Also apply the same hardening to the SQLite database file if it stores secrets (bot tokens, keys).

---

# Learning: DB-Backed Settings Need Key Allowlists And Paired Validation

**Category:** pattern
**Severity:** standard
**Tags:** [sqlite, settings, config, validation]
**Applicable-when:** Adding a generic key-value settings table to an application

## What Happened

The `console_settings` table used a generic `set_setting(key, value)` interface. During review, two problems surfaced: (1) a typo in any call site would silently write to the wrong key and the correct key would never be found, and (2) the save handler allowed persisting `chat_id` without `bot_token`, creating a half-configured state.

## Root Cause / Key Insight

A generic key-value store creates three drift seams: the write surface (what keys the UI sends), the read surface (what keys the resolver expects), and the runtime contract (what combinations are valid). Without a key allowlist at the write boundary, typos are invisible. Without paired-config validation, partial saves create states the runtime can't interpret.

## Recommendation for Future Work

Define `ALLOWED_SETTING_KEYS` as a set constant and validate in `set_setting()`. Use named constants for key strings across all call sites. When settings form a logical pair (token + chat_id, host + port), enforce the invariant at the write boundary: either both are present or both are cleared.

---

# Learning: Config Contract Must Be Shared, Not Reimplemented Per Surface

**Category:** failure
**Severity:** critical
**Tags:** [config, architecture, drift, preflight]
**Applicable-when:** Multiple system surfaces (runtime, UI, preflight, docs) need to interpret the same configuration

## What Happened

The `DB > env fallback` Telegram config contract was implemented correctly in the notification runtime's `resolve_telegram_config()`. But the Settings page reimplemented the DB-reading logic to detect config source, preflight reimplemented it with raw SQLite, and the save handler had its own partial-config rules. The review found 6 of 9 P2 findings were recurrences of a known "config drift" pattern.

## Root Cause / Key Insight

When a config interpretation rule exists in more than one place, each copy drifts independently. The approach document explicitly planned for "one shared contract" but execution delivered parallel reimplementations. The fix was to have `resolve_telegram_config_with_source()` return both the config and its source, so the UI doesn't need parallel reads, and to have preflight delegate to the shared resolver after its table-existence guard.

## Recommendation for Future Work

When a config precedence rule is needed by more than one surface, implement it exactly once and have all consumers call that single function. If a consumer needs additional metadata (like "where did this config come from?"), extend the canonical function's return type rather than reimplementing the logic. Test the shared contract from each consumer's perspective.

---

# Learning: Sanitize Error Details At User-Facing Boundaries

**Category:** failure
**Severity:** standard
**Tags:** [security, error-handling, api]
**Applicable-when:** Returning error information from an API endpoint that calls external services

## What Happened

The `/settings/test` endpoint caught `NotificationDeliveryError` and returned `str(exc)` directly in the JSON response. The exception messages could include raw HTTP status codes, Telegram API rejection descriptions, and `URLError` reasons exposing internal DNS/proxy topology.

## Root Cause / Key Insight

Passing raw exception messages to users is a recurring pattern because it's the simplest implementation. But exceptions from external service calls (HTTP clients, DNS, proxies) can contain internal infrastructure details that are useful for debugging but harmful if exposed.

## Recommendation for Future Work

At user-facing API boundaries, return generic error categories ("Failed to send", "Invalid configuration", "Service unavailable") and log the full exception server-side with `logger.warning()`. Never pass `str(exc)` from external service calls directly to the response body.
