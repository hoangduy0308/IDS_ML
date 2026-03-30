# IDS Flow Extractor Replacement — Context

**Feature slug:** ids-flow-extractor-replacement
**Date:** 2026-03-30
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature defines the research and planning boundary for replacing the current CICFlowMeter-like flow extractor contract without writing code yet, with emphasis on identifying the true model-serving contract, dependency seams, and acceptable compatibility strategy.

**Domain type(s):** CALL | RUN | ORGANIZE | READ

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Compatibility Strategy
- **D1** Prioritize pragmatic compatibility, not blind drop-in fidelity.
  *Rationale: adapter and preflight may change in controlled ways if that is required to preserve correctness, but the work should not assume a full contract redesign by default.*

- **D2** Optimize for model-serving correctness first.
  *Rationale: the most important success criterion is that runtime features entering the active model bundle remain semantically correct and stable; live/demo convenience is secondary.*

- **D3** Use a tiered contract analysis.
  *Rationale: planning must classify extractor outputs into `must-have`, `adapter-recoverable`, and `non-critical/legacy` rather than assuming all historical CICFlowMeter-like fields are equally required.*

### Source Of Truth
- **D4** When docs and running code disagree, treat code and tests as the source of truth and record the mismatch explicitly.
  *Rationale: downstream planning should anchor on the currently enforced runtime contract, then identify documentation drift as a follow-up artifact rather than designing against stale prose.*

### Scope Boundary
- **D5** This phase is research/discovery only.
  *Rationale: no implementation, no migration, no prototype extractor, and no plan execution details are allowed until the extractor contract and risk map are clear.*

- **D6** Planning may compare architectural options, but must not assume a full redesign unless the dependency map proves the legacy shell is mostly accidental.
  *Rationale: preserve decision pressure toward the narrowest safe change set until research shows otherwise.*

### Agent's Discretion
- The planning agent may decide how to gather evidence for feature criticality, dependency classification, and compatibility tradeoffs, provided it honors D1-D6 and does not skip validation before execution.

---

## Specific Ideas & References

- The target is a replacement for the current flow extractor layer that today behaves like a CICFlowMeter command-wrapper.
- The user explicitly wants the work ordered as:
  1. read docs and existing code,
  2. extract the precise contract the new extractor must satisfy,
  3. map all CICFlowMeter assumptions in code/docs/tests,
  4. propose information-filtering and architectural strategies.
- The required eventual research output shape is:
  `Research Summary`, `Extractor Contract`, `CICFlowMeter Dependency Map`, `Information Filtering Strategy`, and `Architectural Options`.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `scripts/ids_live_flow_bridge.py` — the current live bridge contract around extractor invocation, output-path naming, CSV loading, and adapter handoff.
- `scripts/ids_feature_contract.py` — the canonical runtime schema validator for required numeric feature columns and passthrough handling.
- `scripts/ids_live_sensor.py` — the staged live daemon wiring capture, bridge, runtime pipeline, and sink behavior around the active model bundle.
- `scripts/ids_live_sensor_preflight.py` — the preflight/runtime contract for exact binary paths, activation record, jnetpcap, and writable runtime locations.
- `scripts/ids_realtime_pipeline.py` — the runtime JSONL contract that validates records against the feature schema before inference.
- `scripts/ids_record_adapter.py` — the adapter/profile system that likely contains the strongest legacy compatibility logic and must be read deeply during planning.

### Established Patterns
- Exact-path preflight validation for service dependencies: established in `scripts/ids_live_sensor_preflight.py` and reinforced by critical learnings.
- Runtime schema validation before inference: established in `scripts/ids_feature_contract.py` and `scripts/ids_realtime_pipeline.py`.
- Staged live pipeline composition: capture -> bridge -> adapter -> realtime pipeline -> sinks in `scripts/ids_live_sensor.py`.
- Historical CICFlowMeter-like shell contract: default `Cmd` prefix, `_Flow.csv` suffix, and adapter profile `cicflowmeter_primary_v1` in `scripts/ids_live_flow_bridge.py`.

### Integration Points
- The extractor replacement research must trace how `scripts/ids_live_flow_bridge.py` builds command and output expectations.
- The contract analysis must trace how adapted records from `scripts/ids_record_adapter.py` reach `scripts/ids_realtime_pipeline.py`.
- The compatibility decision must include how `scripts/ids_live_sensor_preflight.py` and `scripts/ids_live_sensor.py` assume Java/jnetpcap/extractor-runtime availability.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `AGENTS.md` — governing workflow, gates, and repo-specific Khuym rules.
- `README.md` — current project scope and the canonical doc reading order.
- `docs/final_model_bundle.md` — the active model bundle and feature artifact contract.
- `docs/ids_inference_architecture.md` — inference-side architecture and bundle assumptions.
- `docs/ids_realtime_pipeline_architecture.md` — runtime pipeline contract around structured records and schema validation.
- `docs/ids_record_adapter_architecture.md` — intended adapter responsibilities and profile-driven compatibility logic.
- `docs/ids_live_sensor_architecture.md` — live sensor architecture and runtime dependency expectations.

---

## Outstanding Questions

### Deferred to Planning

- [ ] What is the exact extractor input/output/file/schema/runtime contract across docs, code, and tests? — requires full read of the canonical docs and all listed scripts/tests.
- [ ] Which of the current CICFlowMeter-like assumptions are hard runtime dependencies versus configurable seams versus historical residue? — requires repo-wide dependency tracing.
- [ ] Within the active 72-feature bundle, which features are runtime-critical, which are adapter-recoverable, and which are legacy/non-critical? — requires comparison between training feature columns, adapter profiles, and runtime validation.
- [ ] Would a drop-in shell, a controlled adapter/preflight change, or a staged offline-first extractor produce the best risk-adjusted path? — requires an explicit architectural option analysis after contract extraction.
- [ ] Where are feature-semantics drift risks highest if a new extractor computes values differently from CICFlowMeter-like tooling? — requires training/runtime semantics review.

---

## Deferred Ideas

- Full extractor redesign as a first move — deferred unless planning proves the existing shell contract is mostly accidental rather than materially enforced.
- Immediate implementation spike — deferred until the dependency map and risk analysis are complete.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
