# Spike Findings: ids_ml_new-4vh

**Question**

Can Linux service packaging define a concrete preflight contract for `dumpcap` plus CICFlowMeter dependencies so execution does not fail on missing runtime assumptions?

**Result**

YES

**Evidence**

- The official [`systemd.service`](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) documentation supports `ExecStartPre=` and `ExecCondition=` for preflight checks and recommends `Type=exec` when the service manager should fail startup if the main executable cannot be invoked correctly.
- The same `systemd.service` documentation states that shell pipelines and redirection are not directly supported in `Exec*=` lines, so packaging should use explicit helper commands/scripts rather than relying on shell-only syntax in unit files.
- The official CICFlowMeter [`README.md`](https://github.com/ahlashkari/CICFlowMeter/blob/master/README.md) documents Linux `sudo` as a prerequisite and describes packaging via `./gradlew distZip`.
- The official CICFlowMeter [`build.gradle`](https://github.com/ahlashkari/CICFlowMeter/blob/master/build.gradle) documents the command-mode entrypoint, bundles native libraries into `lib/native`, and sets JVM library-path defaults for the packaged application.

**Validated Constraints**

1. The Linux service package can and should define a preflight contract before daemon startup.
2. The documented preflight contract must verify, at minimum: configured NIC value, `dumpcap` availability, Java runtime availability, CICFlowMeter command-mode availability, `jnetpcap` native-library path availability, and writable spool/output directories.
3. The sample unit/service docs should use `Type=exec` plus explicit `ExecStartPre=` and/or `ExecCondition=` checks so missing dependencies fail before the daemon claims to be healthy.
4. The service docs must describe privilege expectations for live capture separately from the daemon itself, because `dumpcap`/capture permissions are part of deployment, not downstream ML logic.
5. Any multi-step preflight that needs shell behavior should live in an explicit helper script or explicit shell invocation; it should not be embedded implicitly inside `ExecStart=` syntax.

**Impact on Plan**

- The residual packaging concern is reduced from "remember to document dependencies" to a concrete preflight/deployment contract.
- The service/docs bead should embed the dependency matrix and systemd preflight pattern explicitly.
