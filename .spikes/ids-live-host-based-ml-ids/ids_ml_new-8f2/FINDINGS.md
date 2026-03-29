# Spike Findings: ids_ml_new-8f2

**Question**

Can the planned live sensor use a CICFlowMeter-compatible extraction path in a bounded near-realtime loop on one Linux host, without falling back to an offline replay workflow or a handwritten 72-feature reimplementation?

**Result**

NO

**Evidence**

- The official CICFlowMeter README describes the tool as generating biflows from `pcap files` and extracting features from those flows.
- The same upstream README documents flow semantics such as TCP teardown and UDP timeout, which is useful for semantic alignment, but it does not document a primary live-interface or bounded streaming mode for one-host near-realtime operation.
- Planning therefore assumed a direct live-compatible extractor interface without primary-source proof that the official CICFlowMeter path supports that operating model.

**Blocker**

The current approach depends on a live, bounded, CICFlowMeter-compatible extraction seam as its default v1 strategy, but the planning artifacts do not yet prove a concrete extractor/toolchain that supports that mode. Continuing to execution would force implementers either to:

1. invent a handwritten 72-feature extractor, which planning explicitly rejected, or
2. quietly degrade into an offline or pseudo-live replay architecture that has not been approved.

**Required Revision**

Planning must be revised to choose one of these explicit approaches before execution:

1. Select a concrete live-compatible extractor/toolchain and lock its operating constraints, or
2. Revise the upstream architecture to a clearly stated staged-live design (for example, rolling capture windows into bounded extraction jobs) and verify that this still honors the user's `live-first` intent.

**Impact on Plan**

- The existing approach is blocked on extractor viability.
- Execution approval should not be granted until planning revises the extraction strategy and validating re-runs.
