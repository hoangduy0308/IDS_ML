---
title: Same-Host Stack Runtime Hardening
date: 2026-03-29
feature: ids-same-host-stack-runtime-hardening
tags:
  - stack-runtime
  - bootstrap
  - diagnostics
  - redaction
  - restore
  - testing
---

# Same-Host Stack Runtime Hardening

## Summary

This feature succeeded once the stack contract stopped behaving like a thin wrapper around happy-path commands and started behaving like a real host lifecycle surface. The main rework after review was not new capability; it was closing the gap between what the stack layer promised and what it actually verified, especially around bootstrap completion, degraded diagnostics, secret-safe output, and restore failure coverage.

## Patterns

### Full lifecycle verification before success
- Category: pattern
- Severity: critical
- Domain: bootstrap, restore, verification
- Applicable when: a new stack-orchestrator command claims to complete bootstrap, recovery, or restore verification for a same-host deployment

A canonical stack command must execute the full lifecycle it advertises before returning success. In practice that meant `bootstrap` had to run post-start `status` and `smoke` checks and expose the proxy seam result when configured, rather than returning success immediately after service start. The same lesson applies to post-restore flows: recovery is not complete until final readiness and visibility checks pass.

### Degraded and redacted by default
- Category: pattern
- Severity: critical
- Domain: diagnostics, secrets, cli
- Applicable when: a runtime or operations CLI emits health, smoke, or recovery output that may be consumed by humans and automation

Stack-level diagnostics should default to structured degraded payloads and redacted output on expected failures. Raw tracebacks, secret-bearing argv echo, and sensitive notification details widened the operator surface and made automation brittle. The fix was to normalize expected contract failures into degraded payloads and keep notification detail redacted by default.

## Decisions

### GOOD_CALL: keep restore mutation component-owned
- Category: decision
- Severity: standard
- Domain: restore, ownership
- Applicable when: a stack layer sits above component-specific restore commands

The original planning choice to keep restore mutation in component owners was correct. Review pressure did not require a new restore wrapper; it required stronger verification and stronger tests around the existing restore boundary.

### TRADEOFF: reject inline bootstrap passwords
- Category: decision
- Severity: standard
- Domain: bootstrap, secrets
- Applicable when: a setup or bootstrap command needs an operator credential

Rejecting inline `--admin-password` simplified the leak surface and aligned with the documented password-file path. This traded some operator convenience for a much safer default and a smaller set of redaction paths.

## Failures

### Failure: wired contract drift at the stack boundary
- Category: failure
- Severity: critical
- Domain: bootstrap, review
- Applicable when: docs, tests, and CLI all reference the same lifecycle command

The first implementation documented a full bootstrap lifecycle but only executed the mutation and service-start subset. Tests accidentally blessed that truncated sequence. Prevention rule: whenever a stack command is canonical in docs, add tests that prove every promised phase actually runs.

### Failure: new runtime-health seams were only tested on the happy path
- Category: failure
- Severity: standard
- Domain: live-sensor, testing
- Applicable when: adding a new read-only health seam or health taxonomy

The live-sensor seam introduced multiple failure states, but only a small subset was covered initially. Prevention rule: when a new health seam emits named degraded states, pin every emitted state with tests before the seam becomes a stack-level gate.

### Failure: restore verification stayed under-tested in the failure direction
- Category: failure
- Severity: standard
- Domain: restore, testing
- Applicable when: post-restore readiness depends on multiple gates

The first test pass focused on successful restore flows and left inventory and final-gating failures largely unpinned. Prevention rule: if restore is a first-class contract, test both the positive path and the failure matrix for missing artifacts, secret rebinding, notification redrive, and final visibility gating.

## Recommendations

- Treat canonical stack commands as promises, not conveniences: they must execute the whole advertised lifecycle.
- Prefer degraded structured output to exceptions for expected contract failures.
- Default every stack health surface to redacted output unless an explicit operator-only diagnostic mode is requested.
- When a feature adds a new health taxonomy, make branch-complete tests part of the initial implementation rather than a review follow-up.
