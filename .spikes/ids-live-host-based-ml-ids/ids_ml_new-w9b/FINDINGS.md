# Spike Findings: ids_ml_new-w9b

**Question**

Can a Linux-only one-NIC capture layer using AF_PACKET-backed packet capture satisfy the locked host-based sensor boundary, TCP/UDP filtering, and fail-fast restart model for this repo's planned daemon?

**Result**

YES

**Evidence**

- The Python `socket` documentation states that Linux exposes `AF_PACKET` as a low-level interface directly to network devices and supports `ETH_P_ALL` for packet capture. This is sufficient to justify a Linux-specific capture seam inside a Python module.
- The Linux [`packet(7)`](https://man7.org/linux/man-pages/man7/packet.7.html) interface is explicitly designed for low-level packet access on Linux network devices, which matches the locked one-host, one-NIC deployment boundary.
- The `systemd.service` documentation supports supervised long-running services with restart policies such as `Restart=on-failure`, which fits the locked fail-fast fatal-error behavior.

**Validated Constraints**

1. The capture layer must remain Linux-only and explicitly bind to one configured NIC.
2. Fatal socket-open, bind, or privilege/setup failures should be treated as process-fatal so `systemd` can restart the daemon.
3. TCP/UDP filtering should be enforced at or immediately above the capture seam to preserve `D8` and reduce downstream noise.
4. The capture module should be isolated in its own file and API so Linux-specific privilege handling does not leak into adapter/runtime code.

**Impact on Plan**

- The planned `scripts/ids_live_capture.py` seam is viable.
- A validating spike is not blocking execution on the capture-boundary question itself.
- Packaging constraints for `systemd` and Linux privileges should be embedded in the daemon/service beads.
