# Validation: IDS Live Host-Based ML IDS

**Date**: 2026-03-28
**Feature**: `ids-live-host-based-ml-ids`
**Epic**: `ids_ml_new-vtc`

---

## 1. Plan Verification

### Iteration 1

Result: **FAIL**

Failed dimensions:
- **Test coverage / bead quality**: `ids_ml_new-vtc.5` had a shell-unsafe verification command because the `rg` regex pipes were not quoted for the PowerShell execution environment.

Fixes applied:
- updated `ids_ml_new-vtc.5` acceptance criteria so the verification command is executable as written in the current shell environment
- re-checked the bead set after the acceptance-criteria correction

### Iteration 2

Result: **PASS**

All 8 dimensions pass:
1. Requirement coverage: PASS
2. Dependency correctness: PASS
3. File scope isolation: PASS
4. Context budget: PASS
5. Test coverage: PASS
6. Gap detection: PASS
7. Risk alignment: PASS
8. Completeness: PASS

Notes:
- locked decisions `D1-D10` are covered by the revised staged-live bead set
- no dependency cycles were detected
- the revised plan replaces the previously blocked direct-live extractor assumption with an explicit `closed pcap window -> extractor` seam

---

## 2. Spike Execution

### HIGH-risk item 1

- Risk: `Rolling dumpcap capture manager`
- Spike bead: `ids_ml_new-w5d`
- Findings: [FINDINGS.md](F:/Work/IDS_ML_New/.spikes/ids-live-host-based-ml-ids/ids_ml_new-w5d/FINDINGS.md)
- Result: **YES**

Validated constraints:
- use `dumpcap` as the one-NIC rolling capture subprocess
- apply the `tcp or udp` capture filter at the capture seam
- consume windows only after `printname` reports the closed file path
- force `pcap` output where the downstream extractor requires `pcap`

### HIGH-risk item 2

- Risk: `Closed-window extractor toolchain`
- Spike bead: `ids_ml_new-vum`
- Findings: [FINDINGS.md](F:/Work/IDS_ML_New/.spikes/ids-live-host-based-ml-ids/ids_ml_new-vum/FINDINGS.md)
- Result: **YES**

Validated constraints:
- use the official CICFlowMeter command-mode path (`Cmd` / generated `cfm` script) against closed `pcap` windows
- expect extractor output with the `_Flow.csv` suffix
- package Java plus `jnetpcap` native-library requirements explicitly
- keep extractor failures inside the staged-live bridge/error path rather than bypassing the adapter

Spike learnings embedded into affected beads:
- `ids_ml_new-vtc.1`
- `ids_ml_new-vtc.2`
- `ids_ml_new-vtc.4`
- `ids_ml_new-vtc.5`

### Additional risk-hardening spike 1

- Risk: `Bounded staged-live latency / backlog policy`
- Spike bead: `ids_ml_new-3eq`
- Findings: [FINDINGS.md](F:/Work/IDS_ML_New/.spikes/ids-live-host-based-ml-ids/ids_ml_new-3eq/FINDINGS.md)
- Result: **YES**

Validated constraints:
- make the latency claim explicit as `capture window duration + extractor runtime + runtime flush interval`
- keep capture-window duration configurable rather than implicit
- define a maximum pending-window ceiling with fail-fast behavior when backlog exceeds the configured limit
- emit queue-depth, oldest-pending-window age, and extractor-runtime telemetry to local summaries/journald

### Additional risk-hardening spike 2

- Risk: `Linux service preflight / dependency contract`
- Spike bead: `ids_ml_new-4vh`
- Findings: [FINDINGS.md](F:/Work/IDS_ML_New/.spikes/ids-live-host-based-ml-ids/ids_ml_new-4vh/FINDINGS.md)
- Result: **YES**

Validated constraints:
- document and package an explicit preflight contract for `dumpcap`, Java, CICFlowMeter command mode, `jnetpcap`, configured NIC, and writable spool/output paths
- use `Type=exec` plus at least one explicit preflight directive (`ExecStartPre=` or `ExecCondition=`) in the sample `systemd` unit
- keep any shell-dependent preflight logic in an explicit helper script or explicit shell invocation rather than relying on implicit shell syntax in `Exec*=` lines

Additional hardening learnings embedded into affected beads:
- `ids_ml_new-vtc.3`
- `ids_ml_new-vtc.4`
- `ids_ml_new-vtc.5`

---

## 3. Bead Polishing

### `bv --robot-suggest`

- dependency suggestions adopted: `0`
- rationale: suggestions for the current epic were either transitive or speculative; no missing dependency was strong enough to justify graph changes

### `bv --robot-insights`

- critical issues resolved: `0`
- cycles found: `0`
- notable graph facts:
  - `ids_ml_new-vtc.2` remains the intentional semantic-fidelity articulation point
  - `ids_ml_new-vtc.4` remains the intentional integration bottleneck before docs and end-to-end fixtures

### `bv --robot-priority`

- priority adjustments made: `0`
- rationale: the current priorities still reflect the intended execution order well enough for validating

### Deduplication

- duplicates found in the current epic: `0`
- note: `bv --robot-suggest` surfaced duplicate suggestions for older unrelated beads in the wider repo graph, but none applied to the current epic

### Fresh-eyes review

Manual cold-read pass against the revised beads:
- critical issues: `0`
- minor issues: `0`

---

## 4. Conclusion

Validation status: **READY FOR APPROVAL**

Residual concerns:
- real host performance still requires environment-specific tuning, but the plan now makes the lag contract and backlog ceiling explicit instead of leaving them implicit
- packaging still depends on host provisioning, but the required dependency/preflight contract is now concrete rather than inferred

Confidence level: **MEDIUM-HIGH**

The revised staged-live plan is structurally sound, the new HIGH-risk seams have concrete source-backed paths, and the residual latency/packaging concerns have been reduced to explicit execution constraints rather than open questions. The feature is ready for the GATE 2 execution decision.
