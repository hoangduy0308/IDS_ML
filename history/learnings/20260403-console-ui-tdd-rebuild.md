---
date: 2026-04-03
feature: ids-console-ui-pencil-rebuild
categories: [pattern, decision, failure]
severity: critical
tags: [ui, jinja2, javascript, css, security, xss, tdd, bead-decomposition, templates]
---

# Learning: innerHTML Injection in Polling Renderers Is Always an XSS Risk

**Category:** failure
**Severity:** critical
**Tags:** [security, xss, javascript, innerHTML, polling]
**Applicable-when:** Any vanilla JS function that rebuilds DOM content via `innerHTML` using data fetched from an API endpoint.

## What Happened

The `initLiveLogsPoller()` function in `console.js` rebuilt `#live-logs-feed` via `innerHTML` on every poll cycle. Fields `source_event_id` and `event_ts` from `/api/v1/alerts` were injected raw — no escaping. Any alert whose `source_event_id` contained `<script>`, `<img onerror=...>`, or similar would execute in the operator's browser. Caught in review; fixed by adding a 5-line `esc()` helper before `renderRows()` and wrapping all user-data fields.

## Root Cause / Key Insight

The function was written to match the server-rendered Jinja2 template logic, which auto-escapes via `{{ }}`. But `innerHTML` string concatenation in JavaScript has no equivalent automatic escaping — the mental model from Jinja2 does not transfer to JS. DB-origin strings (IDs, event sources, reasons) look safe in normal data but are user-controlled at the sensor boundary.

## Recommendation for Future Work

Any JS function that writes `container.innerHTML = ...` with data from a `fetch()` response must escape all user-controlled fields before injection. Add a minimal `esc()` helper (replace `&`, `<`, `>`, `"`) at the top of the renderer and apply it to every field that is not a constant. Add this to the reviewer checklist for any JS polling or SSE renderer.

---

# Learning: Foundation-First Phase Structure for Full UI Rebuilds

**Category:** pattern
**Severity:** standard
**Tags:** [ui, jinja2, tdd, bead-decomposition, templates, css]
**Applicable-when:** Any full rewrite of a server-rendered UI with shared base templates, a CSS token layer, and multiple screens.

## What Happened

The console UI rebuild was structured in three phases: (1) CSS token layer + base template + auth + all routes as 501 stubs, (2) the 6 existing screens with real implementations, (3) the 3 new screens + verification. This ordering meant every screen in Phase 2 and Phase 3 could build on a confirmed working shell, test an authenticated client, and extend real templates rather than guessing at the base.

## Root Cause / Key Insight

When multiple screens share a base template, CSS variables, sidebar, and auth middleware, any worker that implements a screen before the base is settled has to guess at contracts and redo work when they shift. Delivering the shared shell as a standalone Phase 1 with its own passing tests establishes a stable foundation that all subsequent work can build on without coordination overhead.

## Recommendation for Future Work

For any server-rendered UI rebuild with 3+ screens: Phase 1 = CSS token layer + base template + auth + all routes registered (stubs OK) + auth tests passing. Only start implementing individual screens after Phase 1 tests pass. This works even in a serial bead chain — the cost of Phase 1 is paid once and amortized across all screens.

---

# Learning: Serial Bead Chain for Routes Sharing a Single File

**Category:** pattern
**Severity:** standard
**Tags:** [bead-decomposition, web.py, swarming, file-scope]
**Applicable-when:** When multiple route beads all modify the same high-traffic file (e.g., `web.py`, `router.py`, `urls.py`) and cannot be decomposed further.

## What Happened

All Phase 3 route beads (System Health, Suppression Rules, Live Logs, Verification) shared `web.py`. Rather than attempting parallel execution with merge coordination, the beads were chained sequentially via dependency (`cnh3 → 7vke → ut75 → bui4`). This produced clean commits, no conflicts, and a predictable execution order.

## Root Cause / Key Insight

File-reservation conflicts in `web.py` are guaranteed when multiple beads each add route handlers to the same file. Parallel execution requires merge logic that adds zero value for additive route additions. A serial chain eliminates the conflict entirely at the cost of parallelism — which is acceptable when each bead is fast (12–18 tests per screen, ~30 min per bead).

## Recommendation for Future Work

When route beads all touch the same file, chain them serially via `br dep add` before swarming. Reserve parallelism for beads that touch disjoint files (templates, CSS, tests). The dependency chain documents execution order and also documents the architectural relationship between the screens.

---

# Learning: CSS Modifier Naming Convention Drift Across Multi-Template Swarms

**Category:** failure
**Severity:** standard
**Tags:** [css, templates, jinja2, naming-convention, review]
**Applicable-when:** A swarm delivers multiple Jinja2 templates in sequence when the CSS file defines a component modifier naming convention.

## What Happened

The CSS file (`console.css`) defines single-hyphen modifier classes: `btn-primary`, `btn-danger`, `btn-sm`. All Phase 1 and Phase 2 templates used this convention correctly. The Phase 3 `suppression_rules.html` template used double-hyphen BEM (`btn--primary`, `btn--danger`, `btn--sm`). The buttons rendered but were completely unstyled — no error, no test failure, silent visual regression. Caught in review; fixed by renaming the classes.

## Root Cause / Key Insight

The Phase 3 worker was implementing in a fresh context and modeled button classes from memory rather than from an existing template. BEM double-hyphen (`btn--modifier`) is a common convention and an easy default — but this project uses single-hyphen. Tests verify route status codes and HTML structure, not CSS class names, so the drift was invisible to CI.

## Recommendation for Future Work

Lock the CSS modifier naming convention in `CONTEXT.md` (or the Phase N contract) as an explicit decision: "modifier classes use single-hyphen: `btn-primary`, not `btn--primary`." During review of any new template, grep for `btn--`, `badge--`, or other BEM double-hyphen patterns against the CSS file's actual class definitions.

---

# Learning: Triage Helper Key Names Must Be Anchored in Data Contract Notes

**Category:** failure
**Severity:** standard
**Tags:** [jinja2, templates, data-contracts, consistency, triage]
**Applicable-when:** Multiple Jinja2 templates consume the same DB query helper output in different sessions or by different workers.

## What Happened

`list_alerts_for_triage()` in `alerts.py` sets `alert["suppressed"]` (no `is_` prefix). Phase 2's `alerts.html` used `alert.get("suppressed", False)` correctly. Phase 3's `live_logs.html`, written by a different worker in a later session, used `alert.get("is_suppressed", False)` — the suppressed badge and suppression filter silently rendered wrong. Caught in review; fixed by correcting both occurrences in the template.

## Root Cause / Key Insight

The key name `suppressed` (not `is_suppressed`) is only visible by reading `alerts.py:111`. A worker implementing a new template that also displays suppression state has no guardrail pointing them to the canonical key. The correct name is an implementation detail of the helper, not documented in the CONTEXT or data contract.

## Recommendation for Future Work

When a feature includes multiple templates that render the same triage data (alert suppression, severity levels, status flags), add the canonical field names to the CONTEXT.md data contract section or the phase contract. "Suppression flag: `alert['suppressed']` (not `is_suppressed`) — set by `list_alerts_for_triage()` in `alerts.py`." This costs one line and prevents a class of silent wrong-render bugs.

---

# Learning: CONTEXT.md Function References Can Drift From the Real Codebase

**Category:** failure
**Severity:** standard
**Tags:** [context, planning, health, api-contracts]
**Applicable-when:** CONTEXT.md references a specific function name from an existing backend module.

## What Happened

CONTEXT.md decision D6a stated: "System Health is built from existing `/readyz` + `/healthz` payloads and `_prepare_health_snapshot()`." The function `_prepare_health_snapshot()` does not exist in `ids/console/health.py`. The real function is `build_readiness_payload(config, include_sensitive=True)`. The Phase 3 worker discovered this during implementation and used the correct function; no downstream impact because the worker read the actual source before implementing.

## Root Cause / Key Insight

Exploring locked the function name from a quick scan of `health.py`. The private helper `_prepare_health_snapshot` may have been renamed or was never the right public interface. CONTEXT.md captured the name as-is without verifying the call signature.

## Recommendation for Future Work

When CONTEXT.md references a specific function from an existing module, verify the function exists and note its actual signature: `build_readiness_payload(config, include_sensitive=True)` in `ids/console/health.py`. A worker blocked mid-bead on a missing function is more expensive than 30 seconds of verification during exploring.
