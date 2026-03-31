# Findings

## Question
What is the smallest contract surface that can move into `ids.core` without creating circular imports or reopening bundle and feature-schema drift?

## Evidence
- `scripts/ids_feature_contract.py` is already a pure contract module for feature validation. It defines `FlowFeatureContract`, the validated/quarantined record dataclasses, numeric coercion, and schema loading at lines 10-13, 37-105, and 224.
- `scripts/ids_model_bundle.py` mixes two different concerns in one file: pure bundle-contract types/builders at lines 12-17, 20-24, 63-84, 106-168, and 181-270, and operational lifecycle helpers at lines 297-401.
- Current imports are one-way. Runtime and ops code import the contract modules, but the contract modules do not import runtime/ops code. Examples: `scripts/ids_realtime_pipeline.py`, `scripts/ids_live_sensor.py`, `scripts/ids_inference.py`, `scripts/ids_live_sensor_preflight.py`, `scripts/ids_live_sensor_health.py`, `scripts/ids_model_bundle_manage.py`, and `scripts/ids_same_host_stack.py` all depend on `scripts.ids_feature_contract` or `scripts.ids_model_bundle`.
- `scripts/ids_record_adapter.py` dynamically imports `scripts.ids_feature_contract` and only needs the contract surface, which confirms the adapter edge is already downstream-only.
- The tests lock the current contract behavior in place. `tests/test_ids_feature_contract.py` checks aliasing, quarantine behavior, and canonical feature-column equality with the training manifest. `tests/test_ids_model_bundle.py` checks manifest versioning, compatibility metadata, digest validation, and activation-record round-tripping. `tests/test_ids_live_sensor_preflight.py`, `tests/test_ids_inference.py`, and `tests/test_ids_live_sensor_health.py` assert that the bundle contract is the runtime gating mechanism, not just a data container.

## Decision
YES.

The smallest safe move into `ids.core` is a leaf-only contract slice: pure feature-schema contract types/validators and pure bundle-manifest/activation-record contract types/builders. That boundary is safe because it stays one-way, does not pull in runtime or ops modules, and does not encode bundle selection, promotion, rollback, or status-wiring behavior inside core.

## Safe boundary
- Move into `ids.core`:
  - `FlowFeatureContract`
  - `ValidatedFlowRecord`
  - `QuarantinedFlowRecord`
  - `BatchValidationResult`
  - `coerce_numeric_feature`
  - `read_json`
  - `load_feature_columns`
  - `ModelBundleContractError`
  - `ActiveBundleResolutionError`
  - `ModelBundleManifest`
  - `ActiveBundleRecord`
  - `SUPPORTED_BUNDLE_MANIFEST_VERSION`
  - `SUPPORTED_ACTIVATION_RECORD_VERSION`
  - `SUPPORTED_FEATURE_SCHEMA_KIND`
  - `SUPPORTED_INFERENCE_CONTRACT_VERSION`
  - `build_feature_schema_metadata`
  - `build_inference_contract_metadata`
  - `build_activation_record_payload`

- Keep out of `ids.core`:
  - `DEFAULT_FEATURE_COLUMNS_PATH`
  - `DEFAULT_TRAINING_FEATURE_COLUMNS_PATH`
  - `load_default_contract`
  - `DEFAULT_BUNDLE_CONFIG_NAME`
  - `DEFAULT_ACTIVATION_RECORD_NAME`
  - `load_model_bundle_manifest`
  - `load_activation_record`
  - `resolve_active_model_bundle`
  - `build_bundle_status_payload`
  - `verify_candidate_bundle`
  - `promote_candidate_bundle`
  - `rollback_active_bundle`
  - `write_activation_record`

## Constraints
- `ids.core` must remain a leaf package. It cannot import `ids.runtime`, `ids.ops`, `ids.console`, or adapter modules.
- `ids.core` must not own repo-path defaults or artifact-location constants. Those are layout details, not contracts, and moving them would hard-code the current bundle/manifest storage shape into the shared layer.
- The bundle contract must remain single-source and fail-closed. No parallel override paths for model path, feature schema path, threshold, or activation record state.
- The feature contract must remain canonical and schema-locked. Training-manifest equality stays as a test-backed invariant, not something inferred by core from runtime defaults.
- Runtime and ops code may depend on core contracts, but core must not depend back on the runtime or ops layers.

## Recommended rules to embed into affected beads
- Put only pure contracts, dataclasses, and validators into `ids.core`; leave lifecycle, CLI, and filesystem mutation helpers outside core.
- Treat repo artifact paths as domain-local config, never as shared-core constants.
- Preserve the single activation contract: one manifest, one activation record, one verified runtime selection path.
- Preserve the feature-schema equality check as a regression test, not as a runtime fallback.
- Keep dependency direction strictly one-way: `ids_record_adapter`, runtime, and ops may import core; core may not import them.
