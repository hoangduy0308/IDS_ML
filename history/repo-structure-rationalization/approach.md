# Approach: Repo Structure Rationalization

**Date**: 2026-03-30
**Feature**: `repo-structure-rationalization`
**Based on**:
- `history/repo-structure-rationalization/discovery.md`
- `history/repo-structure-rationalization/CONTEXT.md`

---

## 1. Gap Analysis

> What exists vs. what the feature requires.

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Production package spine | Mostly flat `scripts/*.py`, plus one partial package at `scripts/ids_operator_console/` | One canonical product package tree with explicit `core`, `runtime`, `console`, and `ops` seams | High |
| Compatibility entrypoints | Current `python -m scripts.*` and direct script entrypoints used by docs/deploy/tests | Thin wrappers that preserve current public surfaces while implementation moves behind them | High |
| Shared/core contracts | Cross-domain contracts exist but are scattered (`ids_feature_contract`, `ids_model_bundle`, parts of adapter/runtime config) | A narrow shared/core boundary for model/bundle/schema/config contracts only | High |
| Runtime domain layout | Live sensor, bridge, extractor, inference, sinks, and health are split across flat scripts | Coherent runtime subpackages with internal ownership and lower cross-domain coupling | High |
| Operator console layout | Good internal package already exists, but still lives under `scripts/` and is coupled to top-level wrappers | Promote console into the canonical product package tree without breaking assets, CLI, or server wiring | High |
| Ops / orchestration layout | Preflight, manage CLIs, and same-host stack are mixed near runtime code in `scripts/` | Explicit `ops` layer for preflight, lifecycle CLIs, and stack orchestration | High |
| Training / experiment zone | Preprocess, benchmark, tune, train, and packaging scripts live beside production code | Separate top-level ML workflow zone distinct from production-path code | Medium |
| Tests and docs navigation | `tests/` is flat; `docs/` mixes canonical and historical material in one directory | Domain-mirrored tests and `docs/current` vs `docs/archive` style navigation | High |

---

## 2. Recommended Approach

> Specific strategy. Not "here are options" - a concrete recommendation.

Introduce one canonical product package root named `ids/` with four subpackages: `ids/core`, `ids/runtime`, `ids/console`, and `ids/ops`. Move production-serving implementation behind that package tree in phase 1, while keeping the existing `scripts/*.py` and `python -m scripts.*` surfaces as thin compatibility wrappers that only delegate into canonical package modules. Keep training, benchmark, preprocessing, and model-packaging workflows outside that product package tree in a separate top-level zone named `ml_pipeline/`, and migrate tests/docs in lockstep after each domain move so ownership becomes visible without requiring a big-bang rewrite.

### Why This Approach

- It honors `D3` and `D8` by separating internal architecture cleanup from public-surface change; wrappers keep current deploy/runbook entrypoints stable while code moves behind them.
- It matches the strongest existing codebase precedent at `scripts/ids_operator_console/`, which already proves that package-owned implementation plus thin entrypoints works here.
- It supports `D2`, `D4`, and `D5` better than a `scripts/`-only cleanup because it creates an explicit production-path tree and an explicit experiment/history tree instead of relying on naming discipline alone.
- It applies prior learnings about runtime wiring, preflight separation, and single-contract model activation by giving `ids/core` and `ids/ops` explicit homes instead of leaving those seams diffused across flat scripts.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Canonical product code root | `ids/` umbrella package with `core`, `runtime`, `console`, `ops` subpackages | Cleaner Python import story than many top-level packages, while still honoring D4's domain split |
| Backward compatibility in phase 1 | keep `scripts/*.py` as thin wrappers only | Required by D3/D8 and by existing deploy/docs/tests that point at `scripts.*` |
| Shared code policy | only true contracts/schemas/config/path primitives may enter `ids/core` | Directly enforces D9 and avoids a junk-drawer `shared` package |
| Console placement | move current `scripts/ids_operator_console/` implementation under `ids/console/` and keep server/manage wrappers | Reuses the repo's strongest package precedent while preserving runtime contract |
| Ops placement | preflight, management CLIs, and same-host stack live under `ids/ops/` | Preserves runtime-vs-mutation separation from prior learnings |
| Training/experiment placement | move preprocessing, stage, tune, train, threshold, packaging workflows into top-level `ml_pipeline/` | Keeps product code and experimental workflow code visibly distinct |
| Test migration | move tests by domain alongside code moves; represent `unit`, `integration`, `e2e` explicitly under each domain | Honors D6 without requiring one risky all-at-once test rewrite |
| Docs migration | create canonical/current navigation separate from archived/historical material | Honors D7 and reduces reader confusion about which docs define active contracts |

---

## 3. Alternatives Considered

> What was evaluated and rejected. Important: bead workers see this and understand why the chosen approach is non-negotiable.

### Option A: Keep `scripts/` as the main code tree and only add subfolders inside it

- Description: Leave `scripts/` as the canonical home of both production and experiment code, but reorganize it internally.
- Why considered: Lowest short-term path churn and easiest way to preserve current CLIs.
- Why rejected: It fails D5 in practice because production-path and experiment-path code still share the same top-level identity. It also keeps wrapper code and implementation code mixed in the same surface, which is the ambiguity we are trying to remove.

### Option B: Big-bang rewrite of imports, entrypoints, tests, and docs in one wave

- Description: Move everything to the final package structure immediately and update all callers at once.
- Why considered: Maximally clean end state with fewer temporary wrappers.
- Why rejected: It violates D3/D8, creates a very large blast radius, and risks breaking deploy/runbook contracts before validating can spike the migration assumptions.

### Option C: Split into many peer top-level packages (`runtime/`, `console/`, `core/`, `ops/`, `ml/`)

- Description: Use several top-level domain packages instead of one product umbrella package.
- Why considered: Makes domain ownership explicit at the root.
- Why rejected: It increases top-level clutter, makes imports noisier, and gives less immediate coherence to new readers than `ids/<subdomain>` for the product path plus one separate ML workflow zone.

---

## 4. Risk Map

> Every component that is part of this feature must appear here.
> Workers use this to calibrate how carefully to proceed.

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| `ids/` product package spine + wrapper strategy | **HIGH** | Architectural change, blast radius > 5 files, affects imports and runtime entrypoints | Spike in validating: prove wrapper pattern and import resolution are safe |
| `ids/core` extraction of bundle/schema/config contracts | **HIGH** | Central contract modules are imported broadly; wrong split could reopen semantic drift | Spike in validating: confirm minimal safe core boundary |
| `ids/runtime` migration of live sensor / bridge / pipeline / extractor modules | **HIGH** | Runtime + deploy + test blast radius, multiple files, service contracts involved | Spike in validating: prove phase-1 runtime moves preserve current entrypoints |
| `ids/console` promotion from `scripts/ids_operator_console/` | **HIGH** | Existing package pattern helps, but templates/static assets and service entrypoints are sensitive | Validate package-relative asset and app-factory wiring |
| `ids/ops` migration of preflight / manage / stack orchestration | **HIGH** | Same-host deploy/runbook coupling and prior learnings about verify-vs-mutate boundaries | Validate CLI and deploy invocation compatibility |
| `ml_pipeline/` creation for training / benchmark / preprocessing | **MEDIUM** | Mostly structural and not deployment-facing, but spans many workflow scripts | Proceed with explicit wrapper/file-move map |
| Tests reorganization | **HIGH** | 29 test files, discovery/import behavior can drift during moves | Validate phased test move plan before execution |
| Docs current/archive reorganization | **MEDIUM** | Mostly content/navigation churn, but broken references can hurt onboarding and operations | Link-check / grep-driven reference verification |

### Risk Classification Reference

```
Pattern in codebase?        -> YES = LOW base
External dependency?        -> YES = HIGH
Blast radius > 5 files?     -> YES = HIGH
Otherwise                   -> MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `ids/` package spine and wrapper strategy: can the repo safely introduce a canonical package tree while preserving `scripts.*` execution surfaces in phase 1?
- `ids/core` boundary: what is the minimal set of cross-domain modules that belongs in core without creating a dumping ground or circular imports?
- `ids/runtime` migration: what migration order preserves live sensor / extractor / pipeline behavior while wrappers still point to the moved implementation?
- `ids/console` + `ids/ops` migration: how do we preserve app-factory wiring, asset loading, preflight, and manage CLI contracts during package promotion?
- tests reorganization: what sequence preserves pytest import/discovery stability while domain-mirroring the suite?

---

## 5. Proposed File Structure

> Where new files will live. Workers use this to plan their work.

```text
ids/
  core/
    __init__.py
    feature_contract.py
    model_bundle.py
    config_contracts.py         # only if truly cross-domain
  runtime/
    __init__.py
    inference.py
    realtime_pipeline.py
    live_capture.py
    live_flow_bridge.py
    live_sensor.py
    live_sensor_health.py
    live_sensor_sinks.py
    extractor/
      __init__.py
      offline_window.py
      serializer.py
    adapter/
      __init__.py
      record_adapter.py
  console/
    __init__.py
    config.py
    auth.py
    db.py
    migrations.py
    web.py
    alerts.py
    reporting.py
    notifications.py
    notification_runtime.py
    ops.py
    health.py
    static/
    templates/
  ops/
    __init__.py
    live_sensor_preflight.py
    operator_console_preflight.py
    model_bundle_manage.py
    operator_console_manage.py
    same_host_stack.py
    same_host_stack_manage.py

ml_pipeline/
  data_prep/
    preprocess_iot_diad.py
  benchmark/
    stage_kaggle_benchmark.py
    stage_kaggle_scaling.py
    stage_kaggle_tuning.py
    stage_kaggle_promotion.py
  training/
    train_iot_diad_binary.py
    tune_top_models.py
    posttrain_threshold_analysis.py
  packaging/
    package_final_model.py

scripts/
  ids_inference.py                  # thin wrapper -> ids.runtime.inference
  ids_live_sensor.py                # thin wrapper -> ids.runtime.live_sensor
  ids_operator_console_server.py    # thin wrapper -> ids.console/web app factory
  ids_operator_console_manage.py    # thin wrapper -> ids.ops.operator_console_manage
  ids_same_host_stack_manage.py     # thin wrapper -> ids.ops.same_host_stack_manage
  ...

tests/
  runtime/
    unit/
    integration/
    e2e/
  console/
    unit/
    integration/
  ops/
    integration/
  core/
    unit/
  ml/
    unit/
    integration/

docs/
  current/
    runtime/
    console/
    operations/
    model/
    ml/
  archive/
```

---

## 6. Dependency Order

> Dependency order for bead creation. This is planning guidance, not a runtime wave scheduler.

```text
Layer 1 (sequential): package spine + migration map + compatibility wrapper contract
Layer 2 (parallel): core boundary extraction and runtime domain migration design
Layer 3 (parallel): console promotion and ops package separation
Layer 4 (parallel): training/experiment zone separation, test-layout migration plan, docs current/archive migration
Layer 5 (sequential): final cross-cutting wrapper/reference cleanup
```

### Parallelizable Groups

- Group A: package spine, wrapper contract, and migration map - foundational, no parallel alternative
- Group B: runtime domain move plan and core extraction plan - can run in parallel once Group A is fixed
- Group C: console + ops migration plan - can run in parallel with Group B after Group A
- Group D: ML workflow separation, tests mirror plan, and docs navigation plan - can run after Group A while B/C mature
- Group E: final cleanup and validation alignment - depends on Groups B, C, and D

---

## 7. Institutional Learnings Applied

> From Phase 0 - how past learnings shaped this approach.

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | entrypoints must run the real app factory | phase 1 keeps thin wrappers and explicitly forbids duplicate bootstrap surfaces |
| `history/learnings/20260329-operator-console-production-hardening.md` | runtime verify-only and mutation paths must stay separate | `ids/ops` is distinct from `ids/console`, and manage/preflight stay out of runtime packages |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | production model selection stays on one activation contract | `ids/core` is defined narrowly around canonical contracts, not a generic grab bag |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | host-service preflight/deploy seams must stay explicit | preflight and stack orchestration stay in `ids/ops`, not buried inside runtime internals |
| `history/learnings/critical-patterns.md` | validation must reject overlapping write scopes and missing spikes | decomposition will isolate wrapper/core/runtime/console/docs/test work into separate beads with explicit risks |

---

## 8. Open Questions for Validating

> Items that couldn't be resolved in planning. The khuym:validating skill's plan-checker will address these.

- [ ] Does the repo need a minimal packaging spine (for example package `__init__.py` and import-path conventions only), or is a fuller Python packaging artifact also required in phase 1? - matters because the repo currently has no `pyproject.toml` or equivalent.
- [ ] What is the safest first migration slice: `ids/core` + wrappers, or console promotion first because it already has an internal package precedent? - impacts blast-radius control.
- [ ] How should pytest discovery/imports be stabilized during domain test moves without creating a long-lived dual-import mess? - impacts execution sequencing and review burden.
