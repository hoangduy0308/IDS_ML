# Discovery — ids-console-ui-pencil-rebuild

---

## Institutional Learnings

### Directly Applicable

**[20260330] Split UI Redesigns Into Foundation, Route, Surface, And Verification Beads**
- The previous UI redesign (`ids-operator-console-ui-redesign`) succeeded by isolating the shared shell/CSS/JS into one first bead, route/IA wiring into the next, then parallelizing disjoint page-surface beads, then a verification bead.
- **Applied here:** Phase 1 = shell + tokens + auth. Phase 2 = 6 existing screens. Phase 3 = 3 new screens + verification.

**[20260328] Keep Service Entrypoint Wired To The Real App Factory**
- `server.py` must import from `ids.console.web:create_operator_console_web_app`, which it already does. After the rewrite, this wiring must remain intact.
- **Applied here:** Phase 3 verification must include a test that `server.py` exposes a real feature route.

**[20260329] Split Runtime Verification From Operator Mutation Paths**
- Suppression rules CRUD (D6) is a web mutation path. It must use CSRF and the `OperatorStore` mutation layer, never raw SQL in `web.py`.
- **Applied here:** `OperatorStore.deactivate_suppression_rule()` must be added before the route is implemented.

---

## Architecture Topology

**Location in codebase:**
```
ids/console/
  web.py              ← FULL REWRITE (all routes, app factory)
  templates/          ← FULL REWRITE (9 screens + partials)
  static/
    console.css       ← FULL REWRITE (CSS token layer + components)
    console.js        ← FULL REWRITE (polling, client interactions)
  db.py               ← EXTEND ONLY (add deactivate_suppression_rule)
  auth.py             ← UNCHANGED
  health.py           ← UNCHANGED
  alerts.py           ← UNCHANGED
  reporting.py        ← UNCHANGED
  server.py           ← UNCHANGED (wiring stays intact)
```

**App factory:**
- `create_operator_console_web_app(config, store=None) -> FastAPI`
- Registers: SessionMiddleware, StaticFiles (/static), Jinja2Templates
- All routes registered inline in factory
- `render_template()` helper injects: request, admin, triage/severity/state labels, nav, generated_at
- `_open_store()` helper: returns injected test store OR opens from config path

---

## Existing Routes (19 total — must be preserved or extended)

### Public
| Method | Path | Notes |
|--------|------|-------|
| GET | `/healthz` | liveness — unchanged |
| GET | `/readyz` | readiness — unchanged |
| GET | `/login` | login page |
| POST | `/login` | login submit |

### Authenticated HTML Pages (currently 6 screens)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/` | redirects → /overview |
| GET | `/overview` | main dashboard |
| GET | `/dashboard` | legacy redirect → /overview (303) |
| GET | `/alerts` | triage queue with status_filter |
| GET | `/alerts/{alert_id}` | detail view |
| POST | `/alerts/{alert_id}/notes` | CSRF |
| POST | `/alerts/{alert_id}/status` | CSRF |
| GET | `/operations` | anomaly + readiness |
| GET | `/anomalies` | legacy redirect → /operations (303) |
| GET | `/reports` | historical rollup |
| POST | `/logout` | CSRF |

### JSON API (unchanged)
| Method | Path |
|--------|------|
| GET | `/api/v1/console/snapshot` |
| GET | `/api/v1/alerts` |
| GET | `/api/v1/anomalies` |
| GET | `/api/v1/summaries` |

### NEW (3 screens from D9)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/live-logs` | event feed (D5, D8) |
| GET | `/suppression-rules` | list active rules |
| POST | `/suppression-rules` | add rule (CSRF) |
| POST | `/suppression-rules/{rule_id}/deactivate` | deactivate (CSRF) |
| GET | `/system-health` | readyz + health snapshot view |

---

## Existing Tests (8 files in tests/console/)

| File | What it tests | Impact of rewrite |
|------|--------------|-------------------|
| `test_ids_operator_console_web.py` | Routes, HTML rendering, JSON API, auth redirects | **Must be updated** — route tests need new templates |
| `test_ids_operator_console_auth.py` | Login/logout, CSRF, session | **Must be updated** — auth forms change |
| `test_ids_operator_console_config.py` | Config loading, app factory, CLI | **Must be updated** — app factory now has 3 new routes |
| `test_ids_operator_console_alerts.py` | Suppression, triage, notes | **Unchanged** — tests alert domain logic, not routes |
| `test_ids_operator_console_db.py` | DB primitives | **Extend** — add test for `deactivate_suppression_rule()` |
| `test_ids_operator_console_ingest.py` | Ingest logic | **Unchanged** |
| `test_ids_operator_console_notifications.py` | Notification queue/dispatch | **Unchanged** |
| `test_ids_operator_console_notification_runtime.py` | Worker loop | **Unchanged** |
| `test_ids_operator_console_reporting.py` | Report bundle/rollup | **Unchanged** |

---

## Pencil Design Complexity Map

| Screen | Complexity | Key implementation challenge |
|--------|-----------|------------------------------|
| 07 Login | Low | Centered card, no sidebar |
| 08 Suppression Rules | Low-Med | Table + add/deactivate form |
| 02 Alerts | Med | Filter bar + data table |
| 04 Operations | Med | Metrics row + anomaly table |
| 05 Reports | Med | Metrics row + report tables |
| 09 System Health | Med | Metrics row + health breakdown |
| 01 Overview | Med-High | Dashboard grid (metrics + alerts + anomaly preview) |
| 03 Alert Detail | Med-High | Deep nested sections, breadcrumb, forms |
| 06 Live Logs | High | Terminal area, detail panel, polling JS |

**Shared patterns (design once, reuse):**
- Sidebar partial (280px): logo, 9-item nav (adding Live Logs, Suppression, System Health), user footer
- Top bar partial: title, search/actions slot
- Dark card container pattern (used in tables across 5+ screens)
- Metrics/stat row pattern (Overview, Operations, Reports, System Health)

---

## DB Extension Required

**File:** `ids/console/db.py`
**New method needed:**
```python
def deactivate_suppression_rule(self, *, rule_id: int) -> bool:
    """Set is_active = 0 for the given rule. Returns True if a row was updated."""
    now = _utc_now_iso()
    with self._connection:
        cursor = self._connection.execute(
            "UPDATE suppression_rules SET is_active = 0, updated_at = ? WHERE id = ? AND is_active = 1",
            (now, rule_id),
        )
    return cursor.rowcount > 0
```
**Test needed:** Add to `test_ids_operator_console_db.py`

---

## Technical Constraints

- No build step (D4) — fonts must load via CDN (Geist + JetBrains Mono from Google Fonts or Bunny Fonts)
- No CSS framework — all layout is hand-written CSS using design tokens
- Live Logs uses `setInterval` polling 5–10s (D8) — pure vanilla JS
- All mutating POSTs require CSRF token in form body
- `OperatorStore` is the only DB access layer — no direct SQL in web.py (established pattern)
- Legacy redirects must survive: `/dashboard → /overview`, `/anomalies → /operations`
- JSON API routes stay unchanged — only HTML page routes and new routes are affected
