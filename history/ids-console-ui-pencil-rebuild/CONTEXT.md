# IDS Console UI — Pencil Rebuild

**Feature slug:** ids-console-ui-pencil-rebuild
**Date:** 2026-04-02
**Exploring session:** complete
**Scope:** Standard

---

## Feature Boundary

Delete the existing Jinja2 HTML templates, static CSS/JS, and `ids/console/web.py` entirely. Implement a new 9-screen operator console from the Pencil design file at `design/UI`, following a TDD approach. Three screens that don't currently have backend routes (Live Logs, Suppression Rules, System Health) will get real routes wired to existing or minimally-extended DB/health infrastructure. No other backend layers (DB schema outside suppression helpers, ingest pipeline, auth model) are changed.

**Domain type(s):** SEE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Scope and Deliverables

- **D1** Implement all 9 screens with real backend routes. The 3 screens not currently in `web.py` (Live Logs, Suppression Rules, System Health) must have full FastAPI routes, not placeholders.
  *Rationale: User explicitly chose B — all 9 screens, all wired.*

- **D2** Full rewrite: delete `ids/console/web.py`, all files in `ids/console/templates/`, `ids/console/static/console.css`, and `ids/console/static/console.js`. Write everything from scratch.
  *Rationale: User explicitly chose B — clean rewrite, not incremental patch.*

### Design Source of Truth

- **D3** The Pencil file `design/UI` is the primary source of truth for layout, structure, component hierarchy, and visual mode (Dark). The `design-taste-frontend` skill governs typography, color token system, and spacing scale where the Pencil file does not specify exact values.
  *Rationale: User chose "A and B" — Pencil for structure, taste skill for system gaps.*

- **D3a** All 9 screens use Dark mode (`theme: {Mode: "Dark"}`). This overrides the previous PRD "light-mode" direction. Pencil is now the visual source of truth.
  *Rationale: Every frame in design/UI carries `theme: {Mode: "Dark"}`.*

### CSS Architecture

- **D4** CSS variables as the design token layer + component-based CSS. No Tailwind, no CSS framework, no build step.
  *Rationale: No build dependency, direct Pencil token → CSS variable mapping, consistent with server-rendered Jinja2.*

### New Screen Data Sources

- **D5** Live Logs (`06 - Nhật ký trực tiếp`) feeds from existing `alerts` + `anomalies` DB tables as a unified event feed. No new DB table.
  *Rationale: No new infrastructure; existing data is sufficient for a terminal-style event feed.*

- **D8** Live Logs uses client-side polling (`setInterval`, 5–10s interval) to refresh the event feed. No SSE, no WebSocket.
  *Rationale: Polling is sufficient for "Live" feel; SSE adds streaming endpoint + EventSource complexity that is inconsistent with the server-rendered approach.*

- **D6** Suppression Rules (`08 - Quy tắc ẩn`) implements full CRUD: list active rules, add new rule, deactivate rule — via web forms with CSRF. DB method `add_suppression_rule()` already exists in `OperatorStore`; a `deactivate_suppression_rule()` method needs to be added.
  *Rationale: User chose B — full CRUD, matching the Pencil design which includes an "Add rule" button.*

- **D6a** System Health (`09 - Trạng thái hệ thống`) is built from existing `/readyz` + `/healthz` payloads and `_prepare_health_snapshot()`. No new data infrastructure needed.
  *Rationale: Existing health + readiness payload covers all visible fields in the Pencil design.*

### Test Strategy

- **D7** TDD — tests are written before implementation for every route and feature. Each backend route gets a failing test first, then implementation.
  *Rationale: User explicitly said "test before implement".*

- **D9** Route paths for the 3 new screens: `/live-logs`, `/suppression-rules`, `/system-health`.
  *Rationale: Locked during exploring to give planning a stable route contract.*

- **D10** Test files follow existing `tests/console/` layout and naming convention. No restructuring.
  *Rationale: Consistency with current project test structure; avoids mid-phase reorganization.*

---

## Pencil Design Reference

**File:** `design/UI` (open with Pencil MCP, not plain Read)

### 9 frames (top-level):
| ID | Screen | Current route |
|----|--------|--------------|
| `eDUgz` | 01 - Tổng quan (Overview) | `/overview` (existing) |
| `IdE4V` | 02 - Cảnh báo (Alerts) | `/alerts` (existing) |
| `D8Cy6` | 03 - Chi tiết cảnh báo (Alert Detail) | `/alerts/{alert_id}` (existing) |
| `swPGV` | 04 - Vận hành (Operations) | `/operations` (existing) |
| `Cmv4w` | 05 - Báo cáo (Reports) | `/reports` (existing) |
| `rJIYx` | 06 - Nhật ký trực tiếp (Live Logs) | **NEW** |
| `gAUzv` | 07 - Đăng nhập (Login) | `/login` (existing) |
| `i7RHe` | 08 - Quy tắc ẩn (Suppression Rules) | **NEW** |
| `ibfMx` | 09 - Trạng thái hệ thống (System Health) | **NEW** |

### CSS Variables (complete — extracted from design/UI via get_variables)

Both Light and Dark values. Dark mode is the locked baseline (D3a).

| Variable | Light | Dark |
|----------|-------|------|
| `--background` | `#F2F3F0` | `#111111` |
| `--foreground` | `#111111` | `#FFFFFF` |
| `--card` | `#FFFFFF` | `#1A1A1A` |
| `--card-foreground` | `#111111` | `#FFFFFF` |
| `--border` | `#CBCCC9` | `#2E2E2E` |
| `--input` | `#CBCCC9` | `#2E2E2E` |
| `--muted` | `#F2F3F0` | `#2E2E2E` |
| `--muted-foreground` | `#666666` | `#B8B9B6` |
| `--primary` | `#FF8400` | `#FF8400` |
| `--primary-foreground` | `#111111` | `#111111` |
| `--secondary` | `#E7E8E5` | `#2E2E2E` |
| `--secondary-foreground` | `#111111` | `#FFFFFF` |
| `--accent` | `#F2F3F0` | `#111111` |
| `--accent-foreground` | `#111111` | `#F2F3F0` |
| `--destructive` | `#D93C15` | `#FF5C33` |
| `--ring` | `#666666` | `#666666` |
| `--popover` | `#FFFFFF` | `#1A1A1A` |
| `--popover-foreground` | `#111111` | `#FFFFFF` |
| `--sidebar` | `#E7E8E5` | `#18181b` |
| `--sidebar-accent` | `#CBCCC9` | `#2a2a30` |
| `--sidebar-accent-foreground` | `#18181b` | `#fafafa` |
| `--sidebar-foreground` | `#666666` | `#fafafa` |
| `--sidebar-border` | `#CBCCC9` | `#ffffff1a` |
| `--sidebar-primary` | `#18181b` | `#18181b` |
| `--sidebar-primary-foreground` | `#fafafa` | `#fafafa` |
| `--sidebar-ring` | `#71717a` | `#71717a` |
| `--color-success` | `#DFE6E1` | `#222924` |
| `--color-success-foreground` | `#004D1A` | `#B6FFCE` |
| `--color-error` | `#E5DCDA` | `#24100B` |
| `--color-error-foreground` | `#8C1C00` | `#FF5C33` |
| `--color-warning` | `#E9E3D8` | `#291C0F` |
| `--color-warning-foreground` | `#804200` | `#FF8400` |
| `--color-info` | `#DFDFE6` | `#222229` |
| `--color-info-foreground` | `#000066` | `#B2B2FF` |
| `--radius-m` | `16px` | `16px` |
| `--radius-none` | `0` | `0` |
| `--radius-pill` | `999px` | `999px` |
| `--font-primary` | `JetBrains Mono` | `JetBrains Mono` |
| `--font-secondary` | `Geist` | `Geist` |
| `--white` | `#FFFFFF` | `#FFFFFF` |
| `--black` | `#000000` | `#000000` |

### Design system observations:
- Font families in use: `Geist` (body/UI), `JetBrains Mono` (monospace/code/IDs)
- Sidebar width: 280px, fixed
- All screens: 1440×900 viewport
- Color system: CSS variables (`$--primary`, `$--background`, `$--foreground`, `$--sidebar`, `$--border`, `$--card`, `$--muted-foreground`, `$--color-success`, etc.)
- Shell pattern: sidebar (280px) + main content area (fill)

---

## Existing Code Context

### Files to DELETE in full:
- `ids/console/web.py` — route tree and page context logic
- `ids/console/templates/` — all HTML templates
- `ids/console/static/console.css` — all styling
- `ids/console/static/console.js` — client-side scripts

### Files to KEEP (backend, not touched by this feature):
- `ids/console/db.py` — `OperatorStore`, all DB primitives (add `deactivate_suppression_rule` method here)
- `ids/console/auth.py` — session auth, CSRF token logic
- `ids/console/alerts.py` — `list_alerts_for_triage`, `is_alert_suppressed`
- `ids/console/health.py` — `_prepare_health_snapshot`, `build_readiness_payload`
- `ids/console/reporting.py` — `build_report_bundle`, `build_report_rollup`
- `ids/console/notifications.py`, `notification_runtime.py`
- `ids/console/ingest.py`
- `ids/console/config.py`, `migrations.py`, `ops.py`
- `ids/console/server.py` — entrypoint, unchanged

### Established Patterns (planning must continue):
- FastAPI + Jinja2, server-rendered, session-based auth (`SessionMiddleware`)
- CSRF on all mutating POSTs: `POST /logout`, `POST /alerts/{id}/notes`, `POST /alerts/{id}/status`, new suppression rule POSTs
- Legacy redirects must survive rewrite: `/dashboard → /overview`, `/anomalies → /operations`
- JSON API routes (`/healthz`, `/readyz`, `/api/v1/*`) must remain unchanged
- `OperatorStore` is the only DB access layer — no direct SQL in `web.py`

### New DB method needed:
- `OperatorStore.deactivate_suppression_rule(rule_id: int)` — sets `is_active = 0` in `suppression_rules` table. Must be added to `ids/console/db.py` before the Suppression Rules route can be implemented.

---

## Canonical References

**Downstream agents MUST read before implementing.**

- `design/UI` — Pencil design file, open with Pencil MCP `batch_get` to inspect each frame
- `docs/current/console/ids_operator_console_ui_prd.md` — product intent, personas, page roles, data requirements (still valid for data field matrix)
- `docs/current/console/ids_operator_console_ui_surface_spec.md` — route inventory, auth contracts, data model per screen (still binding for existing 6 screens)
- `ids/console/db.py` — `OperatorStore` full API: read before adding new routes
- `ids/console/health.py` — `build_readiness_payload`, `_prepare_health_snapshot`
- `history/learnings/critical-patterns.md` — critical patterns; especially `[20260328] Keep Service Entrypoints Wired To The Real App Factory`

---

## Outstanding Questions

### Resolved (locked during exploring)
- [x] Route paths for 3 new screens: `/live-logs`, `/suppression-rules`, `/system-health` — locked as D9.
- [x] Live Logs transport: polling at 5–10s — locked as D8.
- [x] CSS token completeness: all `$--*` variables in `design/UI` have exact hex/rem values for both Light and Dark modes. See `get_variables()` output — no guessing needed.
- [x] Test file structure: keep `tests/console/` layout, mirror current naming convention — locked as D10.

### Deferred to Planning
- [ ] Whether `console.js` rewrite uses Alpine.js or stays pure vanilla JS
- [ ] Split of templates into partials vs. full-page files — planner decides structure

---

## Deferred Ideas

- Light mode / theme toggle — dark mode is locked for this phase
- Multi-sensor selector in HTML pages — JSON API already supports `sensor_id` but HTML pages do not; deferred to phase 2
- Model promotion / rollback UI — remains CLI-only
- Report export action — deferred to phase 2
- Fleet / multi-host views — out of scope for same-host console

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions (D1–D7), pencil design frame IDs, existing code context, resolve-before-planning questions
- **validating** reads: locked decisions to verify plan-checker coverage
- **reviewing** reads: locked decisions for UAT verification

Decision IDs (D1–D7) are stable. Reference them by ID in all downstream artifacts.
