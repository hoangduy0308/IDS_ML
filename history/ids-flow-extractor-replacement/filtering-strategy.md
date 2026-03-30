# Information Filtering Strategy

## Purpose

This artifact defines what information must stay in extractor output, what can be normalized by the adapter layer, and what should be treated as legacy shell residue.

The goal is to preserve model-serving correctness first, per `D2` and `D3`.

## Tiered Feature Table

| Tier | What belongs here | Current examples | Why it stays here | Execution rule |
|---|---|---|---|---|
| `must-have` | Information required to satisfy the active 72-feature model bundle and preserve scoring correctness | All 72 canonical features in `artifacts/final_model/catboost_full_data_v1/feature_columns.json`, including ports/protocol, duration, packet-count and length metrics, IAT/timing metrics, flag counts, header/segment metrics, bulk metrics, subflow metrics, window bytes, and active/idle metrics | `FlowFeatureContract` and `RealtimePipelineRunner` treat these as the production scoring boundary | Production extractor paths must still deliver all 72 semantics. Any subset output is spike-only evidence until validating approves otherwise. |
| `adapter-recoverable` | Information that can arrive under profile-specific names or observability fields and be normalized before scoring | `SrcPort -> Src Port`, `DstPort -> Dst Port`, `FlowDuration -> Flow Duration`, primary/secondary metadata aliases, `flow_family`, `transport_family`, `capture_mode` | The adapter already owns explicit profile mappings, metadata normalization, and controlled extras | Keep this logic explicit in adapter profiles. Do not invent hidden fallback or silent feature synthesis. |
| `non-critical/legacy` | Shell and packaging details that are real today but are not the deepest model-facing contract | `Cmd`, `_Flow.csv`, CICFlowMeter brand wording, Java path, `jnetpcap` path | Bridge defaults and live preflight enforce them today, but the model runtime does not score on them directly | They may change only through explicit bridge/preflight/stack migration work with regression coverage. |

## What Must Stay In Extractor Output

- Enough per-flow data to produce the full 72-feature bundle semantics from closed-window pcaps.
- Stable record boundaries so the adapter sees one coherent flow record at a time.
- Deterministic numeric values for the model-facing features once adaptation completes.

If a candidate extractor cannot supply those semantics, the safe outcome is not "best effort"; it is a blocked path or a validating-gated retraining decision.

## What Can Move Into Adapter Normalization

- Source key spelling differences between extractor families
- Profile-specific metadata aliases
- Controlled extras that matter for observability but not scoring
- Explicit profile selection between known accepted source surfaces

The adapter is allowed to normalize naming and metadata. It is not allowed to invent missing model features, silently downgrade the 72-feature boundary, or accept arbitrary schemas.

## What To Treat As Legacy Shell Residue

- The exact legacy wrapper name
- The exact output filename suffix
- Brand-specific wording about CICFlowMeter
- Live packaging assumptions that belong to preflight rather than scoring

These details should not drive the replacement design unless a test or runtime gate proves they are still enforced on the path being changed.

## Guardrails For Later Beads

- Keep the tier-1 boundary on the active bundle's 72 features until validating explicitly approves a different production contract.
- Prefer explicit adapter-profile work over widening the runtime contract.
- Do not move shell naming details into the must-have tier.
- Treat any proposal to drop features, synthesize missing values, or bypass activation-record bundle loading as a contract change that needs validating, not a local implementation detail.
