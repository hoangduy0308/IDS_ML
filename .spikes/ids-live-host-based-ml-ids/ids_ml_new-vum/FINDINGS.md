# Spike Findings: ids_ml_new-vum

**Question**

Is there a concrete, source-backed headless extractor path for the revised architecture where closed `pcap` windows are converted into CICFlowMeter-shaped flow exports without requiring a direct live-interface mode?

**Result**

YES

**Evidence**

- The official CICFlowMeter repository README states that the tool generates biflows from `pcap files` and extracts features from those flows.
- The official [`build.gradle`](https://github.com/ahlashkari/CICFlowMeter/blob/master/build.gradle) defines a `JavaExec` task named `exeCMD` with `main = "cic.cs.unb.ca.ifm.Cmd"` and a generated start script `cfm`, which is explicit headless packaging for a command-mode entrypoint.
- The official [`Cmd.java`](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/ifm/Cmd.java) accepts a `pcap` file or folder as the first argument and an output folder as the second argument, then processes each `pcap` input into flow exports.
- The official [`FlowMgr.java`](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/flow/FlowMgr.java) declares `FLOW_SUFFIX = "_Flow.csv"`, giving the output naming contract for the extractor stage.

**Validated Constraints**

1. The revised plan has a concrete extractor path: run CICFlowMeter in command mode against each closed `pcap` window, not against the NIC directly.
2. The capture stage should emit `pcap` windows, not rely on `pcapng`, because the command-mode extractor contract is explicitly framed around `pcap` file/folder input.
3. The bridge bead must normalize `_Flow.csv` output into the adapter's structured-record profile instead of expecting JSON-native extractor output.
4. Packaging must account for the extractor's Java runtime and `jnetpcap` native-library requirements documented in the official repo.
5. The daemon must treat extractor invocation and output-shape failures as window-stage errors/quarantine paths, not as reasons to bypass the adapter boundary.

**Impact on Plan**

- The revised staged-live architecture now has a concrete headless extractor contract and is no longer blocked by the earlier "direct live extractor" assumption.
- Validation is not blocked on extractor existence for the revised architecture.
- The bridge and service beads should embed the command-mode CICFlowMeter constraints explicitly.
