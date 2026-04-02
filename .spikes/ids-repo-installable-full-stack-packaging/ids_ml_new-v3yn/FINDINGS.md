# Spike: ids_ml_new-v3yn

Result: YES

Question:
- Can one repo-root `pyproject.toml` install the canonical IDS product surface and package console assets without breaking checkout wrapper smoke?

Decision:
- Yes for phase-1 `editable checkout install`.

Validated shape:
- Add one repo-root build backend and package discovery for `ids` and `ml_pipeline`.
- Register installed console entrypoints directly to canonical modules.
- Package `ids.console` assets explicitly:
  - `templates/**/*.html`
  - `static/*.css`
  - `static/*.js`
- Keep `scripts/*` unchanged as compatibility wrappers only.

Evidence:
- [ids/__init__.py](F:/Work/IDS_ML_New/ids/__init__.py) already defines `ids` as canonical and `scripts/*` as compatibility-only.
- [ids_inference.py](F:/Work/IDS_ML_New/scripts/ids_inference.py) is a thin bootstrap wrapper into `ids.runtime.inference`.
- [ids_operator_console_server.py](F:/Work/IDS_ML_New/scripts/ids_operator_console_server.py) already boots the canonical app factory from `ids.console.web`.
- Canonical console assets already live under:
  - [templates](F:/Work/IDS_ML_New/ids/console/templates)
  - [static](F:/Work/IDS_ML_New/ids/console/static)
- Existing wrapper smoke only exercises repo-checkout wrapper behavior:
  - [test_ids_runtime_wrapper_smoke.py](F:/Work/IDS_ML_New/tests/runtime/test_ids_runtime_wrapper_smoke.py)
  - [test_ml_workflow_wrapper_smoke.py](F:/Work/IDS_ML_New/tests/ml/test_ml_workflow_wrapper_smoke.py)

Constraints:
- This spike validates editable install only, not wheel/sdist.
- If `ml_pipeline.packaging.package_final_model` remains an installed command, package discovery must include `ml_pipeline`.
- Wrapper smoke still assumes the repo checkout exists, which is acceptable because wrappers are compatibility-only.
- Package-data config is mandatory; otherwise operator-console code can install without its templates/static payload.
