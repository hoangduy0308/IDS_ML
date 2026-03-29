# IDS Operator Console Operations

## Production Topology

- App binds internally on `127.0.0.1:8765`
- Reverse proxy terminates TLS and forwards:
  - `Host`
  - `X-Forwarded-Proto`
  - `X-Forwarded-For`
- Public origin is declared explicitly with `IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL`

## Required Files

- Env file: `/etc/ids-operator-console/ids-operator-console.env`
- Secret key file: `/etc/ids-operator-console/console.secret`
- Optional Telegram bot token file: `/etc/ids-operator-console/telegram-bot-token.secret`

The repo does not store secret material. Backup/restore only records secret references.

## Fresh Bootstrap

1. Populate `/etc/ids-operator-console/ids-operator-console.env`
2. Write a non-placeholder secret into `/etc/ids-operator-console/console.secret`
3. Run:

```bash
python scripts/ids_operator_console_manage.py \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  migrate --allow-bootstrap
```

4. Bootstrap the admin credential:

```bash
python scripts/ids_operator_console_manage.py \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  bootstrap-admin --username admin --password-file /secure/path/admin.password
```

5. Start the service:

```bash
systemctl enable --now ids-operator-console.service
```

6. Run smoke:

```bash
python scripts/ids_operator_console_manage.py \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json smoke
```

## Upgrade From V1

1. Stop the service if it is already running.
2. Inspect current state:

```bash
python scripts/ids_operator_console_manage.py \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json status
```

3. Apply the explicit migration:

```bash
python scripts/ids_operator_console_manage.py \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  migrate
```

4. If the legacy DB never had an admin user, run `bootstrap-admin`.
5. Run preflight or restart the service.
6. Run `smoke` and verify `/readyz` returns ready.

## Backup

Online backup is allowed:

```bash
python scripts/ids_operator_console_manage.py \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json backup --output-dir /var/backups/ids-operator-console
```

The backup artifact contains:

- SQLite snapshot copied via SQLite backup API
- `manifest.json`
- config values needed for restore drill validation
- secret references only

## Restore Drill

Restore is offline-only. Do not restore over a running service.

1. Stop the service:

```bash
systemctl stop ids-operator-console.service
```

2. Ensure secret references are present again on the host.
3. Run restore:

```bash
python scripts/ids_operator_console_manage.py \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json restore \
  --backup-dir /var/backups/ids-operator-console/backup-YYYYMMDDTHHMMSSffffffZ \
  --service-stopped
```

4. Run smoke before restarting traffic.
5. Start the service and verify `/readyz`.

## Retention

Prune old backup directories by keeping the newest N:

```bash
python scripts/ids_operator_console_manage.py \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json prune-retention \
  --backup-root /var/backups/ids-operator-console \
  --keep-last 7
```

## Smoke Expectations

`smoke` is expected to verify:

- `/healthz` returns `200`
- `/readyz` returns `200`
- root redirect is wired to `/login`
- config/schema/admin bootstrap contract is still valid

If smoke fails, treat that as a deployment blocker rather than a warning.
