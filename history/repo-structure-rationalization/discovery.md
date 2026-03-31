# Discovery Report: Repo Structure Rationalization

**Date**: 2026-03-30
**Feature**: `repo-structure-rationalization`
**CONTEXT.md reference**: `history/repo-structure-rationalization/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md` - keep exact-path preflight and deployment contracts explicit for Linux services instead of smearing them into generic runtime code.
- `history/learnings/critical-patterns.md` - keep production model selection on one activation contract; repo reorganization must not re-open split bundle/model/schema overrides.
- `history/learnings/critical-patterns.md` - keep service entrypoints wired to the real app factory; wrapper files are acceptable only if they remain thin and canonical.
- `history/learnings/critical-patterns.md` - split runtime verification from mutation/maintenance flows for persistent services and operational CLIs.
- `history/learnings/critical-patterns.md` - validating must reject overlapping write scopes and unspiked high-risk assumptions before execution.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | operator-console service topology | Server entrypoints must stay wired to the canonical app factory; a refactor cannot leave a shadow bootstrap surface behind. | high |
| `history/learnings/20260329-operator-console-production-hardening.md` | operator-console runtime vs admin CLI | Runtime verify-only paths and operator mutation paths should stay separate in both layout and ownership. | high |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | bundle lifecycle and activation contract | Shared/core extraction must preserve the single activation-record contract instead of scattering model config across multiple package seams. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | live sensor deployment and preflight | Host-service dependencies should remain explicit through config + preflight seams rather than implicit shell/path coupling hidden in business logic. | high |

---

## Agent A: Architecture Snapshot

> Source: file tree analysis, import graph, architecture docs

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts/ids_live_sensor.py` + related runtime scripts | live capture, extractor bridge, runtime scoring, sink orchestration | `scripts/ids_live_sensor.py`, `scripts/ids_live_capture.py`, `scripts/ids_live_flow_bridge.py`, `scripts/ids_live_sensor_sinks.py` |
| `scripts/ids_realtime_pipeline.py` + `scripts/ids_feature_contract.py` | model-facing validation and realtime inference | `scripts/ids_realtime_pipeline.py`, `scripts/ids_feature_contract.py`, `scripts/ids_inference.py` |
| `scripts/ids_record_adapter.py` + extractor scripts | normalization between extractor-family rows and canonical 72-feature runtime contract | `scripts/ids_record_adapter.py`, `scripts/ids_offline_window_extractor.py`, `scripts/ids_offline_window_serializer.py` |
| `scripts/ids_model_bundle*.py` | bundle packaging, activation verification, promotion lifecycle | `scripts/ids_model_bundle.py`, `scripts/ids_model_bundle_manage.py`, `scripts/package_final_model.py` |
| `scripts/ids_operator_console/` | operator web app, persistence, notifications, reporting, auth | `scripts/ids_operator_console/__init__.py`, `scripts/ids_operator_console/web.py`, `scripts/ids_operator_console/db.py`, `scripts/ids_operator_console/ops.py` |
| top-level operator/stack entrypoints | runtime wrappers and same-host orchestration | `scripts/ids_operator_console_server.py`, `scripts/ids_operator_console_manage.py`, `scripts/ids_operator_console_preflight.py`, `scripts/ids_same_host_stack.py`, `scripts/ids_same_host_stack_manage.py` |
| training and experiment scripts | preprocessing, benchmark staging, tuning, training, threshold work | `scripts/preprocess_iot_diad.py`, `scripts/stage_kaggle_*.py`, `scripts/train_iot_diad_binary.py`, `scripts/tune_top_models.py`, `scripts/posttrain_threshold_analysis.py` |

### Entry Points

- **Batch inference**: `python -m scripts.ids_inference`
- **Live sensor service**: `python -m scripts.ids_live_sensor`
- **Operator web service**: `scripts/ids_operator_console_server.py`
- **Operator admin / worker CLI**: `scripts/ids_operator_console_manage.py`
- **Model lifecycle CLI**: `scripts/ids_model_bundle_manage.py`
- **Same-host stack CLI**: `scripts/ids_same_host_stack_manage.py`
- **Training / experiment CLIs**: top-level `scripts/preprocess_iot_diad.py`, `scripts/train_iot_diad_binary.py`, `scripts/tune_top_models.py`, `scripts/stage_kaggle_*.py`

### Key Files to Model After

- `scripts/ids_operator_console/` - demonstrates that a real domain package already works in this repo and supports templates/static assets cleanly.
- `scripts/ids_operator_console_server.py` - demonstrates the desired phase-1 wrapper shape: thin entrypoint delegating to a package-owned app factory.
- `scripts/ids_operator_console_manage.py` - demonstrates a dedicated operator/maintenance CLI separate from runtime serving.
- `scripts/ids_same_host_stack.py` - demonstrates cross-domain orchestration that should remain distinct from the runtime modules it coordinates.

---

## Agent B: Pattern Search

> Source: import search, direct file reading, architecture docs

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| package-owned runtime surface with thin server wrapper | `scripts/ids_operator_console/` + `scripts/ids_operator_console_server.py` | domain package + thin entrypoint | Yes |
| explicit admin/mutation CLI split from runtime | `scripts/ids_operator_console_manage.py` | maintenance CLI separate from web runtime | Yes |
| orchestrator over owned subsystems | `scripts/ids_same_host_stack.py` | stack-level wrapper over live sensor + console + bundle owners | Yes |
| shared contract reused by runtime and tests | `scripts/ids_feature_contract.py`, `scripts/ids_model_bundle.py` | canonical contract module imported across runtime/test surfaces | Yes |
| domain-adjacent serializer/helper split | `scripts/ids_offline_window_extractor.py`, `scripts/ids_offline_window_serializer.py` | logic module plus serialization helper | Yes |

### Reusable Utilities

- **Feature/schema contract**: `scripts/ids_feature_contract.py` - canonical 72-feature validation boundary; should remain a first-class shared contract seam.
- **Bundle activation logic**: `scripts/ids_model_bundle.py` - production configuration contract shared by live runtime and management tooling.
- **Operator config loader**: `scripts/ids_operator_console/config.py` - example of centralizing runtime/deploy config inside one domain package.
- **Operator health/reporting/ops split**: `scripts/ids_operator_console/health.py`, `scripts/ids_operator_console/reporting.py`, `scripts/ids_operator_console/ops.py` - evidence that domain-internal submodules already scale better than one flat script.

### Naming Conventions

- Production-path Python modules currently use `ids_<domain>.py` at the script layer.
- Domain package naming already exists for `scripts.ids_operator_console`.
- Tests are named `tests/test_<script-or-subsystem>.py` and mostly mirror script entrypoints rather than package ownership.
- Docs use architecture/operations-oriented filenames such as `docs/ids_live_sensor_architecture.md` and `docs/ids_same_host_stack_operations.md`.

---

## Agent C: Constraints Analysis

> Source: `requirements.txt`, `README.md`, architecture/operations docs, import graph

### Runtime & Framework

- **Python version**: `3.11.x` in `README.md`; `requirements.txt` header tested on `Python 3.11.9`
- **Language/runtime**: Python only for repo-owned code
- **Web framework**: FastAPI `0.115.12`, Starlette `0.46.2`, Uvicorn `0.34.0`
- **ML/runtime stack**: pandas `3.0.1`, scikit-learn `1.6.1`, catboost `1.2.10`

### Existing Dependencies (Relevant to This Feature)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | `0.115.12` | operator console web runtime |
| `uvicorn` | `0.34.0` | web service entrypoint |
| `jinja2` | `3.1.6` | server-rendered operator UI |
| `pandas` | `3.0.1` | batch/realtime frame handling |
| `catboost` | `1.2.10` | inference model runtime |
| `pytest` | `8.3.5` | regression test suite |

### New Dependencies Needed

No new third-party dependencies are required to plan or execute this repo-structure refactor. The feature is structural, not library-driven.

### Build / Quality Requirements

```bash
# Existing practical quality gates visible in repo docs and recent STATE history
python -m pytest tests/test_ids_inference.py tests/test_ids_realtime_pipeline.py tests/test_ids_record_adapter.py -q
python -m pytest tests/test_ids_live_sensor.py tests/test_ids_live_flow_bridge.py tests/test_ids_live_sensor_preflight.py tests/test_ids_same_host_stack_manage.py -q
python -m pytest tests/test_ids_operator_console_web.py tests/test_ids_operator_console_ops.py tests/test_ids_operator_console_preflight.py -q
```

### Structural Constraints

- `scripts/` currently contains 29 top-level Python files, mixing product runtime, lifecycle management, orchestration, and experiment/training code in one zone.
- `tests/` currently contains 29 top-level test files and does not mirror package ownership yet.
- `scripts/ids_operator_console/` is the only real subpackage under `scripts/`; the rest of the runtime is still mostly flat.
- At least 7 runtime/management entrypoints still patch import behavior with `if __package__ in (None, ""):`, which means package-native imports are not yet fully stabilized.
- No `pyproject.toml`, `setup.cfg`, `setup.py`, `tox.ini`, `mypy.ini`, or `.ruff.toml` was found, so the repo currently lacks a stronger packaging/lint/typecheck spine to lean on during moves.
- Same-host deployment contracts in `deploy/` and `docs/ids_same_host_stack_operations.md` hard-code current script entrypoints, so phase 1 must preserve those seams or provide exact compatibility wrappers.

### Database / Storage / Artifact Boundaries

- Production runtime boundaries already exist around:
  - activation record + bundle manifests
  - local JSONL sensor outputs
  - operator console SQLite database
- Experiment/training paths rely on `artifacts/`, staged Kaggle outputs, and dataset-prep flows that should remain outside the production package tree.

---

## Agent D: External Research

> Source: skipped intentionally
> Guided by locked decisions in CONTEXT.md - not generic research

No external research was needed. This feature is a repo-internal structural refactor that should build on existing Python/runtime patterns already in the codebase.

### Known Gotchas / Anti-Patterns

- **Anti-pattern**: turning `shared/core` into a bucket for unrelated leftovers
  - Why it matters: it recreates the current ambiguity under a new directory name and breaks D9.
  - How to avoid: admit only real cross-domain contracts, schemas, config primitives, and narrow utilities.

- **Anti-pattern**: moving runtime modules without preserving thin compatibility entrypoints
  - Why it matters: `deploy/` artifacts and operator runbooks currently point at `scripts.*` surfaces directly.
  - How to avoid: keep wrappers stable in phase 1 and move implementation behind them first.

- **Anti-pattern**: merging runtime-serving code and mutation/maintenance code into the same package surface
  - Why it matters: prior learnings show this hides readiness and production-hardening defects.
  - How to avoid: keep runtime, preflight, orchestration, and admin/manage seams explicit in both code layout and bead scopes.

---

## Open Questions

> Items that were not resolvable through research alone.
> These will be raised to the synthesis step in Phase 2.

- [ ] What exact top-level package names should replace or sit behind the current `scripts.*` runtime surfaces without introducing circular imports?
- [ ] Should phase 1 create a new package root outside `scripts/`, or should it first convert `scripts/` into a clearer package tree while preserving `python -m scripts.*` compatibility?
- [ ] What is the smallest safe migration sequence that improves structure early without forcing a repo-wide test move in the first bead?

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a Python repo with clear product/runtime concepts and good doc coverage, but most of the implementation still lives in a flat `scripts/` surface. The strongest exception is `scripts/ids_operator_console/`, which already behaves like a real package and shows a healthier internal split.

**What we need**: a hybrid structure that separates production-path runtime/console/core code from experiment/training/history paths, preserves current entrypoints in phase 1, and gives tests/docs a migration target that mirrors ownership instead of script filenames.

**Key constraints from research**:
- deployment and same-host operations still bind directly to current `scripts.*` entrypoints, so wrappers or compatibility seams are mandatory in phase 1
- the repo lacks a stronger packaging/typecheck spine, so moves must lean on explicit test slices and narrow bead scopes rather than a single global build gate
- shared contracts such as feature schema, bundle activation, and preflight/config surfaces must remain explicit and not be diluted by the reorg

**Institutional warnings to honor**:
- keep runtime entrypoints wired to canonical app/service factories
- keep runtime verify-only paths separate from operator mutation paths
- keep production bundle selection on one activation contract
- keep host-service preflight/deploy seams explicit instead of hiding them inside generic runtime code
