# Spike Findings: ids_ml_new-w5d

**Question**

Can the revised staged-live sensor rely on `dumpcap` to capture from one Linux NIC, rotate bounded window files, and notify the daemon only after each window file closes?

**Result**

YES

**Evidence**

- The official [`dumpcap(1)`](https://www.wireshark.org/docs/man-pages/dumpcap.html) manual states that dumpcap captures live traffic and writes packets to files.
- The same manual documents `-b duration:<seconds>` and `-b files:<count>` for multi-file and ring-buffer capture, which is exactly the bounded rolling-window model the revised plan needs.
- The same manual documents `-b printname:<filename>` and says it prints the name of the most recently written file *after the file is closed*. This is the key boundary needed for a staged-live daemon to avoid reading partially written windows.
- The manual also documents per-interface capture filters via `-f`, interface selection via `-i`, and output format selection via `-F`, which fits the locked `one host`, `one NIC`, and `TCP/UDP only` scope.

**Validated Constraints**

1. The capture manager can be implemented as a Linux subprocess boundary around `dumpcap` instead of a custom in-process packet sniffer.
2. The daemon should capture only one configured interface and apply a `tcp or udp` capture filter at the `dumpcap` seam.
3. The daemon should consume windows only after `printname` reports the closed file path.
4. The capture process should write bounded rolling windows into a dedicated spool directory and treat startup/bind/permission failure as process-fatal for supervisor restart.
5. The capture output should be forced to `pcap` when the downstream extractor requires `pcap` rather than the default `pcapng`.

**Impact on Plan**

- The revised staged-live capture boundary is viable.
- Validation is not blocked on the rolling `dumpcap` window model itself.
- The capture beads should lock around `dumpcap` subprocess supervision, closed-window notifications, bounded spool paths, and fatal error escalation.
