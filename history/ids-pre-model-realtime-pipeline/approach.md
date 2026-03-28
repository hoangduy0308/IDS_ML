# Approach: IDS Pre-Model Realtime Pipeline

**Date**: 2026-03-27
**Feature**: `ids-pre-model-realtime-pipeline`
**Based on**:
- `history/ids-pre-model-realtime-pipeline/discovery.md`
- `history/ids-pre-model-realtime-pipeline/CONTEXT.md`

---

## 1. Gap Analysis

> What exists vs. what the feature requires.

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Model bundle + threshold | `artifacts/final_model/catboost_full_data_v1/` with `model_bundle.json`, `feature_columns.json`, `model.cbm` | Reuse as canonical runtime config | Small — already exists |
| Batch schema alignment + scoring | `scripts/ids_inference.py` aligns `DataFrame` input and scores batches | Refactor-safe reuse in a realtime pipeline | Medium — existing code, new call path |
| Realtime input contract | None | Structured event contract around the frozen `72` model features | New |
| Record-level schema adaptation | None beyond exact batch alignment | Explicit alias/validator layer that can separate valid rows from quarantined rows | New |
| Realtime micro-batch runner | None | Long-running or looped runner that ingests structured flow events, batches briefly, and scores continuously | New |
| Quarantine + schema anomaly outputs | Training-time quarantine manifests only | Runtime quarantine sink and anomaly-alert sink | New |
| Deployment docs for pre-model runtime | `docs/ids_inference_architecture.md` documents only the batch inference layer | End-to-end architecture for realtime flow-event handling | Medium — extend existing design language |

---

## 2. Recommended Approach

Implement a thin Python runtime layer that accepts newline-delimited structured flow events, applies an explicit `feature extraction contract -> feature aliasing/alignment -> model inference` path, and writes two output streams: model alerts for valid records and quarantine/anomaly events for invalid ones. Keep the canonical contract anchored to the bundled `feature_columns.json`, and treat all schema adaptation as a separate, explicit step before the existing `IDSInferencer` is called. Reuse `ids_inference.py` for model loading and scoring so the current batch CLI remains intact while the new runtime path builds on the same model/bundle logic. For v1, use JSONL-friendly local inputs and outputs rather than adding a broker or embedding packet sniffing; that matches the repo’s current script-first architecture and keeps the system demonstrable, testable, and easy to explain.

### Why This Approach

- Reuses the strongest existing pattern at `F:/Work/IDS_ML_New/scripts/ids_inference.py` instead of replacing working model-loading logic.
- Honors locked decisions `D1`, `D2`, `D3`, and `D4` from `CONTEXT.md`: flow-record input only, upstream collector boundary, micro-batch realtime behavior, and quarantine-on-schema-failure.
- Mirrors the quarantine-first hygiene already used in `F:/Work/IDS_ML_New/scripts/preprocess_iot_diad.py`, which is the best local precedent for safe schema enforcement.
- Avoids introducing a queue, web framework, or packet-capture dependency that the codebase does not currently use.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime interface | Structured JSONL flow events from file path or `stdin` | Easiest v1 interface for a script-based repo; preserves “realtime log/event” semantics without external infra |
| Contract source of truth | `artifacts/final_model/catboost_full_data_v1/feature_columns.json` | Deployment should anchor to the bundled model contract, not infer fields dynamically |
| Adaptation layer | Dedicated contract/validator module in `scripts/` | Keeps aliasing, required fields, type coercion, and quarantine logic separate from model scoring |
| Batch policy | Small micro-batches with configurable `max_batch_size` and `flush_interval_seconds` | Matches locked decision `D3` and current DataFrame-based inferencer |
| Invalid record handling | Quarantine + schema anomaly event, never score malformed records | Matches locked decision `D4` and closes the evasion gap discussed during exploring |
| Output sinks | JSONL alert stream + JSONL quarantine stream + stdout summary stats | Fits repo conventions and stays easy to test locally |

---

## 3. Alternatives Considered

### Option A: Put raw packet sniffing and flow assembly inside the IDS service

- Description: build a single service that captures packets, assembles flows, computes all features, and runs the model.
- Why considered: it sounds like a more “complete IDS” in one component.
- Why rejected: violates locked decision `D2`, creates train/deploy feature-drift risk, and expands scope into packet processing before the current model contract is even integrated.

### Option B: Introduce a broker-backed consumer (Kafka/Redis/etc.) as the first runtime

- Description: define the runtime around a queue topic and implement a proper stream consumer immediately.
- Why considered: message brokers are common in production streaming systems.
- Why rejected: there is no existing broker pattern, dependency, or infrastructure in the repo, so this would add operational complexity before the contract and schema path are proven locally.

### Option C: Keep everything file-batch only and extend `ids_inference.py` with more flags

- Description: continue using only CSV/Parquet batch files and treat that as the deployment path.
- Why considered: it would minimize new code.
- Why rejected: it does not satisfy the user’s stated goal of building toward a realtime IDS path and conflates static file scoring with an online pre-model pipeline.

---

## 4. Risk Map

> Every component that is part of this feature must appear here.
> Workers use this to calibrate how carefully to proceed.

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Canonical feature contract module | **MEDIUM** | New code, but built directly on frozen schema and existing alignment patterns | Unit tests for required columns, type coercion, and alias handling |
| Schema alias/adaptation rules | **HIGH** | Security-sensitive and novel in this repo; bad mapping could create silent model drift or evasion gaps | Validate mapping behavior with explicit good/bad fixture records |
| `ids_inference.py` compatibility-preserving refactor | **MEDIUM** | Existing working path must not break while becoming reusable | Existing tests must still pass; add regression coverage for bundle loading and alignment |
| Realtime micro-batch runner | **HIGH** | Novel runtime pattern in this repo and central to the deployment architecture | Dry-run with mixed valid/invalid JSONL events; verify flush behavior and no dropped valid records |
| Quarantine + schema anomaly outputs | **MEDIUM** | New behavior, but modeled after preprocessing quarantine precedent | Tests for per-record quarantine and batch continuation |
| Architecture/documentation updates | **LOW** | Follows existing docs pattern | Manual doc review against code plan |

### Risk Classification Reference

```
Pattern in codebase?        → YES = LOW base
External dependency?        → YES = HIGH
Blast radius > 5 files?    → YES = HIGH
Otherwise                   → MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `Schema alias/adaptation rules`: prove that the runtime can adapt upstream collector field names without silently inventing or default-filling missing model features.
- `Realtime micro-batch runner`: prove that the chosen flush policy and mixed-record handling do not lose valid records, stall on malformed records, or drop a final partial batch during shutdown/end-of-stream.

---

## 5. Proposed File Structure

> Where new files will live. Workers use this to plan their work.

```text
scripts/
  ids_feature_contract.py           # Canonical 72-feature contract, alias rules, record validation
  ids_realtime_pipeline.py          # JSONL/stream micro-batch runtime that reuses IDSInferencer
  ids_inference.py                  # Small refactor only if needed to share config/alignment helpers safely
tests/
  test_ids_feature_contract.py      # Unit tests for aliasing, coercion, and quarantine classification
  test_ids_realtime_pipeline.py     # Micro-batch + valid/invalid mixed-stream behavior
  test_ids_inference.py             # Existing regression suite remains in place
docs/
  ids_realtime_pipeline_architecture.md   # End-to-end runtime architecture and data contract
history/
  ids-pre-model-realtime-pipeline/
    CONTEXT.md
    discovery.md
    approach.md
```

---

## 6. Dependency Order

> Dependency order for bead creation. This is planning guidance, not a runtime wave scheduler.

```text
Layer 1 (sequential): Define contract module and alias/validation rules
Layer 2 (parallel): Refactor reusable inference helpers + write contract tests
Layer 3 (sequential): Implement realtime micro-batch runner on top of the contract/inferencer
Layer 4 (parallel): Add runtime tests + architecture documentation
```

### Parallelizable Groups

- Group A: `Refactor reusable inference helpers`, `Add contract validation tests` — both depend on the contract shape being fixed but can proceed together afterward.
- Group B: `Implement realtime micro-batch runner` — depends on Group A.
- Group C: `Document runtime architecture` — depends on the recommended approach and can run in parallel with late-stage testing once interfaces stabilize.

---

## 7. Institutional Learnings Applied

No prior institutional learnings relevant to this feature.

---

## 8. Open Questions for Validating

> Items that couldn't be resolved in planning. The khuym:validating skill's plan-checker will address these.

- [ ] What exact alias map is safe to support for likely upstream collectors without weakening the strict `72`-feature contract? This matters because over-permissive mapping creates silent drift.
- [ ] What micro-batch defaults (`max_batch_size`, `flush_interval_seconds`) give “realtime enough” behavior while still keeping the runner simple and deterministic in tests?
- [ ] Should the first runtime accept both `stdin` and `--input-path`, or is one of them enough for the initial implementation? This affects CLI/API simplicity and demo ergonomics.
- [ ] What shutdown/end-of-stream behavior is required for partially filled micro-batches? This matters because a realtime runner must not silently lose the last valid records when input pauses or the process exits.
