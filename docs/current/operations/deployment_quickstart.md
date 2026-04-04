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

## Target-host bootstrap

The canonical target-host bootstrap still goes through `ids-stack`:

```bash
ids-stack \
  --repo-root /opt/ids_ml_new \
  --python-binary /opt/ids_ml_new/.venv/bin/python \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --dumpcap-binary /usr/bin/dumpcap \
  --extractor-command-prefix /opt/cicflowmeter/Cmd \
  --spool-dir /var/lib/ids-live-sensor \
  --alerts-output-path /var/log/ids-live-sensor/ids_live_alerts.jsonl \
  --quarantine-output-path /var/log/ids-live-sensor/ids_live_quarantine.jsonl \
  --summary-output-path /var/log/ids-live-sensor/ids_live_sensor_summary.jsonl \
  --proxy-public-url https://console.example \
  --json bootstrap \
  --candidate-bundle-root /opt/ids_ml_new/artifacts/final_model/candidate_bundle \
  --admin-username admin \
  --admin-password-file /secure/admin.password
```

`ops/install.sh --bootstrap` is a convenience wrapper around this contract. It does not replace `ids-stack` as the canonical operator path.

If the host is bootstrapping directly from the bundle currently shipped in this repo checkout instead of a separately staged `candidate_bundle`, pass `--candidate-bundle-root /opt/ids_ml_new/artifacts/final_model/catboost_full_data_v1` explicitly.

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
