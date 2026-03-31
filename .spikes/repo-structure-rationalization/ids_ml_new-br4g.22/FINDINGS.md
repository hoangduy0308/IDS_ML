# Question
Can preflight, manage, and same-host stack flows move under `ids.ops` while preserving CLI semantics and deploy/runbook compatibility?

# Evidence
- The target surfaces are already CLI front-ends with stable parser/subcommand contracts and explicit exit behavior: [scripts/ids_live_sensor_preflight.py](F:/Work/IDS_ML_New/scripts/ids_live_sensor_preflight.py#L13), [scripts/ids_operator_console_preflight.py](F:/Work/IDS_ML_New/scripts/ids_operator_console_preflight.py#L106), [scripts/ids_model_bundle_manage.py](F:/Work/IDS_ML_New/scripts/ids_model_bundle_manage.py#L32), [scripts/ids_operator_console_manage.py](F:/Work/IDS_ML_New/scripts/ids_operator_console_manage.py#L76), and [scripts/ids_same_host_stack_manage.py](F:/Work/IDS_ML_New/scripts/ids_same_host_stack_manage.py#L34).
- The same-host stack implementation is already split from its CLI shell: [scripts/ids_same_host_stack.py](F:/Work/IDS_ML_New/scripts/ids_same_host_stack.py#L480) owns `validate_stack_preflight`, `run_stack_bootstrap`, `run_stack_recovery`, and `run_stack_post_restore_check`, while [scripts/ids_same_host_stack_manage.py](F:/Work/IDS_ML_New/scripts/ids_same_host_stack_manage.py#L183) only parses args and dispatches.
- Deploy and runbook surfaces are hardcoded to the current `scripts/*.py` paths, not to import locations: [deploy/systemd/ids-live-sensor.service](F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service#L19), [deploy/systemd/ids-operator-console.service](F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service#L30), [deploy/systemd/ids-operator-console-notify.service](F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console-notify.service#L28), and [docs/ids_same_host_stack_operations.md](F:/Work/IDS_ML_New/docs/ids_same_host_stack_operations.md#L20).
- Tests pin these exact surfaces and command strings, including deploy wiring and runbook compatibility: [tests/test_ids_operator_console_preflight.py](F:/Work/IDS_ML_New/tests/test_ids_operator_console_preflight.py#L110) and [tests/test_ids_same_host_stack_manage.py](F:/Work/IDS_ML_New/tests/test_ids_same_host_stack_manage.py#L1408).

# Decision (YES)
Yes. These flows can move under `ids.ops` without breaking CLI semantics or deploy/runbook compatibility, provided the existing `scripts/*.py` entrypoints remain as thin compatibility wrappers and the argv contract stays unchanged.

# CLI/deploy constraints
- Keep `/opt/ids_ml_new/scripts/...` entrypoints valid for systemd units and runbooks until wrappers and docs are updated together.
- Preserve subcommand names, flag names, JSON output mode, and the current `0/2` readiness exit-code convention.
- Preserve the multi-token `--extractor-command-prefix` handling exactly as-is.
- Keep `ids.ops` limited to preflight, manage, and stack orchestration; do not mix runtime serving or console app code into that package.
- Do not change default entrypoint paths inside same-host stack orchestration unless the deploy artifacts change in the same release.

# Recommended rules to embed into affected beads
- Preserve wrapper files for every moved CLI in phase 1.
- Add regression tests for exact CLI strings, JSON mode, and exit codes before changing import locations.
- Update systemd units and runbooks only after wrapper-based compatibility is proven.
- Treat `ids.ops` as orchestration/maintenance only; keep runtime and console code in their own packages.
- Never change command semantics to make the move look cleaner if that would break existing automation.
