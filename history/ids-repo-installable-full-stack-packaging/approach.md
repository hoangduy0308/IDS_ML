# Approach: IDS Repo-Installable Full Stack Packaging

**Date**: 2026-04-01
**Feature**: ids-repo-installable-full-stack-packaging
**Based on**:
- `history/ids-repo-installable-full-stack-packaging/discovery.md`
- `history/ids-repo-installable-full-stack-packaging/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Package metadata | `requirements.txt` only; no `pyproject.toml` or install metadata | one formal install surface for the repo-installable stack | New |
| Canonical entrypoints | `ids/*` modules already expose `main()` surfaces for runtime and ops commands | installed CLI entrypoints mapped directly to canonical modules | Medium |
| Compatibility wrappers | `scripts/*` thin wrappers exist and already have smoke coverage | keep wrappers alive as compatibility-only surfaces during install migration | Small |
| Internal orchestration dependencies | `ids.ops.same_host_stack*` still defaults subordinate command paths to `repo_root/scripts/...` | canonical ops orchestration must stop depending on wrapper file paths for its primary execution story | Large |
| Production deploy assets | `deploy/systemd/*` and nginx assets exist, but they still point at wrapper paths and mixed asset roots | converge deploy assets on the canonical packaged/operator path without breaking D6 | Medium |
| Runtime/bundle contract | activation-record, manifest, and stack lifecycle contracts already exist and are tested | preserve those contracts while removing split-path or local-workstation assumptions | Small |
| Path/config normalization | many production-adjacent commands still carry `F:\\Work\\IDS_ML_New\\...` defaults | centralize target-host defaults and make workstation paths non-required | Large |
| Console assets/runtime wiring | canonical console app exists, but service assets still reference `scripts/ids_operator_console/*` static/templates and those assets are not yet formalized as install payload | canonicalize service-facing asset roots and include them in install packaging | Medium |
| Verification | strong pytest coverage exists for wrappers, stack contracts, docs-command smoke, and bundle validation | extend verification so “installable full stack” is explicitly proven, not inferred | Medium |

---

## 2. Recommended Approach

Introduce a repo-root `pyproject.toml` that formalizes the repository as an installable Python product while keeping the current checkout-first deployment model. For phase 1, the install contract is **editable checkout install only** (`pip install -e .` plus the chosen extras), not wheel/sdist distribution. The install surface must expose canonical CLI entrypoints directly from `ids.runtime.*`, `ids.ops.*`, and the one approved production-adjacent ML packaging command, and those entrypoints must resolve straight into canonical module `main()` surfaces rather than through `scripts/*`. Existing `scripts/*` wrappers stay supported, but only as explicitly documented compatibility surfaces and never as the primary operator path in docs, deploy assets, or canonical orchestration. In parallel, normalize production-path defaults away from workstation-specific `F:\...` assumptions into one explicit same-host Linux contract centered on `/opt/ids_ml_new`, `/etc/ids-operator-console`, and `/var/lib`/`/var/log`, and move stack-orchestration defaults away from `repo_root/scripts/...` so canonical ops code no longer depends on wrapper file paths for its primary path. Package the canonical console templates/static assets as part of the install surface, preserve production model activation strictly on the existing `verify/promote -> active-bundle record` flow, and explicitly forbid any new packaged-runtime story based on raw bundle path overrides. Then realign deploy assets, docs, and verification around that packaged contract so a fresh Linux host can install from the repo checkout and complete `preflight`, `bootstrap`, `status`, and `smoke` through one operator-facing path using canonical installed entrypoints and an activated bundle.

### Why This Approach

- Reuses the strongest existing product seam instead of inventing a new deployment topology: same-host Linux, activation-record model selection, and stack orchestration already exist in code and docs.
- Honors locked decisions D1-D9 directly: production-first, full stack, repo-installable, one activation contract, one documentation spine, and wrapper compatibility without making wrappers canonical again.
- Avoids external-library churn: the gap is packaging metadata and contract normalization, not a missing framework.
- Uses existing test philosophy as the enforcement layer: wrapper smoke, runbook command smoke, stack JSON contracts, path-safety tests, and bundle-contract tests already define what “real” looks like.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Install metadata | Add one repo-root `pyproject.toml` and package discovery for `ids` plus the minimal production ML packaging surface | Satisfies D3/D4 with the least new machinery and no new runtime dependency surface |
| Install mode | Prove editable checkout install only in phase 1; defer wheel/sdist | Keeps the repo-installable contract aligned with the current checkout-first operator model and narrows validation blast radius |
| Canonical CLI mapping | Register console scripts to canonical module `main()` functions in `ids.runtime.*`, `ids.ops.*`, and `ml_pipeline.packaging.package_final_model`, with no installed entrypoint routed through `scripts/*` | Satisfies D6 while keeping implementation in canonical modules and making the canonical/compatibility boundary explicit |
| Wrapper policy | Keep `scripts/*` wrappers as compatibility-only shims, extend smoke coverage for them, and forbid them from being the primary documented or deployed operator path | Applies the wrapper-contract learnings and avoids breaking runbooks or direct-file usage mid-transition without leaving the primary contract ambiguous |
| Stack orchestration dependency direction | Refactor canonical stack orchestration so its primary subordinate-command strategy resolves canonical installed entrypoints or canonical module execution, not wrapper file paths | Applies the `scripts -> ids` one-way dependency rule and removes an architectural seam hidden inside ops defaults |
| Production path defaults | Introduce centralized Linux host defaults/config resolution for production-path commands; treat current `F:\...` paths as non-production compatibility only | Satisfies D7 and exact-path preflight learnings |
| Bundle handling | Keep the candidate bundle under the repo checkout/artifacts tree for the first repo-installable pass; production activation still happens only through `verify/promote` + active-bundle record, and no new packaged-runtime path may bypass that flow | Keeps D8 intact, avoids large binary wheel complexity in the first slice, and makes the activation contract explicit in planning rather than implied |
| Console asset packaging | Treat `ids/console/templates` and `ids/console/static` as canonical package data and stop treating `scripts/ids_operator_console/*` as the long-term service asset root | Aligns the operator service path with the real app surface and reduces wrapper-root drift |
| Deploy asset convergence | Move systemd/nginx/docs toward the packaged canonical operator path while preserving thin wrapper compatibility during the migration window | Satisfies D9 without creating two long-lived operator stories |

---

## 3. Alternatives Considered

### Option A: Keep `requirements.txt` + wrappers only, document the current repo layout better

- Description: leave install mechanics mostly unchanged and improve docs around `python scripts/...`.
- Why considered: lowest implementation cost and smallest blast radius.
- Why rejected: it does not actually create a formal install surface, leaves workstation-path assumptions alive, and keeps wrappers as the de facto product path instead of compatibility seams.

### Option B: Jump straight to `.deb` or container-first deployment

- Description: skip repo-installable normalization and package directly into OS-native or container artifacts.
- Why considered: operator-facing deployment artifacts can feel “more complete.”
- Why rejected: it would freeze an install contract before canonical packaging metadata, path normalization, and wrapper/entrypoint boundaries are coherent. That would amplify drift rather than reduce it.

### Option C: Build a wheel-first artifact that bundles the model payload

- Description: package runtime code and the candidate model bundle into one Python distribution payload.
- Why considered: single artifact delivery is superficially attractive.
- Why rejected: the existing product contract is checkout-first and activation-record-driven. Bundling the model into a wheel increases artifact complexity and blurs the existing explicit verify/promote boundary before the repo-installable path is stabilized.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Repo-root packaging metadata and package discovery | **HIGH** | Core infrastructure change with blast radius across install, import, CLI, package data, and test surfaces | Validating should confirm that the editable-install metadata shape preserves checkout execution, canonical entrypoint discovery, and package-data inclusion without creating a second install mode in phase 1 |
| Canonical CLI registration and operator-path convergence | **HIGH** | Touches many entrypoints and could silently create divergence between docs, systemd units, and actual callable surfaces | Validating should spike install/entrypoint shape and prove that installed commands resolve directly to canonical `ids/*` modules while wrappers remain compatibility-only |
| Stack orchestration dependency-direction cleanup | **HIGH** | Canonical ops code currently defaults to wrapper paths; changing this is architectural and affects bootstrap/recover flows | Validating should prove the chosen subordinate-command strategy preserves lifecycle behavior without reintroducing wrapper dependence |
| Production-path default/path normalization | **HIGH** | Multiple production-adjacent modules currently carry local defaults; mistakes can reopen path-drift or host-safety issues | Validating should spike the path-default strategy and audit which surfaces must change in phase 1 |
| Deploy assets + docs convergence | **HIGH** | Blast radius spans docs, systemd, nginx, asset roots, and operator expectations | Validating should verify whether deploy assets can move in the same execution wave without breaking compatibility |
| Wrapper preservation and smoke expansion | **MEDIUM** | Strong precedent exists, but many user-facing seams still need explicit coverage | Proceed with wrapper-smoke additions embedded in the same beads that touch wrappers |
| Bundle packaging command exposure | **MEDIUM** | Existing pattern exists in `ml_pipeline`, but the product boundary must stay explicit and avoid dragging historical workflows into the runtime contract | Verify with packaging-command smoke, bundle-contract tests, and explicit verify/promote active-bundle coverage |
| Full-host bootstrap verification | **MEDIUM** | Strong same-host stack precedent exists, but final “installable” proof spans multiple already-hardened components | Reuse and extend stack tests and runbook-smoke rather than inventing a new verification layer |

### HIGH-Risk Summary (for khuym:validating skill)

- `repo-root packaging metadata and package discovery`: does the editable-install-only phase 1 contract preserve canonical imports, wrapper compatibility, and test discovery without introducing a second execution topology?
- `canonical CLI registration and operator-path convergence`: can deploy/docs move to packaged canonical entrypoints in the same feature while explicitly keeping installed commands on `ids/*` modules and wrappers as compatibility-only?
- `stack orchestration dependency-direction cleanup`: how should the stack layer invoke subordinate commands once wrapper file paths stop being the primary canonical seam?
- `production-path default/path normalization`: which `F:\...` defaults are genuinely production-path blockers versus non-blocking historical workflow defaults?
- `deploy assets + docs convergence`: can service units, asset roots, and operator docs be made canonical in one pass, or must some compatibility seams remain temporarily explicit?

---

## 5. Proposed File Structure

```text
pyproject.toml                               # New install metadata and console_scripts

ids/
  __init__.py                                # Existing canonical package root
  core/
    path_defaults.py                         # New shared Linux host defaults / path contract helpers
  runtime/
    inference.py                             # Existing canonical CLI surface; default-path cleanup
    realtime_pipeline.py                     # Existing canonical CLI surface; default-path cleanup
    adapter/
      record_adapter.py                      # Existing runtime-adjacent default-path cleanup
  ops/
    same_host_stack_manage.py                # Existing canonical stack CLI; packaged-entrypoint target
    same_host_stack.py                       # Existing orchestration; path/default alignment if needed
    live_sensor_preflight.py                 # Existing preflight surface
    operator_console_preflight.py            # Existing preflight surface
    model_bundle_manage.py                   # Existing bundle lifecycle CLI
    operator_console_manage.py               # Existing maintenance/worker CLI
  console/
    web.py                                   # Existing canonical app factory
    templates/                               # Canonical console asset root
    static/                                  # Canonical console asset root

ml_pipeline/
  packaging/
    package_final_model.py                   # Existing bundle-assembly command; packaged-entrypoint target

scripts/
  *.py                                       # Compatibility wrappers preserved, not canonicalized away

deploy/
  systemd/
    ids-live-sensor.service                  # Updated canonical operator path if phase includes deploy convergence
    ids-operator-console.service
    ids-operator-console-notify.service
  nginx/
    ids-operator-console.conf.example

docs/current/
  operations/                                # Canonical operator docs updated to one install/bootstrap path
  runtime/                                   # Bundle/runtime docs aligned to packaged entrypoints

tests/
  runtime/
    test_ids_runtime_wrapper_smoke.py        # Existing wrapper-smoke seam to extend if needed
  ops/
    test_ids_same_host_stack_manage.py       # Existing stack lifecycle contract seam
    test_ids_live_sensor_preflight.py        # Existing exact-path preflight seam
    test_ids_operator_console_preflight.py   # Existing operator preflight seam
  docs/
    test_docs_path_smoke.py                  # Existing docs-command smoke seam
  ml/
    test_ml_workflow_wrapper_smoke.py        # Existing ML wrapper-smoke seam
```

---

## 6. Dependency Order

```text
Layer 1 (sequential): packaging contract foundation
  - repo-root install metadata
  - packaged canonical entrypoint map
  - shared path/default strategy for production surfaces

Layer 2 (parallel after Layer 1): production-path normalization
  - runtime/bundle path cleanup
  - ops/preflight/stack path cleanup
  - console asset/default cleanup

Layer 3 (parallel after Layer 2): contract convergence
  - wrapper-smoke and install-smoke expansion
  - deploy asset realignment
  - docs/runbook canonicalization

Layer 4 (sequential): final bootstrap proof
  - end-to-end verification path proving install + preflight/bootstrap/status/smoke
```

### Parallelizable Groups

- Group A: production runtime-path cleanup and operator/console path cleanup — can run in parallel once the install contract and shared defaults are defined.
- Group B: wrapper/doc/deploy convergence — depends on Group A so the final public/operator path is based on the normalized contract.
- Group C: final verification bead — depends on Groups A and B and proves D4.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260331-repo-structure-wrapper-contracts.md` | wrappers are executable contracts | the approach keeps wrappers but requires smoke verification in the same migration feature |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | production model selection must stay on one activation contract | the approach keeps activation-record-driven bundle resolution as non-negotiable |
| `history/learnings/20260329-same-host-stack-runtime-hardening.md` | stack commands must execute the full lifecycle they advertise | D4 is defined in terms of full host bootstrap plus status/smoke, not install metadata alone |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Linux services need exact-path preflight and one config source | the approach centralizes production-path defaults instead of leaving duplicated literals in code and deploy assets |
| `history/learnings/20260329-operator-console-production-hardening.md` | runtime verify-only vs mutation paths must stay explicit | the approach preserves the existing console manage/preflight/server separation instead of collapsing bootstrap into runtime install paths |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | runnable service entrypoint must use the real app factory | the approach keeps `scripts/ids_operator_console_server.py` and packaged CLI mapping anchored to the canonical app factory |

---

## 8. Open Questions for Validating

- [x] Phase 1 proves editable checkout install only. Wheel/sdist support is deferred until the repo-installable contract is stable.
- [ ] Can deploy assets and docs move fully to packaged canonical entrypoints in the same feature, or is one compatibility-only deploy seam acceptable for the first repo-installable pass?
- [ ] Which hardcoded local defaults are in-scope blockers for the production packaging path, and which are acceptable temporary compatibility defaults for non-production ML workflows?
- [ ] Should the first pass expose the candidate bundle strictly as a repo checkout artifact under `artifacts/final_model`, or must packaging create a more explicit staging/install story for that payload?

## 9. Planning Clarifications After Validation

- `D6` is now interpreted strictly: installed entrypoints are part of the canonical product contract only when they resolve directly into `ids/*` modules (and the one approved `ml_pipeline.packaging.package_final_model` command). `scripts/*` wrappers remain supported, but only as compatibility surfaces and never as the primary operator-facing path.
- `D8` is now interpreted strictly: packaged production activation must remain on the existing `verify/promote -> active-bundle record -> runtime resolution` chain. No bead, test, doc, or deploy asset in this feature may introduce a production story that depends on raw bundle path overrides instead of the activation record.
- Validation should reject any future bead wording that leaves these two constraints implicit.

---

## 10. Replan Addendum After Blocked Validation

### What Changed

The first review-followup wave was structurally under-owned. The review beads were real, but they did not explicitly own the installed metadata surface, the canonical installed entrypoint spine, or the final packaged bootstrap proof seam. Replanning narrows the existing beads and adds one explicit install-surface bead so those contracts stop being inferred.

### Revised Recommended Topology

The review-followup wave should now be treated as one explicit DAG rooted in the install contract:

```text
ids_ml_new-x1p9  install metadata + canonical entrypoint surface
  -> ids_ml_new-d5ae  ML packaging topology ownership + package defaults
    -> ids_ml_new-qq0f  deploy/docs interpreter-contract convergence
      -> ids_ml_new-z0pb  runtime-scoped path-default boundary + runtime adopters
        -> ids_ml_new-bt3x  explicit realtime inferencer/schema seam
          -> ids_ml_new-m8h0  trust-boundary hardening + final installed bootstrap proof
            -> ids_ml_new-zpih  proof-helper dedupe
```

### Revised Bead Roles

| Bead | Role in the replanned wave |
|------|-----------------------------|
| `ids_ml_new-x1p9` | Explicit owner of `pyproject.toml`, canonical console-script mapping, package-data continuity, and the single operator-facing repo-installable command spine |
| `ids_ml_new-d5ae` | Moves ML packaging topology out of `ids.core` and proves package defaults without re-owning runtime/default concerns |
| `ids_ml_new-qq0f` | Converges docs/deploy assets onto the bootstrap-created installed-environment interpreter contract |
| `ids_ml_new-z0pb` | Keeps `ids.core.path_defaults` runtime-scoped and proves runtime adopters directly |
| `ids_ml_new-bt3x` | Removes the implicit realtime inferencer schema seam after the runtime/default contract is settled |
| `ids_ml_new-m8h0` | Hardens module trust boundary and explicitly owns the final installed `ids-stack` bootstrap/status/smoke failure-proof seam |
| `ids_ml_new-zpih` | Deduplicates proof helpers only after the proof shape has stabilized |

### Replan Risk Map

| Component | Risk Level | Why |
|-----------|------------|-----|
| `ids_ml_new-x1p9` install surface owner | **HIGH** | It is the seam validation previously said was implicit across D3/D6/D9. |
| `ids_ml_new-d5ae` ML packaging topology | **MEDIUM** | Boundary cleanup with focused blast radius in packaging code and ML tests. |
| `ids_ml_new-qq0f` interpreter-contract convergence | **HIGH** | Docs, deploy assets, and operator contract must align on one runtime story. |
| `ids_ml_new-z0pb` runtime/default boundary | **MEDIUM** | Shared-core ownership cleanup with direct runtime adopter proof. |
| `ids_ml_new-bt3x` realtime schema seam | **MEDIUM** | Localized runtime API seam, but it touches explicit contract shape. |
| `ids_ml_new-m8h0` trust boundary + final proof | **HIGH** | Security-sensitive preflight logic plus the final packaged bootstrap proof owner. |
| `ids_ml_new-zpih` helper dedupe | **LOW** | Test-only refactor once proof shape is stable. |

### Replan Decision Rationale

This replan adds only one new bead, but it changes the wave from "a set of review fixes that happen to relate to packaging" into "a packaging-contract repair chain." That is the minimum change that answers the blocked validating report without reopening the full feature plan. The head bead makes D3/D6/D9 explicit, the tail bead makes D4/D8 explicit, and the middle beads each own one boundary instead of mixed concerns.
