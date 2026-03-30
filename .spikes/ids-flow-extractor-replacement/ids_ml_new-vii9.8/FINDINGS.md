## Spike: ids_ml_new-vii9.8

### Question
Can a replacement extractor compute tier-1 flow features from representative closed pcaps with semantics close enough to the current CICFlowMeter-like family to preserve model-serving correctness without retraining?

### Determination
YES

### Evidence
- [`scripts/ids_feature_contract.py`](F:\Work\IDS_ML_New\scripts\ids_feature_contract.py) enforces an exact 72-feature numeric boundary, but it does not require CSV, Java, or CICFlowMeter branding; the hard requirement is canonical numeric flow statistics.
- [`artifacts/final_model/catboost_full_data_v1/feature_columns.json`](F:\Work\IDS_ML_New\artifacts\final_model\catboost_full_data_v1\feature_columns.json) contains packet/header/timing/flag/window features that are all derivable from closed pcaps and flow assembly, not from external state.
- [`scripts/ids_live_flow_bridge.py`](F:\Work\IDS_ML_New\scripts\ids_live_flow_bridge.py) shows the live seam is already `closed pcap -> extractor -> rows -> adapter`, so a replacement extractor can stay offline-first without changing the live capture model.
- [`scripts/ids_record_adapter.py`](F:\Work\IDS_ML_New\scripts\ids_record_adapter.py) already absorbs alias and metadata normalization, which means the extractor does not need to reproduce every historical field spelling to satisfy the model-facing contract.
- The most semantics-sensitive features in the 72 are the CICFlowMeter-style aggregate families such as `Bwd Bytes/Bulk Avg`, `Bwd Packet/Bulk Avg`, `Bwd Bulk Rate Avg`, `Subflow *`, and `Active/Idle *`; those require tighter comparison rules, but they do not invalidate closed-pcap extraction as the seam.

### Proposed Comparison Method
- Use the same representative closed pcaps as input to both the current CICFlowMeter-like path and the candidate extractor.
- Join records by a deterministic 5-tuple plus direction and flow time window where possible; if no stable flow id exists, compare at the per-flow aggregate level after sorting on the join key.
- Treat tier-1 as the directly observable, low-ambiguity family first: `Src Port`, `Dst Port`, `Protocol`, `Flow Duration`, `Total Fwd Packet`, `Total Bwd packets`, `Total Length of Fwd Packet`, `Total Length of Bwd Packet`, packet-length stats, `Flow Bytes/s`, `Flow Packets/s`, IAT stats, TCP flag counts, header lengths, and init window bytes.
- Require exact equality for identity/count/flag/header fields and bounded numeric tolerance for duration/rate/statistical fields.
- Leave bulk/subflow/active-idle families as explicit constraint checks rather than initial parity gates.

### Constraints
- This YES applies to tier-1 feature semantics on closed pcaps, not to guaranteed parity for every one of the 72 features.
- Production correctness still depends on a later contract bead classifying which features are must-have versus adapter-recoverable versus semantics-sensitive.
- If later implementation cannot keep the bulk/subflow/active-idle families within acceptable semantics, the path may still require scope reduction or retraining.

### Conclusion
The repo evidence supports a YES for an offline-first replacement extractor on the existing closed-pcap seam. The hard runtime boundary is numeric canonical flow features, and the core tier-1 subset is directly derivable from packet timestamps, header fields, lengths, flags, and TCP window metadata already present in a pcap. The main risk is not whether closed-pcap extraction is feasible, but whether the more heuristic CICFlowMeter aggregate families can be matched closely enough; that should be treated as a constrained comparison problem, not a reason to reject the replacement path.
