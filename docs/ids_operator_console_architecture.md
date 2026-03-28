# IDS Operator Console Architecture (V1)

## Scope

`ids_operator_console` is a same-host operator service layered on top of the existing `ids_live_sensor` outputs. It does not replace the sensor and does not add IPS/control-plane behavior.

## Runtime Shape

- Producer: `ids_live_sensor` writes durable JSONL outputs (`alerts`, `quarantine`, `summary`).
- Consumer: `ids_operator_console` ingests those streams into an embedded SQLite store.
- Service: `FastAPI + Jinja` application served by `scripts/ids_operator_console_server.py`.
- Auth: single-admin signed-cookie session boundary with CSRF checks.
- Notifications: Telegram delivery is a decoupled path backed by durable delivery bookkeeping.

## Storage Boundary

The operator store (`scripts/ids_operator_console/db.py`) persists:

- alert records, triage status, notes, status history
- schema anomalies and summary snapshots
- ingest offsets with file identity (`inode`, `device`, offset)
- suppression rules for model-alert presentation/notification
- admin auth/session state
- notification delivery state (`pending/retry/sent/failed`, attempts, next retry, provider id)

## Ingest Contract

`scripts/ids_operator_console/ingest.py` enforces:

- source of truth is JSONL files (not journald)
- offsets commit only after newline-terminated records are parsed
- partial trailing lines are deferred until completion
- truncate/replace resets are detected via file identity + offset safety checks
- alert/anomaly/summary streams remain separated in storage

## Notification Contract

`scripts/ids_operator_console/notifications.py` follows failure-isolation rules:

- local operator persistence happens before outbound delivery
- candidate alerts come from triage/suppression-aware query helpers
- delivery attempts update durable bookkeeping each try
- retry/backoff is stored in DB so restarts do not lose state
- Telegram failure never deletes or hides local alert/anomaly state

## Deployment Contract

- unit file: `deploy/systemd/ids-operator-console.service`
- preflight gate: `scripts/ids_operator_console_preflight.py`
- preflight verifies exact-path runtime assumptions before `ExecStart`
- service remains same-host and Python-native to align with existing operational model
