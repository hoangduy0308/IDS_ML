---
date: 2026-03-29
feature: ids-model-bundle-promotion-hardening
categories: [pattern, decision, failure]
severity: critical
tags: [model-bundle, activation, compatibility, live-sensor, operator-console]
---

# Learning: Keep Production Model Selection On One Activation Contract

**Category:** pattern
**Severity:** critical
**Tags:** [model-bundle, compatibility, activation, deployment]
**Applicable-when:** Hardening a single-host ML runtime that ships a prebuilt model bundle into a supervised service

## What Happened

The IDS runtime originally allowed production wiring to mix `bundle_root`, raw `model_path`, raw `feature_columns_path`, and threshold overrides across CLI flags, runtime config, and systemd. That left a real deployment seam where the host could score with model bundle A while loading schema or threshold from B. The feature only became production-ready after model artifact, feature schema, and inference threshold traveled together in one versioned manifest and runtime/preflight resolved that manifest only through a host-local activation record.

## Root Cause / Key Insight

Model bundles are not safe just because the files live in the same directory. If production still accepts independent path overrides, the deployment contract remains split and operators can cut over into an incompatible semantic mix without realizing it.

## Recommendation for Future Work

Once a model is promoted into production, keep runtime selection on one activation contract:

- versioned manifest for model + schema + threshold + compatibility metadata
- one host-local activation record that points to the active bundle
- verify-only startup that fails closed on incompatibility
- explicit operator mutation commands for promote and rollback

Do not reintroduce raw production overrides for model path, schema path, or threshold after the activation contract exists.

---

# Learning: Reuse The Runtime Summary Path For Active-Model Visibility

**Category:** decision
**Severity:** standard
**Tags:** [observability, operator-console, summaries, readiness]
**Applicable-when:** A neighboring console or dashboard needs to display active runtime state without becoming the owner of that state

## What Happened

The feature needed operator visibility for the live model but explicitly stayed out of control-plane territory. The clean solution was to publish active-bundle metadata from the live sensor sink into the existing summary JSONL stream, then let the operator console ingest and surface that data through readiness and dashboard views.

## Root Cause / Key Insight

The console did not need to own model activation to make model state visible. Reusing the runtime summary path preserved the single-host boundary, kept the runtime independent of the console database, and avoided inventing a second source of truth for bundle state.

## Recommendation for Future Work

If a same-host service already publishes durable summary telemetry, prefer extending that summary contract for read-only operator visibility before adding a new state store or control plane.

---

# Learning: Test Failed Promotion And Post-Restore Visibility, Not Only Happy Paths

**Category:** failure
**Severity:** standard
**Tags:** [rollback, backup-restore, regression, review]
**Applicable-when:** A feature adds explicit lifecycle commands and backup/restore expectations around production runtime state

## What Happened

The happy-path promote and rollback flow was straightforward to verify, but the subtle production risks were elsewhere: a failed candidate promotion could accidentally disturb the previously active bundle, and a restore drill could bring back a healthy database while losing visibility of what bundle had last been seen. The review pass had to add regressions for both failure modes.

## Root Cause / Key Insight

Lifecycle hardening is easy to overfit to successful cutovers. The more realistic regressions are often "bad candidate leaves active state untouched" and "restore preserves the visibility path operators rely on to understand what is live."

## Recommendation for Future Work

For production lifecycle features, require at least one regression in each of these categories:

- failed mutation preserves last known-good active state
- backup/restore preserves the operator-facing visibility contract
- runbooks match the exact command and readiness semantics shipped by the code
