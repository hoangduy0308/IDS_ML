# Discovery Report: IDS Flow Extractor Replacement

**Date**: 2026-03-30
**Feature**: `ids-flow-extractor-replacement`
**CONTEXT.md reference**: `history/ids-flow-extractor-replacement/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md` — keep exact-path preflight contracts for Linux services; do not let live runtime depend on implicit helper discovery.
- `history/learnings/critical-patterns.md` — production model selection must stay on one activation contract; extractor work must not reopen raw production overrides for schema or threshold.
- `history/learnings/critical-patterns.md` — validation must spike HIGH-risk assumptions before swarming; this feature clearly has semantic and runtime-contract spikes.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | live sensor / extractor seam | The safe live seam is `live capture -> closed pcap window -> extractor -> adapter -> realtime pipeline`; do not assume direct live extraction. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | live sensor preflight | Service packaging is safer when preflight validates exact helper paths, NIC, bundle contract, and writable roots before the daemon loop starts. | high |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | model bundle runtime | The live runtime must resolve model + schema + threshold only through the activation record; extractor work must preserve that boundary. | high |
| `history/learnings/20260328-adapter-rollback-contract.md` | adapter file-mode publishing | Adapter output and quarantine paths are one transactional contract; any future extractor-side file outputs should respect the same fail-closed discipline. | medium |

---

## Agent A: Architecture Snapshot

> Source: file tree, docs, code entry points, tests

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts/ids_live_flow_bridge.py` | Closed-window extractor invocation and CSV-to-adapter handoff | `scripts/ids_live_flow_bridge.py`, `tests/test_ids_live_flow_bridge.py` |
| `scripts/ids_record_adapter.py` | Profile-based normalization from CICFlowMeter-like records into the 72-feature runtime boundary | `scripts/ids_record_adapter.py`, `tests/test_ids_record_adapter.py` |
| `scripts/ids_feature_contract.py` | Canonical 72-feature validation, alias normalization, passthrough extraction | `scripts/ids_feature_contract.py` |
| `scripts/ids_realtime_pipeline.py` | Runtime JSONL ingestion, quarantine, micro-batch scoring | `scripts/ids_realtime_pipeline.py`, `tests/test_ids_realtime_pipeline.py` |
| `scripts/ids_live_sensor.py` | Staged live daemon composing capture, bridge, runtime, sink | `scripts/ids_live_sensor.py`, `tests/test_ids_live_sensor.py`, `tests/test_ids_live_sensor_e2e.py` |
| `scripts/ids_live_sensor_preflight.py` | Exact-path preflight for live sensor helper binaries and bundle activation | `scripts/ids_live_sensor_preflight.py`, `tests/test_ids_live_sensor_preflight.py` |
| `scripts/ids_same_host_stack*.py` | Same-host stack orchestration and deployment contract delegation | `scripts/ids_same_host_stack.py`, `scripts/ids_same_host_stack_manage.py`, `tests/test_ids_same_host_stack_manage.py` |
| `artifacts/final_model/catboost_full_data_v1/` | Production model bundle contract | `feature_columns.json`, `model_bundle.json`, `training_summary.json` |

### Entry Points

- **Extractor bridge**: `scripts/ids_live_flow_bridge.py`
- **Adapter CLI / library**: `scripts/ids_record_adapter.py`
- **Realtime runtime**: `scripts/ids_realtime_pipeline.py`
- **Live sensor daemon**: `scripts/ids_live_sensor.py`
- **Live sensor preflight**: `scripts/ids_live_sensor_preflight.py`
- **Same-host stack CLI**: `scripts/ids_same_host_stack_manage.py`
- **Deployment unit**: `deploy/systemd/ids-live-sensor.service`
- **Canonical operator docs**: `docs/ids_live_sensor_architecture.md`, `docs/ids_live_sensor_operations.md`, `docs/ids_same_host_stack_operations.md`

### Key Files to Model After

- `scripts/ids_live_flow_bridge.py` — current extractor shell contract: `command prefix + <pcap> + <output-dir>`, expected `_Flow.csv`, CSV header read, adapter handoff.
- `scripts/ids_record_adapter.py` — existing normalization layer with explicit profiles, no defaulting/imputation, and canonical metadata ownership.
- `scripts/ids_feature_contract.py` — strongest model-facing contract in the repo today: exact 72 canonical features, numeric only, passthrough preserved but excluded from scoring.
- `tests/test_ids_live_flow_bridge.py` — golden behavioral expectations for missing output, invalid CSV, adapter quarantine, and profile mismatch.
- `tests/test_ids_live_sensor_preflight.py` — hard preflight contract for `dumpcap`, `java`, extractor binary, `jnetpcap`, activation record, and writable output parents.

---

## Agent B: Pattern Search

> Source: docs, tests, symbol/regex search, fixture inspection

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Primary CICFlowMeter-like normalization | `scripts/ids_record_adapter.py` | Mixed same-name + alias override map into canonical 72-feature record | Yes |
| Secondary CICFlowMeter-like normalization | `scripts/ids_record_adapter.py` | Closed profile-specific alias map with different metadata envelope keys | Yes |
| Extractor window orchestration | `scripts/ids_live_flow_bridge.py` | Run external tool on closed pcap, require one CSV output, adapt each row | Yes |
| Runtime scoring boundary | `scripts/ids_realtime_pipeline.py` | Validate JSONL record per record, quarantine bad records, only score canonical features | Yes |
| Same-host preflight delegation | `scripts/ids_same_host_stack.py` | Stack CLI builds `LiveSensorPreflightConfig` and delegates exact component preflight | Yes |

### Reusable Utilities

- **Canonical feature validation**: `scripts/ids_feature_contract.py` — enforces required feature presence, numeric coercion, alias normalization, passthrough extraction.
- **Adapter profile registry**: `scripts/ids_record_adapter.py` — explicit profile selection, fixed source-key surface, metadata ownership, controlled extras.
- **Activation contract**: `scripts/ids_model_bundle.py` and bundle artifacts — resolve live bundle through `active_bundle.json`, fail closed on incompatibility.
- **Bridge error envelope**: `scripts/ids_live_flow_bridge.py` — standard `window_stage_error` payload for extractor/output/adapter stage failures.
- **Live sink telemetry**: `scripts/ids_live_sensor.py` + sink modules — preserves quarantine/alert split and summary telemetry.

### Naming Conventions

- Adapter profiles are stable IDs: `cicflowmeter_primary_v1`, `cicflowmeter_secondary_v1`.
- Live bridge expects extractor outputs named `<pcap-stem>_Flow.csv`.
- Model-facing features use the exact canonical names from `artifacts/final_model/catboost_full_data_v1/feature_columns.json`.
- Adapter-owned metadata keys are fixed: `adapter_profile`, `source_flow_id`, `source_collector_id`, `source_timestamp`.
- Controlled passthrough extras currently standardized as `flow_family`, `transport_family`, `capture_mode`.

### Key Contract Findings

- The model-facing runtime does **not** care about CSV or CICFlowMeter branding directly. It cares that each record reaching `FlowFeatureContract` contains all 72 canonical features and that all are numeric.
- The bridge/live-sensor layer **does** currently care about the legacy shell shape:
  - default command prefix `("Cmd",)`
  - output suffix `_Flow.csv`
  - rows readable by `csv.DictReader`
  - default adapter profile `cicflowmeter_primary_v1`
- The adapter is not a generic mapper. It accepts only explicit, closed source-key surfaces and quarantines unmapped or canonical-only hybrid payloads instead of silently falling back.
- Primary and secondary fixtures confirm that current upstream records are mostly canonical-looking CICFlowMeter-style fields plus a small alias set and metadata envelope, not arbitrary schemas.

---

## Agent C: Constraints Analysis

> Source: docs, bundle artifacts, scripts, tests, deployment unit

### Runtime & Framework

- **Language/runtime**: Python 3.11.x
- **Core model runtime**: CatBoost bundle loaded through repo-local Python scripts
- **Live sensor execution model**: Linux `systemd` daemon
- **Capture model**: `dumpcap` on one NIC, closed pcap windows, staged-live pipeline

### Existing Dependencies (Relevant to This Feature)

| Package / Dependency | Purpose | Contract Status |
|----------------------|---------|-----------------|
| `dumpcap` | Live packet capture into closed windows | hard for live sensor, irrelevant for offline extractor |
| `Cmd` / CICFlowMeter command wrapper | Current extractor process contract | hard in live bridge today, potentially replaceable |
| `java` | Required by current packaged extractor path | hard in live preflight/stack today, potentially historical after replacement |
| `jnetpcap` | Native dependency expected by current extractor install | hard in live preflight/stack today, potentially historical after replacement |
| `active_bundle.json` + bundle manifest | Canonical production model/schema/threshold selection | hard and must remain |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None required at planning time | This research is repo-local and can proceed without choosing a new extractor implementation yet. | LOW |

### Build / Quality Requirements

```bash
# Existing regression surfaces that will matter for implementation beads:
python -m pytest tests/test_ids_record_adapter.py -q
python -m pytest tests/test_ids_realtime_pipeline.py -q
python -m pytest tests/test_ids_live_flow_bridge.py -q
python -m pytest tests/test_ids_live_sensor.py tests/test_ids_live_sensor_e2e.py tests/test_ids_live_sensor_preflight.py -q
python -m pytest tests/test_ids_same_host_stack_manage.py -q
```

### Deployment / Ops Constraints

- Live startup currently fails closed unless absolute paths for `dumpcap`, `java`, extractor binary, `jnetpcap`, activation record, spool dir, and output parents all validate.
- Same-host bootstrap, preflight, recover, and post-restore checks all propagate the live-sensor dependency surface through stack management commands.
- Production runtime must continue to resolve `feature_columns.json` and threshold only through the active bundle contract, not through new extractor-specific overrides.

### Contract Tiering Constraints

- **Hard model-facing inputs**: all 72 canonical features listed in `feature_columns.json`; runtime has no missing-value fill or feature synthesis path.
- **Adapter-owned passthrough**: `adapter_profile`, normalized source IDs/timestamps, controlled extras. These matter for observability but not scoring.
- **Legacy shell**: `Cmd`, `_Flow.csv`, Java, `jnetpcap`, exact CICFlowMeter field spellings. These are enforced today above the model-facing boundary, but not by the model bundle itself.

---

## Agent D: External Research

> Source: not required for this planning pass
> Guided by locked decisions in CONTEXT.md — the current task is to extract repo-local contract truth first

### Library Documentation

- No external research performed in this planning pass. The decision boundary and the requested outputs are anchored in repo-local docs, code, tests, and artifacts.

### Community Patterns

- None included. Prior repo-local planning artifacts for `ids-live-host-based-ml-ids` already capture the relevant staged-live seam insight and are sufficient for this pass.

### Known Gotchas / Anti-Patterns

- **Gotcha**: proving that a new extractor can emit *some* numeric features is not enough.
  - Why it matters: current runtime requires all 72 canonical features, and the model bundle offers no evidence that a smaller subset is acceptable in production.
  - How to avoid: classify features into tiers, but treat the full 72-feature boundary as the current hard runtime contract until validating proves a safer relaxation path.

- **Anti-pattern**: treating the current live dependency stack (`Cmd`, Java, `jnetpcap`) as if it were the same thing as the model contract.
  - Common mistake: cloning every CICFlowMeter shell assumption into the replacement extractor without first checking whether the model-facing runtime actually needs it.
  - Correct approach: preserve the closed-window staged-live seam, then separate hard model/adapter/runtime requirements from operational packaging residue.

---

## Open Questions

> Items that were not resolvable through research alone.

- [ ] Can a replacement extractor reproduce the semantics of tier-1 flow features closely enough from closed pcaps without relying on CICFlowMeter’s exact implementation? — impacts whether adapter/preflight changes are enough or retraining becomes necessary.
- [ ] Which current Java/`jnetpcap` assumptions are truly extractor-specific versus incidentally baked into same-host tooling? — impacts live deployment blast radius.
- [ ] Is there any model-artifact evidence outside the current bundle that justifies a runtime-safe subset smaller than 72 features? — planning found no such evidence in the shipped bundle.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a clean staged-live IDS pipeline whose strongest stable contract is the model-facing 72-feature boundary plus activation-record-driven bundle loading. Above that boundary, the repo currently hardcodes a CICFlowMeter-like shell: `Cmd`, `_Flow.csv`, Java, `jnetpcap`, and primary adapter profile assumptions.

**What we need**: a replacement strategy that preserves model-serving correctness and the safe closed-window seam while disentangling which legacy CICFlowMeter assumptions must remain, which can move into adapter/configuration, and which should be retired.

**Key constraints from research**:
- `FlowFeatureContract` and the bundle contract currently require all 72 canonical features and numeric coercion; there is no runtime imputation or feature synthesis path.
- The adapter is explicit and closed-surface, so any new extractor must either emit a current profile shape or be paired with an explicit new adapter profile/configurable normalization surface.
- Live sensor, systemd packaging, and same-host stack currently propagate Java/`jnetpcap`/extractor path assumptions widely, making live integration a higher-blast-radius change than offline extraction.

**Institutional warnings to honor**:
- Keep the staged-live seam on closed pcaps unless validating proves a different live boundary safe.
- Preserve exact-path preflight and single activation-record bundle selection.
- Treat semantic fidelity and deployment-contract changes as HIGH-risk spikes before execution.

---

## Addendum: CICFlowMeter Dependency Map

Bead `ids_ml_new-vii9.10` wrote the repo-backed dependency classification to `history/ids-flow-extractor-replacement/dependency-map.md`.

The short version:

- `java` and `jnetpcap` are current live-path `hard dependency` items because preflight, service wiring, stack defaults, and tests all enforce them today.
- `Cmd`, `_Flow.csv`, `cicflowmeter_primary_v1`, and CICFlowMeter-style headers are current `configurable dependency` items because the bridge/adapter already expose them as explicit config or profile surfaces.
- The real hard runtime boundary remains the activation-record bundle contract plus the 72 canonical numeric features; CICFlowMeter branding itself is not the source of truth.

## Addendum: Research Summary And D4 Drift Log

Bead `ids_ml_new-vii9.11` wrote two follow-on artifacts:

- `history/ids-flow-extractor-replacement/research-summary.md`
- `history/ids-flow-extractor-replacement/doc-code-mismatches.md`

Use them together when planning the replacement seam:

- `research-summary.md` captures the repo-backed extractor contract from docs, code, and tests.
- `doc-code-mismatches.md` records the places where docs overstate or blur the enforced contract and where `D4` requires code/tests to win.

Key downstream reminder:

- the strongest enforced boundary is still `closed pcap -> bridge -> adapter -> 72 canonical features -> active bundle runtime`
- Java, `jnetpcap`, and CICFlowMeter naming are current live-path packaging facts, but not the deepest model-facing contract
