# Spike: ids_ml_new-awn2

Result: YES

Question:
- Can production-facing runtime and bundle commands share one Linux path-default contract without reopening activation or path-safety seams?

Decision:
- Yes, as long as the shared helper only normalizes defaults and does not weaken the activation-record contract or path-authorization boundaries.

In-scope production commands:
- `ids.runtime.inference`
- `ids.runtime.realtime_pipeline`
- `ids.runtime.live_sensor`
- `ids.runtime.live_sensor_health`
- `ids.runtime.adapter.record_adapter` if it remains in the packaged host ingest path
- `ml_pipeline.packaging.package_final_model` for bundle staging/output defaults only, not for production activation semantics

Explicit exclusions / compatibility-only defaults:
- Raw `--model-path`, `--feature-columns-path`, and `--threshold` fallback behavior in runtime CLIs remain compatibility/dev-only, not the production story.
- Hardcoded `F:\Work\IDS_ML_New\...` defaults in `ml_pipeline.packaging.package_final_model` are workflow compatibility defaults today and should not define production activation behavior.
- Direct `bundle_root` or config-path usage can remain an operator/tooling seam, but production still resolves the active bundle from the activation record.

Evidence:
- The runtime path already depends on activation-record semantics in canonical bundle handling.
- The production-facing seams sit under:
  - [inference.py](F:/Work/IDS_ML_New/ids/runtime/inference.py)
  - [realtime_pipeline.py](F:/Work/IDS_ML_New/ids/runtime/realtime_pipeline.py)
  - [record_adapter.py](F:/Work/IDS_ML_New/ids/runtime/adapter/record_adapter.py)
  - [package_final_model.py](F:/Work/IDS_ML_New/ml_pipeline/packaging/package_final_model.py)

Constraints:
- Do not reintroduce a split production story where runtime can pick model/schema/threshold independently of `verify/promote -> active_bundle.json`.
- Path normalization and path authorization must remain separate.
- Secrets and deployment-local values must stay externalized to env/config/operator input rather than becoming package defaults.
