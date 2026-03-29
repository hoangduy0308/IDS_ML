# Spike Findings: ids_ml_new-tz9

**Question:** Can `model_bundle.json` evolve into a versioned compatibility contract without breaking current bundle consumers?
**Result:** YES
**Date:** 2026-03-29

## Evidence

- [`scripts/package_final_model.py`](F:/Work/IDS_ML_New/scripts/package_final_model.py) already emits `model_bundle.json` as the canonical bundle manifest.
- [`scripts/ids_inference.py`](F:/Work/IDS_ML_New/scripts/ids_inference.py) already resolves bundle-backed inference through `IDSModelConfig.from_bundle(...)` and `from_config_path(...)`.
- The current manifest at [`artifacts/final_model/catboost_full_data_v1/model_bundle.json`](F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1/model_bundle.json) already contains the core fields needed for in-place evolution: model artifact, feature schema file, threshold, labels, metrics, and provenance.

## Conclusion

The repo already treats `model_bundle.json` as the canonical on-disk bundle manifest, so the lowest-risk path is to evolve that file in place rather than introduce a dual-manifest reader. The current consumers are local repo code that will be updated in the same feature, which keeps migration blast radius contained.

## Locked Constraints For Execution

- Add an explicit manifest version field and a compatibility block to `model_bundle.json`; do not create a second production manifest unless implementation evidence forces it.
- Preserve the existing bundle fields (`model_artifact`, `feature_columns_file`, `threshold`, labels) during the migration so loader changes can remain additive first.
- Compatibility validation must prove schema/config/inference-contract match before runtime accepts the bundle.
- Production bundle resolution must fail closed when compatibility metadata is missing or mismatched.

## Beads Affected

- `ids_ml_new-hup.1`
- `ids_ml_new-hup.2`
- `ids_ml_new-hup.3`
