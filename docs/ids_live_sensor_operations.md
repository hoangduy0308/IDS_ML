# IDS Live Sensor Operations

## Scope

This guide covers the v1 operating model for the live host-based IDS sensor on Linux.

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
- the model bundle exists
- the configured NIC name is correct
- the spool and log directories are writable

The sample service unit uses an explicit preflight command so the service fails fast if any of those requirements are missing.

## Recommended paths

The sample deployment layout is:

- checkout: `/opt/ids_ml_new`
- spool root: `/var/lib/ids-live-sensor`
- JSONL outputs and summaries: `/var/log/ids-live-sensor`

The daemon writes its own capture-window artifacts under the spool root and keeps its alert and quarantine outputs local.

## systemd behavior

The sample service is designed to run as a supervisor-managed daemon:

- `Type=exec`
- `Restart=on-failure`
- `WantedBy=multi-user.target`
- explicit preflight checks before `ExecStart`

`StateDirectory=` and `LogsDirectory=` are used so the service can own its local storage roots without relying on ad hoc bootstrap logic.

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

## Journald and JSONL

The sensor keeps two operator-facing traces:

- JSONL files for alerts, quarantines, and summaries
- journald-friendly text summaries for quick inspection

The journal message should remain short and operational, while the JSONL files remain the durable record.

## Preflight details

The preflight check should fail if any of the following are missing:

- `dumpcap`
- `java`
- the CICFlowMeter command wrapper
- `jnetpcap`
- the model bundle files
- a writable spool directory
- a writable log directory

If you need more elaborate setup logic, keep it in an explicit helper script or explicit shell invocation. Do not bury shell assumptions inside `ExecStart=`.

## Deferred features

The first release intentionally defers:

- Telegram notifications
- webhook or SIEM delivery
- IPS or automatic network response

Those are separate features and should not be confused with the local IDS sensor boundary.

## Example operator checks

Useful checks during deployment and debugging:

- verify the unit file content with `systemctl cat ids-live-sensor`
- verify preflight binaries with `command -v dumpcap`, `command -v java`, and `command -v Cmd`
- verify the local outputs are writable and rotating as expected
- inspect journald for the compact summary line when the daemon flushes telemetry

