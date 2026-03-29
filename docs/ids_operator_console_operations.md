# IDS Operator Console Operations

## Production Topology

- App binds internally on `127.0.0.1:8765`
- Reverse proxy terminates TLS and forwards:
  - `Host`
  - `X-Forwarded-Proto`
  - `X-Forwarded-For`
- Public origin is declared explicitly with `IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL`

The operator console does not own model promotion state. It is visibility-first for the live sensor runtime and reads active-bundle metadata from ingested sensor summaries.

## Required Files

- Env file: `/etc/ids-operator-console/ids-operator-console.env`
- Secret key file: `/etc/ids-operator-console/console.secret`
- Optional Telegram bot token file: `/etc/ids-operator-console/telegram-bot-token.secret`

The repo does not store secret material. Backup/restore only records secret references.

## Model bundle visibility boundary

This feature adds read-only visibility for the active model bundle. The console is expected to surface:

- active bundle name/version
- activated timestamp
- compatibility state
- rollback target from the latest live sensor summary

Promotion and rollback remain explicit CLI operations outside the web UI:

- [ids_model_bundle_manage.py](F:/Work/IDS_ML_New/scripts/ids_model_bundle_manage.py)

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

`smoke` verifies the wired runtime contract of the console itself. Active bundle visibility appears in `/readyz` and the dashboard after the console has ingested at least one live sensor summary containing an `active_bundle` block.

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

For bundle visibility, also verify that `/readyz` contains `components.active_bundle` and that the dashboard shows the current bundle identity once fresh sensor summaries have been ingested.

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

If the database already contains ingested live sensor summaries, the backup also preserves the last known active bundle visibility state stored in those summary rows. The backup does not replace the live sensor activation record itself.

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

After restore, treat the console and the live sensor as separate readiness domains:

- console restore proves the web/database contract is healthy
- live sensor must still re-validate `/var/lib/ids-live-sensor/active_bundle.json` before the host is considered fully ready for IDS scoring

If you expect bundle visibility immediately after restore, make sure either:

- the restored database already contains recent summary rows with `active_bundle`, or
- the live sensor is restarted and allowed to emit a fresh summary after its own preflight succeeds

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

For this feature, operators should also inspect the `/readyz` payload body and confirm:

- `components.active_bundle.ok` reflects whether a summary-backed active bundle state is currently available
- `components.active_bundle.state.active_bundle_name` matches the sensor summary when one has been ingested

If smoke fails, treat that as a deployment blocker rather than a warning.

## Example operator checks

- run `python scripts/ids_operator_console_manage.py --database-path ... --json smoke`
- inspect `/readyz` for `components.active_bundle`
- verify the dashboard `Sensor Health` section shows active bundle, bundle status, activated-at, and rollback target
- confirm live sensor summaries are still being ingested into the console database
