# Linux Prerequisites

System packages required before running the IDS same-host stack installer.

## Required Packages

### Python 3.11+

The application runtime. The installer creates a dedicated virtual environment at `/opt/ids_ml_new/.venv`.

```bash
# Ubuntu 22.04+ / Debian 12+
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev python3-pip

# Verify
python3.11 --version
python3.11 -m pip --version
```

### Wireshark / dumpcap

Live packet capture for the IDS sensor. The `dumpcap` binary must be available.

```bash
sudo apt install wireshark-common
# Or for a lighter install:
sudo apt install tshark

# Verify
which dumpcap
dumpcap --version
```

The default path is `/usr/bin/dumpcap`. Configurable via `--dumpcap-binary`, which the installer persists into `/etc/ids-live-sensor/ids-live-sensor.env` before bootstrap and steady-state runtime.

### Packaged extractor default

The canonical packaged extractor path is the installed module entrypoint created by the target-host virtual environment:

```bash
/opt/ids_ml_new/.venv/bin/ids-offline-window-extractor
```

No separate extractor package is required for the canonical `console-only` or `full-stack same-host` product paths.

### CICFlowMeter compatibility override

CICFlowMeter remains supported only as a compatibility override when an operator intentionally replaces the packaged extractor via `--extractor-command-prefix` or the equivalent live-sensor environment contract.

The packaged service/env contract expects `IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX` to be one executable path. Multi-token prefixes such as `python -m ...` are not part of the canonical installed runtime contract.

Compatibility path: `/opt/cicflowmeter/Cmd`

The packaged service contract accepts one exact executable path in `IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX`; multi-token extractor wrappers are outside the canonical installer/runtime path.

Refer to the CICFlowMeter project documentation for build and installation instructions. The binary must be executable by the `ids-sensor` system user.

```bash
# Verify compatibility override only
/opt/cicflowmeter/Cmd --help
```

### GNU coreutils

The `install`, `chmod`, and `chown` commands used by the installer for permission hardening. Pre-installed on all standard Linux distributions.

```bash
# Verify
which install chmod chown
```

### bash

Required by the release/install helper scripts in `ops/`. The packaged live-sensor startup contract is the installed Python/module path documented in the same-host operations docs, not a shell-wrapper startup surface.

```bash
# Verify
bash --version
```

### systemd

Service management for the 3 IDS services. Standard on modern Ubuntu/Debian/RHEL.

```bash
# Verify
systemctl --version
```

## Optional Packages

### nginx

Reverse proxy with HTTPS termination for the operator console. An example configuration is provided at `deploy/nginx/ids-operator-console.conf.example`.

```bash
sudo apt install nginx

# Verify
nginx -v
```

### certbot

SSL certificate provisioning via Let's Encrypt. Only needed if using nginx with HTTPS.

```bash
sudo apt install certbot python3-certbot-nginx

# Verify
certbot --version
```

## System Users

The installer creates two system users automatically:

- `ids-sensor` — runs the live sensor service
- `ids-operator` — runs the operator console and notification worker

No manual user creation is needed.

## Host Directory Layout

The installer creates these directories with hardened permissions:

| Path | Owner | Mode | Purpose |
|------|-------|------|---------|
| `/opt/ids_ml_new` | root | 0755 | Application checkout root |
| `/opt/ids_ml_new/.venv` | root | 0755 | Python virtual environment |
| `/etc/ids-operator-console/` | root:ids-operator | 0750 | Configuration and secrets |
| `/var/lib/ids-live-sensor/` | ids-sensor | 0750 | Sensor runtime state |
| `/var/log/ids-live-sensor/` | ids-sensor | 0750 | Sensor output logs |
| `/var/lib/ids-operator-console/` | ids-operator | 0750 | Console database |
| `/var/backups/ids-operator-console/` | ids-operator | 0750 | Console backups |

## Next Steps

After installing prerequisites:

1. Build a release bundle: [ops/README-deploy.md](../../../ops/README-deploy.md)
2. Deploy to the target host: [deployment_quickstart.md](deployment_quickstart.md)
3. Full operations guide: [ids_same_host_stack_operations.md](ids_same_host_stack_operations.md)
