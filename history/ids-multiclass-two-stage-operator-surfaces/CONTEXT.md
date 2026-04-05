# Two-Stage Family Operator Surfaces - Context

**Feature slug:** ids-multiclass-two-stage-operator-surfaces
**Date:** 2026-04-05
**Exploring session:** complete
**Scope:** Standard

---

## Feature Boundary

This feature makes the existing operator console show and explain stage-2 family enrichment on alert-triage surfaces so operators can use the new family signal during investigation without reopening the runtime, bundle, or model-training contract.

**Domain type(s):** SEE | READ

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Operator Surface Priority
- **D1** `family prediction` appears in both the alerts queue (`/alerts`) and the alert detail page (`/alerts/{alert_id}`); those are the primary operator surfaces for this phase.
  *Rationale: operators need the family signal both when scanning the queue and when opening one alert for deeper investigation.*

- **D2** The alerts queue stays triage-first: each row gets a compact family/status presentation, not a new expanded workflow, extra charts, or a family-heavy dashboard treatment.
  *Rationale: the queue's job is fast prioritization, not full model interpretation.*

- **D3** The alert detail page is the explanation surface: it should show the family label, family status, confidence, and any abstention context the runtime already emits so operators can understand why an alert is `known` versus `unknown`.
  *Rationale: detail is where the operator should understand the decision, not just see the label.*

### Scope Boundaries
- **D4** This phase reuses the existing alert route topology and existing console navigation; it does not create a new family-specific page or redesign unrelated console screens.
  *Rationale: the operator already triages in the existing alerts flow, so the safest rollout is to enrich that path instead of inventing a parallel surface.*

- **D5** This first operator-facing slice does not add family rollups, charts, queue filters, sorting controls, or report-first experiences. `Reports` stays secondary and can follow in a later lane if needed.
  *Rationale: the first value is making the live triage flow usable, not widening scope into historical analytics.*

- **D6** This slice is read-only for family metadata. No family-based suppression rules, automations, or new triage states are introduced here.
  *Rationale: the operator should first see and interpret the new signal before the repo adds control-plane behavior that depends on it.*

### Operator Semantics
- **D7** UI copy and docs must state clearly that `unknown` means the binary stage still judged the event to be an attack, but stage 2 did not confidently assign a known family.
  *Rationale: operators must not misread `unknown` as benign, missing data, or a runtime failure.*

- **D8** Benign rows do not get a family label. Family fields are only meaningful for attack alerts carrying stage-2 enrichment.
  *Rationale: `Benign` is not an attack family and should stay semantically separate from both `known` and `unknown`.*

- **D9** Legacy alerts or alerts created before family enrichment existed must remain readable. When family fields are absent, the UI should show an explicit unavailable/legacy state rather than faking a family conclusion.
  *Rationale: the console already contains historical rows and must degrade honestly while the rollout transitions.*

### Agent's Discretion
- Planning may choose the exact badge/cell layout, labels, and wording as long as D1-D9 remain true.
- Planning may decide whether the detail view shows `confidence` and `margin` as raw numeric fields, rounded display values, or labeled support text, as long as the operator can distinguish `known`, `unknown`, and unavailable states.

---

## Specific Ideas & References

- The chosen primary flow is: see the family signal in the queue, then open the detail page to understand it.
- The user delegated the remaining operator-surface decisions to the agent after locking the primary surface direction.
- This phase intentionally follows the already-completed runtime contract lane rather than reopening bundle/runtime design.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `ids/console/web.py` - owns the existing `/alerts` and `/alerts/{alert_id}` HTML routes plus the authenticated JSON surfaces. This is the main integration seam for family UI work.
- `ids/console/templates/alerts.html` - current triage queue table; best place to add one compact family/status presentation per row without changing the route model.
- `ids/console/templates/alert_detail.html` - current investigation workspace; best place to add the richer explanation block for family semantics and confidence.
- `ids/console/alerts.py` - builds triage-ready alert rows and timeline data from the operator store; planning should inspect whether family fields are already surfaced here or still need shaping.
- `docs/current/console/ids_operator_console_ui_surface_spec.md` - documents the current operator-console route/data contract for alerts and detail pages.

### Established Patterns
- Existing alert workflow pattern: operators already triage through `/alerts` and deepen through `/alerts/{alert_id}` rather than switching to a separate analysis page.
- Additive runtime contract pattern: the runtime lane already chose additive enrichment fields rather than replacing binary alert semantics.
- Honest degraded-state pattern: the console specs already require explicit `no-data` / degraded / optional-state handling instead of pretending missing state is healthy.

### Integration Points
- `history/ids-multiclass-two-stage-runtime-contract/CONTEXT.md` - runtime lane that already locked the stage-2 payload semantics this UI must honor.
- `history/ids-multiclass-two-stage-classification/phase-1-acceptance-summary.md` - explains why `unknown` exists and why forced closed-set family labels are unsafe.
- `ids/console/web.py`, `ids/console/templates/alerts.html`, and `ids/console/templates/alert_detail.html` - the concrete alert surfaces this feature will extend.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `history/ids-multiclass-two-stage-runtime-contract/CONTEXT.md` - defines the runtime family fields and the `known | unknown | benign` semantics the console must preserve.
- `history/ids-multiclass-two-stage-classification/CONTEXT.md` - original feature context that locked the overall two-stage direction and the OOD/abstain intent.
- `history/ids-multiclass-two-stage-classification/phase-1-acceptance-summary.md` - evidence for why `unknown` must remain an operator-visible state.
- `docs/current/console/ids_operator_console_ui_surface_spec.md` - current alert/detail route and UI contract to extend rather than replace.
- `history/learnings/critical-patterns.md` - repo-level critical patterns, especially around keeping existing contracts additive and fail-closed.

---

## Outstanding Questions

### Resolve Before Planning

None.

### Deferred to Planning

- [ ] Are the family fields already persisted as first-class alert columns/decoded row fields, or does the first UI slice need to read them from `payload_json` while keeping legacy rows compatible? - Planning needs a focused read of the store/ingest shaping path.
- [ ] Should the detail page show raw `attack_family_confidence` and `attack_family_margin` values directly, or summarize them with operator-facing copy while keeping exact values secondary? - Planning should inspect current template density and payload shape.
- [ ] Does the alerts queue need a tiny passive family legend/help text to avoid misreading `unknown`, or is cell-level labeling enough? - Planning should review the current queue density and existing copy patterns.

---

## Deferred Ideas

- Add family-based filtering, sorting, or alert-priority views to the queue - deferred until the first operator slice proves the signal is useful in normal triage.
- Add family rollups or family-specific sections to `Reports` - deferred because this phase is queue/detail first, not analytics-first.
- Add family-aware notification or suppression behavior - deferred because this phase is read-only for family metadata.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
