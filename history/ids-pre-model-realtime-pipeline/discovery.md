# Discovery Report: IDS Pre-Model Realtime Pipeline

**Date**: 2026-03-27
**Feature**: `ids-pre-model-realtime-pipeline`
**CONTEXT.md reference**: `history/ids-pre-model-realtime-pipeline/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- None applicable. `history/learnings/critical-patterns.md` does not exist in this workspace.

### Domain-Specific Learnings

No prior learnings for this domain.

---

## Agent A: Architecture Snapshot

> Source: file tree analysis, local docs/scripts/tests

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts/` | All executable pipeline logic lives here as Python CLIs and reusable script modules. | `scripts/ids_inference.py`, `scripts/preprocess_iot_diad.py`, `scripts/package_final_model.py` |
| `tests/` | Regression coverage for script behavior. | `tests/test_ids_inference.py` |
| `docs/` | Architecture, experiment state, and deployment-facing narrative. | `docs/ids_inference_architecture.md`, `docs/final_model_bundle.md`, `docs/experiment_progress_checkpoint.md` |
| `artifacts/final_model/catboost_full_data_v1/` | Frozen deployment bundle for the chosen model. | `model_bundle.json`, `feature_columns.json`, `model.cbm` |
| `artifacts/cic_iot_diad_2024_binary/manifests/` | Training-time frozen schema and cleaning metadata. | `feature_columns.json`, `cleaning_report.json`, `quarantine_manifest.csv` |
| `CIC-IoT-DIAD-2024/Anomaly Detection - Flow Based features/` | Dataset-local reference for the original flow-feature extraction semantics. | `README.txt` |

### Entry Points

- **CLI inference**: `F:/Work/IDS_ML_New/scripts/ids_inference.py`
- **CLI preprocessing**: `F:/Work/IDS_ML_New/scripts/preprocess_iot_diad.py`
- **CLI bundle packaging**: `F:/Work/IDS_ML_New/scripts/package_final_model.py`
- **Tests**: `F:/Work/IDS_ML_New/tests/test_ids_inference.py`
- **No existing service/runtime entry point**: there is currently no daemon, API server, stream consumer, or queue worker in the repo.

### Key Files to Model After

- `F:/Work/IDS_ML_New/scripts/ids_inference.py` — model loading, frozen-schema alignment, and batch scoring pattern to reuse rather than replace.
- `F:/Work/IDS_ML_New/scripts/preprocess_iot_diad.py` — strict schema hygiene, quarantine-first error handling, and manifest-writing pattern.
- `F:/Work/IDS_ML_New/tests/test_ids_inference.py` — current testing style for importing script modules from `scripts/` and validating behavior with narrow unit tests.
- `F:/Work/IDS_ML_New/docs/ids_inference_architecture.md` — already documents the intended `feature extraction -> schema alignment -> inference -> alert` flow and should be extended, not contradicted.

---

## Agent B: Pattern Search

> Source: grep/search, direct file reads

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Batch model scoring from frozen schema | `F:/Work/IDS_ML_New/scripts/ids_inference.py` | Config dataclass + schema load + `pandas` alignment + CatBoost scoring | Yes |
| Quarantine of malformed source inputs | `F:/Work/IDS_ML_New/scripts/preprocess_iot_diad.py` | Validate early, quarantine bad inputs, continue pipeline | Yes |
| Frozen feature schema lookup | `F:/Work/IDS_ML_New/scripts/train_iot_diad_binary.py`, `F:/Work/IDS_ML_New/scripts/posttrain_threshold_analysis.py`, `F:/Work/IDS_ML_New/scripts/ids_inference.py` | Small `read_json` helpers + load `feature_columns.json` | Yes |
| Bundle-driven model configuration | `F:/Work/IDS_ML_New/scripts/ids_inference.py`, `F:/Work/IDS_ML_New/scripts/package_final_model.py` | Versioned bundle config with threshold and labels | Yes |

### Reusable Utilities

- **Validation/alignment**: `F:/Work/IDS_ML_New/scripts/ids_inference.py` — `load_feature_columns`, `IDSModelConfig`, and `IDSInferencer.align_features`.
- **Schema hygiene / quarantine semantics**: `F:/Work/IDS_ML_New/scripts/preprocess_iot_diad.py` — `validate_file`, `sanitize_numeric`, and quarantine manifests.
- **Bundle metadata**: `F:/Work/IDS_ML_New/scripts/package_final_model.py` — existing source of truth for threshold, label names, and artifact locations.
- **Tests**: `F:/Work/IDS_ML_New/tests/test_ids_inference.py` — current unit tests prove CLI helper modules can be tested without invoking the full model artifact.

### Naming Conventions

- Script modules: `snake_case.py` under `scripts/`
- Config/state carriers: small `@dataclass` types when configuration needs to be explicit
- CLI shape: `argparse` with local `parse_args()` and `main()`
- Output pattern: file-based outputs (`.csv`, `.parquet`, `.json`) with explicit summary JSON printed to stdout
- Tests: `tests/test_<script_or_feature>.py`

---

## Agent C: Constraints Analysis

> Source: local environment, script imports, CLI/tool inspection

### Runtime & Framework

- **Python version**: `3.11.9`
- **Runtime**: Python CLI/scripts, not a web framework or message consumer framework
- **Test runner**: `pytest 8.3.5`
- **Issue tracker / beads tool**: `br.exe` is installed and available in the workspace

### Existing Dependencies (Relevant to This Feature)

| Package | Version | Purpose |
|---------|---------|---------|
| `pandas` | `3.0.1` | DataFrame alignment, batch assembly, output writing |
| `numpy` | `2.4.2` | Numeric coercion and array handling |
| `pyarrow` | `22.0.0` | Parquet IO used throughout the dataset pipeline |
| `catboost` | `1.2.10` | Final deployed model runtime |
| `scikit-learn` | `1.6.1` | Existing ML experimentation utilities and metrics |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None preferred for v1 | The repo already has enough to implement a script-based realtime prototype using structured JSONL/file/pipe inputs | LOW |

### Build / Quality Requirements

```bash
# Current verifiable quality gates in this repo:
pytest F:\Work\IDS_ML_New\tests\test_ids_inference.py -q

# For the new feature, planning should preserve this style:
# - unit tests for contract/alignment/quarantine behavior
# - a targeted dry-run that feeds structured flow events into the new runtime path
```

### Storage / Output Constraints

- Existing codebase strongly favors filesystem sinks (`json`, `csv`, `parquet`) over brokers or service databases.
- There is no existing queue, broker, API, or persistent online store to build on.
- The simplest v1 “realtime” surface that matches the current repo is a structured stream/file contract such as JSON Lines rather than introducing Kafka, Redis Streams, or a web server.

---

## Agent D: External Research

> Source: intentionally skipped

### Library Documentation

No external research performed. The planned v1 approach can be built on existing in-repo patterns and currently installed Python packages.

### Community Patterns

No external pattern research performed because CONTEXT.md does not require a new library, protocol, or vendor integration for v1.

### Known Gotchas / Anti-Patterns

- **Gotcha**: upstream flow collectors may emit CICFlowMeter-like fields with slightly different names or omit fields that the trained model expects.
  - Why it matters: the model contract is frozen at exactly `72` feature names; silent best-effort mapping would create deployment drift.
  - How to avoid: make alias mapping explicit, versioned, and fail-to-quarantine instead of auto-filling missing model features.

- **Anti-pattern**: combining raw packet capture, flow extraction, schema adaptation, and model inference into one new service.
  - Common mistake: trying to “finish the whole IDS” in one component.
  - Correct approach: keep upstream flow extraction out of scope and only implement the post-extraction contract and runtime layer in this phase.

---

## Open Questions

> Items that were not resolvable through research alone.
> These will be raised to the synthesis step in Phase 2.

- [ ] Should the first runtime interface be `stdin`/file-based JSONL, a watched directory, or a local socket? The repo currently favors file/CLI patterns, but the exact envelope still needs a v1 choice.
- [ ] Which non-model metadata fields should survive alongside the `72` model features in alert/quarantine outputs? This affects traceability but must not leak into inference.
- [ ] What threshold should raise a higher-order `schema anomaly` alert when too many records are quarantined in a short window?

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a stable Python script pipeline with a frozen CatBoost bundle, strict `72`-feature batch inference in `ids_inference.py`, and strong schema/quarantine precedent in `preprocess_iot_diad.py`.

**What we need**: a thin realtime runtime layer that accepts structured flow events, applies explicit schema adaptation and record-level quarantine, reuses the existing inferencer, and emits alert/quarantine outputs without introducing raw packet handling or external infrastructure.

**Key constraints from research**:
- The feature should stay inside the current Python/script idiom and avoid unnecessary new dependencies.
- The `72`-feature contract is fixed and must be enforced exactly; aliasing can adapt names but must never invent missing model features.
- There is no existing service or queue framework in the repo, so the v1 runtime should use a minimal structured stream/file contract that is easy to demo and test locally.

**Institutional warnings to honor**:
- No prior institutional learnings for this domain.
