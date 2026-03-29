# Approach: IDS Operator Console UI Redesign

**Date**: 2026-03-30
**Feature**: ids-operator-console-ui-redesign
**Based on**:
- `history/ids-operator-console-ui-redesign/discovery.md`
- `history/ids-operator-console-ui-redesign/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Application shell | Sticky topbar in `templates/base.html` | Desktop-first sidebar shell + mobile drawer + stronger workspace hierarchy | Large |
| Primary IA | `Dashboard / Anomalies / Reports` plus detail/login | `Overview / Alerts / Operations / Reports` with detail surfaces and compatibility handling | Large |
| Overview surface | One combined `dashboard.html` page | Rebalanced overview that summarizes alerts + runtime health without collapsing signal separation | Medium |
| Alert workspace | Queue embedded inside dashboard | Dedicated `Alerts` workspace optimized for scan speed | Medium |
| Operations surface | Simple anomalies table | Broader `Operations` page combining anomaly lane and runtime/readiness context | Medium |
| Reports surface | Basic summary table only | Hybrid trend + operational table/export view | Medium |
| Visual system | Blue-glass cards, hero-style metrics, single CSS file | Precision-lab light workspace, lower chrome, stronger typography, explicit state system | Large |
| Detail pages | Existing alert detail is functional but visually flat | Read-deep detail surface aligned to new shell and hierarchy | Medium |
| Verification | Existing route/config/reporting tests | Expanded coverage for renamed/aliased routes, shell/navigation, and state distinctions | Medium |

---

## 2. Recommended Approach

Implement the redesign as an in-place evolution of the existing FastAPI + Jinja + CSS/JS console rather than a new frontend stack. Keep `create_operator_console_web_app()` as the canonical app factory, introduce canonical new product routes for `Overview`, `Alerts`, and `Operations`, and preserve compatibility by redirecting legacy paths such as `/dashboard` and `/anomalies` to the new canonical surfaces. Rebuild the shared visual language around a desktop-first sidebar shell, low-chrome precision-lab styling, and explicit state handling, with one foundation pass owning `console.css` so later surface work can stay template-focused. Preserve `Alert Detail` as a contextual deep-read surface, upgrade `Reports` with server-shaped summary widgets plus lightweight visual cues instead of introducing a charting dependency, and keep all current alert/anomaly/summary semantics intact so the UI remains strictly visibility/triage/reporting oriented.

### Why This Approach

- It follows the existing Python-native product slice documented in `history/learnings/20260328-operator-console-runtime-wiring.md` and avoids a risky stack migration with no locked requirement.
- It honors locked decisions `D2`, `D10`, `D11`, and `D12` from `CONTEXT.md` by making IA, shell, and visual system first-class implementation targets rather than treating the work as a CSS polish pass.
- It avoids the gotchas surfaced in discovery: no HUD-style theatrics, no unnecessary chart dependency, and no split between the tested app and the runtime app factory.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend stack | Keep FastAPI + Jinja + progressive CSS/JS | Existing pattern is strong, no new dependency is required, and runtime/service wiring remains stable |
| IA migration | Add canonical routes `/overview`, `/alerts`, `/operations`, `/reports` and keep `/dashboard` + `/anomalies` as compatibility redirects | Makes the new product model explicit while containing backward-compatibility work to a clear seam |
| Shared shell | Refactor `base.html` into a sidebar-oriented application shell with reusable partial(s) | Centralizes the biggest UX change and prevents page-by-page drift |
| Reports visuals | Use server-shaped summary metrics and lightweight inline visualizations instead of adding a chart library | Preserves low dependency risk and keeps reports operationally readable |
| CSS strategy | Keep `console.css` as the shipped asset but give one dedicated foundation bead ownership of its token/layout restack | Avoids asset-pipeline churn while also preventing CSS from becoming an uncontrolled shared write hotspot |
| Detail workflow | Preserve form-driven triage and note flows, redesign hierarchy only | Keeps the existing authenticated workflow and CSRF/session pattern intact |

---

## 3. Alternatives Considered

### Option A: Move the console to a SPA or new frontend framework

- Description: Introduce React/Vue or a richer client architecture for the redesign.
- Why considered: Could offer more freedom for sophisticated layouts and interactions.
- Why rejected: No locked requirement demands it, the codebase already has a proven Python-native app pattern, and this would create a new dependency/runtime surface with much higher validation and deployment risk.

### Option B: Cosmetic CSS refresh only, keep current IA and top navigation

- Description: Restyle the existing templates without changing routes, shell, or page model.
- Why considered: Lowest immediate code churn.
- Why rejected: Violates locked decisions `D2`, `D10`, and `D11`; it would leave the product model essentially unchanged and fail the actual redesign brief.

### Option C: Heavy dashboard treatment with chart library and SOC/HUD visual language

- Description: Add charting dependencies and adopt a more dramatic cybersecurity dashboard look.
- Why considered: Security products often gravitate toward this style and the current repo already exposes trendable data.
- Why rejected: Conflicts with locked `precision lab` art direction, adds dependency/accessibility risk, and would push reports toward decoration over operator readability.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Shell + IA route refactor in `web.py` and `base.html` | **HIGH** | Blast radius crosses route handlers, redirects, navigation, tests, and docs | Validating should inspect alias/redirect strategy and runtime-route coverage |
| Shared visual-system rewrite in `console.css` | **HIGH** | Full restack across every page surface and responsive behavior | Validating should check write-scope isolation and regression coverage strategy |
| Overview + Alerts + Operations surface redesign | **MEDIUM** | Major UI change, but built on existing route/data patterns with no new dependency | Proceed with targeted route/template tests |
| Reports hybrid trend layer | **MEDIUM** | New presentation layer on top of existing reporting helpers | Proceed; verify with reporting tests and route assertions |
| Alert detail redesign | **MEDIUM** | Workflow already exists; risk is mostly hierarchy/regression, not novelty | Proceed with existing alert-detail tests plus UI assertions |
| Login visual redesign | **LOW** | Functional contract stays intact and surface is small | Proceed |
| Compatibility redirects | **MEDIUM** | Direct route-name references exist in tests/docs; wrong mapping causes drift | Proceed with explicit redirect/route assertions |
| Expanded verification/docs updates | **MEDIUM** | User-facing naming changes ripple into tests and operations docs | Proceed with disciplined updates |

### Risk Classification Reference

```
Pattern in codebase?        -> YES = LOW base
External dependency?        -> YES = HIGH
Blast radius > 5 files?     -> YES = HIGH
Otherwise                   -> MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `Shell + IA route refactor`: verify the chosen alias/redirect strategy keeps runtime wiring, tests, and operational docs coherent.
- `Shared visual-system rewrite`: verify bead decomposition keeps file scopes narrow enough and does not force overlapping edits across all templates at once.

---

## 5. Proposed File Structure

```text
scripts/
  ids_operator_console/
    web.py                            # Route/alias updates and context shaping
    reporting.py                      # Reused summary/rollup helpers for reports
    static/
      console.css                     # Full visual-system restack, same shipped asset
      console.js                      # Sidebar/drawer and lightweight UX enhancements
    templates/
      base.html                       # New shell skeleton
      overview.html                   # New primary post-login surface
      alerts.html                     # New dedicated alert workspace
      operations.html                 # New runtime/anomaly surface
      reports.html                    # Hybrid summary + history redesign
      alert_detail.html               # Read-deep alert investigation surface
      login.html                      # Refreshed auth surface
      partials/
        app_sidebar.html              # Shared nav/sidebar
        top_utility_bar.html          # Shared secondary chrome / status area
tests/
  test_ids_operator_console_web.py    # Route and rendered-surface assertions
  test_ids_operator_console_config.py # Canonical app wiring / routes
  test_ids_operator_console_reporting.py
docs/
  ids_operator_console_operations.md  # IA naming and route references if changed
```

---

## 6. Dependency Order

```text
Layer 1 (foundation): Shell + IA mapping + design token strategy
Layer 2 (parallel after Layer 1): Overview/Alerts surfaces and Operations/Reports surfaces
Layer 3 (sequential): Alert detail + login alignment with new shell
Layer 4 (sequential): Tests, compatibility coverage, and docs alignment
```

### Parallelizable Groups

- Group A: `Shell + route mapping`, `Visual system foundation` - coordinated foundation work, but `console.css` ownership stays with the visual-system bead and route/template ownership stays with the shell bead
- Group B: `Overview + Alerts surfaces`, `Operations + Reports surfaces` - can run in parallel after foundation lands
- Group C: `Alert detail + login alignment` - depends on shell and visual primitives
- Group D: `Tests + docs + compatibility verification` - depends on all user-visible route/surface changes

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | Runtime entrypoint must stay bound to the real app factory | Approach keeps `create_operator_console_web_app()` and plans explicit route-wiring verification |
| `history/learnings/20260329-operator-console-production-hardening.md` | Runtime verify-only path must not blur with operator mutation | Approach explicitly limits redesign to read/triage/report UI and excludes control-plane or bootstrap changes |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | Console visibility should remain summary-driven, not state-owning | Approach keeps active-bundle/runtime health as read-only Overview/Operations context, not editable settings |
| `history/learnings/critical-patterns.md` | High-risk write scopes must be isolated before execution | Decomposition plan separates foundation, surfaces, and verification instead of creating one giant UI bead |

---

## 8. Open Questions for Validating

- [ ] Does the planned redirect strategy (`/dashboard` -> `/overview`, `/anomalies` -> `/operations`) create any hidden contract drift in smoke/docs/tests beyond the already identified web/config surfaces? - If wrong, execution could ship a visually correct UI with broken operational references.
- [ ] Is the proposed bead split strict enough to keep `console.css` and shared shell templates from overlapping across workers? - If wrong, swarm execution will create reservation conflicts and merge risk.
