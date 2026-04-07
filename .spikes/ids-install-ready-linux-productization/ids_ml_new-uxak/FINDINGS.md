# Spike Findings: ids_ml_new-uxak

**Question**

Can Phase 2 safely make full-stack install auto-run canonical bundle `verify + promote` for the bundled default artifact without reopening bootstrap trust drift or introducing silent fallback semantics?

**Answer**

YES.

The current stack path can support this safely, but only if install remains a selector of bundle root rather than a second bundle/activation implementation.

## Why The Answer Is YES

- `ids/ops/same_host_stack.py` already routes bootstrap mutation through canonical module execution with `_build_module_command(...)`, `-I`, scrubbed `PYTHON*` environment, and `cwd=python_binary.parent`.
- `run_stack_bootstrap(...)` already performs `verify` then `promote` through `ids-model-bundle-manage`, and only proceeds after the validated preflight/bootstrap gate passes.
- Existing proof coverage in `tests/ops/test_ids_same_host_stack_manage.py` and `tests/ops/test_ids_repo_installable_bootstrap_proof.py` already pins the repaired interpreter/bootstrap trust boundary.

## Hard Constraints

1. `ops/build_release.sh` must validate the exact shipped default bundle before the tarball is written.
2. `ops/install.sh` may only select the candidate bundle root; it must not parse manifests itself or write `active_bundle.json` directly.
3. All bundle mutation must remain on the existing validated interpreter/env contract:
   - `<python> -I -m ...`
   - scrubbed `PYTHON*`
   - `cwd=python_binary.parent`
4. The validated preflight/operator-config snapshot must remain authoritative through bootstrap; do not re-resolve config on the hot path.
5. Precedence must stay fail-closed:
   - valid explicit override
   - else valid bundled default
   - else abort
6. `console-only` never attempts bundle activation.
7. Activation ownership remains one activation-record contract via `ids-model-bundle-manage`.

## Breaking Seam If Mishandled

The dangerous seam is between:

- build/install choosing a bundled default root
- bootstrap executing privileged bundle mutation

If release or install starts doing its own manifest verification or resolves a different interpreter, environment, or root than the path `ids-stack bootstrap` later executes, the feature reopens the exact April 3 trust-boundary bug. The other breaking seam is override failure silently falling through to the bundled default.

## Required Adjustments To Phase 2 Artifacts

- Story 1 / `ids_ml_new-1u8h.6`: pin one exact bundled default artifact root so release and install validate/select the same shipped artifact.
- Story 2 / `ids_ml_new-1u8h.9`: state explicitly that install only selects the bundle root; `ids-stack bootstrap` remains the sole `verify + promote` mutation path.
- Story 3 / `ids_ml_new-1u8h.7`: require a precedence-matrix regression proving `override > bundled default > abort` with no silent fallback after failed override/default validation.
