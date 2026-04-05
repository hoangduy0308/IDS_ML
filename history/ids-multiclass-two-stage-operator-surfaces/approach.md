# Approach: Two-Stage Family Operator Surfaces

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-operator-surfaces`
**Based on**:
- `history/ids-multiclass-two-stage-operator-surfaces/discovery.md`
- `history/ids-multiclass-two-stage-operator-surfaces/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Runtime family semantics | `ids/runtime/inference.py` and `ids/runtime/realtime_pipeline.py` already emit `attack_family`, confidence, margin, and `family_status` | Operator console must consume the same meaning without redefining it | Small |
| Alert persistence | `ids/console/db.py` stores generic alert rows plus `payload_json` | Canonical operator-facing family view model on top of persisted payloads | Medium |
| Alert detail surface | `ids/console/templates/alert_detail.html` shows network/triage context and notes | Explanation block for `known`, `unknown`, and legacy/unavailable family states | Medium |
| Alerts queue | `ids/console/templates/alerts.html` shows triage-first rows with severity/status/suppression | Compact family/status presentation that stays scan-friendly | Medium |
| Regression proof | Existing web tests cover auth, queue, detail, notes, status updates | Family-aware route/template tests for known/unknown/legacy behavior | Medium |
| Docs/spec | `docs/current/console/ids_operator_console_ui_surface_spec.md` documents current queue/detail fields | Updated operator contract for family enrichment semantics | Small |

---

## 2. Recommended Approach

Keep the operator rollout additive, just like the runtime rollout. The console should not gain a new DB schema or a new family-specific route first; it should gain one shared alert-family shaping helper on top of the existing `payload_json` path, then render that shared contract in the detail page first and the queue second. This is the right fit for the repo because the data is already arriving from runtime, the operator surfaces already exist, and the main failure mode here is semantic drift, not missing infrastructure. The feature should close by pinning route-level tests and docs so future work cannot quietly reinterpret `unknown`, `benign`, or legacy alerts.

### Why This Approach

- It matches the existing additive runtime rollout at [inference.py](F:/Work/IDS_ML_New/ids/runtime/inference.py) and [realtime_pipeline.py](F:/Work/IDS_ML_New/ids/runtime/realtime_pipeline.py) instead of inventing a second contract for operators.
- It honors locked decisions `D1` through `D9` in [CONTEXT.md](F:/Work/IDS_ML_New/history/ids-multiclass-two-stage-operator-surfaces/CONTEXT.md): queue + detail primary, read-only slice, explicit `unknown`, and honest legacy behavior.
- It avoids the config-drift anti-pattern from the Telegram settings lane by centralizing family interpretation in one helper rather than spreading it across routes and templates.
- It keeps blast radius down: no new dependency, no new route family, and no SQLite migration unless planning later proves that `payload_json` normalization is insufficient.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Family metadata source | Normalize from `payload_json` in one shared alert helper first | The store already persists runtime fields generically; this avoids an unnecessary schema change for the first operator slice. |
| Semantic authority | Treat runtime field names and meanings as canonical | Keeps operator meaning aligned with the completed runtime-contract lane. |
| Surface order | Detail page first, queue second | One alert must explain the signal correctly before the queue uses a compact shorthand at scale. |
| Legacy handling | Explicit unavailable/legacy display, not silent omission | Satisfies `D9` and prevents operators from reading absent data as a confident family result. |
| Verification strategy | Route-level web tests plus doc/spec updates | The app factory and rendered surfaces are the real contract here. |

---

## 3. Alternatives Considered

### Option A: Add first-class family columns to the `alerts` table before any UI work

- Description: migrate the SQLite schema and persist family fields as top-level DB columns first.
- Why considered: it would make queue/detail rendering simpler long-term.
- Why rejected: it widens the first operator slice into migration and ingest work even though the needed data is already present in `payload_json`. The current feature boundary is operator surfaces, not persistence redesign.

### Option B: Render family fields directly from `payload_json` inside each template

- Description: let `alerts.html` and `alert_detail.html` each read nested payload keys independently.
- Why considered: quickest path for a one-off visual change.
- Why rejected: it recreates the "shared contract reimplemented per surface" failure pattern. Queue/detail/JSON surfaces would drift on fallback rules and legacy handling almost immediately.

### Option C: Start with reports or family analytics instead of queue/detail

- Description: show family counts and charts in `Reports` first.
- Why considered: summary analytics can look impressive with less dense row UI work.
- Why rejected: locked decision `D5` explicitly keeps reports secondary. Operators need family context while triaging live alerts, not only in historical summaries.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Shared alert-family hydration helper | **MEDIUM** | Shared semantic boundary; if wrong, every surface misreads `unknown` / legacy state | Focused unit/route tests for known, unknown, benign/legacy cases |
| Alert detail rendering | **LOW** | Follows existing detail-template pattern | Web test for concrete rendered states |
| Alerts queue rendering | **MEDIUM** | Shared high-traffic template; must stay triage-dense and not confuse legacy rows | Queue route tests for compact states and fallback copy |
| Doc/spec update | **LOW** | Existing doc surface already exists | Doc review + tests still reference canonical field names |
| Shared route files (`web.py`) | **MEDIUM** | Central file touched by multiple console features | Keep phase/story ordering clear; validating should verify write-scope safety |

### Risk Classification Reference

```
Pattern in codebase?        -> YES = LOW base
External dependency?        -> YES = HIGH
Blast radius > 5 files?     -> YES = HIGH
Otherwise                    -> MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

No HIGH-risk components. Validating can focus on semantic coverage and write-scope clarity rather than spikes.

---

## 5. Proposed File Structure

```text
ids/
  console/
    alerts.py                        # Extend with canonical family view-model shaping
    web.py                           # Pass the shaped family fields into queue/detail pages
    templates/
      alerts.html                    # Compact family/status cell in triage table
      alert_detail.html              # Explanation block for family semantics and confidence
tests/
  console/
    test_ids_operator_console_alerts_web.py   # Family-aware queue/detail route proofs
    test_ids_operator_console_web.py          # Shared web-app integration proof if needed
    test_ids_operator_console_ingest.py       # Optional ingest proof if payload carriage needs pinning
docs/
  current/
    console/
      ids_operator_console_ui_surface_spec.md # Extend queue/detail contract with family fields
```

---

## 6. Dependency Order

```text
Layer 1 (sequential): Alert-family shaping contract in alerts.py
Layer 2 (sequential): Detail page rendering on top of the shaped contract
Layer 3 (sequential): Queue rendering on top of the same shaped contract
Layer 4 (parallel or trailing): Docs/spec and any supporting regression proof
```

### Parallelizable Groups

- Group A: shared alert-family shaping helper — must land first because every visible surface depends on the same semantics.
- Group B: detail-page rendering — depends on Group A and should come before queue shorthand.
- Group C: queue rendering — depends on Group A and benefits from the detail-page semantics already being nailed down.
- Group D: docs/spec updates and small supporting proofs — can follow the UI contract once the visible semantics are stable.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260404-telegram-settings-deploy-hardening.md` | Shared config/interpretation rules must not be reimplemented per surface | Centralize family-field interpretation in one helper instead of decoding semantics separately in queue/detail templates |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | The real app factory and route tree are the runtime contract | Use route-level web tests against `/alerts` and `/alerts/{id}` as the primary proof surface |
| `history/learnings/20260403-console-ui-tdd-rebuild.md` | Shared field names drift silently across templates and sessions | Treat family field names and fallback keys as canonical contract notes in planning/docs/tests |
| `history/learnings/20260405-composite-runtime-review-contracts.md` | Additive enrichment was the right rollout shape | Keep operator work additive too: consume existing family enrichment rather than replacing queue/detail semantics |

---

## 8. Open Questions for Validating

No open questions. The main validating job is to confirm the phased shape, semantic clarity, and shared write-scope safety.
