# Discovery Report: IDS Repo-Installable Full Stack Packaging

**Date**: 2026-04-01
**Feature**: ids-repo-installable-full-stack-packaging
**CONTEXT.md reference**: `history/ids-repo-installable-full-stack-packaging/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- Keep production model selection on one activation contract. Do not reintroduce split `model/schema/threshold` runtime overrides.
- Treat compatibility wrappers as executable contracts. If `scripts/*` remain supported, CI must exercise them directly.
- Use exact-path preflight contracts for Linux services. Avoid duplicated deployment literals and bare `PATH` discovery for host-sensitive helpers.
- Canonical stack commands are lifecycle contracts. `bootstrap`, `recover`, and related commands must execute the full documented verification path before returning success.
- Keep canonical modules independent from compatibility layers. Dependency direction must stay `scripts -> ids/ml_pipeline`, never the reverse.
- Host-level path handling must separate normalization from authorization and prove root containment where filesystem trust boundaries matter.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260331-repo-structure-wrapper-contracts.md` | wrappers / migration | Preserved wrappers are part of the product contract and need direct smoke coverage in the same change that keeps them alive. | high |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | model activation | Production runtime must resolve one active bundle through one activation record; packaging must not reopen raw path override seams. | high |
| `history/learnings/20260329-same-host-stack-runtime-hardening.md` | stack orchestration | Stack commands must prove the full documented lifecycle, especially post-start readiness/smoke, not just mutation or service start. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | live-sensor deploy/preflight | Linux services become safer when preflight validates one exact config source and exact helper paths before the daemon loop begins. | medium |
| `history/learnings/20260329-operator-console-production-hardening.md` | console deploy/runtime | Runtime paths should remain verify-only; bootstrap/migration/recovery stay on explicit maintenance commands and must share the same deploy/preflight contract. | medium |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | service entrypoint wiring | The runnable server entrypoint must import the same canonical app factory the feature routes actually live behind. | medium |

---

## Agent A: Architecture Snapshot

> Source: gkg repo_map, file tree analysis

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `ids/core` | bundle contracts, feature-contract primitives, activation resolution | `ids/core/model_bundle.py`, `ids/core/model_bundle_activation.py` |
| `ids/runtime` | inference, realtime pipeline, live sensor, health/runtime surfaces | `ids/runtime/inference.py`, `ids/runtime/realtime_pipeline.py`, `ids/runtime/live_sensor.py`, `ids/runtime/live_sensor_health.py` |
| `ids/console` | operator console config, web app, ops, notification worker, assets | `ids/console/web.py`, `ids/console/ops.py`, `ids/console/notification_runtime.py`, `ids/console/templates/`, `ids/console/static/` |
| `ids/ops` | preflight, manage, model lifecycle, same-host stack orchestration | `ids/ops/model_bundle_manage.py`, `ids/ops/live_sensor_preflight.py`, `ids/ops/operator_console_preflight.py`, `ids/ops/same_host_stack.py`, `ids/ops/same_host_stack_manage.py` |
| `scripts` | compatibility entrypoints and direct-file bootstrap shims | `scripts/ids_inference.py`, `scripts/ids_same_host_stack_manage.py`, `scripts/ids_operator_console_server.py`, `scripts/package_final_model.py` |
| `ml_pipeline` | ML workflow orchestration and bundle assembly outside the runtime-serving tree | `ml_pipeline/packaging/package_final_model.py`, `ml_pipeline/training/posttrain_threshold_analysis.py` |
| `deploy` | shipped host integration assets | `deploy/systemd/*.service`, `deploy/nginx/ids-operator-console.conf.example` |
| `docs/current` | canonical runtime and operations contract | `docs/current/runtime/final_model_bundle.md`, `docs/current/operations/ids_same_host_stack_operations.md` |
| `tests` | contract, wrapper-smoke, runbook-smoke, and host-lifecycle verification | `tests/runtime/*`, `tests/ops/*`, `tests/docs/test_docs_path_smoke.py`, `tests/ml/test_ml_workflow_wrapper_smoke.py` |

### Entry Points

- **Canonical runtime CLI/module**: `ids/runtime/inference.py`, `ids/runtime/realtime_pipeline.py`, `ids/runtime/live_sensor.py`, `ids/runtime/live_sensor_health.py`
- **Canonical ops CLI/module**: `ids/ops/model_bundle_manage.py`, `ids/ops/live_sensor_preflight.py`, `ids/ops/operator_console_preflight.py`, `ids/ops/operator_console_manage.py`, `ids/ops/same_host_stack_manage.py`
- **Canonical web app factory**: `ids.console.web.create_operator_console_web_app`, surfaced by `scripts/ids_operator_console_server.py`
- **Compatibility wrappers**: `scripts/*.py` modules and direct-file execution paths
- **Host integration surfaces**: `deploy/systemd/*.service`, `deploy/nginx/ids-operator-console.conf.example`

### Key Files to Model After

- `scripts/ids_inference.py` — demonstrates the thin wrapper bootstrap pattern for direct-file compatibility.
- `scripts/ids_same_host_stack_manage.py` — demonstrates wrapper delegation from a compatibility entrypoint into the canonical ops module.
- `scripts/ids_operator_console_server.py` — demonstrates the desired “real server entrypoint uses canonical app factory” wiring pattern.
- `tests/runtime/test_ids_runtime_wrapper_smoke.py` — demonstrates how wrapper contracts are currently enforced through `--help` and import-surface smoke tests.
- `tests/docs/test_docs_path_smoke.py` — demonstrates that documented commands are treated as executable contracts, not prose only.

---

## Agent B: Pattern Search

> Source: grep, semantic search, gkg import_usage, targeted file reads

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Runtime wrapper preservation | `scripts/ids_inference.py`, `scripts/ids_same_host_stack_manage.py` | thin repo-root bootstrap wrapper delegating to canonical modules | Yes |
| Wrapper smoke verification | `tests/runtime/test_ids_runtime_wrapper_smoke.py`, `tests/ml/test_ml_workflow_wrapper_smoke.py` | `python -m scripts.* --help` and direct-file `--help` smoke | Yes |
| Documented-command verification | `tests/docs/test_docs_path_smoke.py` | docs/runbook command string treated as testable contract | Yes |
| Canonical app wiring | `scripts/ids_operator_console_server.py` + `ids.console.web` | runnable service entrypoint imports the real app factory | Yes |
| Activation-contract enforcement | `ids/runtime/inference.py`, `ids/core/model_bundle.py`, `ids/ops/model_bundle_lifecycle.py` | canonical bundle/config/activation exclusivity with fail-closed validation | Yes |
| Stack lifecycle verification | `ids/ops/same_host_stack_manage.py`, `ids/ops/same_host_stack.py`, `tests/ops/test_ids_same_host_stack_manage.py` | full-stack JSON contract plus degraded exit codes and post-start verification | Yes |

### Reusable Utilities

- **Wrapper smoke support**: `wrapper_smoke_support.py` — shared helpers for `python -m ... --help`, direct-file `--help`, and no-traceback smoke assertions.
- **Bundle contract validation**: `ids/core/model_bundle.py` — versioned manifest validation, digest checks, domain-specific contract errors.
- **Activation resolution**: `ids/core/model_bundle_activation.py` — single active bundle resolution path for runtime callers.
- **Stack command orchestration**: `ids/ops/same_host_stack.py` — central lifecycle sequencing and degraded diagnosis logic.
- **Canonical web app creation**: `ids.console.web` via `create_operator_console_web_app` — real console app surface for any installed CLI/server mapping.

### Naming Conventions

- Canonical package roots are domain-oriented: `ids.core`, `ids.runtime`, `ids.console`, `ids.ops`, and `ml_pipeline.*`.
- Compatibility wrappers keep historical script-like names under `scripts/*.py`.
- Ops/runtime CLIs expose imperative command names such as `preflight`, `bootstrap`, `status`, `smoke`, `recover`, `verify`, `promote`, and `rollback`.
- Tests mirror product seams: `tests/runtime`, `tests/ops`, `tests/console`, `tests/ml`, `tests/docs`.

---

## Agent C: Constraints Analysis

> Source: `requirements.txt`, repo-root file scan, tests, deploy assets, docs

### Runtime & Framework

- **Python version**: tested on `Python 3.11.9`
- **Language/runtime**: Python CLI + same-host services
- **ML/runtime stack**: `catboost`, `pandas`, `pyarrow`, `scikit-learn`
- **Web/runtime stack**: `fastapi`, `starlette`, `uvicorn`, `jinja2`, `python-multipart`, `httpx`
- **Supervisor/deploy assumptions**: `systemd`, `nginx`, exact Linux filesystem paths such as `/opt/ids_ml_new`, `/var/lib/ids-live-sensor`, `/etc/ids-operator-console`

### Existing Dependencies (Relevant to This Feature)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | `0.115.12` | operator console web service |
| `uvicorn` | `0.34.0` | ASGI server runtime |
| `jinja2` | `3.1.6` | console templates |
| `catboost` | `1.2.10` | production model loading/scoring |
| `pandas` | `3.0.1` | inference/realtime data frame handling |
| `pyarrow` | `22.0.0` | parquet IO |
| `pytest` | `8.3.5` | main regression harness |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None required by locked decisions | The repo already contains the runtime, web, deploy, and verification surfaces needed for the packaging feature. The main gap is packaging metadata and path normalization, not a missing product library. | LOW |

### Build / Quality Requirements

```bash
# Existing quality surfaces already treated as contracts:
python -m pytest tests -q
python -m pytest tests/runtime/test_ids_inference.py tests/runtime/test_ids_realtime_pipeline.py tests/runtime/test_ids_record_adapter.py -q
python -m scripts.ids_inference --help
python -m scripts.ids_live_sensor --help
python -m scripts.ids_same_host_stack_manage --help
python scripts/ids_realtime_pipeline.py --help
```

### Packaging / Install Constraints

- There is currently **no** `pyproject.toml`, `setup.py`, `setup.cfg`, or `MANIFEST.in` at the repo root.
- `requirements.txt` is the only current install surface; there is no formal package metadata or console-script registration.
- Many runtime/ML modules still carry hardcoded workstation defaults under `F:\Work\IDS_ML_New\...`.
- Deploy assets still point explicitly at `scripts/*.py` paths and `/opt/ids_ml_new` as the checkout root.
- Systemd units currently reference console templates/static under `scripts/ids_operator_console/*`, while canonical defaults in docs/code now treat `ids/console/*` as the real product asset roots.
- Existing tests already assert wrapper help surfaces, runbook command liveness, stack JSON payload behavior, and path-safety rules. Packaging work can attach to those seams instead of inventing a new verification philosophy.

### Storage / Host-State Boundaries

- **Active model selection**: `/var/lib/ids-live-sensor/active_bundle.json`
- **Live-sensor logs and JSONL outputs**: `/var/log/ids-live-sensor`
- **Operator console database**: `/var/lib/ids-operator-console/operator_console.db`
- **Operator env + secrets**: `/etc/ids-operator-console/ids-operator-console.env`, `/etc/ids-operator-console/console.secret`
- **Repo checkout root**: `/opt/ids_ml_new`

---

## Agent D: External Research

> Source: skipped by design

External research is not required for this feature at planning time. The packaging work builds on existing in-repo patterns, existing dependencies, and an already-documented same-host Linux contract. The unresolved questions are repo-specific packaging choices, not unknown third-party integration behavior.

---

## Open Questions

> Items that were not resolvable through research alone.
> These will be raised to synthesis in Phase 2.

- [ ] Should the first repo-installable pass support only one install mode (for example editable checkout install) or both editable and wheel/sdist install? This affects blast radius and validation scope.
- [ ] Should packaged console asset defaults move fully from `scripts/ids_operator_console/*` to `ids/console/*` in the same feature, or should the first pass preserve current service-unit paths and only add installed entrypoints? This affects migration risk for deploy artifacts.
- [ ] Which hardcoded `F:\Work\IDS_ML_New\...` defaults belong to production-path surfaces and therefore must be removed in the first pass, versus ML workflow/history commands that can remain compatibility defaults temporarily?
- [ ] Should the candidate model bundle be part of the repo-installable product payload or treated as an operator-provided/staged prerequisite referenced by docs and stack/bootstrap commands?

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a domain-organized canonical Python package tree under `ids/*`, explicit same-host Linux deploy assets, documented full-stack lifecycle commands, hardened model-bundle activation rules, and an existing test philosophy that already treats wrappers, runbooks, and stack JSON outputs as executable contracts.

**What we need**: a single formal install/distribution layer that turns the repo into an installable same-host product without reopening wrapper drift, path drift, split activation semantics, or deploy/runtime mismatches.

**Key constraints from research**:
- There is no package metadata today; the repo still relies on `requirements.txt` plus direct checkout execution.
- Production deploy surfaces still point at `scripts/*.py` entrypoints and exact Linux host paths under `/opt`, `/etc`, and `/var`.
- Several production-adjacent modules still carry workstation-specific `F:\Work\IDS_ML_New\...` defaults that conflict with a repo-installable Linux target.
- Existing tests already encode wrapper-smoke, docs-command liveness, path-safety, and full stack lifecycle expectations; the plan should reuse and extend those instead of inventing a new quality gate.

**Institutional warnings to honor**:
- Preserve one activation contract for production model selection.
- Treat wrappers and documented commands as real executable contracts.
- Keep stack/bootstrap verification complete and explicit.
- Maintain exact-path preflight and path-containment protections for host-level operations.

---

## Planning Addendum: Review-Followup Replan

### Why Planning Reopened

The first review-followup bead set failed `khuym:validating` after three plan-check iterations. The blocker was not missing codebase context anymore; it was graph structure. The open beads described real review fixes, but they left three seams implicit:

- install metadata ownership in `pyproject.toml`
- canonical installed entrypoint ownership across docs and deploy assets
- final packaged bootstrap proof ownership after the upstream fixes landed

### Discovery Conclusion For The Replan

The already-implemented feature still has the right canonical surfaces:

- `pyproject.toml` owns the repo-installable metadata and console-script map
- `tests/ops/test_ids_repo_installable_surface.py` owns installed entrypoint and package-data proof
- `tests/ops/test_ids_repo_installable_bootstrap_proof.py` owns the installed `ids-stack` bootstrap/status/smoke contract
- `deploy/systemd/*` and `docs/current/*` are the operator-facing contract surfaces that must stay aligned with the installed command surface

The structural mistake in the first follow-up wave was assuming those seams could stay implicit while review fixes changed runtime, docs, and packaging defaults. Replanning therefore needs one explicit install-surface owner bead ahead of the other fixes, and one explicit final-proof owner bead at the tail.

### Revised Structural Spine

The replanned wave should execute in this order:

```text
install surface owner
  -> ML packaging topology owner
    -> deploy/docs interpreter-contract owner
      -> runtime path-default boundary owner
        -> realtime schema-seam owner
          -> trust-boundary + final bootstrap-proof owner
            -> proof-helper dedupe
```

Concrete bead IDs after the replan:

```text
ids_ml_new-x1p9
  -> ids_ml_new-d5ae
    -> ids_ml_new-qq0f
      -> ids_ml_new-z0pb
        -> ids_ml_new-bt3x
          -> ids_ml_new-m8h0
            -> ids_ml_new-zpih
```

### Replan-Specific Takeaway

For review-followup waves on an already-implemented feature, discovery does not usually need more code research. The real job is to identify which previously implicit seams now need explicit bead ownership so validation can map them back to locked decisions without guessing.
