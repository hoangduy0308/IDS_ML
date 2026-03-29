# IDS Operator Console UI Redesign - Context

**Feature slug:** ids-operator-console-ui-redesign
**Date:** 2026-03-30
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature redesigns the full operator-console user experience and visual system for the existing same-host IDS web product, covering shell navigation, overview/dashboard, alerts surfaces, anomaly/operations surfaces, reports, login, and shared UI states, without changing the product into a control plane or altering the underlying alert/anomaly/runtime data contracts.

**Domain type(s):** SEE | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Product Direction
- **D1** The redesign must balance operational effectiveness with a premium feel, use medium information density, and treat light mode as the primary design baseline.
  *Rationale: The user wants the console to feel substantially better designed without sacrificing operator usability or defaulting to a dark mission-control aesthetic.*

- **D2** The information architecture should be reorganized around the existing data and workflows instead of preserving the current page grouping verbatim, and the default post-login destination must be an `Overview` surface.
  *Rationale: The current routes are useful implementation seams, but the user wants a clearer product structure rather than a cosmetic reskin of the old grouping.*

- **D8** The `Reports` surface must be hybrid: a summary/trend layer at the top followed by practical operational tables, filters, snapshots, and export-oriented history below.
  *Rationale: The console should support fast reading of trends without drifting into a pure analytics or BI product.*

### Signal Semantics And Workflow
- **D3** `Alerts` and `anomalies/operations` must remain clearly separate lanes in the UX, meeting only at the `Overview` level rather than being merged into one event queue.
  *Rationale: Existing product and pipeline documents already define schema anomalies as operational/pipeline signals, not attack predictions, and the redesign must preserve that semantic boundary.*

- **D6** The `Overview` first fold must balance alert pressure and runtime/system health instead of letting one dominate as a hero metric.
  *Rationale: Operators need to understand both "what requires triage" and "whether the system itself is healthy" at a glance.*

- **D7** The interaction model must be hybrid: list/workspace views optimize for fast scanning, while detail pages optimize for read-depth with timeline, notes, status history, and investigation metadata.
  *Rationale: The repo already has per-alert workflow depth, and the redesign should sharpen that rather than flatten it into a purely dashboard-like experience.*

### Visual Direction
- **D4** The redesign may refresh the visual identity almost completely; it is not required to preserve the current typography, component language, or blue-glass styling.
  *Rationale: The user explicitly wants a substantial UI/UX redo rather than an incremental polish pass.*

- **D5** The dominant art direction is `precision lab`: clean, technical, exact, and calm, not cinematic command-center and not editorial/lifestyle.
  *Rationale: This matches the user's preference for a more professional, technical operator product rather than a dramatic SOC wall.*

- **D11** The primary navigation model must become `Overview / Alerts / Operations / Reports`, with `Alert Detail` and `Login` treated as contextual/detail surfaces rather than first-class primary-nav destinations.
  *Rationale: This structure matches the locked lane separation and creates a more legible product model than the current `Dashboard / Anomalies / Reports` shell.*

- **D12** The visual system must move away from glassy hero cards and marketing-style chrome toward a more rigorous application workspace: strong typography, restrained color accents, explicit dividers, table/list emphasis, and panel treatments only where the panel is semantically meaningful.
  *Rationale: The target feel is premium through precision and hierarchy, not through decorative gradients or dashboard-card mosaics.*

### Interaction And Responsive Behavior
- **D9** The redesign is desktop-first. Mobile only needs to support reading, navigation, and basic action paths competently; it does not need near-parity with the desktop workflow.
  *Rationale: The user explicitly treats mobile as secondary for this operator surface.*

- **D10** The application shell must use a fixed desktop sidebar and a drawer pattern on mobile instead of top navigation as the primary wayfinding model.
  *Rationale: The new IA needs stronger persistent navigation and workspace orientation than the current topbar affords.*

- **D13** Motion must stay restrained and utility-driven: subtle page/section entrances, row or panel hover/focus feedback, and shell transitions are allowed, but ornamental animation and theatrical motion are out of scope.
  *Rationale: The chosen art direction is technical and precise; motion should improve hierarchy and affordance, not spectacle.*

- **D14** Empty, loading, and degraded states must be explicit operational states. The redesign must clearly distinguish `no alerts`, `no data yet`, and `runtime degraded/misconfigured` instead of styling them as one generic empty panel.
  *Rationale: In an operator console, state clarity is part of the product contract, not a decorative afterthought.*

### Agent's Discretion
- The planner/implementer may choose the exact route mapping, template structure, and progressive-enhancement strategy as long as the resulting product model clearly exposes `Overview`, `Alerts`, `Operations`, and `Reports`.
- The planner/implementer may choose the exact typography pair, spacing scale, token names, and light-theme palette as long as they honor the `precision lab`, desktop-first, low-chrome direction.
- The planner/implementer may choose the exact chart types and summary widgets for `Reports` as long as charts stay subordinate to operational readability and historical tables.
- The planner/implementer may choose whether alert lists use table-first, row-list, or split-pane composition as long as scan speed stays high and alert detail remains a read-deep surface.

---

## Specific Ideas & References

- User request: read `AGENTS.md`, inspect the repo carefully, and redo the UX/UI for everything related to the current UI surface.
- User explicitly invoked `khuym:exploring`, `frontend-skill`, and `ui-ux-pro-max`, so downstream planning should assume visual quality and system design matter, not only functional correctness.
- The user delegated the remaining unresolved aesthetic and interaction choices to the agent after the core direction was established.
- Desired product feel: a technically rigorous, modern operator console that feels intentionally designed, not a generic admin template and not a dramatic SOC-themed dark dashboard.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `scripts/ids_operator_console/templates/base.html` - current application shell, authenticated nav, footer, and shared template inheritance root.
- `scripts/ids_operator_console/templates/dashboard.html` - current combined-console implementation showing how alerts, anomalies, readiness, and health are rendered together.
- `scripts/ids_operator_console/templates/alert_detail.html` - current alert-detail workflow surface with status changes, note capture, and timeline/history sections.
- `scripts/ids_operator_console/templates/anomalies.html` - current anomaly lane page; useful as the starting semantic boundary for the future `Operations` surface.
- `scripts/ids_operator_console/templates/reports.html` - current reports/history page; useful for understanding summary data already available.
- `scripts/ids_operator_console/templates/login.html` - current login surface and auth form contract.
- `scripts/ids_operator_console/static/console.css` - current global token file and all page styling in one stylesheet; useful for understanding what must be replaced or restructured.
- `scripts/ids_operator_console/static/console.js` - currently only does lightweight timestamp enhancement; useful seam if the redesign stays progressively enhanced rather than framework-heavy.
- `scripts/ids_operator_console/web.py` - canonical route tree and data-shaping layer for all existing UI pages and JSON endpoints.

### Established Patterns
- Server-rendered FastAPI + Jinja2 app: the current console is multi-page, template-driven, and only lightly enhanced client-side.
- Read/triage/monitoring boundary: the web UI is not a mutation-heavy control plane and should stay inside observe/triage/report visibility contracts.
- Distinct signal families: alerts, anomalies, and summaries are already separate storage/query surfaces and should remain semantically distinct in the redesign.
- Authenticated admin console: login/logout/session handling already exist and should remain part of the product flow.
- Shared stylesheet architecture: most current UI decisions live in one CSS file, which means planning can choose between controlled evolution or a more modular restack.

### Integration Points
- `scripts/ids_operator_console/web.py` - page naming, route composition, and template context must be updated here if IA or surface naming changes.
- `scripts/ids_operator_console/templates/*.html` - all primary UI surfaces live here and are the direct redesign targets.
- `scripts/ids_operator_console/static/console.css` - primary visual-system and layout implementation point.
- `scripts/ids_operator_console/static/console.js` - optional progressive-enhancement point for sidebar behavior, utility interactions, and lightweight UX polish.
- `/api/v1/console/snapshot`, `/api/v1/alerts`, `/api/v1/anomalies`, `/api/v1/summaries` in `scripts/ids_operator_console/web.py` - existing machine-readable surfaces that planning should preserve or intentionally map around if richer UI behaviors need them.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `history/ids-operator-console-v1/CONTEXT.md` - original product decisions for the operator console, including the combined-console boundary and alert/anomaly separation.
- `docs/ids_operator_console_operations.md` - runtime and operator contract for the deployed console, including visibility-only model-bundle boundary and notification/runtime separation.
- `docs/ids_realtime_pipeline_architecture.md` - semantic distinction between `model_prediction` alerts and `schema_anomaly` operational events.
- `history/ids-model-bundle-promotion-hardening/CONTEXT.md` - operator-console visibility boundary for active model bundle state; useful so the redesign does not imply control-plane mutation.
- `history/learnings/critical-patterns.md` - project-wide hardened lessons, especially around runtime wiring and verify-only operational boundaries.

---

## Outstanding Questions

### Deferred to Planning
- [ ] Should the redesign stay fully server-rendered Jinja + CSS/JS or introduce a more componentized frontend layer while preserving the same-host FastAPI service boundary? - Planning should choose the lowest-risk implementation shape that can still deliver the desired UI quality.
- [ ] How much route/backward-compatibility preservation is required if `Dashboard` becomes `Overview` and `Anomalies` becomes `Operations` at the product level? - Planning should define whether this is naming-only, route aliasing, or a larger shell refactor.
- [ ] What exact visual token system, font pairing, and chart vocabulary best realize the `precision lab` direction? - Planning should research and choose a concrete design system rather than locking arbitrary token values during exploring.
- [ ] Which current views should become split-pane workspace patterns versus full-page document/detail patterns? - Planning should map the locked interaction model to concrete layouts per surface.

---

## Deferred Ideas

- Full dark-mode parity - deferred because light mode is the locked primary baseline for this redesign.
- Incident/case management - deferred because the console still handles alerts independently rather than introducing a broader case system.
- UI-driven control-plane actions for sensor config, model promotion, rollback, or service lifecycle - deferred because the operator console remains a read/triage/monitoring product.
- Mobile workflow parity with desktop - deferred because desktop-first behavior is explicitly locked.
- Multi-host or fleet-oriented views - deferred because the current product boundary remains same-host and sensor-aware rather than fleet control.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
