# Spike Findings: ids_ml_new-d90e.11

## Question

Can the existing `ml_pipeline.packaging.package_final_model` path be extended to emit one deployable composite bundle, with the same wrapper/entrypoint surface, without introducing a parallel sidecar packager as the real production contract?

## Answer

YES.

## Why

- `ml_pipeline/packaging/package_final_model.py` already owns the canonical bundle assembly flow: it copies the selected model and feature schema, writes `model_bundle.json`, writes metrics/training summaries, and prints one bundle-root payload.
- The wrapper surface is already pinned through `scripts/package_final_model.py`, `tests/ml/test_ml_workflow_wrapper_smoke.py`, and installable-surface checks in `tests/ops/test_ids_repo_installable_surface.py`.
- Existing ML packaging tests in `tests/ml/test_ml_workflow_e2e.py` already exercise the bundle writer end to end and can be extended to prove a composite manifest/output path without inventing a second deploy seam.
- Introducing a separate sidecar packager would reopen the same production-contract split that this feature is explicitly trying to avoid.

## Smallest Credible Proof Slice

1. Extend `ml_pipeline/packaging/package_final_model.py` so it can package either:
   - the legacy binary bundle, or
   - a composite bundle rooted at one bundle directory with stage-1 + stage-2 artifacts and abstention metadata.
2. Extend `tests/ml/test_ml_workflow_e2e.py` to prove:
   - composite packaging emits the expected manifest/source references, and
   - legacy binary packaging still works unchanged.
3. Keep wrapper compatibility pinned separately in `tests/ml/test_ml_workflow_wrapper_smoke.py` and, only if needed, `tests/ops/test_ids_repo_installable_surface.py`.

## Constraints To Carry Into Execution

- Do not create a second production packager as the primary rollout path.
- Keep `scripts/package_final_model.py` pointing at the canonical module path.
- Preserve the current binary packaging path for D9 rollout compatibility.
- Any composite bundle metadata written here must match the activation/runtime contract already validated in Phases 1 and 2.
