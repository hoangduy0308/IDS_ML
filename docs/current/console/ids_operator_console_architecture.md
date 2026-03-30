# IDS Operator Console Architecture (Production Hardening)

## Scope

`ids_operator_console` remains a same-host operator service layered on top of `ids_live_sensor` outputs.
This hardening pass does not turn it into an IPS/control-plane component and does not expand into multi-host fleet orchestration.

## Runtime Contract

- Canonical app factory: `ids.console.web:create_operator_console_web_app`
- Service entrypoint: `scripts/ids_operator_console_server.py` as the phase-1 compatibility wrapper over `ids.console.web`
- Notification worker entrypoint: `scripts/ids_operator_console_manage.py notify-worker --poll-interval-seconds <seconds>` for supervised mode, or `notify-run-once` for a single maintenance cycle; the canonical implementation lives in `ids.ops.operator_console_manage`
- App topology: FastAPI + Jinja2 + SQLite, bound on loopback/internal network only
- Edge topology: reverse proxy terminates TLS and forwards `Host`, `X-Forwarded-Proto`, and `X-Forwarded-For`
- Canonical public origin: `IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL`

The runtime now fails closed when the operator database is missing, still on legacy schema, or has no bootstrapped admin user. Startup no longer mutates schema implicitly. Notification dispatch remains outside the FastAPI process and is owned by an explicit same-host worker contract.

## Config And Secrets

Config is centralized in `ids.console.config`.

- Non-secret runtime values come from environment or env-file style configuration.
- Sensitive values support secret-file references:
  - `IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE`
  - `IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE`
- Production requires:
  - non-placeholder secret
  - `IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL=https://...`
  - secure session cookie posture
  - explicit forwarded proxy trust configuration

## Schema And Bootstrap

Schema lifecycle is explicit:

- inspection/migration logic: `ids.console.migrations`
- admin/operator CLI: `ids.ops.operator_console_manage` with `scripts/ids_operator_console_manage.py` as the compatibility entrypoint
- worker-aware preflight gate: `ids.ops.operator_console_preflight` with `scripts/ids_operator_console_preflight.py` as the compatibility entrypoint

Expected operator flow:

1. `migrate --allow-bootstrap` for fresh install, or `migrate` for v1 upgrade
2. `bootstrap-admin`
3. `notify-status` to confirm whether Telegram is intentionally disabled or enabled
4. preflight
5. start the web service and, when Telegram is enabled, the notification worker service

Normal service startup verifies readiness but never auto-applies migrations.

## Health Model

- `/healthz`: lightweight liveness
- `/readyz`: readiness with component breakdown

Readiness distinguishes:

- config contract
- schema state
- admin bootstrap state
- upstream data-path health
- notification component state (`disabled`, `ok`, or `degraded`) without folding notification failures into the top-level `ready` boolean

## Backup And Restore

Operational backup/restore lives in `ids.console.ops`.

- Backup uses SQLite backup primitives against the live WAL database.
- Backup manifest records config and secret references, never secret material.
- Restore is offline-only and requires explicit operator confirmation.
- Restore validates that required secret references have been rebound before declaring success.
- Restored `notification_deliveries` remain part of the operator-facing contract: backlog, failed rows, and last-error visibility must stay intelligible after restore so operators can redrive rather than reconstruct state manually.

## Deployment Artifacts

- systemd unit: `deploy/systemd/ids-operator-console.service`
- notification worker unit: `deploy/systemd/ids-operator-console-notify.service`
- preflight gate: `scripts/ids_operator_console_preflight.py` as the compatibility entrypoint for `ids.ops.operator_console_preflight`
- reverse proxy example: `deploy/nginx/ids-operator-console.conf.example`
- operations runbook: `docs/ids_operator_console_operations.md`

These artifacts are intended to be reviewed together for `EXISTS / SUBSTANTIVE / WIRED`, not as independent placeholders.
