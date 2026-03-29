---
date: 2026-03-30
feature: ids-operator-console-ui-redesign
categories: [pattern, failure]
severity: critical
tags: [agent-coordination, bead-decomposition, ui, fastapi, jinja]
---

# Learning: Split UI Redesigns Into Foundation, Route, Surface, And Verification Beads

**Category:** pattern
**Severity:** standard
**Tags:** [bead-decomposition, ui, fastapi, jinja]
**Applicable-when:** Redesigning a server-rendered product surface that has one shared shell/CSS hotspot and multiple page-level templates.

## What Happened

The operator-console redesign was executed cleanly once the work graph was rebuilt around one foundation bead for `base.html`, shared partials, `console.css`, and `console.js`; one route/IA bead for `web.py`, `overview.html`, and `alerts.html`; then disjoint page-surface beads for `operations.html`, `reports.html`, `alert_detail.html`, and `login.html`, followed by a final verification/docs bead. That split let the redesign land a large visual overhaul on top of FastAPI + Jinja without reopening the same shared files across multiple execution lanes.

## Root Cause / Key Insight

The highest-risk files in UI work are not always the biggest templates; they are the shared shell, stylesheet, and route tree that every surface depends on. If those files are not isolated behind a single early bead, later page work turns into reservation conflicts and merge churn even when the product design itself is sound.

## Recommendation for Future Work

When redesigning a multi-page UI, isolate the shared shell/CSS/JS foundation into one first bead, isolate route/IA wiring into the next bead, and only then parallelize page-surface work on disjoint templates. Keep the final test/docs pass in its own closing bead.

---

# Learning: Use Live Bead State And Commit History To Rescue A Stalled Swarm

**Category:** failure
**Severity:** critical
**Tags:** [agent-coordination, swarming, recovery]
**Applicable-when:** A worker has claimed a bead or reserved files but stops reporting progress during multi-agent execution.

## What Happened

During this redesign, two worker attempts stalled at startup/progress-report boundaries while the validated graph still needed forward movement. The rescue path that worked was to treat the live bead graph, file reservations, `git log`, and test output as the source of truth: release stale reservations, reset the bead to `open`, respawn a narrower executor, and verify completion from closed beads and real commits instead of waiting indefinitely for status chatter.

## Root Cause / Key Insight

Worker messaging can drift or stall independently of actual repository progress. If the coordinator trusts chat status more than `br show`, reservations, and committed code, the swarm can freeze even though the system already contains enough signals to recover safely.

## Recommendation for Future Work

When a worker goes silent, time-box the wait, release stale reservations, reset the bead if needed, and recover using narrower one-bead executors. Verify recovery from the live graph and commit/test evidence, not from missing conversational acknowledgments.
