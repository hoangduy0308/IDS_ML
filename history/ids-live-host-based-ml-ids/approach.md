# Approach: IDS Live Host-Based ML Sensor

**Date**: 2026-03-28
**Feature**: ids-live-host-based-ml-ids
**Based on**:
- `history/ids-live-host-based-ml-ids/discovery.md`
- `history/ids-live-host-based-ml-ids/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Live packet capture | None in repo | Linux host capture on one configured NIC for TCP/UDP traffic | New - novel |
| Flow extraction | Adapter expects CICFlowMeter-like structured records | Continuous live flow extraction with semantics close to training-time feature family | New - high risk |
| Upstream-to-downstream composition | Adapter, runtime, inferencer already exist | In-process daemon that feeds extractor output into adapter + realtime pipeline | Medium - integration |
| Local service packaging | Script CLIs only | Long-running supervised Linux service with local output paths and restart policy | New - operational |
| Live-sensor regression coverage | Adapter/runtime tests exist | Focused tests for capture orchestration, extractor bridge, daemon summaries, and output contracts | New - patterned after existing tests |

---

## 2. Recommended Approach

Build the live IDS as a Linux-only staged-live sensor that keeps the downstream ML stack unchanged and replaces the blocked "direct live extractor" assumption with a bounded rolling-window architecture:

`live NIC capture -> closed pcap window -> extractor subprocess -> adapter -> realtime pipeline -> local JSONL/journald outputs`

In this plan, the sensor process owns one configured NIC and starts a `dumpcap` subprocess filtered to `tcp or udp`, writing short-duration `pcap` windows into a bounded spool directory. The daemon consumes only windows that have already been closed by the capture utility, passes each closed `pcap` file through a CICFlowMeter-compatible extractor path, normalizes the extractor output into the adapter's primary profile, and then reuses the existing `ids_record_adapter.py`, `ids_realtime_pipeline.py`, and `ids_inference.py` path exactly as today.

This architecture is still `live-first`: packets come from the real interface immediately and the sensor runs continuously. The difference is that "live" is enforced at the capture boundary, while extraction is intentionally file-bounded. That removes the unsupported requirement that the extractor itself be interface-native, while preserving the semantic goal of staying close to the repo's CICFlowMeter-shaped training contract.

### Why This Approach

- It reuses the strongest existing pattern in the repo: strict upstream boundary handling followed by reusable downstream runtime components in [`scripts/ids_record_adapter.py`](F:/Work/IDS_ML_New/scripts/ids_record_adapter.py) and [`scripts/ids_realtime_pipeline.py`](F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py).
- It honors locked decisions `D3`, `D5`, `D7`, and `D10` from [`history/ids-live-host-based-ml-ids/CONTEXT.md`](F:/Work/IDS_ML_New/history/ids-live-host-based-ml-ids/CONTEXT.md): end-to-end ML IDS, fail-fast fatal errors, local-first outputs, and alert/quarantine persistence only.
- It directly addresses the validation blocker: the plan no longer assumes a direct live-compatible extractor mode that the current evidence cannot prove.
- It avoids the highest-probability failure mode from discovery: silently drifting away from CICFlowMeter-like feature semantics by hand-building a brand-new extractor inside the daemon.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Capture boundary | A Linux `dumpcap` subprocess writes bounded closed `pcap` windows from one NIC with a `tcp or udp` capture filter | Official docs prove rolling live capture and closed-file notification behavior without forcing custom packet capture code into the daemon |
| Flow extraction strategy | Run the extractor only on closed `pcap` windows, not directly on the interface | Removes the blocked assumption while preserving a CICFlowMeter-shaped `pcap -> flow` contract |
| Downstream composition | Reuse adapter + realtime pipeline + inferencer in-process | Existing tested code already solves schema alignment, quarantine, and ML scoring |
| Working artifacts | `pcap` windows and extractor outputs are bounded spool artifacts, not canonical persisted outputs | Keeps forensic/debug value without changing `D7` and `D10` durable-output boundaries |
| Service packaging | `systemd`-managed long-running sensor with local JSONL sinks and journald summaries | Matches `D4`, `D5`, `D7` and keeps operations simple for one Linux host |
| Persistence policy | Full records for positive alerts and quarantines only; counters for benign/skipped traffic | Matches `D10` and avoids runaway benign-event storage |
| Latency model | Near-realtime is bounded by `capture window duration + extractor runtime + micro-batch flush interval` | Makes the performance contract explicit instead of hiding lag inside an undefined "live extractor" |
| Operational guardrails | Expose capture-window duration, pending-window ceilings, lag telemetry, and systemd preflight checks as first-class config/packaging constraints | Converts the remaining latency and dependency concerns into observable fail-fast behavior instead of implicit assumptions |

---

## 3. Alternatives Considered

### Option A: Reimplement all 72 CICFlowMeter-like features directly in Python using raw sockets or Scapy

- Description: sniff packets in-process and compute the full feature family manually inside the new daemon.
- Why considered: keeps the system self-contained and avoids shelling out to external extractor tooling.
- Why rejected: it combines Linux capture, biflow state, timeout semantics, and 72-feature parity into one novel implementation with no repo precedent and very high semantic-drift risk.

### Option B: Keep the old assumption of a direct live-compatible extractor interface

- Description: keep the original plan where the extractor consumes the interface or a live packet stream directly inside the daemon.
- Why considered: this would minimize intermediate disk artifacts and look closer to an idealized pure-stream design.
- Why rejected: validating already blocked this assumption because the planning evidence does not prove that operating mode for the selected feature family.

### Option C: Stop at live collector/extractor output and keep ML inference as a later feature

- Description: build only the live capture side and emit structured flow records for later use.
- Why considered: lowers short-term complexity of the first live feature.
- Why rejected: it violates the locked end-to-end ML IDS boundary in `D3`; the result would be telemetry infrastructure, not a deployed machine-learning IDS.

### Option D: Deliver alerts directly to SIEM/webhooks/Telegram in the same feature

- Description: combine the live sensor with outbound integrations.
- Why considered: attractive from an operations convenience standpoint.
- Why rejected: the user explicitly deferred outbound sinks, and mixing transport reliability with core detection would blur root-cause analysis during the first live deployment.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Rolling `dumpcap` capture manager | **HIGH** | New external runtime dependency, Linux privilege boundary, and spool lifecycle not yet proven in this repo | Spike in validating |
| Closed-window extractor toolchain | **HIGH** | Still depends on novel external tooling and bounded `pcap -> flow` throughput/shape guarantees | Spike in validating |
| Daemon backlog/orchestration policy | **MEDIUM** | New queueing and cleanup behavior between capture and extraction stages | Additional validating hardening pass completed; execution must keep capture-window duration, pending-window ceilings, and lag telemetry explicit |
| In-process composition into adapter/runtime | **MEDIUM** | Variation on existing runtime pattern, but now with staged upstream inputs | Focused tests |
| Local output rotation and journald summaries | **MEDIUM** | New operational behavior with file mutation risk | Focused implementation + regression tests |
| Systemd unit/config packaging | **MEDIUM** | New deployment packaging plus external binary dependencies | Additional validating hardening pass completed; execution must keep explicit preflight checks for `dumpcap`, Java/CICFlowMeter, `jnetpcap`, NIC config, and writable spool/output paths |
| Adapter/runtime reuse | **LOW** | Existing code path with strong regression coverage | Reuse existing tests plus end-to-end additions |

### HIGH-Risk Summary (for khuym:validating skill)

- `Rolling dumpcap capture manager`: prove the selected one-NIC `dumpcap` boundary can emit bounded closed-window notifications and fit the intended restart/permission model.
- `Closed-window extractor toolchain`: prove the chosen `pcap -> flow` extractor path can process closed windows quickly enough and emit a shape the adapter can consume safely.

### Additional Execution Guardrails (validated after the main HIGH-risk spikes)

- `Bounded staged-live latency`: execution must treat end-to-end lag as `capture window duration + extractor runtime + runtime flush interval`, expose the capture-window knob explicitly, and fail fast if pending closed windows exceed the configured ceiling.
- `Concrete Linux preflight contract`: service packaging must validate `dumpcap`, Java/CICFlowMeter command mode, `jnetpcap` native libraries, configured NIC, and writable spool/output paths before the daemon claims to be running.

---

## 5. Decision Rationale

The chosen approach keeps the product boundary ambitious enough to be a real IDS while removing the exact assumption that blocked the first validation pass. This repo already has a strong downstream ML path, so the best plan is still to feed that stack from a Linux host sensor rather than rewrite it. The key correction is where we place the uncertainty boundary: not at "live extractor reads the NIC", but at "closed `pcap` windows can be extracted quickly enough and accurately enough for near-realtime ML scoring." That is a narrower, more source-backed, and more spikeable question. The follow-up hardening pass then turns the last two residual concerns into explicit execution constraints: bounded lag/backlog behavior and concrete Linux dependency preflight.

---

## 6. Validation-Informed Revision Note

The first validating pass blocked the earlier plan because it assumed a direct live-compatible extractor mode that the planning evidence did not prove. This revised approach responds by explicitly choosing the second allowed recovery path from [`validation.md`](F:/Work/IDS_ML_New/history/ids-live-host-based-ml-ids/validation.md):

- keep `live-first` at the capture boundary
- make extraction explicitly staged-live on closed rolling `pcap` windows
- re-run validating against this narrower and more concrete architecture

The feature is therefore no longer blocked on the old assumption, but it still requires a fresh validating pass before execution.
