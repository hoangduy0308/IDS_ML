STATUS: validated-approved
FEATURE: ids-repo-installable-full-stack-packaging
SKILL: swarming
PHASE: swarm-initializing
VALIDATED_AT: 2026-04-01T13:35:00+07:00

EPIC:
- ID: ids_ml_new-axd0
- Topic: epic-ids_ml_new-axd0
- Coordinator: CrimsonBadger
- Status: approved-for-execution

REVIEW_RESULTS:
- Prior blocking review bead resolved: ids_ml_new-8asd.7
- Prior non-blocking review beads resolved: ids_ml_new-37yb, ids_ml_new-c5sj, ids_ml_new-k66t, ids_ml_new-gahx
- Second-pass fresh-eyes review found no new P1 issues and no security findings.
- Follow-up review beads opened:
  - `ids_ml_new-gqqv` Harden repo-installable proof against ambient site-packages leaks
  - `ids_ml_new-c7jb` Cover fail-closed realtime pipeline feature-columns resolution
  - `ids_ml_new-c8i7` Add negative module-validation coverage for operator and stack preflight
  - `ids_ml_new-wtj1` Deduplicate module import validation helpers across ops preflight paths
  - `ids_ml_new-axic` Make shared repo-root path resolution fully explicit
  - `ids_ml_new-lkh3` Add stack smoke coverage for 303 redirect acceptance

VERIFICATION:
- Focused review suite:
  - `python -m pytest tests/ops/test_ids_repo_installable_bootstrap_proof.py tests/ops/test_ids_repo_installable_surface.py tests/ops/test_ids_same_host_stack_manage.py tests/ops/test_ids_operator_console_preflight.py tests/ops/test_ids_operator_console_ops.py tests/runtime/test_ids_inference.py tests/runtime/test_ids_realtime_pipeline.py tests/core/test_ids_path_defaults.py tests/docs/test_docs_path_smoke.py -q`
  - Result: `96 passed`
- Widened feature suite:
  - `python -m pytest tests/ops/test_ids_repo_installable_bootstrap_proof.py tests/ops/test_ids_repo_installable_surface.py tests/docs/test_docs_path_smoke.py tests/runtime/test_ids_runtime_wrapper_smoke.py tests/ml/test_ml_workflow_wrapper_smoke.py tests/runtime/test_ids_inference.py tests/runtime/test_ids_realtime_pipeline.py tests/runtime/test_ids_record_adapter.py tests/ops/test_ids_same_host_stack_manage.py tests/ops/test_ids_operator_console_preflight.py tests/ops/test_ids_operator_console_ops.py tests/ops/test_ids_live_sensor_preflight.py tests/ops/test_ids_model_bundle_manage.py tests/core/test_ids_path_defaults.py -q`
  - Result: `206 passed`
- Known non-blocking environment note:
  - `pytest_asyncio` emits a deprecation warning about `asyncio_default_fixture_loop_scope`, but all invoked suites returned exit code `0`.

KEY_FIXES:
- Same-host stack subordinate execution now uses canonical `ids.*` module surfaces rather than repo `.py` source paths.
- Operator-console preflight validates module importability through the selected interpreter instead of source-file entrypoints.
- Canonical runtime entrypoints fail closed through the activation-record contract unless explicit dev overrides are supplied.
- Shared repo-root path defaults now have explicit Linux-root vs checkout-root behavior with direct tests.
- Bundle runbook now uses Linux same-host canonical examples only.
- Final bootstrap proof now installs the repo into an isolated venv and executes real installed `ids-stack` / `ids-model-bundle-manage` commands.

ACTIVE_WORKERS:
- BlueHarbor — subagent `Planck` — startup hint `ids_ml_new-wtj1`
- SapphireElk — subagent `Kant` — startup hint `ids_ml_new-c7jb`
- AmberGrove — subagent `Pauli` — startup hint `ids_ml_new-gqqv`
- IndigoReef — subagent `Einstein` — startup hint `ids_ml_new-axic`

BLOCKERS:
- `SapphireElk` reported reservation conflict on `ids_ml_new-wtj1` against ops files held by other workers; overseer requested release/narrowing and explicit claim messages on thread `ids_ml_new-axd0`.

HANDOFF:
- Validation approved by user.
- Swarm root: `ids_ml_new-axd0`
- Actionable wave at swarm start: `ids_ml_new-wtj1`, `ids_ml_new-c7jb`, `ids_ml_new-gqqv`, `ids_ml_new-axic`
