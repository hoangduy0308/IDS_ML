# Spike Findings: ids_ml_new-3eq

**Question**

Can the revised staged-live host sensor keep latency bounded with explicit capture-window and backlog controls instead of an undefined "best effort" near-realtime claim?

**Result**

YES

**Evidence**

- The official [`dumpcap(1)`](https://www.wireshark.org/docs/man-pages/dumpcap.html) manual documents `-b duration:<seconds>` for time-bounded rolling windows, `-b files:<count>` for bounded ring-buffer capture, and `-b printname:<filename>` to report each file name only after the file closes.
- The same `dumpcap(1)` manual documents `-B` capture-buffer sizing and `--update-interval`, which means the capture seam has explicit runtime knobs rather than an implicit unbounded stream.
- The repo's current realtime runtime contract in [docs/ids_realtime_pipeline_architecture.md](F:/Work/IDS_ML_New/docs/ids_realtime_pipeline_architecture.md) already exposes `max_batch_size` and `flush_interval_seconds`, so the downstream portion of latency is already bounded by configuration.

**Validated Constraints**

1. The end-to-end latency claim for v1 should be explicit: it is bounded by `capture window duration + extractor runtime + runtime flush interval`. This bound is an inference from the source-backed capture controls plus the repo's existing micro-batch runtime contract.
2. The daemon bead must expose capture-window duration as a first-class config input rather than hard-coding it.
3. The daemon bead must define bounded backlog policy for closed windows, including a maximum pending-window threshold and fail-fast behavior when backlog exceeds the configured ceiling, to stay aligned with locked decision `D5`.
4. Telemetry for queue depth, oldest pending window age, per-window extractor runtime, and downstream flush behavior should be emitted to local summaries/journald so operators can see when the bounded-latency contract is being violated in practice.
5. The plan should avoid promising packet-level realtime semantics. The supported promise is bounded staged-live processing with observable lag controls.

**Impact on Plan**

- The residual latency concern is reduced from an open question to a concrete execution contract.
- The daemon and service/documentation beads should embed capture-window controls, backlog thresholds, and latency-observability requirements explicitly.
