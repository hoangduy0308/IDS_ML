# IDS Live Sensor Operations

## Scope

This guide covers the same-host operating model for the Linux live sensor.

It assumes:

- one protected Linux host
- one explicitly configured NIC
- TCP/UDP flow traffic only
- a continuously running systemd-managed sensor process

## Startup contract

Before the daemon starts, the deployment must verify:

- `dumpcap` is installed and runnable
- Java is installed and runnable
- the CICFlowMeter command-mode wrapper is installed and runnable
- `jnetpcap` is present where the extractor expects it
- the active bundle activation record exists
- the resolved active bundle exists and is compatibility-valid
- the configured NIC name is correct
- the spool and log directories are writable

The sample service unit uses [ids_live_sensor_preflight.py](F:/Work/IDS_ML_New/scripts/ids_live_sensor_preflight.py) as an explicit preflight command so the service fails fast if any of those requirements are missing.

## Recommended paths

The sample deployment layout is:

- checkout: `/opt/ids_ml_new`
- spool root: `/var/lib/ids-live-sensor`
- active bundle record: `/var/lib/ids-live-sensor/active_bundle.json`
- JSONL outputs and summaries: `/var/log/ids-live-sensor`

The daemon writes its own capture-window artifacts under the spool root and keeps its alert and quarantine outputs local.

## systemd behavior

The sample service is designed to run as a supervisor-managed daemon:

- `Type=exec`
- `Restart=on-failure`
- `WantedBy=multi-user.target`
- explicit preflight checks before `ExecStart`

`StateDirectory=` and `LogsDirectory=` are used so the service can own its local storage roots without relying on ad hoc bootstrap logic.

The sample unit also keeps one source of truth for deployment paths and helper binaries by declaring them as environment variables and consuming those same values in both `ExecStartPre=` and `ExecStart=`.

For model lifecycle, the unit uses `IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH` as the canonical source for both preflight and runtime startup. Production deployment should not set independent model/schema/threshold paths anymore.

## Runtime behavior

Normal operation is:

1. `dumpcap` closes a capture window on the configured NIC.
2. The daemon enqueues the closed window.
3. The bridge converts the closed window into extractor output.
4. The adapter turns extractor rows into runtime-ready records.
5. The realtime pipeline scores valid records.
6. The sink writes alerts, quarantines, and summary telemetry locally.

Operator expectations:

- malformed records should appear as quarantine output, not as process failure
- fatal capture/runtime faults should terminate the process and trigger restart
- benign predictions should be counted, not archived as full records by default
- the output files are the primary forensic artifacts for v1
- active bundle identity and compatibility state should appear in summary telemetry

## Journald and JSONL

The sensor keeps two operator-facing traces:

- JSONL files for alerts, quarantines, and summaries
- stdout summary lines collected by journald for quick inspection

The journal message should remain short and operational, while the JSONL files remain the durable record. The implementation formats the summary line once, appends the full JSONL summary, then writes the compact line to stdout so systemd can ship it to journald.

Bundle-aware summaries now include:

- `active_bundle.active_bundle_name`
- `active_bundle.compatibility_status`
- `active_bundle.activated_at`
- `active_bundle.previous_bundle_name`

The compact journald line also carries `active_bundle=<name>` and `bundle_status=<compatibility-status>` for quick operator checks.

## Preflight details

The preflight check should fail if any of the following are missing:

- `dumpcap`
- `java`
- the CICFlowMeter command wrapper
- `jnetpcap`
- the activation record
- the resolved bundle manifest, model artifact, and feature schema files
- bundle compatibility metadata that matches the current runtime inference contract
- a writable spool directory
- a writable log directory

If you need more elaborate setup logic, keep it in an explicit helper script such as [ids_live_sensor_preflight.py](F:/Work/IDS_ML_New/scripts/ids_live_sensor_preflight.py). Do not bury setup assumptions inside the main daemon code.

## Promotion and rollback runbook

The live sensor service stays verify-only at startup. Promotion and rollback are explicit operator steps.

Recommended same-host flow:

1. Verify the candidate bundle contract:

```bash
python /opt/ids_ml_new/scripts/ids_model_bundle_manage.py \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json verify \
  --bundle-root /opt/ids_ml_new/artifacts/final_model/candidate_bundle
```

2. Run a same-host dry-run on representative data before cutover:

```bash
python /opt/ids_ml_new/scripts/ids_inference.py \
  --bundle-root /opt/ids_ml_new/artifacts/final_model/candidate_bundle \
  --input-path /opt/ids_ml_new/artifacts/cic_iot_diad_2024_binary/clean/test.parquet \
  --output-path /tmp/candidate_bundle_predictions.parquet \
  --limit 1000
```

3. Promote the verified bundle:

```bash
python /opt/ids_ml_new/scripts/ids_model_bundle_manage.py \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json promote \
  --bundle-root /opt/ids_ml_new/artifacts/final_model/candidate_bundle
```

4. Restart the service or rerun preflight if your deployment procedure requires it:

```bash
systemctl restart ids-live-sensor.service
```

5. Check readiness and summary output:

- `systemctl status ids-live-sensor.service`
- `journalctl -u ids-live-sensor.service -n 50`
- inspect the newest summary JSONL event for `active_bundle`

If `verify` fails or `promote` raises a contract error, the previous activation record remains in place. A failed compatibility check must be treated as a blocked cutover, not as a warning.

Rollback is explicit:

```bash
python /opt/ids_ml_new/scripts/ids_model_bundle_manage.py \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json rollback
```

Rollback restores the immediately previous known-good bundle recorded at promotion time. If no previous bundle exists in the activation record, rollback is expected to fail closed.

## Restore expectations

Backup and restore procedures must preserve `/var/lib/ids-live-sensor/active_bundle.json` together with the bundle directories it references.

After a restore drill:

- do not assume the restored activation record is valid just because the file exists
- rerun [ids_live_sensor_preflight.py](F:/Work/IDS_ML_New/scripts/ids_live_sensor_preflight.py) or restart the systemd unit so preflight resolves and re-validates the active bundle contract
- only treat the sensor as ready after preflight/runtime can resolve the restored active bundle successfully

## Deferred features

The current release intentionally defers:

- Telegram notifications
- webhook or SIEM delivery
- IPS or automatic network response

Those are separate features and should not be confused with the local IDS sensor boundary.

## Example operator checks

Useful checks during deployment and debugging:

- verify the unit file content with `systemctl cat ids-live-sensor`
- verify the exact configured binary paths still exist and are executable
- verify `IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH` points to the intended activation record
- verify the local outputs are writable and rotating as expected
- inspect journald for the compact summary line when the daemon flushes telemetry
- inspect the newest summary event for `active_bundle.active_bundle_name`, `compatibility_status`, and `previous_bundle_name`
