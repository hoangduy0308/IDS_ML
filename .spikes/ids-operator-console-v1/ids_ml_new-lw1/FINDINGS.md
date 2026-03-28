# Spike Findings: ids_ml_new-lw1

## Question

Can Telegram delivery fail independently from local operator state?

## Result

**YES**

## Evidence

- The official Telegram Bot API exposes a straightforward `sendMessage` method over HTTP and documents a machine-readable API contract:
  - [Telegram Bot API](https://core.telegram.org/bots/api)
- The Bot API documents `retry_after` in response parameters for flood-control style backoff handling, which gives a concrete seam for retry logic instead of making notification delivery synchronous and brittle.
- The locked product boundary in [CONTEXT.md](F:/Work/IDS_ML_New/history/ids-operator-console-v1/CONTEXT.md) requires local dashboard/storage durability first, with Telegram only as an outbound notification path layered on top.
- The existing repo's operator-facing patterns already favor durable local evidence first, then downstream surfaces.

## Validated Constraints

1. Alert/anomaly persistence and triage state must commit locally before any Telegram delivery attempt is made.
2. Telegram sending should happen from a decoupled notifier path with retry bookkeeping, not inline as a prerequisite for ingest or UI mutation.
3. Suppression applies before Telegram delivery, but notifier failures must still leave the local operator record intact and visible.
4. Retry/backoff state should be durable so restarts do not erase delivery history or flood-control delays.

## Impact on Plan

- Telegram remains a viable first outbound channel.
- Validation is not blocked on notifier integration.
- Execution beads should lock around persistent delivery bookkeeping, suppression-before-send, and failure isolation from ingest/triage.
