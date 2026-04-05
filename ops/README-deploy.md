# IDS Same-Host Deploy Bundle

This directory contains the release and install helpers for the fastest supported same-host deployment path.

## Files

- `build_release.sh`: build a sanitized release tarball plus an optional dependency `wheelhouse/`
- `install.sh`: run the in-place installer from the extracted checkout at `/opt/ids_ml_new`
- `ids-operator-console.env.example`: seed env file for `/etc/ids-operator-console/ids-operator-console.env`

## Golden Path

### 1. Build a release bundle

Run on the build/source machine:

```bash
bash ./ops/build_release.sh
```

The script emits:

- `dist/release/ids_ml_new-<timestamp>.tar.gz`
- a tarball that already includes the repo checkout and `wheelhouse/` for dependency installation

### 2. Copy the archive to the target host

Example:

```bash
scp dist/release/ids_ml_new-*.tar.gz root@target:/tmp/
```

### 3. Extract under `/opt/ids_ml_new`

Run on the target host:

```bash
mkdir -p /opt
tar -xzf /tmp/ids_ml_new-*.tar.gz -C /opt
```

The archive is expected to create `/opt/ids_ml_new`. Keep that path as-is; the service units, env template, and docs treat `/opt/ids_ml_new` as the canonical checkout root.

### 4. Install onto the target host

Seed the env file first if you want to edit it before bootstrap:

```bash
cp /opt/ids_ml_new/ops/ids-operator-console.env.example /etc/ids-operator-console/ids-operator-console.env
```

Then install in the supported mode you need:

```bash
sudo bash /opt/ids_ml_new/ops/install.sh --create-secrets
```

This creates a fresh target venv and installs the app via:

```bash
pip install -e /opt/ids_ml_new
```

Console-only is the minimal supported path:

```bash
sudo bash /opt/ids_ml_new/ops/install.sh \
  --mode console-only \
  --create-secrets
```

That path seeds `/etc/ids-operator-console/admin.password` when the file is absent, runs console schema migration and admin bootstrap through `ids-operator-console-manage`, then starts the console and notification services.

Full-stack same-host installs bootstrap the shipped bundled default artifact automatically:

```bash
sudo bash /opt/ids_ml_new/ops/install.sh \
  --mode full-stack-same-host \
  --create-secrets \
  --bootstrap \
  --admin-password-file /secure/admin.password \
  --proxy-public-url https://console.example
```

## Telegram Notifications

Telegram is optional. There are two ways to configure it:

### Option A: Settings UI (recommended for ongoing management)

1. Start the notification worker:
   ```bash
   systemctl enable --now ids-operator-console-notify.service
   ```
2. Log into the operator console dashboard.
3. Click **Settings** in the sidebar.
4. Enter the bot token and chat ID, then click **Save**.
5. Click **Test** to verify the configuration works.

The notification worker checks the database every 30 seconds and picks up new settings automatically — no restart needed.

### Option B: Environment file (for initial/headless bootstrap)

1. Set `IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN` (or `_FILE`) and `IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID` in `/etc/ids-operator-console/ids-operator-console.env`.
2. Start the worker:
   ```bash
   systemctl enable --now ids-operator-console-notify.service
   ```

### Config precedence

Settings saved via the Settings UI (stored in the database) take precedence over environment file values. If both are set, the database values win.

### Check status

```bash
/opt/ids_ml_new/.venv/bin/ids-operator-console-manage \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json notify-status
```

## Canonical verification

After install or bootstrap, use the installed `ids-*` commands:

```bash
/opt/ids_ml_new/.venv/bin/ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json preflight

/opt/ids_ml_new/.venv/bin/ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json status

/opt/ids_ml_new/.venv/bin/ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --proxy-public-url https://console.example \
  --json smoke
```

If `smoke` returns degraded, treat it as a deployment blocker.
