STATUS: swarming-complete
FEATURE: ids_ml_new-8sg2-review-followup
SKILL: swarming
PHASE: swarm-complete
EPIC_ID: ids_ml_new-8sg2
LAST_UPDATED: 2026-04-02T22:15:00+07:00

PURPOSE:
- Execute the approved review-follow-up swarm for the remaining open beads under epic ids_ml_new-8sg2.
- Preserve canonical ids/* behavior while tightening the compatibility-wrapper and bootstrap trust-gate contracts.

ARCHITECTURE_CONTEXT:
- The repo is a same-host IDS stack: model-bundle activation and live-sensor runtime feed the operator console.
- Canonical product/runtime behavior lives under ids/*; scripts/* entrypoints are compatibility-only wrappers.
- The current open work spans two independent surfaces:
- ops/bootstrap trust gating in ids/ops/same_host_stack.py + tests/ops/test_ids_same_host_stack_manage.py
- console wrapper/runtime contract coverage in scripts/ids_operator_console_server.py + tests/console/test_ids_operator_console_config.py, with ids_ml_new-2ypm blocked behind ids_ml_new-ms26

READY_BEADS:
- none

BLOCKED_BEADS:
- none

ACTIVE_WORKERS:
- none

NEXT:
- Swarm complete for epic ids_ml_new-8sg2
- Next skill: khuym:reviewing
- Final coordinator verification: python -m pytest tests/console/test_ids_operator_console_config.py tests/ops/test_ids_same_host_stack_manage.py -q -> 69 passed
