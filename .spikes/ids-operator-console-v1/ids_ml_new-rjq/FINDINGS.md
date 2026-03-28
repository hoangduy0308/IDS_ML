# Spike Findings: ids_ml_new-rjq

## Question

Can FastAPI + Jinja fit this script-first repo without adding a Node toolchain?

## Result

**YES**

## Evidence

- The current local environment already has the required Python-side runtime pieces importable: `fastapi`, `starlette`, `jinja2`, `uvicorn`, `itsdangerous`, and `python_multipart`.
- The existing repo already uses script entrypoints with explicit repo-root import bootstrapping in [scripts/ids_live_sensor.py](F:/Work/IDS_ML_New/scripts/ids_live_sensor.py), so a separate `ids_operator_console_server.py` entrypoint can follow the same packaging posture instead of forcing a new build system.
- The current producer-side deployment is already same-host, env-driven, and systemd-managed in [ids-live-sensor.service](F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service), which matches the proposed operator-console deployment shape.
- Official FastAPI docs support server-rendered Jinja templates and mounted static assets in the same app:
  - [FastAPI templates](https://fastapi.tiangolo.com/advanced/templates/)
  - [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/)

## Validated Constraints

1. The operator console should stay server-rendered for v1 and must not introduce a separate Node/SPA toolchain.
2. The foundation bead should expose a minimal app/bootstrap boundary that can be imported before dashboard/business modules are complete.
3. The service should follow the repo's existing `scripts/` entrypoint style and same-host env-driven deployment posture.
4. Login form handling may assume standard form posts because `python-multipart` is already available in the environment.

## Impact on Plan

- The FastAPI + Jinja foundation remains viable.
- Validation is not blocked on framework/toolchain introduction.
- Execution beads should lock around a Python-native app factory, script-style entrypoint, and no-SPA boundary.
