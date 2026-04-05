# Discovery Report: Two-Stage Runtime Family Contract

**Date**: 2026-04-05
**Feature**: `ids-multiclass-two-stage-runtime-contract`
**CONTEXT.md reference**: `history/ids-multiclass-two-stage-runtime-contract/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md` - production model selection must stay on one activation contract, not on split runtime overrides.
- `history/learnings/critical-patterns.md` - daemon/runtime features must fail closed on broken contracts instead of degrading silently.
- `history/learnings/critical-patterns.md` - preflight approval and later execution must share the same validated contract path.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | bundle lifecycle | Production cutover must resolve one versioned active bundle and keep failed promotion from disturbing the last known-good state. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | live sensor runtime | Long-running runtime paths need fail-closed preflight and durable, explicit runtime evidence rather than hidden fallback behavior. | high |
| `history/learnings/20260403-packaging-contract-proof.md` | packaging / bootstrap | Validation and execution must stay bound to the same contract; wrapper and bootstrap seams need explicit tests. | high |
| `history/learnings/20260331-repo-structure-wrapper-contracts.md` | wrappers / compatibility | Compatibility wrappers are real contracts and need direct smoke coverage when canonical modules change. | medium |

---

## Agent A: Architecture Snapshot

> Source: runtime/bundle file-tree analysis and targeted reads

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `ids.core` | Bundle manifest contract and activation record resolution | `ids/core/model_bundle.py`, `ids/core/model_bundle_activation.py`, `ids/core/path_defaults.py` |
| `ids.runtime` | Batch and realtime scoring entrypoints | `ids/runtime/inference.py`, `ids/runtime/realtime_pipeline.py`, `ids/runtime/live_sensor.py`, `ids/runtime/live_sensor_health.py` |
| `ids.ops` | Activation lifecycle and preflight checks | `ids/ops/model_bundle_lifecycle.py`, `ids/ops/model_bundle_manage.py`, `ids/ops/live_sensor_preflight.py` |
| `ml_pipeline.training` | Stage-2 model training and offline evaluation outputs | `ml_pipeline/training/train_iot_diad_family_classifier.py`, `ml_pipeline/training/evaluate_iot_diad_two_stage_gated.py` |
| `ml_pipeline.packaging` | Production bundle assembly | `ml_pipeline/packaging/package_final_model.py` |

### Entry Points

- **CLI / batch inference**: `ids.runtime.inference:main`
- **Realtime JSONL scoring**: `ids.runtime.realtime_pipeline:main`
- **Live sensor daemon**: `ids.runtime.live_sensor:main`
- **Preflight**: `ids.ops.live_sensor_preflight:main`
- **Bundle lifecycle CLI**: `ids.ops.model_bundle_manage:main`

### Key Files to Model After

- `ids/runtime/inference.py` - demonstrates the current canonical binary scoring contract and how runtime resolves an active bundle without allowing split production overrides.
- `ids/core/model_bundle.py` - demonstrates how compatibility metadata, threshold binding, and fail-closed validation are enforced today.
- `ids/ops/model_bundle_lifecycle.py` - demonstrates how activate/rollback/status all flow through one activation record and preserve the previous known-good bundle.
- `ids/ops/live_sensor_preflight.py` - demonstrates the existing verify-only startup gate that resolves the active bundle before the daemon runs.
- `tests/ops/test_ids_model_bundle_manage.py` - demonstrates the failure mode the new composite contract must preserve: a bad candidate must not disturb the active bundle.

---

## Agent B: Pattern Search

> Source: targeted grep plus runtime/ops tests

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Binary inference contract | `ids/runtime/inference.py` | Config dataclass + inferencer + CLI entrypoint | Yes |
| Realtime prediction event emission | `ids/runtime/realtime_pipeline.py` | Buffer -> inferencer -> JSONL event payload | Yes |
| Active bundle resolution | `ids/core/model_bundle_activation.py` | Versioned activation record pointing at a bundle root | Yes |
| Promote / rollback lifecycle | `ids/ops/model_bundle_lifecycle.py` | Verify candidate, atomically write activation record, preserve previous bundle | Yes |
| Bundle contract enforcement | `ids/core/model_bundle.py` | Manifest version + compatibility block + fail-closed validation | Yes |

### Reusable Utilities

- **Activation lifecycle**: `ids/ops/model_bundle_lifecycle.py` - already provides `verify_candidate_bundle`, `promote_candidate_bundle`, and `rollback_active_bundle`.
- **Bundle status payload**: `ids/core/model_bundle_activation.py` - already exposes activation metadata to runtime health and the live sensor summary path.
- **Wrapper smoke patterns**: `tests/runtime/test_ids_runtime_wrapper_smoke.py`, `tests/ops/test_ids_model_bundle_manage.py` - useful for preserving CLI/module compatibility when canonical contracts change.
- **Stage-2 metrics source**: `artifacts/modeling/cic_iot_diad_2024_family_views/family_classifier/reports/oracle_family_eval.json` - current best checkpoint and confidence/margin evidence.

### Naming Conventions

- Runtime config objects use `*Config` dataclasses and classmethod constructors (`from_bundle`, `from_activation_path`).
- Bundle compatibility is declared under `compatibility.<block>` inside `model_bundle.json`.
- Runtime JSONL payloads use explicit flat fields like `attack_score`, `predicted_label`, `is_alert`, `threshold`.
- CLI wrappers preserve canonical module entrypoints and are pinned by targeted help-smoke tests.

---

## Agent C: Constraints Analysis

> Source: `pyproject.toml`, `requirements.txt`, runtime tests, packaging surface

### Runtime & Framework

- **Python version**: `>=3.11`
- **Runtime**: Python CLI / daemon processes
- **Language**: Python
- **Frameworks / core libs**: CatBoost, pandas, pyarrow, scikit-learn, FastAPI for adjacent console surfaces

### Existing Dependencies (Relevant to This Feature)

| Package | Version | Purpose |
|---------|---------|---------|
| `catboost` | `1.2.10` | stage-1 and stage-2 model inference |
| `pandas` | `3.0.1` | feature alignment and event frame assembly |
| `pyarrow` | `22.0.0` | report / dataset contract lineage on the ML side |
| `pytest` | `8.3.5` | runtime / ops regression coverage |

### New Dependencies Needed

No new dependencies appear necessary. The feature can be built on the existing runtime, bundle, and CatBoost surfaces.

### Build / Quality Requirements

```bash
# Practical verification surfaces already present in this repo:
pytest tests/runtime/test_ids_inference.py
pytest tests/runtime/test_ids_realtime_pipeline.py
pytest tests/ops/test_ids_live_sensor_preflight.py
pytest tests/ops/test_ids_model_bundle_manage.py
pytest tests/runtime/test_ids_live_sensor_health.py
pytest tests/runtime/test_ids_runtime_wrapper_smoke.py
```

### Contract / Operational Constraints

- The runtime currently treats the active bundle as authoritative and rejects mixed production overrides; the composite design must preserve that behavior.
- Preflight already resolves the active bundle at startup; composite validation should extend that path rather than add a second startup contract.
- Realtime payloads and batch inference outputs already have downstream consumers; new family data must be additive, not contract-breaking.
- Health and live-sensor summary code already expose active-bundle status; composite bundle visibility should reuse that path rather than invent a console-owned state store.

---

## Agent D: External Research

> Source: not required for this feature

No external research was needed. The feature is an internal contract evolution built on existing repo patterns rather than a new library or third-party integration.

---

## Open Questions

> Items that were not resolvable through research alone.
> These will be raised to the synthesis step in Phase 2.

- [ ] Should the composite bundle be represented as a new manifest version on `model_bundle.json` or as a new `compatibility.inference_contract.version` nested under the existing manifest version? - impacts migration behavior and how much existing lifecycle code must branch.
- [ ] Should stage-2 thresholds be stored as a new top-level bundle block or as compatibility metadata nested under a dedicated stage-2 contract block? - impacts how runtime and lifecycle code reuse existing validation helpers.
- [ ] Where should per-batch stage-2 runtime failures surface for CLI and daemon callers: exception from `IDSInferencer`, wrapper-specific error type, or runtime payload failure envelope? - affects how D12 becomes observable without inventing a hidden fallback path.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a clean binary production contract with one activation record, one bundle manifest, fail-closed validation, and regression coverage across batch inference, realtime pipeline, preflight, lifecycle CLI, and live sensor health.

**What we need**: a composite production contract that adds stage-2 family enrichment and abstention behavior without breaking the binary runtime shape, while remaining compatible with legacy binary bundles during rollout.

**Key constraints from research**:
- one activation contract must continue to own production model selection
- runtime and preflight must fail closed on incompatible composite bundles rather than silently degrade
- family enrichment must be additive on the output side and must reuse existing lifecycle and health surfaces

**Institutional warnings to honor**:
- do not reintroduce split runtime overrides after the activation contract already exists
- preserve the last known-good active bundle on failed promotion
- bind validation and execution to the same composite contract path and keep wrapper seams explicitly tested
