---
date: 2026-03-29
feature: ids-operator-console-production-hardening
categories: [pattern, decision, failure]
severity: critical
tags: [deployment, sqlite, preflight, reverse-proxy, operations]
---

# Learning: Split Runtime Verification From Operator Mutation Paths

**Category:** pattern
**Severity:** critical
**Tags:** [sqlite, bootstrap, migration, startup]
**Applicable-when:** Hardening a same-host service that owns local persistent state and needs both safe startup and explicit operator maintenance commands

## What Happened

The operator console originally bootstrapped its SQLite schema implicitly just by opening the runtime store. That made service startup look healthy in tests while hiding whether the deployment had actually been migrated, bootstrapped, or made production-ready. The hardening pass only became safe once runtime startup switched to pure verification and all shape-changing operations moved behind explicit CLI commands such as `migrate` and `bootstrap-admin`.

## Root Cause / Key Insight

For local-state services, "open the store" is often accidentally treated as harmless, but that blurs inspection, bootstrap, migration, and recovery into one code path. Once those concerns are mixed, review cannot tell whether a service is genuinely ready or merely self-mutating around missing prerequisites.

## Recommendation for Future Work

Keep two separate paths:

- runtime path: verify schema/config/bootstrap state and fail closed
- operator path: mutate state explicitly through CLI/admin workflows

Treat any startup-side schema creation or admin bootstrap as a production-hardening smell unless the feature explicitly requires self-initialization.

---

# Learning: Use Explicit Public Origin And Proxy Trust Inputs For Reverse-Proxied Services

**Category:** decision
**Severity:** standard
**Tags:** [reverse-proxy, fastapi, cookies, deployment]
**Applicable-when:** Shipping an internal app behind Nginx/Caddy/Apache where redirects, cookies, or generated links must reflect an HTTPS public origin

## What Happened

The hardening work stayed on the approved same-host topology instead of moving TLS into the app. Production behavior stabilized only after the runtime contract became explicit about `public_base_url`, `root_path`, and `forwarded_allow_ips`, with secure cookie posture tied to production mode.

## Root Cause / Key Insight

Proxy-aware behavior becomes unreliable when public origin, path prefix, and trusted forwarded-header sources are left implicit. The app may still "work" locally but drift once redirects, cookie flags, or readiness checks are exercised behind the real proxy.

## Recommendation for Future Work

Prefer reverse-proxy TLS termination for same-host internal services, but require:

- explicit public origin
- explicit trusted proxy inputs
- secure cookie defaults in production
- one smoke check that exercises the wired proxy-facing contract

---

# Learning: Preflight Must Consume The Same Secret Contract As Runtime

**Category:** failure
**Severity:** standard
**Tags:** [preflight, secrets, deployment, wiring]
**Applicable-when:** A deployment adds secret-file references or optional credential inputs after an initial runtime-only implementation

## What Happened

During review, a wiring seam appeared: runtime config already supported secret-file loading, but the preflight/deploy artifact path lagged behind for optional Telegram secret-file usage. That mismatch would have let deployment artifacts claim readiness against a narrower contract than the app actually consumed.

## Root Cause / Key Insight

Secret management drift often happens one layer later than the runtime code. It is easy to harden the loader and forget the preflight invocation or unit file, especially when some secrets are optional.

## Recommendation for Future Work

Whenever a runtime gains a new secret or proxy-facing input, update all three surfaces together:

1. runtime loader
2. preflight validator
3. deploy artifact invocation

Review should treat any mismatch between those three as a wiring defect, not a documentation nit.
