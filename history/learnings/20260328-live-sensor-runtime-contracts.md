---
date: 2026-03-28
feature: ids-live-host-based-ml-ids
categories: [pattern, decision, failure]
severity: critical
tags: [ids, live-sensor, daemon, preflight, journald, validation]
---

# Learning: Prefer Closed-Window Staged-Live Seams Over Unproven Direct Live Extraction

**Category:** decision
**Severity:** standard
**Tags:** [ids, extractor, staged-live, semantics]
**Applicable-when:** A live sensor must feed an upstream extractor or ETL tool whose direct interface-native mode is unproven or weakly documented

## What Happened

The first plan assumed the extractor could consume live traffic directly from the NIC. Validation disproved that assumption and forced the feature to pivot into a staged-live design: `live capture -> closed pcap window -> extractor -> adapter -> realtime pipeline`. Once the seam moved to closed windows, the team could keep `live-first` behavior at the capture boundary without reimplementing the CICFlowMeter-like feature family inside the daemon.

## Root Cause / Key Insight

The mistake was treating “live sensor” and “live extractor” as the same requirement. They are not. When the model contract depends on a specific flow-feature family, the safer path is often to keep capture live but make extraction consume only closed, bounded artifacts whose semantics are already supported by the upstream tool.

## Recommendation for Future Work

When a live feature depends on an external extractor, spike the extractor seam before planning around it. If direct live extraction is not proven, prefer a staged-live closed-window boundary and keep the downstream ML contract unchanged.

---

# Learning: Long-Running Daemons Need Durable Runtime Outputs, Not Shutdown-Only Publishing

**Category:** failure
**Severity:** critical
**Tags:** [daemon, durability, jsonl, restart, runtime]
**Applicable-when:** A continuously running process emits alerts, quarantines, or telemetry that operators expect to survive crashes and supervisor restarts

## What Happened

The first live-sensor sink model buffered alert, quarantine, and summary state in memory and only promoted durable output on `close()`. Review exposed that this is the wrong mental model for a supervised daemon: a restart or fatal exit can happen long before orderly shutdown, and in that model the process appears to work while its durable outputs lag behind reality.

## Root Cause / Key Insight

The sink design borrowed a batch-style transactional publish pattern from earlier tooling, but the live sensor is an append-oriented daemon. The core contract is not “publish once at the end”; it is “every material event is durable while the process is still alive.”

## Recommendation for Future Work

For daemon-style components, append durable output during runtime and reserve `close()` for final snapshots or final drains only. Do not make operator-facing evidence depend on graceful shutdown.

---

# Learning: Supervisor-Managed Capture Loops Must Classify Child Exit Explicitly

**Category:** failure
**Severity:** critical
**Tags:** [supervisor, dumpcap, fail-fast, process-lifecycle]
**Applicable-when:** A long-running service depends on a child capture or worker process and must distinguish expected termination from infrastructure failure

## What Happened

The live sensor originally treated the end of the notification stream as effectively successful completion. Review showed that EOF or a quiet stream is not enough for a capture contract: the daemon needed to classify the child process exit from return code plus stderr markers and fail fast on fatal capture errors so `systemd` could restart it.

## Root Cause / Key Insight

The bug came from conflating “no more window notifications” with “capture is healthy.” In supervised systems, those are different facts. A dead or broken child can produce the same outward symptom as a clean stop unless the parent inspects the exit path deliberately.

## Recommendation for Future Work

Whenever a daemon depends on a child process for sensing or ingestion, separate per-window/per-record recovery from process-level exit classification. Treat fatal child exits as supervisor-managed restart events, not as silent end-of-stream conditions.

---

# Learning: Systemd Packaging Is Safer With Exact-Path Preflight And One Config Source

**Category:** pattern
**Severity:** critical
**Tags:** [systemd, preflight, deployment, security]
**Applicable-when:** A Linux service depends on helper binaries, native libraries, device selection, and writable local paths

## What Happened

The first unit-file draft split configuration across duplicated literal paths and shell checks. The review fix consolidated deployment values into environment variables used by both `ExecStartPre=` and `ExecStart=`, then moved the real contract into a dedicated Python preflight script that checks the NIC, exact helper paths, `jnetpcap`, model bundle, and writable output parents.

## Root Cause / Key Insight

Deployment drift becomes much more likely when the unit file hardcodes runtime values in multiple places or relies on bare `PATH` lookups for privileged helpers. A daemon that starts with the wrong helper binary or a missing native dependency is harder to debug than one that fails before the main process loop begins.

## Recommendation for Future Work

For Linux services with host-level dependencies, define one configuration source and validate it in a dedicated preflight step using exact absolute paths. Keep helper binary discovery out of implicit shell lookup whenever the service boundary matters operationally or from a security standpoint.
