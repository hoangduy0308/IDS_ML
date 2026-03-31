# Repo Structure Rationalization - Context

**Feature slug:** repo-structure-rationalization
**Date:** 2026-03-30
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature defines the decision boundary for reorganizing the entire repository into a more professional, clearer, and lower-coupling structure without jumping straight into a public-surface rewrite.

**Domain type(s):** ORGANIZE | READ | RUN

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Scope And Success Criteria
- **D1** The refactor scope is the whole repository, not only the runtime IDS slice.
  *Rationale: the user explicitly wants the repo structure itself to become clear and professional rather than patching one subsystem in isolation.*

- **D2** The target structure must balance three goals at once: clean domain separation, low runtime/deploy cross-coupling, and fast comprehension for new readers.
  *Rationale: the user chose the balanced option over optimizing only one axis.*

- **D3** The rollout must happen in two phases: stabilize internal structure first, then evaluate any public-surface or entrypoint changes.
  *Rationale: this keeps the first wave focused on architecture cleanup instead of mixing it with external contract churn.*

### Top-Level Organization Model
- **D4** Use a hybrid repository structure: stable product/operations code moves toward explicit packages for runtime, console, and shared/core concerns; training, benchmark, and data-prep remain in a separate top-level zone.
  *Rationale: the repo already contains both productized runtime paths and experiment/training paths, and they should not be forced into one uniform package shape.*

- **D5** Production-path code and experiment/history code must be separated explicitly, not just by naming convention.
  *Rationale: the current repo makes it too easy to confuse active runtime surfaces with exploratory or historical material; the user wants a more professional structure.*

### Test And Documentation Shape
- **D6** Tests should mirror the new domain/package layout while still signaling `unit`, `integration`, and `e2e` scope clearly through naming or subfolders.
  *Rationale: ownership needs to be obvious, but test depth must also remain visible to maintainers and reviewers.*

- **D7** Documentation should distinguish canonical/current references from historical or superseded material and should mirror the new system map closely enough that readers can navigate code and docs together.
  *Rationale: structure clarity is not only about code layout; doc navigation is part of the same repo-clarity problem.*

### Migration And Naming Rules
- **D8** Phase 1 should preserve current behavior and compatibility entrypoints wherever practical, using thin wrappers or compatibility seams instead of a big-bang external interface rewrite.
  *Rationale: the user approved a two-phase strategy specifically to avoid mixing internal cleanup with immediate public contract changes.*

- **D9** Shared/core modules are allowed, but only for real cross-domain contracts, schemas, config primitives, and reusable utilities; shared/core must not become a dumping ground.
  *Rationale: a vague shared bucket would recreate the same structural ambiguity under a cleaner name.*

### Agent's Discretion
- The user explicitly delegated the remaining unanswered structure choices to the agent's recommendations instead of continuing the Socratic loop question by question.
- Planning may choose the exact package names, file-move map, compatibility-wrapper strategy, and doc index layout, provided it honors D1-D9.
- Planning may decide whether an existing area should remain top-level or move under a package, but it must preserve the hard separation between production-path and experiment/history-path code.

---

## Specific Ideas & References

- The user's stated goal is to make the repository structure feel "professional" and "optimized for efficiency."
- The user chose to accept the agent's recommendations for the remaining organization choices instead of continuing interactive decision extraction.
- The structure discussion is about repository clarity and boundaries, not about changing model-selection policy, runtime scoring semantics, or the already-validated extractor contract.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `scripts/ids_live_sensor.py` - current live runtime orchestrator for capture -> bridge -> runtime pipeline -> sink; one of the clearest production-path seams.
- `scripts/ids_realtime_pipeline.py` - model-facing streaming/scoring boundary around `FlowFeatureContract` and batching; likely part of a runtime package boundary.
- `scripts/ids_record_adapter.py` - profile-driven normalization layer between extractor-family data and canonical runtime features; strong candidate for shared contract/domain placement.
- `scripts/ids_operator_console_server.py` - thin entrypoint wrapper that already delegates to a deeper package instead of keeping all logic in one script.
- `scripts/ids_operator_console/` - existing subpackage with `config`, `db`, `web`, `ops`, `notifications`, templates, and static assets; this is the repo's clearest proof that a package-first structure already fits the codebase.

### Established Patterns
- Script-centric bootstrap pattern: many top-level `scripts/*.py` modules patch `sys.path` via `if __package__ in (None, "")`, which signals that the repo still relies heavily on script-style entrypoints rather than package-native imports.
- Partial package emergence: `scripts/ids_operator_console/` already behaves like a real domain package while most other runtime areas remain flat files under `scripts/`.
- Flat test inventory: `tests/` is mostly organized as one file per current script or subsystem entrypoint rather than mirroring domain ownership.
- Dual-purpose repo surface: `scripts/` currently mixes runtime services, model-bundle management, operator tooling, offline extractors, and training/benchmark staging in one top-level zone.
- README-guided doc navigation: `README.md` already distinguishes canonical reading order from historical/superseded docs, which gives planning a starting point for a cleaner docs structure.

### Integration Points
- Current CLI surfaces such as `python -m scripts.ids_live_sensor`, `python -m scripts.ids_inference`, and other `scripts.*` entrypoints should remain stable in phase 1 unless planning proves a safer compatibility strategy.
- Runtime package planning must account for the seam spanning `ids_live_sensor`, `ids_live_flow_bridge`, `ids_offline_window_extractor`, `ids_record_adapter`, `ids_realtime_pipeline`, and bundle-loading code.
- Console package planning must reconcile the existing `scripts/ids_operator_console/` package with top-level console entrypoints such as `scripts/ids_operator_console_server.py` and `scripts/ids_operator_console_manage.py`.
- Experiment/training planning must cover preprocessing, staging, tuning, training, threshold analysis, and model packaging scripts without letting them leak back into the production-path package tree.
- Docs and tests must be remapped together with code movement so the repo's navigation story improves end to end rather than only inside Python modules.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `README.md` - canonical high-level repo purpose, reading order, and current top-level structure.
- `docs/final_model_bundle.md` - active bundle contract that production-path refactors must not accidentally blur.
- `docs/ids_inference_architecture.md` - inference-side system shape and boundaries.
- `docs/ids_realtime_pipeline_architecture.md` - runtime scoring/data-flow architecture.
- `docs/ids_live_sensor_architecture.md` - live IDS service architecture and supporting seams.
- `docs/ids_operator_console_architecture.md` - operator-console subsystem boundaries and current package surface.
- `docs/ids_same_host_stack_operations.md` - deployment/operations contract that repo restructuring must not obscure.

---

## Outstanding Questions

### Deferred to Planning

- [ ] What exact package tree and file-move map best implement D1-D9 without creating circular imports or wrapper sprawl? - requires repo-wide dependency tracing and migration design.
- [ ] Which modules belong in `shared/core` versus staying runtime-specific or console-specific? - requires concrete import graph analysis, not intuition.
- [ ] Which current `scripts.*` entrypoints should remain as thin compatibility wrappers in phase 1, and which can move immediately without operational risk? - requires CLI/runtime surface inventory.
- [ ] How should docs be partitioned into canonical/current versus historical/archive paths while preserving existing references and reading order? - requires a documentation migration map.
- [ ] What is the safest sequencing for moving tests so coverage remains understandable and runnable throughout the restructure? - requires a phased test-migration plan tied to code moves.

---

## Deferred Ideas

- One-shot public entrypoint rewrite in the first phase - deferred because D3 and D8 explicitly favor internal-structure stabilization first.
- Splitting the repository into multiple repos/packages - deferred because the current decision boundary is repository structure rationalization inside the existing repo, not repo decomposition.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
