# Spike: ids_ml_new-z0t3

Result: YES

Question:
- Can canonical installed entrypoints replace wrapper-first operator commands while preserving wrapper compatibility and one operator path?

Decision:
- Yes, with one important constraint: the operator-console server still needs a canonical installed CLI target in `ids/*` rather than staying only in `scripts/ids_operator_console_server.py`.

Validated CLI mapping shape:
- `ids-stack` -> `ids.ops.same_host_stack_manage:main`
- `ids-model-bundle-manage` -> `ids.ops.model_bundle_manage:main`
- `ids-live-sensor` -> `ids.runtime.live_sensor:main`
- `ids-live-sensor-preflight` -> `ids.ops.live_sensor_preflight:main`
- `ids-operator-console-preflight` -> `ids.ops.operator_console_preflight:main`
- `ids-operator-console-manage` -> `ids.ops.operator_console_manage:main`
- Operator-console server needs a canonical installed CLI target under `ids/*` even though the app factory already lives in `ids.console.web`.

Evidence:
- Deploy assets are still wrapper-first today:
  - [ids-live-sensor.service](F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service)
  - [ids-operator-console.service](F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service)
  - [ids-operator-console-notify.service](F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console-notify.service)
- Ops docs are still wrapper-heavy:
  - [ids_same_host_stack_operations.md](F:/Work/IDS_ML_New/docs/current/operations/ids_same_host_stack_operations.md)
- Wrapper compatibility is low-risk because wrappers are already thin shims into canonical modules.

Constraints:
- This is not a metadata-only change. The operator-console server still lacks a first-class canonical installed CLI surface even though the real app factory is already canonical.
- The main migration risk is deploy/docs drift, not CLI feasibility itself.
- `scripts/*` should remain only as compatibility notes and smoke surfaces, never as a second equal operator path.
