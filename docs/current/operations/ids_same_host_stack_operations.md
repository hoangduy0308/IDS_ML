# IDS Same-Host Stack Operations

## Scope

This runbook is the canonical same-host contract for:

- fresh bootstrap
- stack preflight
- runtime status and smoke
- supervisor-first restart/recovery
- restore inventory checks
- post-restore verification
- degraded diagnosis by explicit failure domain

It coordinates the existing component owners. It does not replace them.

Component ownership remains:

- model activation: `ids.ops.model_bundle_lifecycle` with `ids-model-bundle-manage` as the canonical operator command (`scripts/ids_model_bundle_manage.py` remains compatibility-only)
- live sensor runtime: `ids.runtime.live_sensor` with `deploy/systemd/ids-live-sensor.service` plus `ids-live-sensor-preflight` as the canonical preflight command (`scripts/ids_live_sensor_preflight.py` remains compatibility-only)
- operator console runtime and restore: `ids.console.web`, `ids.console.ops`, and `ids.ops.operator_console_manage` with `ids-operator-console-manage` as the canonical operator command (`scripts/ids_operator_console_manage.py` remains compatibility-only)
- notification worker runtime: `ids.console.notification_runtime` with `deploy/systemd/ids-operator-console-notify.service` plus `ids-operator-console-manage`
- same-host stack console asset defaults: `ids/console/templates` and `ids/console/static`; `scripts/ids_operator_console/*` remains an explicit compatibility override, not the canonical default

## Required Host Paths

- repo checkout: `/opt/ids_ml_new`
- live sensor activation record: `/var/lib/ids-live-sensor/active_bundle.json`
- live sensor logs and JSONL outputs: `/var/log/ids-live-sensor`
- operator console env file: `/etc/ids-operator-console/ids-operator-console.env`
- operator console database: `/var/lib/ids-operator-console/operator_console.db`
- operator backup root: `/var/backups/ids-operator-console`

Deploy references already shipped in-tree:

- `deploy/systemd/ids-live-sensor.service`
- `deploy/systemd/ids-operator-console.service`
- `deploy/systemd/ids-operator-console-notify.service`
- `deploy/nginx/ids-operator-console.conf.example`

## Canonical Stack Commands

The canonical stack implementation lives in `ids.ops.same_host_stack_manage`, surfaced as the installed command `ids-stack`.
`scripts/ids_same_host_stack_manage.py` remains a compatibility entrypoint for direct file execution.

Supported commands:

- `preflight`
- `bootstrap`
- `status`
- `smoke`
- `recover`
- `restore-inventory`
- `post-restore-check`

## Fresh Bootstrap

1. Prepare the host layout, operator env file, and secret files.
2. Verify and promote the candidate model bundle through the model-bundle owner.
3. Bootstrap the operator console schema and admin user.
4. Run the stack-level preflight gate.
5. Start the console service.
6. Start the live sensor service.
7. Start the notification worker only when notifications are enabled.
8. Run stack `status` and `smoke`.
9. When a reverse proxy is configured, check the non-gating proxy seam.

Example:

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
  --json bootstrap \
  --candidate-bundle-root /opt/ids_ml_new/artifacts/final_model/candidate_bundle \
  --admin-username admin \
  --admin-password-file /secure/admin.password
```

The canonical same-host interpreter contract is the Python binary inside the bootstrap-created installed environment at `/opt/ids_ml_new/.venv/bin/python`. Do not point the shipped services at host-global `/usr/bin/python3`; that would split the documented contract from the deployed one.

Pass `--extractor-command-prefix` as separate argv tokens. Do not quote the prefix into a single shell word, or the live sensor service will collapse the extractor command structure.

The bootstrap flow delegates to the existing component owners. It does not own bundle restore, console restore, or service-specific mutation logic.
The same-host stack contract carries the live-sensor extractor command prefix explicitly and leaves deeper extractor/runtime validation to the live-sensor preflight owner.
`bootstrap` does not report success until the post-start `status` and `smoke` checks run; it returns a degraded result and exit code `2` when those checks fail.

## Preflight, Status, and Smoke

Use stack `preflight` as the canonical same-host deploy gate:

```bash
ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json preflight
```

Use stack `status` for whole-stack runtime health and `smoke` for the runtime plus console smoke path:

```bash
ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json status

ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --proxy-public-url https://console.example \
  --json smoke
```

Top-level readiness gates on:

- active bundle runtime readiness
- live sensor runtime health
- operator console readiness/smoke
- notification worker only when configured and enabled

The reverse proxy seam is reported but never gates top-level readiness.
Default stack output stays redacted for notification metadata and returns degraded payloads on expected contract failures instead of raw tracebacks.

## Restart and Recovery

Use stack `recover` after reboot or subsystem failure. This is supervisor-first and preserves component ownership.

```bash
ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --proxy-public-url https://console.example \
  --json recover
```

Recovery ordering is:

1. verify the activation contract
2. restart `ids-live-sensor.service`
3. restart `ids-operator-console.service`
4. restart `ids-operator-console-notify.service` only when notifications are enabled
5. re-run stack `status`
6. re-run stack `smoke`

## Backup and Restore Boundary

The stack layer stays verification-first. It does not add a new restore mutation wrapper.

Use the existing component owners for restore mutations:

```bash
ids-operator-console-manage \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json restore \
  --backup-dir /var/backups/ids-operator-console/backup-YYYYMMDDTHHMMSSffffffZ \
  --service-stopped
```

The minimum restore inventory that must exist before the host can be considered recoverable is:

- `/var/lib/ids-live-sensor/active_bundle.json`
- the bundle directories referenced by that activation record
- `/var/lib/ids-operator-console/operator_console.db`
- the operator backup manifest and backup database artifact
- the secret references required by the operator console restore path

Live sensor JSONL outputs and logs remain preserve-when-practical operator evidence. They are not the primary restore state required to make scoring ready again.

## Restore Inventory Check

After component-owned backup artifacts are present, use stack `restore-inventory`:

```bash
ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json restore-inventory \
  --operator-backup-dir /var/backups/ids-operator-console/backup-YYYYMMDDTHHMMSSffffffZ
```

This verifies inventory only. It does not restore anything.

## Post-Restore Check

After the console restore command succeeds and secrets are rebound on the host, use stack `post-restore-check`:

```bash
ids-stack \
  --repo-root /opt/ids_ml_new \
  --operator-env-file /etc/ids-operator-console/ids-operator-console.env \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --proxy-public-url https://console.example \
  --json post-restore-check \
  --operator-backup-dir /var/backups/ids-operator-console/backup-YYYYMMDDTHHMMSSffffffZ \
  --notification-redrive-limit 100
```

`post-restore-check` proves:

- restore inventory is present
- the live sensor preflight boundary re-validates the active bundle contract
- the canonical stack recovery path runs cleanly
- `notify-status` is checked when notifications are enabled
- `notify-redrive` is executed when restored notification rows are still failed
- operator visibility re-establishes active bundle state through restored or freshly ingested summaries

## Degraded Diagnosis

Stack `status`, `smoke`, `recover`, and `post-restore-check` keep these failure domains explicit:

- `model_activation_contract`
- `live_sensor_data_path`
- `operator_visibility_path`
- `outbound_notification_path`
- `reverse_proxy_edge_seam`

Interpretation:

- `model_activation_contract`: activation record or bundle contract is missing or invalid
- `live_sensor_data_path`: summary-backed runtime evidence is stale, missing, malformed, or mismatched
- `operator_visibility_path`: console readiness or smoke is degraded, or bundle visibility is not yet restored
- `outbound_notification_path`: notification runtime is `ok`, `degraded`, or explicit `disabled`
- `reverse_proxy_edge_seam`: public proxy reachability is degraded but non-gating

Operator follow-up commands remain component-specific:

```bash
ids-operator-console-manage \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json notify-status

ids-operator-console-manage \
  --database-path /var/lib/ids-operator-console/operator_console.db \
  --json notify-redrive --limit 100

ids-model-bundle-manage \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json verify \
  --bundle-root /opt/ids_ml_new/artifacts/final_model/candidate_bundle
```

If stack `smoke`, `recover`, or `post-restore-check` returns degraded, treat that as a deployment blocker rather than a warning.
