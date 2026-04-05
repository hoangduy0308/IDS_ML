# Discovery Report: Two-Stage Family Operator Surfaces

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-operator-surfaces`
**CONTEXT.md reference**: `history/ids-multiclass-two-stage-operator-surfaces/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md` — additive enrichment should stay additive at the consumer surface too; do not turn missing family metadata into a fake closed-set answer.
- `history/learnings/critical-patterns.md` — fail-closed and explicit semantics matter for staged contracts; the UI should distinguish `known`, `unknown`, `benign`, and legacy/unavailable instead of collapsing them together.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | `ids.console.server` / `ids.console.web` | Treat the real app factory and its route tree as the runtime contract; regression proof must exercise the actual operator surface, not a placeholder entrypoint. | high |
| `history/learnings/20260329-operator-console-production-hardening.md` | operator-console runtime and preflight paths | Keep runtime/view paths verify-only and avoid sneaking in mutation or schema side effects while adding read-only operator signals. | high |
| `history/learnings/20260403-console-ui-tdd-rebuild.md` | `ids/console/templates/*`, `ids/console/web.py`, `tests/console/*` | Shared triage field names and shared route files drift easily; anchor canonical alert-field names in one helper and prefer serial ownership for shared `web.py` / template work. | high |
| `history/learnings/20260404-telegram-settings-deploy-hardening.md` | `ids.console.web`, `ids.console.notification_runtime` | When more than one surface needs the same interpretation rule, put that rule in one shared helper and have every surface call it instead of reimplementing it. | high |
| `history/learnings/20260405-composite-runtime-review-contracts.md` | `ids.runtime.inference`, `ids.runtime.realtime_pipeline` | The runtime already chose additive family enrichment (`attack_family`, confidence, margin, `family_status`); operator work should consume that contract, not invent a parallel meaning. | high |

---

## Agent A: Architecture Snapshot

> Source: file tree analysis, targeted file reads

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `ids.console` | Operator-console routes, templates, data shaping, SQLite store | `ids/console/web.py`, `ids/console/alerts.py`, `ids/console/db.py`, `ids/console/templates/alerts.html`, `ids/console/templates/alert_detail.html` |
| `ids.runtime` | Runtime scoring and realtime alert-event emission | `ids/runtime/inference.py`, `ids/runtime/realtime_pipeline.py` |
| `tests.console` | Route-level and template-level proof for operator surfaces | `tests/console/test_ids_operator_console_alerts_web.py`, `tests/console/test_ids_operator_console_web.py`, `tests/console/test_ids_operator_console_ingest.py` |
| `docs.current.console` | Current operator-console route/data contract docs | `docs/current/console/ids_operator_console_ui_surface_spec.md` |
| `history/ids-multiclass-two-stage-runtime-contract` | Canonical runtime-family semantics for this lane | `history/ids-multiclass-two-stage-runtime-contract/CONTEXT.md` |

### Entry Points

- **UI routes**: `ids/console/web.py` defines `/alerts` and `/alerts/{alert_id}` and passes hydrated alert rows into Jinja templates.
- **Data shaping**: `ids/console/alerts.py::list_alerts_for_triage()` reads rows from the store, computes suppression, and decodes `payload_json` into `alert["payload"]`.
- **Persistence**: `ids/console/db.py::alerts` stores generic alert fields plus `payload_json`; there are no first-class family columns today.
- **Alert ingest**: `ids/console/ingest.py` writes runtime events into the operator store via `upsert_alert(...)`.
- **Runtime producer**: `ids/runtime/realtime_pipeline.py` copies `attack_family`, `attack_family_confidence`, `attack_family_margin`, and `family_status` into emitted alert events when composite runtime scoring is active.

### Key Files to Model After

- `ids/console/alerts.py` — current canonical alert hydration path; best place to normalize family metadata once so templates do not decode/interpret payloads separately.
- `tests/console/test_ids_operator_console_alerts_web.py` — existing route-first TDD pattern for the alert queue and alert detail screens.
- `tests/console/test_ids_operator_console_web.py` — existing auth/root-path/web-app integration pattern; useful for shared route contract proof.
- `docs/current/console/ids_operator_console_ui_surface_spec.md` — current UI contract that already describes the queue/detail surfaces and should be extended, not replaced.

---

## Agent B: Pattern Search

> Source: targeted grep and file reads

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Alert queue hydration | `ids/console/alerts.py::list_alerts_for_triage()` | DB row -> hydrated dict -> template consumption | Yes |
| Payload decode helper | `ids/console/alerts.py::_decode_payload()` and `ids/console/web.py::_with_decoded_payload()` | decode once near boundary, keep templates simple | Yes |
| Legacy/optional state rendering | `ids/console/templates/alerts.html`, `ids/console/templates/alert_detail.html`, `docs/current/console/ids_operator_console_ui_surface_spec.md` | explicit badges and `—` fallback instead of silent omission | Yes |
| Route-level screen TDD | `tests/console/test_ids_operator_console_alerts_web.py` | seed DB rows, render page, assert concrete text and forms | Yes |
| Shared config-resolution rule | `resolve_telegram_config_with_source()` pattern from settings lane | shared interpretation helper instead of per-surface reimplementation | Conceptually yes |

### Reusable Utilities

- **Alert shaping**: `ids/console/alerts.py` — already owns suppression calculation and payload decoding for queue/detail pages.
- **Operator store**: `ids/console/db.py::upsert_alert()` / `list_alerts()` — persists generic alert records without requiring a new schema for family metadata.
- **Runtime family contract**: `ids/runtime/inference.py` and `ids/runtime/realtime_pipeline.py` — already define the canonical field names and `known | unknown | benign` semantics.
- **Template contract tests**: `tests/console/test_ids_operator_console_alerts_web.py` — cheapest way to pin known/unknown/legacy rendering.

### Naming Conventions

- Jinja templates use simple row keys like `alert["suppressed"]`, not alternate spellings such as `is_suppressed`.
- Route files and templates stay additive under the existing `/alerts` and `/alerts/{alert_id}` topology; no separate family route pattern exists today.
- Operator UI badges and fallback text favor explicit state labels over inferred semantics.

---

## Agent C: Constraints Analysis

> Source: `pyproject.toml`, console/runtime source, existing tests

### Runtime & Framework

- **Python version**: `>=3.11`
- **Runtime**: Python CLI + FastAPI service
- **Framework**: FastAPI + Starlette sessions + Jinja2 templates
- **Storage**: SQLite via `sqlite3`

### Existing Dependencies (Relevant to This Feature)

| Package | Purpose |
|---------|---------|
| `fastapi` / `starlette` | Operator-console web routes and TestClient |
| `jinja2` | Server-rendered queue/detail pages |
| `sqlite3` | Alert persistence through `OperatorStore` |
| `pandas` / `catboost` | Upstream runtime-family producers; not changed directly by this feature |

### New Dependencies Needed

No new dependencies appear necessary. The current stack already supports this UI slice.

### Build / Quality Requirements

```bash
# Targeted proofs that should gate this feature:
pytest tests/console/test_ids_operator_console_alerts_web.py
pytest tests/console/test_ids_operator_console_web.py
pytest tests/console/test_ids_operator_console_ingest.py
```

### Database / Storage

- **Current shape**: `ids/console/db.py` stores alert rows with generic top-level network fields and one `payload_json` blob.
- **Important constraint**: there are no first-class `attack_family*` columns in the `alerts` table today.
- **Implication**: the lightest-weight operator rollout is to normalize runtime family fields from `payload_json` into one canonical alert view model instead of migrating the SQLite schema first.

---

## Agent D: External Research

> Source: none required

### Library Documentation

No external library research was needed. The feature fits existing repo patterns and existing framework usage.

### Community Patterns

Not applicable. The planning question is about local codebase integration and existing product semantics, not a new library or external protocol.

### Known Gotchas / Anti-Patterns

- **Anti-pattern**: decode `payload_json` separately in each template or route.
  - Why it matters: this would recreate the config-drift problem from the Telegram settings lane, but for family semantics.
  - How to avoid: shape family metadata once in `ids/console/alerts.py` and let all queue/detail consumers read the same keys.

- **Anti-pattern**: ship a queue badge before one clicked-through explanation surface exists.
  - Why it matters: operators could see `unknown` in the queue and misread it as runtime failure or benign traffic.
  - How to avoid: make the detail page the first trustworthy explanation surface, then mirror the compact signal into the queue.

---

## Open Questions

No unresolved research blockers remain. The remaining choices are planning tradeoffs, not missing codebase facts.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: the runtime already emits additive family enrichment fields, the operator store already persists those events generically via `payload_json`, and the operator console already has stable `/alerts` and `/alerts/{id}` surfaces with strong route-level tests.

**What we need**: one shared alert-family view model plus phased UI work that first explains the family signal correctly and then exposes it compactly in the queue without widening scope into reports or new control-plane behavior.

**Key constraints from research**:
- The `alerts` table has no first-class family columns, so planning should default to shared payload normalization rather than a schema migration.
- `web.py` and the alert templates are shared high-traffic files; phase/story design should keep that write scope understandable and conflict-aware.
- The UI must preserve runtime semantics exactly: `known`, `unknown`, `benign`, and legacy/unavailable are different states.

**Institutional warnings to honor**:
- Shared interpretation rules must live in one helper, not be reimplemented per surface.
- The real app factory and route tree are the contract; tests must exercise those surfaces directly.
