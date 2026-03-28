# Discovery: IDS Structured Record Adapter

**Date**: 2026-03-27
**Feature**: `ids-structured-record-adapter`
**Based on**:
- `history/ids-structured-record-adapter/CONTEXT.md`

---

## Institutional Learnings

No prior learnings for this domain.

---

## 1. Architecture Topology

### Current relevant modules

| Path | Role | Why it matters for adapter planning |
|------|------|-------------------------------------|
| `scripts/ids_feature_contract.py` | Strict 72-feature schema contract, alias handling, numeric coercion, quarantine result types | Closest local precedent for adapter-stage mapping, validation, and quarantine semantics |
| `scripts/ids_realtime_pipeline.py` | JSONL runtime that consumes structured records and emits alerts/quarantine | Immediate downstream consumer for the adapter output |
| `scripts/ids_inference.py` | Bundle loading and batch scoring | Confirms downstream runtime expects already-aligned model features |
| `docs/ids_realtime_pipeline_architecture.md` | Runtime boundary documentation | Defines where the adapter must stop and the runtime must start |
| `scripts/preprocess_iot_diad.py` | Dataset-side quarantine and schema consistency pipeline | Best local precedent for quarantine-first hygiene and manifest/report patterns |

### Feature fit

The new adapter sits one layer upstream of the runtime that was just built:

`upstream structured record -> adapter -> ids_realtime_pipeline.py -> ids_inference.py -> alert/quarantine outputs`

This is a new component, but it lands inside an existing script-first Python pipeline rather than a service framework or broker topology.

---

## 2. Existing Patterns

### Pattern A: Strict schema contracts, not best-effort mapping

Observed in `scripts/ids_feature_contract.py`:
- explicit one-to-one alias map only
- missing required features quarantine the record
- non-numeric required features quarantine the record
- passthrough metadata is preserved but excluded from model scoring

Implication for adapter:
- adapter profiles should stay explicit and versioned
- profile mapping must fail to quarantine, not silently coerce semantics

### Pattern B: JSONL-friendly pipeline boundaries

Observed in `scripts/ids_realtime_pipeline.py`:
- accepts either `stdin` or file input
- writes JSONL outputs incrementally
- separates valid scoring path from malformed input path

Implication for adapter:
- adapter CLI should follow the same `stdin/stdout or file-path` operational shape
- adapter outputs should stay easy to pipe directly into the realtime runtime

### Pattern C: Quarantine-first hygiene

Observed in `scripts/preprocess_iot_diad.py`:
- malformed source inputs are quarantined instead of patched
- schema mismatch becomes a first-class manifest/output, not just a log line

Implication for adapter:
- adapter-stage errors need their own stable quarantine contract
- quarantine records should be inspectable as data, not only printed to stderr

---

## 3. Technical Constraints

### Runtime / dependency constraints

- Repo appears to be a lightweight Python script project with no `pyproject.toml`, `requirements.txt`, or environment file checked in at root.
- Existing IDS scripts already depend on `pandas`, `catboost`, and stdlib facilities.
- The adapter should avoid introducing new external dependencies if possible.

### Build / verification constraints

- Current local verification command is `pytest -q`.
- Existing IDS runtime and contract tests already live under `tests/`.
- New adapter work should extend this path rather than introducing a second test harness.

### Contract constraints from locked decisions

- Input family must remain `CICFlowMeter-like structured records`.
- Output must be direct `72`-feature records, not an intermediate schema.
- Profiles are explicit, not auto-detected.
- Transformation is limited to field mapping, rename, coercion, and validation.

These constraints rule out:
- generic schema engines
- free-form config-driven mappers
- derived-feature calculators
- packet-processing dependencies

---

## 4. Concrete Planning Implications

### Primary profile candidate

The strongest v1 primary profile is a flat CICFlowMeter-like record that uses mostly canonical feature names, with a small explicit alias set matching current precedent in `ids_feature_contract.py`:
- examples already present: `SrcPort`, `DstPort`, `FlowDuration`, `Tot Fwd Pkts`, `Tot Bwd Pkts`, `TotLen Fwd Pkts`, `Pkt Len Min/Max/Mean/Std/Var`, `Init Fwd Win Byts`, `Init Bwd Win Byts`

This gives planning a concrete baseline without inventing a brand new source family.

### Secondary profile candidate

The most practical secondary profile is another flat CICFlowMeter-like record that:
- keeps the same flow-feature semantics
- changes a few field names or envelope metadata keys
- proves profile switching and metadata normalization without becoming a semantic translator

Example difference class:
- `trace_id` vs `flow_id`
- `sensor_id` vs `collector_id`
- alternate timestamp/source envelope field names

### File layout precedent

The repo favors single-purpose scripts under `scripts/`, with tests in `tests/` and architecture docs in `docs/`.

That makes the most natural v1 layout:
- one new adapter module/script under `scripts/`
- one focused adapter test file under `tests/`
- one architecture/contract doc under `docs/`
- optional lightweight demo fixture under `artifacts/demo/`

---

## 5. Open Technical Questions for Synthesis

- Should the adapter core and CLI live in one file or two? The repo leans toward one-file script entrypoints, but the feature wants a reusable library core.
- Should the adapter reuse `FlowFeatureContract` directly after profile normalization, or should it define an adapter-stage contract object and then delegate into `FlowFeatureContract` for final canonical validation?
- How tightly should adapter quarantine mirror runtime quarantine versus staying clearly stage-specific?

---

## 6. Summary

**What we have**:
- a strict 72-feature contract
- a working realtime JSONL runtime
- a clear quarantine-first precedent
- a script-first Python repo with pytest-based verification

**What we need**:
- a narrow adapter layer that normalizes one primary and one secondary CICFlowMeter-like source profile into direct model-ready records
- a dedicated adapter-stage quarantine stream
- a CLI shape that fits both pipes and file-based demos

**What planning should optimize for**:
- minimal semantic drift
- explicit profile/version boundaries
- reuse of current contract/runtime code
- no new dependency or framework surface unless unavoidable
