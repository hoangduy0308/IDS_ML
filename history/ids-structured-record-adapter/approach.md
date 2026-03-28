# Approach: IDS Structured Record Adapter

**Date**: 2026-03-27
**Feature**: `ids-structured-record-adapter`
**Based on**:
- `history/ids-structured-record-adapter/CONTEXT.md`
- `history/ids-structured-record-adapter/discovery.md`

---

## 1. Recommended Approach

Implement a narrow adapter module under `scripts/` that owns explicit profile-based normalization from `CICFlowMeter-like upstream records` into direct `72-feature structured flow records` plus controlled passthrough metadata. The adapter should expose a reusable core API for record adaptation and a thin CLI wrapper for `stdin/stdout` and file-path I/O. The core should normalize a selected upstream profile, extract stable passthrough metadata, delegate final canonical validation to the existing `FlowFeatureContract`, and emit one of two outputs per record: `adapted record` or `adapter-stage quarantine record`.

Concretely, the adapter should:
- define a small profile registry with one primary and one secondary profile
- use explicit per-profile field maps only; no generic mapping DSL
- normalize profile-specific field names and metadata envelope keys into a stable adapter output shape
- reuse `FlowFeatureContract` for the final `72`-feature validation boundary instead of duplicating model contract logic
- emit adapted JSONL records that the current `ids_realtime_pipeline.py` can read directly
- emit a separate adapter-specific quarantine JSONL stream for records that fail profile normalization or final canonical validation

This keeps the adapter boundary tight, reuses the strongest local pattern, and avoids introducing new infrastructure before the upstream shape is proven.

Implementation choices now locked in:
- primary profile: `cicflowmeter_primary_v1`
- secondary profile: `cicflowmeter_secondary_v1`
- fixed normalized metadata keys: `adapter_profile`, `source_flow_id`, `source_collector_id`, `source_timestamp`
- adapter quarantine event type: `adapter_quarantine`
- adapter quarantine shared fields: `profile`, `reason`, `record_index`, `source_record`

One explicit guardrail for planning and implementation: the primary upstream profile should not collapse into “already-canonical 72-feature input with a different filename”. It should include a real CICFlowMeter-like naming surface, at least for the short-form aliases already seen in local precedent, so the adapter proves actual upstream normalization rather than acting as a pass-through wrapper.

---

## 2. Alternatives Considered

### Alternative A: Generic config-driven mapper for arbitrary upstream sources

- Why considered: it sounds flexible and future-proof.
- Why rejected: it violates the v1 boundary locked in `CONTEXT.md`, creates a larger correctness surface, and makes validation/review harder because semantics move into open-ended config instead of explicit code.

### Alternative B: Extend `ids_feature_contract.py` directly to become the adapter

- Why considered: there is already contract and alias logic in place.
- Why rejected: `ids_feature_contract.py` is the model-facing canonical boundary. Adapter-stage profile handling, metadata-envelope normalization, and adapter-specific quarantine should remain a distinct layer rather than mixing upstream concerns into the final model contract.

### Alternative C: Make the adapter file-only and skip streaming I/O

- Why considered: smaller implementation surface.
- Why rejected: it weakens the adapter's usefulness in the actual IDS path because the downstream runtime already supports `stdin/stdout` style composition and the locked decision explicitly allows pipeline-style execution.

### Alternative D: Emit an intermediate normalized schema and add another mapper before runtime

- Why considered: could separate upstream normalization from model alignment.
- Why rejected: the locked decision requires the adapter to finish at the direct `72`-feature boundary. An intermediate schema would add another translation layer and another place for drift.

---

## 3. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Profile registry and field-mapping definitions | **HIGH** | Wrong field mapping silently corrupts deploy semantics; this is the most correctness-sensitive part of the feature | Unit tests for primary/secondary profile mapping and collision/missing-field behavior |
| Adapter core normalization pipeline | **MEDIUM** | New code, but built on top of existing contract patterns | Tests for valid adaptation, passthrough extraction, and final canonical validation delegation |
| Adapter-stage quarantine contract | **MEDIUM** | New output type with stage-specific semantics | Tests for error classification and required shared fields |
| CLI wrapper with stdin/stdout and file modes | **MEDIUM** | Existing pattern exists in runtime, but adapter adds a second executable boundary | CLI tests for file mode, stdin mode, and output path behavior |
| Downstream compatibility with `ids_realtime_pipeline.py` | **HIGH** | The whole point of the feature is producing records the runtime can consume directly | Dry-run proving adapter output can feed runtime without extra schema translation |
| Documentation and demo fixture | **LOW** | Existing docs/demo pattern already exists | Manual review plus regression-oriented fixture coverage |

Failure modes called out in adversarial review:
- choosing a “primary profile” that is effectively already canonical would under-test the adapter and create false confidence
- letting passthrough extras absorb too much of the source record would blur the adapter boundary and make downstream observability inconsistent

---

## 4. Decision Rationale

This approach is the most defensible one because it draws the adapter boundary exactly where the previous feature stopped: the runtime expects model-ready structured records, so the adapter's job is to produce that contract and stop there. It avoids the two biggest failure modes for this stage of the project:

- semantic drift from over-flexible or implicit mapping logic
- architecture sprawl from mixing packet extraction, generic config systems, or additional intermediate schemas into a component that should stay narrow

Reusing `FlowFeatureContract` as the final validation gate is the strongest local choice because the model-facing schema is already frozen there. Keeping adapter-stage profiles explicit and versioned also makes future extension tractable: adding a third profile later is a local change to a bounded registry, not a rewrite of the entire contract layer.

---

## 5. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Canonical 72-feature contract | `scripts/ids_feature_contract.py` | Reuse as final adapter output validator | Small |
| Realtime runtime consumer | `scripts/ids_realtime_pipeline.py` | Feed it with adapter-produced JSONL records | Small |
| Upstream profile normalization | None | Explicit primary + secondary profile registry | New |
| Adapter-specific quarantine contract | None | Separate adapter-stage error output | New |
| Adapter CLI | None | `stdin/stdout` + file-path wrapper | New |
| Adapter docs/demo | Runtime docs only | Adapter contract + profile boundary docs | Medium |

---

## 6. Proposed File Structure

```text
scripts/
  ids_record_adapter.py            # Core adapter logic + thin CLI wrapper
tests/
  test_ids_record_adapter.py       # Profile mapping, quarantine, CLI, downstream-compat tests
docs/
  ids_record_adapter_architecture.md   # Adapter boundary, profile model, output contracts
artifacts/
  demo/
    ids_record_adapter_primary_sample.jsonl
    ids_record_adapter_secondary_sample.jsonl
history/
  ids-structured-record-adapter/
    CONTEXT.md
    discovery.md
    approach.md
```

---

## 7. Dependency Order

```text
Layer 1: Define adapter output/quarantine contract and profile registry shape
Layer 2: Implement adapter core normalization and final canonical validation
Layer 3: Implement CLI I/O wrapper and downstream runtime compatibility path
Layer 4: Add tests, fixtures, and adapter architecture docs
```

### Parallelizable Groups

- Group A: `Contract/profile registry` and `test scaffolding` can move in parallel once the approach is fixed.
- Group B: `CLI I/O wrapper` depends on the adapter core.
- Group C: `docs/fixtures` can run after interface shapes stabilize and in parallel with late-stage tests.

---

## 8. HIGH-Risk Summary (for validating)

- `Profile registry and field-mapping definitions`: validate that the chosen primary and secondary profiles stay CICFlowMeter-like and do not silently invent missing model features.
- `Downstream compatibility with ids_realtime_pipeline.py`: validate that adapter output can be piped directly into the runtime without another translation step or passthrough leakage into scoring.

Implementation note:
- the adapter-stage contract remains separate from `FlowFeatureContract`; the registry normalizes profile-specific names first, then the later bead can delegate final canonical validation to the frozen model contract.
