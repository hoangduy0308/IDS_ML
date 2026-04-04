# Operations docs

Canonical same-host operations docs live here.

- [linux_prerequisites.md](linux_prerequisites.md) — system packages required before installation
- [deployment_quickstart.md](deployment_quickstart.md) — fastest path to deploy on a new Linux host
- [ids_same_host_stack_operations.md](ids_same_host_stack_operations.md) — full stack operations guide
- [e2e_demo_runbook.md](e2e_demo_runbook.md) — end-to-end demo walkthrough

## Release Safety

Release bundles are built using `git archive` so only tracked files are included. Untracked local files (secrets, credentials, editor state) cannot leak into the shipped artifact. See [deployment_quickstart.md](deployment_quickstart.md) for the full release flow.

## Telegram Configuration

Telegram notifications can be configured two ways:

1. **Settings UI** (recommended): Log into the dashboard, go to Settings, enter bot token and chat ID. Changes take effect within 30 seconds.
2. **Environment file**: Set `IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN` and `IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID` in the env file for initial/headless setup.

Database settings (via Settings UI) take precedence over environment file values. The Settings page, the Test button, and the notification worker all use the same effective-config resolver: database values win, environment values serve as fallback when no database settings exist. The page shows "via database" or "via environment" to indicate which source is active.

The Settings page is root-path-aware and works correctly when the console is mounted behind a reverse proxy at a non-root path (e.g. `/console`).

## Install Hardening

The installer (`ops/install.sh`) hardens pre-seeded operator env files to `0640 root:ids-operator` permissions, even if the file already existed before the install. This prevents leaking secrets (e.g. Telegram bot token) to other local users when operators follow the documented pre-seed flow.

The notification worker (`ids-operator-console-notify.service`) is enabled alongside the base services during a fresh install, so Telegram dispatch is operational after reboot without manual post-install steps.

See [deployment_quickstart.md](deployment_quickstart.md) for details.
