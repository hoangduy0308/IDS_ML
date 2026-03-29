# Spike Findings: Legacy Route Redirect Contract

**Spike ID:** ids_ml_new-u8xd
**Question:** Do legacy route redirects preserve operator-console runtime, tests, and docs contracts?
**Result:** YES

## Evidence Reviewed

- `scripts/ids_operator_console/web.py`
- `scripts/ids_operator_console_server.py`
- `tests/test_ids_operator_console_web.py`
- `tests/test_ids_operator_console_config.py`
- `docs/ids_operator_console_operations.md`
- existing route references found via `rg` across `scripts/`, `tests/`, and `docs/`

## Determination

Redirecting `/dashboard` -> `/overview` and `/anomalies` -> `/operations` is feasible without breaking the same-host runtime model, as long as the canonical app factory remains `create_operator_console_web_app()` and the contract changes are reflected in route tests and operator docs.

## Constraints Required For YES

- Keep `scripts/ids_operator_console_server.py` unchanged as the canonical runtime entrypoint importing `create_operator_console_web_app()`.
- Update `tests/test_ids_operator_console_web.py` to assert the new canonical routes and the legacy redirects explicitly.
- Update `tests/test_ids_operator_console_config.py` if route-level assertions still hard-code `/dashboard`.
- Update `docs/ids_operator_console_operations.md` anywhere the old route vocabulary is part of the operator contract.
- Update `scripts/ids_operator_console/templates/alert_detail.html` back-navigation so it points at the new Alerts workflow instead of the legacy dashboard queue.

## Why This Is Not A NO

- The runtime contract does not depend on the route names themselves; it depends on the canonical app factory and wired route tree.
- The current codebase already centralizes route construction inside `web.py`, so redirects can be implemented in one place.
- The blast radius is real, but it is bounded to routes, tests, templates, and docs already identified in planning.
