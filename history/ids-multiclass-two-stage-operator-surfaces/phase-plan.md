# Phase Plan: Two-Stage Family Operator Surfaces

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-operator-surfaces`
**Based on**:
- `history/ids-multiclass-two-stage-operator-surfaces/CONTEXT.md`
- `history/ids-multiclass-two-stage-operator-surfaces/discovery.md`
- `history/ids-multiclass-two-stage-operator-surfaces/approach.md`

---

## 1. Feature Summary

This feature makes the new stage-2 family signal usable inside the existing operator console instead of leaving it buried in raw runtime payloads. After it lands, an operator scanning the alert queue can see a compact family/status signal, then click into one alert and understand whether the system is saying "known family", "attack but unknown family", or "this is an older alert with no family enrichment yet." The work is phased because the explanation surface has to become trustworthy before the queue starts using a compact shorthand that operators will rely on under time pressure.

---

## 2. Why This Breakdown

- Phase 1 has to happen first because one alert detail page is where the operator learns what the new family signal actually means; shipping queue shorthand first would make `unknown` easy to misread.
- Phase 2 stays separate because once one alert is trustworthy, the remaining job is to make the high-volume triage flow and docs match that same meaning without widening scope into reports or automation.
- This phased approach contains the real risk: semantic drift between runtime, helper code, templates, and docs. By solving "one alert explained correctly" first, later rollout becomes mostly propagation and proof instead of guesswork.

---

## 3. Phase Overview Table

| Phase | What Changes In Real Life | Why This Phase Exists Now | Demo Walkthrough | Unlocks Next |
|-------|----------------------------|---------------------------|------------------|--------------|
| Phase 1: Make One Alert Explain The Family Signal | An operator can open one alert detail page and see a clear family outcome: known family, unknown family, or legacy/unavailable, with supporting confidence context and no change to triage controls. | This is obviously first because queue shorthand is unsafe until one clicked-through explanation surface is correct. | Replay or seed one enriched alert and one legacy alert, open `/alerts/{id}`, and see both render truthful family context instead of raw payload guessing or silent omission. | The queue can now show the same signal compactly without inventing new meaning. |
| Phase 2: Bring The Same Meaning Into The Triage Queue And Docs | The alerts queue becomes family-aware in a compact, scan-friendly way, and the operator docs/specs explain the same states the UI now shows. | Once Phase 1 makes one alert trustworthy, the value shifts to fast triage and durable contract proof. | Open `/alerts`, scan rows with known/unknown/legacy states, then read the updated surface spec and tests that pin those exact meanings. | Review / ship / later family analytics work if desired. |

---

## 4. Phase Details

### Phase 1: Make One Alert Explain The Family Signal

- **What Changes In Real Life**: an operator investigating a single alert no longer has to infer stage-2 family meaning from raw JSON or ignore it entirely. The detail page itself explains whether the family signal is confident, abstained to `unknown`, or absent because the alert predates the enrichment rollout.
- **Why This Phase Exists Now**: this is the smallest believable slice of the feature. If the detail page cannot explain the signal honestly, every later queue-level badge becomes dangerous shorthand.
- **Stories Inside This Phase**:
  - Story 1: Shape one canonical family view model for alerts — normalize family metadata from persisted payloads into stable queue/detail keys.
  - Story 2: Teach the detail page to explain the signal — render family label, status, confidence context, and explicit legacy/unavailable fallback.
  - Story 3: Prove one-alert semantics with route tests — pin known, unknown, and legacy rendering through the real `/alerts/{id}` route.
- **Demo Walkthrough**: seed or replay three representative alerts: one enriched `known`, one enriched `unknown`, and one legacy row without family fields. Open each alert detail page and verify the operator can tell, without reading raw JSON, what the system believes and why.
- **Unlocks Next**: the alerts queue can safely adopt a compact family/status presentation because operators now have a trustworthy explanation surface to click into.

### Phase 2: Bring The Same Meaning Into The Triage Queue And Docs

- **What Changes In Real Life**: the operator no longer needs to open every alert to discover family context. The queue itself shows a compact family/status signal that matches the detail page, and the docs/specs explain those states so the meaning survives beyond one implementation session.
- **Why This Phase Exists Now**: after Phase 1, the family signal is trustworthy on one alert. The next practical step is to make that same meaning usable at queue speed and durable in docs/tests.
- **Stories Inside This Phase**:
  - Story 1: Add compact family/status presentation to queue rows — extend the triage table without turning it into a report or dashboard.
  - Story 2: Handle queue-level fallback and light guidance — make `unknown` and legacy/unavailable readable at a glance without extra workflow.
  - Story 3: Freeze the operator contract in tests and docs — update the surface spec and route proofs so future work cannot silently redefine the family states.
- **Demo Walkthrough**: open `/alerts` and scan a mixed queue where one row shows a known family, one shows `unknown`, and one shows a legacy/unavailable state. Click through to a detail page and see that the deeper explanation matches the queue badge. Then inspect the updated surface spec and tests that define the same behavior.
- **Unlocks Next**: final review and any later work on analytics, reports, or family-aware automation.

---

## 5. Phase Order Check

- [x] Phase 1 is obviously first
- [x] Each later phase depends on or benefits from the one before it
- [x] No phase is just a technical bucket with no user/system meaning

---

## 6. Approval Summary

- **Current phase to prepare next**: `Phase 1 - Make One Alert Explain The Family Signal`
- **What the user should picture after that phase**: opening one alert detail page is enough to understand whether the new family signal is known, unknown, or simply unavailable on that older alert.
- **What will not happen until later phases**: the alerts queue will not carry the compact family shorthand yet, and docs/specs will not be finalized until Phase 2.
