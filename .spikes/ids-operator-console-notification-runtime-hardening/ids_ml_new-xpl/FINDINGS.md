# Spike Findings: ids_ml_new-xpl

**Question**: Can the notification worker own `ingest -> queue -> dispatch` without breaking failure isolation?

**Decision**: `YES`

## Evidence

- `scripts/ids_operator_console/ingest.py` already exposes `ingest_sensor_outputs_once()` and persists stream offsets, which makes the ingest phase restart-safe and deterministic for a same-host worker.
- `scripts/ids_operator_console/alerts.py` already narrows notification candidates through `list_alerts_for_notification()`, which applies suppression filtering and excludes terminal triage states.
- `scripts/ids_operator_console/db.py` already persists delivery rows in `notification_deliveries`, dedupes by `(channel, target, dedupe_key)`, and persists retry metadata such as `attempt_count`, `next_attempt_at`, `provider_message_id`, and `last_error`.
- `scripts/ids_operator_console/notifications.py` already isolates Telegram failures into `retry` or `failed` states via `dispatch_pending_telegram_notifications()` instead of mutating alerts or readiness state.
- `tests/test_ids_operator_console_notifications.py` already proves retryable failures keep local state intact and success marks rows `sent`.

## Constraints Locked By This Spike

- The final worker must not rely on `queue_and_dispatch_notifications()` as the production contract because that helper skips the ingest phase and does not express disabled-mode or status-snapshot semantics.
- The new runtime seam must orchestrate phases explicitly in this order: ingest refresh, queue candidates, dispatch due deliveries, emit status snapshot.
- Dispatch failure must remain delivery-local. It may degrade notification health, but it must not mutate alert triage state, break ingest offset persistence, or flip core console readiness.
- Disabled Telegram mode must short-circuit queue growth explicitly; the runtime layer cannot blindly call `queue_alert_notifications()` when notifications are intentionally off.

## Result

The planned runtime-core bead remains valid. The implementation needs a new orchestration layer, not a redesign of the existing notification primitives.
