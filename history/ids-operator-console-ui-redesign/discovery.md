# Discovery Report: IDS Operator Console UI Redesign

**Date**: 2026-03-30
**Feature**: ids-operator-console-ui-redesign
**CONTEXT.md reference**: `history/ids-operator-console-ui-redesign/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md` - Keep runtime verification separate from mutation and do not let UI work accidentally reintroduce control-plane behavior or startup-side state mutation.
- `history/learnings/critical-patterns.md` - Keep the service entrypoint wired to the real app factory; route and shell refactors must preserve the canonical `create_operator_console_web_app()` path used by the runtime.
- `history/learnings/critical-patterns.md` - Validate write scopes and HIGH-risk seams before execution; this redesign spans multiple templates plus the route tree, so bead boundaries must be narrow and explicit.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | operator-console runtime wiring | UI changes are not done until the runnable server path still exposes the real app factory and a representative feature route. | high |
| `history/learnings/20260329-operator-console-production-hardening.md` | operator-console runtime contract | Redesign must stay inside verify-only runtime boundaries and must not blur UI polish with bootstrap/migration/operator mutation flows. | high |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | operator visibility boundary | Active model/bundle visibility should remain read-only and summary-driven; the new UI must not imply ownership of activation state. | medium |

---

## Agent A: Architecture Snapshot

> Source: file tree analysis, route inspection, targeted file reads

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts/ids_operator_console/` | Canonical operator-console application package | `web.py`, `config.py`, `auth.py`, `reporting.py`, `templates/`, `static/` |
| `scripts/ids_operator_console/templates/` | Server-rendered UI surfaces | `base.html`, `dashboard.html`, `alert_detail.html`, `anomalies.html`, `reports.html`, `login.html` |
| `scripts/ids_operator_console/static/` | Shared styling and progressive enhancement | `console.css`, `console.js` |
| `scripts/ids_operator_console_server.py` | Runnable server entrypoint | `build_operator_console_app()`, `main()`, `run_server()` |
| `scripts/ids_operator_console_manage.py` / `scripts/ids_operator_console_preflight.py` | Operator/maintenance contract outside the web runtime | CLI and preflight surfaces referenced by deploy and tests |
| `tests/` | Regression coverage for routes, config, reporting, auth, ops, preflight | `test_ids_operator_console_web.py`, `test_ids_operator_console_config.py`, `test_ids_operator_console_reporting.py`, related operator-console tests |

### Entry Points

- **UI**: `scripts/ids_operator_console/web.py` renders `/login`, `/dashboard`, `/alerts/{alert_id}`, `/anomalies`, `/reports`
- **Machine-readable UI data**: `scripts/ids_operator_console/web.py` exposes `/api/v1/console/snapshot`, `/api/v1/alerts`, `/api/v1/anomalies`, `/api/v1/summaries`
- **Server**: `scripts/ids_operator_console_server.py` imports `create_operator_console_web_app()` and runs it with uvicorn
- **Operator/maintenance**: `scripts/ids_operator_console_manage.py` and `scripts/ids_operator_console_preflight.py`

### Key Files to Model After

- `scripts/ids_operator_console/web.py` - demonstrates the canonical route and template-context composition; all UX work should route through this file rather than creating a parallel app path.
- `scripts/ids_operator_console/templates/dashboard.html` - demonstrates the existing combined-console semantics, including alert and anomaly separation.
- `scripts/ids_operator_console/templates/alert_detail.html` - demonstrates the current depth of workflow that must be preserved in the redesign.
- `tests/test_ids_operator_console_web.py` - demonstrates how route-level behavior is currently verified and what user-visible contracts already have tests.
- `tests/test_ids_operator_console_config.py` - demonstrates runtime wiring expectations for the canonical app entrypoint.

---

## Agent B: Pattern Search

> Source: grep, targeted file reads, route/test inspection

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Combined overview shell | `scripts/ids_operator_console/templates/dashboard.html` | One page mixes alert queue, health, readiness, and anomaly lane | Yes, but should be reorganized into the locked `Overview` IA |
| Detail workflow | `scripts/ids_operator_console/templates/alert_detail.html` | Read-deep page with forms, timeline, notes, and metadata | Yes |
| Reporting rollup helpers | `scripts/ids_operator_console/reporting.py` | Server-side rollup/export preparation across alerts/anomalies/summaries | Yes |
| Session auth + CSRF | `scripts/ids_operator_console/auth.py` | Session-backed admin auth with CSRF token in forms | Yes |
| App factory wiring | `scripts/ids_operator_console_server.py` + `scripts/ids_operator_console/web.py` | Single canonical app factory for runtime | Must be preserved |

### Reusable Utilities

- **Auth/session**: `scripts/ids_operator_console/auth.py` - login session establishment, auth checks, and CSRF validation already exist and should be reused rather than redesigned functionally.
- **Report aggregation**: `scripts/ids_operator_console/reporting.py` - ready-made export and rollup helpers that can support a richer `Reports` surface without changing data contracts.
- **Context shaping**: `scripts/ids_operator_console/web.py` - helper functions such as `_prepare_health_snapshot()`, `_with_decoded_payload()`, and route-level context assembly should remain the data seam for new templates.
- **Minimal enhancement seam**: `scripts/ids_operator_console/static/console.js` - current JS is tiny, which means planning can preserve progressive enhancement and avoid inventing a heavy client architecture unless the value is real.

### Naming Conventions

- Product/service names are explicit and descriptive: `IDS Operator Console`, `create_operator_console_web_app`, `build_operator_console_app`.
- Routes are currently noun-like and literal: `/dashboard`, `/anomalies`, `/reports`, `/alerts/{id}`, `/login`.
- Tests are pytest files named by subsystem: `test_ids_operator_console_<area>.py`.
- Templates are one file per page surface under `scripts/ids_operator_console/templates/`.

---

## Agent C: Constraints Analysis

> Source: imports, runtime code, tests, executing targeted pytest

### Runtime & Framework

- **Python runtime in active environment**: `3.11`
- **Web runtime**: FastAPI `0.115.12`
- **ASGI/runtime layer**: Starlette `0.46.2`
- **Server**: Uvicorn `0.34.0`
- **Templating**: Jinja2 `3.1.6`
- **Storage/runtime boundary**: sqlite-backed same-host service with session auth and server-rendered HTML

### Existing Dependencies (Relevant to This Feature)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | `0.115.12` | Route tree, forms, JSON endpoints, HTML responses |
| `starlette` | `0.46.2` | Sessions and test client behavior |
| `uvicorn` | `0.34.0` | Runnable app server |
| `jinja2` | `3.1.6` | Server-rendered template engine |
| `pytest` | environment-installed | Main verification surface for console contracts |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None required by default | The redesign can be delivered within the existing FastAPI + Jinja + CSS/JS stack | low |

### Build / Quality Requirements

```bash
# Existing verification seams that already pass and should remain green:
python -m pytest -q tests/test_ids_operator_console_web.py tests/test_ids_operator_console_config.py

# Additional relevant verification surfaces for redesign work:
python -m pytest -q tests/test_ids_operator_console_reporting.py
python -m pytest -q tests/test_ids_operator_console_auth.py
```

- No repo-root Python package manifest or frontend package manifest was discovered during planning; dependency constraints are enforced primarily through the existing Python environment and pytest-based regression coverage.
- Route names are referenced directly in templates, tests, and docs, so navigation/IA changes have a wider blast radius than pure CSS edits.

### Database / Storage (if applicable)

- **Storage**: sqlite via `scripts/ids_operator_console/db.py`
- **Runtime verification boundary**: `scripts/ids_operator_console/migrations.py` and config/preflight flows
- **Data seam relevant to UI**: alerts, anomalies, and summaries are already persisted separately and exposed separately in route helpers and JSON endpoints

---

## Agent D: External Research

> Source: local `ui-ux-pro-max` knowledge base and design-system search
> Guided by locked decisions in CONTEXT.md - not generic web inspiration

### Design-System Inputs

| Source | Key Result | Planning Interpretation |
|--------|------------|-------------------------|
| `ui-ux-pro-max` typography search: `precision lab technical clean minimal` | `Space Mono` was too brutalist; `Inter` was too generic; `Archivo + Space Grotesk` surfaced as the strongest modern/minimal direction from the local dataset | Planning should keep typography open but favor a strong technical sans pairing over the current Fira stack or all-mono treatment |
| `ui-ux-pro-max` style search: `technical minimal dashboard` | `HUD / Sci-Fi FUI` is visually tempting for cybersecurity but accessibility-poor and too theatrical; `Data-Dense Dashboard` and `Executive Dashboard` both surfaced useful traits | Planning should combine restrained density and operational clarity, not adopt neon/HUD motifs |
| `ui-ux-pro-max` UX search: `sidebar accessibility loading states` | Sidebar/nav state clarity, visible hover/focus, and explicit loading feedback are high-severity UX concerns | Planning should treat shell accessibility and state feedback as first-class parts of the redesign, not polish tasks |

### Known Gotchas / Anti-Patterns

- **Anti-pattern**: turning a security console into a dark sci-fi HUD
  - Why it matters: conflicts with locked decisions `D1`, `D5`, and `D12`; hurts readability and state clarity
  - Correct approach: use a precise light workspace with restrained accents and status semantics

- **Anti-pattern**: adding a charting dependency just to decorate `Reports`
  - Why it matters: introduces new blast radius and dependency risk without a locked requirement for rich client charting
  - Correct approach: prefer server-shaped summaries and lightweight visualizations unless planning proves a real need for a new library

- **Gotcha**: inaccessible loading or hover states in a sidebar/workspace shell
  - Why it matters: the redesign is moving core navigation into a sidebar, so orientation and affordance become structural, not cosmetic
  - How to avoid: plan keyboard-visible focus, clear active states, reduced-motion handling, and explicit no-data/loading/degraded variants

---

## Open Questions

> Items that were not resolvable through research alone.
> These will be raised into the synthesis step.

- [ ] Should route changes be implemented as renamed pages with legacy aliases/redirects, or should the UI vocabulary change while stable route paths remain? - impacts blast radius across templates, docs, and tests
- [ ] Should `Reports` use purely server-rendered summary widgets and inline SVG micro-visuals, or is there enough value to justify a charting dependency? - impacts dependency risk and implementation scope
- [ ] Is it safer to modularize CSS into clearer sections/files during the redesign, or keep one stylesheet and restructure internally for lower file churn? - impacts file scope and worker parallelization

---

## Summary for Synthesis (Phase 2 Input)

> Brief synthesis for the next planning step.

**What we have**: a canonical FastAPI + Jinja operator-console stack with a single app factory, server-rendered templates, minimal JS, separate alert/anomaly/summary semantics, and meaningful pytest coverage around routes, config, reporting, auth, and runtime wiring.

**What we need**: a full UX/UI redesign that reorganizes the product model into `Overview / Alerts / Operations / Reports`, replaces the visual system and shell, sharpens scan-fast/detail-deep workflow, and preserves the verify-only, same-host, non-control-plane runtime contract.

**Key constraints from research**:
- Route and IA changes will touch templates, route handlers, tests, and docs together; this is not a CSS-only pass.
- No new dependency is required to deliver the redesign; existing Python-native patterns are a strong fit and a safer default.
- Alert/anomaly/summaries separation is already encoded in code and tests and must remain visible in the new IA.

**Institutional warnings to honor**:
- Keep `scripts/ids_operator_console_server.py` wired to the same canonical app factory used by tests and runtime.
- Do not let UI changes imply or introduce runtime mutation/control-plane behavior.
- Keep high-risk write scopes separated cleanly before execution; shell/IA work and individual surface redesigns should not be one giant bead.
