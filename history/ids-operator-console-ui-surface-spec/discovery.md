# Discovery — IDS Operator Console UI Surface Spec

Generated: 2026-04-01

## gkg Route + API Snapshot

Definitions found via `gkg search_codebase_definitions`:

- `create_operator_console_web_app.healthz`
- `create_operator_console_web_app.readyz`
- `create_operator_console_web_app.alerts_page`
- `create_operator_console_web_app.alert_detail`
- `create_operator_console_web_app.api_console_snapshot`
- `create_operator_console_web_app.api_alerts`
- `create_operator_console_web_app.api_anomalies`
- `create_operator_console_web_app.api_summaries`
- `build_liveness_payload`
- `build_readiness_payload`
- `build_report_bundle`
- `transition_alert_status`
- `add_investigation_note`

## Key Findings

- HTML surface is server-rendered and session-authenticated.
- JSON surface is authenticated via the same session and returns `401` instead of redirect when unauthenticated.
- UI data comes from three primary record families:
  - `alerts`
  - `anomalies`
  - `summaries`
- Health/readiness are separate from summary-backed snapshots and should not be conflated in UI.
- Notification degradation does not flip top-level readiness by itself.
- Active bundle visibility is summary-backed and may legitimately be absent even when the console is otherwise ready.

## Schema-Level Facts From `db.py`

Tables directly relevant to UI:

- `alerts`
- `anomalies`
- `summaries`
- `alert_notes`
- `alert_status_history`
- `suppression_rules`
- `notification_deliveries`

Field-level implications:

- alert triage state is persisted in `alerts.triage_status`
- triage timeline is stored separately in `alert_status_history`
- notes are stored separately in `alert_notes`
- suppression is a presentation/notification concern driven by `suppression_rules`, not a destructive mutation of alert payload
- summaries are upserted per `(sensor_id, summary_ts)`

## UI-Critical Behavioral Facts

- `/overview` loads alerts with `include_suppressed=True`, limit `8`
- `/alerts` loads alerts with `include_suppressed=True`, limit `200`
- `/operations` loads anomalies limit `200`
- `/reports` builds a report bundle with:
  - alerts limit `200`
  - anomalies limit `100`
  - summaries limit `100`
  - `include_suppressed_alerts=True`
- `/api/v1/console/snapshot` supports sensor filtering and returns:
  - alerts limit `500`
  - anomalies limit `500`
  - summaries limit `200`
- `/api/v1/alerts` supports:
  - `sensor_id`
  - `triage_status`
  - `include_suppressed`
- `/api/v1/anomalies` supports `sensor_id`
- `/api/v1/summaries` supports `sensor_id`

## Authentication / CSRF Facts

- unauthenticated HTML routes redirect `303` to `/login`
- unauthenticated JSON routes return `401 Authentication required`
- mutating form routes require `csrf_token`
- login sets secure session cookie posture in production

## Data Modeling Facts The UI Must Respect

- triage states are exactly:
  - `new`
  - `acknowledged`
  - `investigating`
  - `resolved`
  - `false_positive`
- notification state can be:
  - `disabled`
  - `ok`
  - `degraded`
  - `misconfigured`
- readiness component detail exists only when `include_sensitive=True`
- public `healthz` / `readyz` payloads are intentionally redacted
