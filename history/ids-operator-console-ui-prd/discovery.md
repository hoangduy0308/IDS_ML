# Discovery — IDS Operator Console UI PRD

Generated: 2026-04-01

## Architecture Snapshot

Source: `gkg repo_map` on `ids/console`, `ids/runtime`, `ids/ops`, `ml_pipeline`

- Top UI module: `ids/console`
- Runtime data producers: `ids/runtime`
- Operational command surfaces: `ids/ops`
- Model build/training pipeline: `ml_pipeline`

Key directories:

- `ids/console/static`
- `ids/console/templates`
- `ids/ops`
- `ids/runtime`
- `ml_pipeline/packaging`
- `ml_pipeline/training`

Architecture summary:

- Current web UI is concentrated in the operator console, not spread across the whole repo.
- Runtime and operations are mostly CLI/service-oriented surfaces that feed or validate the console.
- The console is the visibility layer for same-host IDS operation.

## Existing Patterns

Query set via `gkg search_codebase_definitions`:

- `create_operator_console_web_app`
- `overview`
- `operations_page`
- `reports_page`
- `alert_detail`
- `login_page`
- `require_authenticated_redirect`
- `build_readiness_payload`
- `active_bundle`

Matches and pattern summary:

- `ids/console/web.py`:
  - `create_operator_console_web_app`
  - `overview_page`
  - `alerts_page`
  - `operations_page`
  - `reports_page`
  - `alert_detail`
  - Pattern: one FastAPI app factory renders all HTML surfaces and related JSON endpoints.
- `ids/console/config.py`:
  - `OperatorConsoleConfig`
  - Pattern: same-host config contract with strict production-safe cookie/base-url rules.
- `ids/console/health.py`:
  - `build_readiness_payload`
  - Pattern: readiness is broken into explicit components instead of one opaque health flag.
- `ids/console/reporting.py`:
  - `build_report_bundle`
  - `build_report_rollup`
  - Pattern: reports are table/rollup-first, built from alerts, anomalies, and summary rows.
- `ids/ops/same_host_stack.py`:
  - `build_stack_status_payload`
  - Pattern: stack diagnosis keeps failure domains explicit and machine-readable.
- `ids/ops/model_bundle_lifecycle.py`:
  - `promote_candidate_bundle`
  - `rollback_active_bundle`
  - Pattern: bundle lifecycle exists, but as CLI/ops flow rather than current web UI actions.

## Dependency Graph

File: `ids/console/web.py`

Imports:

- `fastapi`, `fastapi.responses`, `fastapi.templating`
- `starlette.middleware.sessions`
- `ids.console.alerts`
- `ids.console.auth`
- `ids.console.config`
- `ids.console.db`
- `ids.console.health`
- `ids.console.migrations`
- `ids.console.reporting`

Imported by / wired through:

- `scripts/ids_operator_console_server.py`
- tests under `tests/console/*`

Dependency summary:

- UI pages depend on store-backed alert/anomaly/summary reads plus readiness payload generation.
- Session auth and CSRF are already present, so the design can assume authenticated server-rendered workflows.
- Report, health, and bundle visibility are already available in backend data contracts.

## Product Boundary Confirmed From Code

- Current real UI surface: operator console only.
- Current HTML pages:
  - `/login`
  - `/overview`
  - `/alerts`
  - `/alerts/{alert_id}`
  - `/operations`
  - `/reports`
- Current JSON surfaces:
  - `/healthz`
  - `/readyz`
  - `/api/v1/console/snapshot`
  - `/api/v1/alerts`
  - `/api/v1/anomalies`
  - `/api/v1/summaries`

Out-of-scope for the current UI baseline:

- model promote / rollback actions
- service restart / recovery actions
- schema migration / bootstrap actions
- multi-host fleet management
- IPS or active response controls

## Design Implications

- The UI should optimize for fast reading and triage, not for broad mutation-heavy admin workflows.
- Alert signal and operational anomaly signal must stay visually separate.
- Active bundle visibility belongs in the UI because the data already exists, but bundle mutation should remain outside the web UI for now.
- A future sensor selector is technically plausible because JSON APIs already accept `sensor_id`, even though the current templates do not expose that control.
