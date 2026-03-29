# IDS Operator Console Architecture (Production Hardening)

## Scope

`ids_operator_console` remains a same-host operator service layered on top of `ids_live_sensor` outputs.
This hardening pass does not turn it into an IPS/control-plane component and does not expand into multi-host fleet orchestration.

## Runtime Contract

- Service entrypoint: `scripts/ids_operator_console_server.py`
- Canonical app factory: `scripts/ids_operator_console/web.py:create_operator_console_web_app`
- App topology: FastAPI + Jinja2 + SQLite, bound on loopback/internal network only
- Edge topology: reverse proxy terminates TLS and forwards `Host`, `X-Forwarded-Proto`, and `X-Forwarded-For`
- Canonical public origin: `IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL`

The runtime now fails closed when the operator database is missing, still on legacy schema, or has no bootstrapped admin user. Startup no longer mutates schema implicitly.

## Config And Secrets

Config is centralized in `scripts/ids_operator_console/config.py`.

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

- inspection/migration logic: `scripts/ids_operator_console/migrations.py`
- admin/operator CLI: `scripts/ids_operator_console_manage.py`

Expected operator flow:

1. `migrate --allow-bootstrap` for fresh install, or `migrate` for v1 upgrade
2. `bootstrap-admin`
3. preflight
4. start service

Normal service startup verifies readiness but never auto-applies migrations.

## Health Model

- `/healthz`: lightweight liveness
- `/readyz`: readiness with component breakdown

Readiness distinguishes:

- config contract
- schema state
- admin bootstrap state
- upstream data-path health

## Backup And Restore

Operational backup/restore lives in `scripts/ids_operator_console/ops.py`.

- Backup uses SQLite backup primitives against the live WAL database.
- Backup manifest records config and secret references, never secret material.
- Restore is offline-only and requires explicit operator confirmation.
- Restore validates that required secret references have been rebound before declaring success.

## Deployment Artifacts

- systemd unit: `deploy/systemd/ids-operator-console.service`
- preflight gate: `scripts/ids_operator_console_preflight.py`
- reverse proxy example: `deploy/nginx/ids-operator-console.conf.example`
- operations runbook: `docs/ids_operator_console_operations.md`

These artifacts are intended to be reviewed together for `EXISTS / SUBSTANTIVE / WIRED`, not as independent placeholders.
