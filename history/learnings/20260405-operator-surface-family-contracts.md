---
date: 2026-04-05
feature: ids-multiclass-two-stage-operator-surfaces
categories: [pattern, decision, failure]
severity: critical
tags: [operator-console, semantics, queue, detail, testing, bead-decomposition]
---

# Learning: Normalize Additive Runtime Fields Into One UI-Facing State Contract

**Category:** pattern
**Severity:** standard
**Tags:** [operator-console, semantics, runtime-contract]
**Applicable-when:** A new runtime signal is stored in optional payload/blob fields and must appear on more than one operator surface without opening a schema lane.

## What Happened

This feature succeeded because it introduced one canonical helper, `build_alert_family_view()` in `ids/console/alerts.py`, to convert persisted `payload_json` into a stable UI-facing family contract. The detail page, queue row, route tests, and docs all consumed that normalized contract instead of re-decoding `payload_json` independently. That let the operator-facing slice stay inside console files while preserving the meanings already locked in the runtime lane.

## Root Cause / Key Insight

The hard problem was semantic drift, not infrastructure. Once the runtime lane had already settled on additive family fields, the correct move was to normalize that contract once at the consumer boundary and project it at different UI densities. Repeating the interpretation rule in templates or route handlers would have recreated the same drift pattern already seen in other repo lanes.

## Recommendation for Future Work

When a new runtime field must appear on multiple surfaces, build one payload-to-view-model normalizer first and make every queue/detail/API/doc consumer read that contract instead of re-deriving meaning locally.

---

# Learning: Sequence Explanation Surfaces Before Queue Shorthand

**Category:** decision
**Severity:** standard
**Tags:** [ui, queue, detail, rollout]
**Applicable-when:** A new model state or label could be operationally misleading if operators see the shorthand before they can click through to a trustworthy explanation.

## What Happened

This lane deliberately made `/alerts/{id}` trustworthy before teaching `/alerts` to show a compact `Family Signal` column. Phase 1 locked the detail-page explanation for `known`, `unknown`, `benign`, and `legacy_unavailable`; only after that did Phase 2 propagate the same meaning into the queue and docs. The queue work then became mostly propagation and contract freeze instead of guesswork.

## Root Cause / Key Insight

`unknown` was the dangerous state here. If queue shorthand had shipped first, operators could have read it as benign traffic, missing data, or runtime failure. By sequencing the explanation surface first, the compact queue surface inherited a meaning that was already visible, testable, and reviewable.

## Recommendation for Future Work

When introducing a state label that can be misunderstood, ship the clicked-through explanation surface first and only then add the high-volume summary surface.

---

# Learning: Write The Full Visible State Matrix Before Implementing A Stateful UI Surface

**Category:** failure
**Severity:** critical
**Tags:** [testing, state-machine, review, ui-contract]
**Applicable-when:** A UI surface must distinguish several operator-visible semantic states and each state carries different label/copy/field-presence rules.

## What Happened

Phase 1 initially covered `known`, `unknown`, and `legacy` well enough to look complete, but `benign` was under-specified in both helper behavior and route proof. That allowed `attack_family`, confidence, and margin to leak through a `benign` state until review-fix bead `ids_ml_new-3rc7.9` forced the helper and route tests to pin the full four-state contract. The review-fix loop was not caused by missing infrastructure; it was caused by an incomplete visible state matrix.

## Root Cause / Key Insight

The implementation and tests followed the demo path rather than the full contract table. Locked decisions already required a four-state model (`known | unknown | benign | legacy_unavailable`), but the first-pass proof did not enforce one regression case per state. In stateful operator UI work, an omitted state is not a small gap; it is usually where semantic leakage hides.

## Recommendation for Future Work

Before implementing a stateful UI surface, write the complete visible state matrix first and require at least one route-level regression case per semantic state before declaring the phase done.

---

# Learning: If A Later Story Owns Wording, Earlier Structural Beads Must Stay Truly Neutral

**Category:** decision
**Severity:** standard
**Tags:** [bead-decomposition, shared-files, queue]
**Applicable-when:** Sequential beads share the same high-traffic template or spec file and one bead owns structure while a later bead owns final semantics or wording.

## What Happened

Phase 2 split queue work correctly on paper: Story 1 owned the `Family Signal` column structure and the known-state rendering, while Story 2 owned the final `unknown`, `legacy_unavailable`, and `benign` wording. In practice, the first queue commit still exposed interim labels that had to be corrected in the next bead. The decomposition worked only after Story 2 tightened the wording and dedicated smoke tests pinned the intended queue matrix.

## Root Cause / Key Insight

Shared-file decomposition is not safe unless ownership boundaries survive the implementation, not just the plan. A structural bead that leaks temporary operator-visible meaning weakens the contract of the later semantic bead and creates unnecessary churn in shared templates.

## Recommendation for Future Work

When a later bead owns wording or semantics, keep earlier shared-template beads neutral outside their owned states; do not ship temporary labels that look user-final.

---

# Learning: Freeze Operator Semantics With Canonical Route Proof And Written Surface Spec Together

**Category:** pattern
**Severity:** standard
**Tags:** [testing, docs, app-factory, contract]
**Applicable-when:** The real feature contract lives in a rendered operator workflow rather than in a helper return value alone.

## What Happened

The lane only became durable after the queue/detail meaning was pinned in the canonical app-factory web tests and written into `docs/current/console/ids_operator_console_ui_surface_spec.md`. Helper-level proof was useful, but it was the rendered `/alerts` and `/alerts/{id}` behavior plus the written spec that made later review and epic close straightforward. The final route sweep passed cleanly with 74 tests.

## Root Cause / Key Insight

Operator-facing semantics drift most easily when the executable proof and the human-facing contract live in different places. Freezing both at the same time turns “what the UI means” into something future workers can neither accidentally reinterpret nor silently forget to document.

## Recommendation for Future Work

When a UI feature introduces new operator-visible meaning, finish with canonical route-level proof and surface-spec updates in the same closing bead.
