# Approach: IDS Flow Extractor Replacement

**Date**: 2026-03-30
**Feature**: `ids-flow-extractor-replacement`
**Based on**:
- `history/ids-flow-extractor-replacement/discovery.md`
- `history/ids-flow-extractor-replacement/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Model-facing schema contract | `FlowFeatureContract` + bundle `feature_columns.json` enforce exact 72 canonical numeric features | A replacement extractor strategy that never breaks this boundary silently | Medium |
| Extractor shell contract | `LiveFlowBridge` expects `Cmd <pcap> <output-dir>` and `<pcap-stem>_Flow.csv` | A replacement seam that can swap extractor implementation without corrupting downstream correctness | Medium |
| Upstream normalization | Adapter supports only `cicflowmeter_primary_v1` / `secondary_v1` closed profiles | A decision on whether the replacement should target the primary profile directly or introduce an explicit new profile/config path | Medium |
| Live deployment contract | Preflight, systemd, and same-host stack assume Java + extractor binary + `jnetpcap` | A controlled plan for retiring or parameterizing these dependencies if the new extractor does not need them | High |
| Semantic validation | Existing tests prove shape and failure handling, not semantic equivalence of newly computed flow statistics | Golden contract tests and validation spikes for semantic drift on key features | High |
| Offline demo path | Adapter + realtime pipeline demos already exist and are stable | A minimal replacement-extractor evaluation path that proves correctness before live integration | Low |

---

## 2. Recommended Approach

Recommend an **offline-first, closed-window replacement extractor that initially targets the existing primary adapter contract, followed by controlled bridge/preflight generalization only after semantic validation passes**. In practice, that means the first implementation path should accept a bounded `pcap` input, emit a deterministic structured output for closed-window processing, and preserve the current staged-live seam `capture -> closed pcap -> extractor -> adapter -> realtime pipeline`. The replacement should optimize for model-serving correctness rather than shell mimicry: keep the 72-feature bundle boundary hard, keep activation-record bundle loading untouched, and let adapter or bridge configuration absorb naming/metadata differences where safe. Live sensor and same-host tooling should only be relaxed after validating proves which Java/`jnetpcap`/`Cmd` assumptions are extractor-specific rather than true runtime requirements.

### Why This Approach

- It honors **D1** by preserving compatibility where it matters operationally while refusing blind fidelity to historical packaging residue.
- It honors **D2** and **D3** by keeping the 72-feature model-facing boundary hard and forcing a tiered analysis of what belongs in extractor output versus adapter normalization.
- It follows the existing staged-live pattern in `scripts/ids_live_sensor.py` and `history/learnings/20260328-live-sensor-runtime-contracts.md`, avoiding the proven mistake of equating “live sensor” with “direct live extractor”.
- It preserves the safest production contracts already hardened in `scripts/ids_live_sensor_preflight.py`, `scripts/ids_same_host_stack.py`, and the bundle activation flow.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Live ingestion seam | Keep closed-window `pcap` seam | Existing pattern, lowest semantic and operational risk |
| First compatibility target | Emit data consumable by `cicflowmeter_primary_v1` or an equally explicit successor profile | Reuses the current adapter contract and isolates semantic risk to one seam |
| Model boundary | Keep exact 72-feature validation unchanged; treat any subset extractor as spike-only evidence, not a production target | Locked by D2/D4 and reinforced by bundle/runtime code |
| Metadata handling | Keep model-irrelevant metadata in adapter passthrough, not in extractor-specific scoring logic | Matches `FlowFeatureContract` and `ids_realtime_pipeline.py` |
| Live deployment migration | Parameterize/remove Java and `jnetpcap` only after extractor implementation proves they are obsolete | Preserves exact-path preflight discipline and reduces premature blast radius |

---

## 3. Alternatives Considered

### Option A: Pure drop-in replacement of `Cmd <pcap> <output-dir>` and `_Flow.csv`

- Description: keep the full legacy shell contract intact and require the new extractor to impersonate the old one as closely as possible.
- Why considered: lowest visible change to bridge, service unit, and same-host stack.
- Why rejected: it over-optimizes for packaging compatibility and risks dragging unnecessary Java/`jnetpcap`/naming baggage into the new extractor before proving those constraints matter to model correctness.

### Option B: New extractor contract plus immediate adapter/preflight/runtime refactor

- Description: define a new extractor output surface up front and update bridge, adapter, preflight, stack, docs, and tests together.
- Why considered: cleaner long-term architecture and fewer historical seams.
- Why rejected: too much blast radius before semantic fidelity is proven; it would combine the hardest correctness problem with the widest deployment change in one move.

### Option C: Direct live extractor from NIC rather than closed-window staged processing

- Description: bypass file-bounded extraction and make the replacement extractor consume live traffic directly.
- Why considered: might reduce windowing latency and feel more “native”.
- Why rejected: prior repo learnings already disproved this assumption for the current architecture; it reopens the highest-risk seam with no evidence that it is needed.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Replacement extractor semantic core | **HIGH** | Novel implementation, directly affects training/runtime feature semantics, no existing proof that new calculations match current family closely enough | Spike in validating: semantic fidelity on representative closed pcaps and tier-1 features |
| Adapter profile strategy | **MEDIUM** | Existing adapter patterns exist, but planning must choose whether to target `cicflowmeter_primary_v1` directly or add a new explicit profile | Validate explicit profile surface and regression coverage |
| Bridge compatibility layer | **MEDIUM** | Existing pattern exists in `ids_live_flow_bridge.py`, but contract may need controlled generalization beyond `Cmd`/`_Flow.csv` | Regression tests for command building, output discovery, and window-stage error handling |
| Live sensor preflight contract | **HIGH** | Operationally sensitive, currently hardcodes Java/extractor/`jnetpcap`; any change affects startup gating and deployment docs | Spike in validating: safe parameterization/removal path without weakening fail-closed behavior |
| Same-host stack orchestration | **HIGH** | Blast radius spans stack bootstrap/preflight/recover/post-restore and docs; any extractor dependency change propagates through many files | Validating must confirm write-scope decomposition and stack regression plan |
| Bundle/runtime model contract | **LOW** | Existing pattern is hardened and should remain untouched | Proceed; regression only to prove no contract drift |
| Demo fixtures and runbooks | **MEDIUM** | Several demo/docs assume CICFlowMeter-like profile IDs and current shell/dependency names | Regression update path after implementation choices stabilize |

### HIGH-Risk Summary (for khuym:validating skill)

- `Replacement extractor semantic core`: can the new extractor compute tier-1 flow features closely enough from closed pcaps to preserve model-serving correctness without retraining?
- `Live sensor preflight + same-host stack dependency migration`: can Java/`jnetpcap`/legacy extractor-path assumptions be parameterized or removed without weakening exact-path preflight and deployment readiness semantics?

---

## 5. Proposed File Structure

```text
scripts/
  ids_live_flow_bridge.py              # Controlled compatibility changes if extractor shell differs
  ids_record_adapter.py                # Optional new explicit profile or profile registry extension
  ids_live_sensor.py                   # Only if live integration needs new bridge config
  ids_live_sensor_preflight.py         # Only if extractor dependency surface changes
  ids_same_host_stack.py               # Same-host preflight delegation changes, if needed
  ids_same_host_stack_manage.py        # CLI defaults/help text if runtime dependency surface changes
  ids_<new_extractor>.py               # New extractor entrypoint (offline-first)

tests/
  test_ids_live_flow_bridge.py         # Bridge contract regressions
  test_ids_record_adapter.py           # Adapter profile/output regressions
  test_ids_live_sensor_preflight.py    # Preflight dependency regressions
  test_ids_live_sensor.py              # Live daemon wiring regressions
  test_ids_same_host_stack_manage.py   # Stack CLI / deployment contract regressions
  test_ids_<new_extractor>.py          # New extractor contract and fixture tests

docs/
  ids_live_sensor_architecture.md      # Dependency/runtime wording if legacy assumptions change
  ids_live_sensor_operations.md        # Preflight/runbook updates
  ids_same_host_stack_operations.md    # Same-host CLI/runbook updates
  e2e_demo_runbook.md                  # Demo commands and fixture path updates
```

---

## 6. Dependency Order

```text
Layer 1 (sequential): Contract/golden-fixture definition for replacement extractor boundary
Layer 2 (sequential): Offline replacement extractor semantic core
Layer 3 (parallel): Bridge compatibility updates + adapter profile/config updates
Layer 4 (sequential): Live sensor preflight and same-host stack dependency migration
Layer 5 (parallel): Docs, demo fixtures, and regression updates
```

### Parallelizable Groups

- Group A: `bridge compatibility`, `adapter profile/config updates` — can proceed in parallel after extractor contract/golden fixtures are stable.
- Group B: `live sensor preflight`, `same-host stack orchestration` — should remain coupled after Group A because they share the deployment dependency surface.
- Group C: `docs/demo/test updates` — can run after Groups A and B stabilize.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Prefer closed-window staged-live seams over unproven direct live extraction | Recommended approach keeps `pcap` windows as the extractor seam and rejects direct NIC-native extraction as the first move |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Linux services need exact-path preflight with one config source | Approach keeps preflight hard and treats helper-dependency migration as a HIGH-risk, validating-gated step |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | Production model/schema/threshold selection must stay on one activation contract | Approach forbids reopening raw schema/threshold overrides while changing the extractor layer |
| `history/learnings/20260328-adapter-rollback-contract.md` | Multi-output publishing and rollback must be treated as one contract | Any future extractor-side durable outputs should follow existing fail-closed, test-heavy file publishing patterns rather than ad hoc side effects |

---

## 8. Open Questions for Validating

- [ ] What tolerance or comparison method should the semantic-fidelity spike use for tier-1 features extracted from the same closed pcaps? — this determines whether the replacement is “correct enough” without retraining.
- [ ] Can the bridge accept a more explicit extractor contract than `_Flow.csv` discovery without harming live operational simplicity? — impacts whether compatibility stays shell-shaped or becomes declarative.
- [ ] If the new extractor cannot supply all 72 features with acceptable semantics, does the project stop at offline research or pivot into a retraining-required path? — execution safety depends on this decision being surfaced early.

## 9. Addendum: Contract Package

Bead `ids_ml_new-vii9.4` wrote the narrowed pre-implementation contract package:

- `history/ids-flow-extractor-replacement/contract-spec.md`
- `history/ids-flow-extractor-replacement/filtering-strategy.md`

Use them as the guardrail for downstream execution:

- `contract-spec.md` defines the exact current bridge -> adapter -> runtime -> bundle contract from repo evidence.
- `filtering-strategy.md` defines the tier split between must-have bundle semantics, adapter-recoverable normalization, and legacy shell residue.

The critical downstream rule remains unchanged:

- subset extractor output is spike-only evidence, not a production-ready contract, until validating explicitly approves a narrower boundary
