# Spike Findings: ids_ml_new-kys

## Question

Can persisted-offset ingest tail the current JSONL outputs safely?

## Result

**YES**

## Evidence

- The current sink writes newline-delimited JSON records directly to durable files in append mode and flushes after each record in [scripts/ids_live_sensor_sinks.py](F:/Work/IDS_ML_New/scripts/ids_live_sensor_sinks.py).
- The live sensor docs explicitly define the JSONL outputs as the v1 source of truth for operator-facing evidence:
  - [ids_live_sensor_architecture.md](F:/Work/IDS_ML_New/docs/ids_live_sensor_architecture.md)
  - [ids_live_sensor_operations.md](F:/Work/IDS_ML_New/docs/ids_live_sensor_operations.md)
- Output paths are validated as distinct files before runtime starts, which lowers ambiguity around the ingest seam.
- The current producer does not internally rotate those JSONL outputs, so a same-host importer can safely start from an append-first contract and still protect itself against future truncation/replacement.

## Validated Constraints

1. The importer should tail the JSONL files, not journald, because the JSONL files are the durable source of truth.
2. Offset state must be committed only after a full newline-terminated record is parsed successfully.
3. The importer must track file identity plus offset and reset safely on truncate/replace instead of assuming monotonic append forever.
4. Attack alerts, schema anomalies, and summaries must remain separate record classes in storage, matching the upstream contract.

## Impact on Plan

- The file-tail ingest seam remains viable.
- Validation is not blocked on the current `alerts/quarantine/summary` contract.
- Execution beads should lock around newline-safe offset commits, truncate/replace detection, and JSONL-first ingest.
