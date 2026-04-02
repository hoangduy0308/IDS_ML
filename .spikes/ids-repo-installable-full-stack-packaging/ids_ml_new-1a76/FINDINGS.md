# Spike: ids_ml_new-1a76

Result: YES

Question:
- Can same-host stack orchestration switch off repo-root script paths without changing lifecycle payload contracts?

Decision:
- Yes. Keep the lifecycle contract in `ids/ops/same_host_stack.py` and change only the invocation wiring in `ids/ops/same_host_stack_manage.py`.

Validated subordinate-command strategy:
- Replace default `repo_root/scripts/*.py` entrypoints with canonical invocation specs, preferably command-prefix or module-execution tuples.
- Representative targets:
  - `python -m ids.ops.model_bundle_manage`
  - `python -m ids.ops.operator_console_manage`
  - canonical operator-console server entrypoint once exposed under `ids/*`
- Preserve `run_stack_bootstrap()` and related lifecycle functions so payloads and exit semantics stay unchanged.

Evidence:
- Affected code paths:
  - [same_host_stack_manage.py](F:/Work/IDS_ML_New/ids/ops/same_host_stack_manage.py)
  - [same_host_stack.py](F:/Work/IDS_ML_New/ids/ops/same_host_stack.py)
  - [operator_console_preflight.py](F:/Work/IDS_ML_New/ids/ops/operator_console_preflight.py)
- Contract tests already exist around payload/exit behavior:
  - [test_ids_same_host_stack_manage.py](F:/Work/IDS_ML_New/tests/ops/test_ids_same_host_stack_manage.py)

Constraints:
- Current defaults in `same_host_stack_manage.py` still hardcode `repo_root/scripts/*.py`, so the canonical seam is not real yet.
- `validate_stack_preflight()` currently reasons about file-style entrypoints; preflight must evolve alongside the invocation strategy.
- Existing tests and fixtures still assume `scripts/*.py`, so they need to be migrated without weakening lifecycle assertions.
