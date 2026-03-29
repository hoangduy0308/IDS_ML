---
date: 2026-03-29
feature: ids-operator-console-notification-runtime-hardening
categories: [decision, failure, pattern]
severity: standard
tags: [notifications, runtime, readiness, deploy, recovery]
---

# Learning: Keep Notification Ownership Outside The Web Process

**Category:** decision
**Severity:** standard
**Tags:** [notifications, runtime, systemd]
**Applicable-when:** Any same-host maintenance path needs to run continuously under supervisor control

## What Happened

The notification path became production-ready only after the worker was treated as a separate same-host runtime instead of a background thread inside `ids_operator_console_server.py`. The shipped shape uses `notify-worker` as the explicit operator entrypoint and keeps the web service in verify-only mode.

## Root Cause / Key Insight

Background maintenance inside the web process blurs failure domains and makes readiness harder to reason about. A separate worker process keeps queue/dispatch/retry ownership explicit and lets systemd supervise the runtime cleanly.

## Recommendation for Future Work

Always keep same-host maintenance work outside the web request path. If the runtime needs continuous ownership, give it a separate worker entrypoint and supervise that process explicitly.

---

# Learning: Make Supervised Workers Long-Running By Default

**Category:** failure
**Severity:** standard
**Tags:** [daemon, supervisor, scheduling]
**Applicable-when:** Shipping a worker unit that is supposed to own an always-on maintenance loop

## What Happened

The first review pass found that `notify-worker` was effectively one-shot: the systemd unit and CLI both used `--iterations 1`, and the worker helper accumulated results in a way that fit bounded runs but not a real daemon. The fix pass changed the CLI default to supervised long-running mode and honored the configured poll cadence.

## Root Cause / Key Insight

It is easy to make a worker look wired while still leaving it functionally one-shot. If the default execution path exits cleanly after one cycle, the runtime does not actually own the queue.

## Recommendation for Future Work

Never default a supervised worker to a bounded iteration count unless the command name clearly says `run-once`. Add a regression test for poll cadence and make the long-running contract the default behavior.

---

# Learning: Sanitize Public Readiness, Expose Detail In Operator Status

**Category:** decision
**Severity:** standard
**Tags:** [readiness, auth, exposure, ops]
**Applicable-when:** A public `/readyz` surface must stay actionable without leaking operator details

## What Happened

The readiness payload initially exposed notification target and raw-ish error detail to unauthenticated callers. The fix split the contract: `/readyz` keeps the notification component visible but sanitized, while `notify-status` retains the operator-facing detail.

## Root Cause / Key Insight

Public health endpoints tend to be probed by load balancers and infrastructure, not just humans. That makes target IDs and raw error messages a reconnaissance surface even when the underlying feature is healthy enough to keep serving traffic.

## Recommendation for Future Work

When a health surface is public, keep counts and state but sanitize target and error text. If operators need the full detail, provide an explicit authenticated or CLI status surface alongside it.

---

# Learning: Persist Delivery State Locally And Verify Redrive After Restore

**Category:** decision
**Severity:** standard
**Tags:** [sqlite, recovery, restore, redrive]
**Applicable-when:** A same-host notification system needs restart-safe retry and post-restore recoverability

## What Happened

The feature kept `notification_deliveries` as the local source of truth and used the existing SQLite state for retry, failure, and redrive semantics. The recovery test was strengthened so restore verification now exercises `notify-redrive`, not only visibility of failed rows.

## Root Cause / Key Insight

For same-host runtime contracts, local persisted delivery state is simpler and more reliable than introducing a broker. But visibility alone is not enough; operators need a proven recovery path that moves restored failures back into actionable queue state.

## Recommendation for Future Work

Keep delivery lifecycle state local when the runtime is same-host and single-queue. Always add a restore-plus-redrive test, not just a restore-visibility test, whenever failed work must remain recoverable after restart.

---

# Learning: Fail Closed On Partial Telegram Config And Wire It Everywhere

**Category:** pattern
**Severity:** standard
**Tags:** [deploy, preflight, config, testing]
**Applicable-when:** A service has an optional secret pair that becomes mandatory only when the feature is enabled

## What Happened

The deploy and preflight contract only became robust after Telegram token/chat pairing was verified end-to-end and the systemd units referenced the same worker contract as the CLI. Tests now cover token-only and chat-only cases, and the service units point to the same explicit worker path.

## Root Cause / Key Insight

Optional notification config is a drift trap: code can support it while deploy and preflight silently disagree about when it is actually enabled. A single paired-config contract prevents that split and makes failures obvious early.

## Recommendation for Future Work

Whenever an optional subsystem becomes production-enabled, wire loader, preflight, systemd, docs, and tests to one exact contract. Add negative tests for partial configuration so the system fails closed instead of half-enabling.
