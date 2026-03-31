## Candidate: keep-canonical-contracts-separate-from-lifecycle-and-compatibility-layers
Category: pattern
Tags: architecture, model-bundle, activation, ops, compatibility, canonical-imports
Applies to review beads: `ids_ml_new-tv8z`
Summary: Canonical package code should depend on canonical contracts only, while activation, promotion, rollback, status management, and compatibility wrappers stay in the operational or wrapper layer. When contract modules absorb lifecycle behavior or canonical runtime code imports through `scripts.*`, the repo recreates the same drift seam the restructure was meant to remove.
Evidence: review bead `ids_ml_new-tv8z` consolidates four overlapping findings around `ids/core/model_bundle.py`, `ids/runtime/inference.py`, and `scripts/ids_model_bundle.py`: split lifecycle operations out of `ids.core`, keep runtime imports off the `scripts` layer, and restore the D8/D9 boundary.
Related patterns: `history/learnings/20260329-model-bundle-promotion-hardening.md`, `history/learnings/20260329-operator-console-production-hardening.md`, `history/learnings/20260330-extractor-contract-hardening.md`
Recommended title: YYYYMMDD-keep-canonical-contracts-separate-from-lifecycle-and-compatibility-layers.md

## Candidate: treat-compatibility-wrappers-and-entrypoints-as-executable-contracts
Category: failure
Tags: wrappers, smoke-tests, entrypoints, stack, runtime, ml-pipeline, compatibility
Applies to review beads: `ids_ml_new-br4g.24`, `ids_ml_new-br4g.25`, `ids_ml_new-0hbt`, `ids_ml_new-bs63`
Summary: Phase-1 compatibility wrappers are not documentation-only seams; they are supported execution contracts and need explicit smoke coverage plus intentional wrapper surfaces. If the suite tests only canonical modules and leaves `scripts.*` wrappers implicit or wildcard-exported, deployment and automation can drift away from the code paths CI actually proves.
Evidence: review beads `ids_ml_new-br4g.24` and `ids_ml_new-br4g.25` require smoke coverage for runtime and ops wrappers, `ids_ml_new-0hbt` extends the same gap into migrated `ml_pipeline` entrypoints, and `ids_ml_new-bs63` shows that wildcard re-exports keep the compatibility promise implicit instead of explicit.
Related patterns: `history/learnings/20260328-operator-console-runtime-wiring.md`, `history/learnings/20260329-same-host-stack-runtime-hardening.md`, `history/learnings/20260330-extractor-contract-hardening.md`
Recommended title: YYYYMMDD-treat-compatibility-wrappers-and-entrypoints-as-executable-contracts.md

## Candidate: harden-post-migration-test-layouts-against-hidden-coverage-drift
Category: failure
Tags: pytest, test-layout, bootstrap, duplicate-tests, migration, coverage
Applies to review beads: `ids_ml_new-9ku3`, `ids_ml_new-5fty`
Summary: After a mirrored test-tree migration, shared bootstrap and test identity need to be treated as first-class contracts. Duplicate test names and per-file `sys.path` surgery can make the suite look comprehensive while silently dropping cases or masking import-layout breakage.
Evidence: review bead `ids_ml_new-9ku3` captures the shadowed duplicate definitions in `tests/runtime/test_ids_live_sensor_health.py`, while `ids_ml_new-5fty` captures the remaining per-file bootstrap hacks despite the new shared `tests/conftest.py`.
Related patterns: no direct prior match in `history/learnings/`; this is a new candidate surfaced by the current review rather than a confirmed repeat pattern
Recommended title: YYYYMMDD-harden-post-migration-test-layouts-against-hidden-coverage-drift.md

## Candidate: normalize-hostile-metadata-at-contract-boundaries
Category: failure
Tags: error-handling, metadata, model-bundle, restore, fail-closed
Applies to review findings: 1, 2
Summary: Boundary parsers should translate malformed or missing manifest, activation, or backup metadata into domain errors instead of letting raw `KeyError`, `ValueError`, or JSON parse exceptions escape. The same repo keeps rediscovering that external metadata is untrusted and should fail closed at the edge.
Evidence: review findings 1 and 2 show `ids/core/model_bundle.py`, `ids/core/model_bundle_activation.py`, and `ids/console/ops.py` still surface raw parse and lookup errors before the boundary can normalize them.
Related patterns: `history/learnings/20260329-model-bundle-promotion-hardening.md`, `history/learnings/20260329-same-host-stack-runtime-hardening.md`, `history/learnings/20260329-operator-console-production-hardening.md`
Recommended title: YYYYMMDD-normalize-hostile-metadata-at-contract-boundaries.md

## Candidate: enforce-path-containment-after-normalization-for-host-level-file-operations
Category: failure
Tags: filesystem, path-resolution, containment, preflight, restore, security
Applies to review findings: 3, 6
Summary: Host-level file guards should either reject relative inputs before normalization or resolve and then verify containment against the intended root. If the guard trusts a resolved path without a strict root check, a caller can slip past the intended boundary or point restore inventory outside the selected backup root.
Evidence: review findings 3 and 6 point at `ids/ops/same_host_stack.py` path guards and restore inventory loading; both are containment problems caused by trusting resolved paths without a strict root check.
Related patterns: `history/learnings/20260328-live-sensor-runtime-contracts.md`, `history/learnings/20260329-same-host-stack-runtime-hardening.md`, `history/learnings/20260328-adapter-rollback-contract.md`
Recommended title: YYYYMMDD-enforce-path-containment-after-normalization-for-host-level-file-operations.md
