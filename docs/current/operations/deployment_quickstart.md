# Deployment Quickstart

This is the fastest supported path for deploying the same-host IDS stack onto another Linux machine.

The deployment bundle is intentionally anchored on:

- installed `ids-*` console scripts from `pyproject.toml`
- repo checkout rooted at `/opt/ids_ml_new`
- systemd service units under `deploy/systemd/`
- lifecycle orchestration through `ids-stack`

## Release artifact

The repo now ships a deployment helper set under `ops/`:

- `ops/build_release.sh`
- `ops/install.sh`
- `ops/ids-operator-console.env.example`
- `ops/README-deploy.md`

Recommended flow:

1. Run `bash ./ops/build_release.sh` on the source/build machine.
2. Copy the resulting `ids_ml_new-<timestamp>.tar.gz` to the target host.
3. Extract it so the checkout lands at `/opt/ids_ml_new`.
4. Run `sudo bash /opt/ids_ml_new/ops/install.sh`.
5. Verify with `ids-stack --json preflight`, `status`, and `smoke`.

The release bundle is built using `git archive`, which exports only tracked files from the repository. Untracked and gitignored local files (secrets, credentials, `.claude/`, etc.) are excluded by construction. The only generated artifact added post-export is `wheelhouse/` for dependency wheels.

`ops/install.sh` is intentionally an in-place installer. It recreates `/opt/ids_ml_new/.venv`, installs pinned dependencies, then installs the app from the extracted checkout with `pip install -e /opt/ids_ml_new`. The installer also hardens the operator env file permissions (`0640 root:ids-operator`) regardless of how the file was originally created, and enables the notification worker service alongside the base services.

## Target-host install

`ops/install.sh` is the canonical installer. It has one supported path per mode.

Console-only install:

```bash
sudo bash /opt/ids_ml_new/ops/install.sh \
  --mode console-only \
  --create-secrets
```

Full-stack same-host install:

```bash
sudo bash /opt/ids_ml_new/ops/install.sh \
  --mode full-stack-same-host \
  --create-secrets \
  --bootstrap \
  --admin-password-file /secure/admin.password \
  --proxy-public-url https://console.example
```

`console-only` seeds `/etc/ids-operator-console/admin.password` when the file is absent and `--create-secrets` is set, then runs console migration, admin bootstrap, and service start through `ids-operator-console-manage` before it reports success.

The full-stack path bootstraps through the shipped bundled default artifact and keeps `ids-stack` as the canonical operator-facing bootstrap/readiness surface.

The same-host bootstrap surface underneath the installer remains `ids-stack`:

```bash
ids-stack \
  --repo-root /opt/ids_ml_new \
  --python-binary /opt/ids_ml_new/.venv/bin/python \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --dumpcap-binary /usr/bin/dumpcap \
  --extractor-command-prefix /opt/ids_ml_new/.venv/bin/python -m ids.runtime.extractor.offline_window_extractor \
  --spool-dir /var/lib/ids-live-sensor \
  --alerts-output-path /var/log/ids-live-sensor/ids_live_alerts.jsonl \
  --quarantine-output-path /var/log/ids-live-sensor/ids_live_quarantine.jsonl \
  --summary-output-path /var/log/ids-live-sensor/ids_live_sensor_summary.jsonl \
  --proxy-public-url https://console.example \
  --json bootstrap \
  --admin-username admin \
  --admin-password-file /secure/admin.password
```

The exact bundled-default artifact path for the canonical same-host bootstrap example lives in
`docs/current/operations/ids_same_host_stack_operations.md`.

The console-only readiness checks after install use the canonical console manage surface:

```bash
ids-operator-console-manage \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json status

ids-operator-console-manage \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json smoke

ids-operator-console-manage \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json notify-status
```

The packaged live-sensor helper default is the repository-backed extractor module:

```bash
/opt/ids_ml_new/.venv/bin/python -m ids.runtime.extractor.offline_window_extractor
```

`/opt/cicflowmeter/Cmd` remains a compatibility override, not the default install path.

## Telegram Notifications

Telegram remains optional. There are two configuration approaches:

### Settings UI (recommended)

After bootstrap, log into the dashboard and navigate to **Settings**. Enter the bot token and chat ID, click **Save**, then **Test** to verify. The notification worker picks up changes from the database every 30 seconds — no service restart needed.

The Settings page always shows the effective Telegram configuration using the same precedence rule as the runtime worker: database settings win, environment values serve as fallback. The page indicates the active source ("via database" or "via environment") so operators can see which config is in effect.

### Environment file (headless/initial setup)

Set `IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN` (or `_FILE`) and `IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID` in the env file before starting services. These values are used as fallback when no database settings exist.

### Notification worker

The installer enables `ids-operator-console-notify.service` alongside the base services by default. After a fresh install and reboot, the notification worker is already running. To verify:

```bash
systemctl status ids-operator-console-notify.service
```

If the service was not enabled during install (e.g. `--skip-service-enable` was used), enable it manually:

```bash
systemctl enable --now ids-operator-console-notify.service
```

Database settings (configured via Settings UI) take precedence over environment file values. If both sources are configured, the database wins.

If all Telegram values are omitted, notification state is intentionally `disabled`.
