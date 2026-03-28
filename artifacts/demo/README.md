# Demo Fixtures

`ids_realtime_pipeline_sample.jsonl` is a lightweight dry-run fixture for the v1 IDS realtime path.

It intentionally mixes:
- valid structured flow events
- a record that fails numeric feature validation
- an invalid JSON line

The fixture exists so local review can demonstrate `JSONL -> alert/quarantine` behavior without heavy datasets or live network capture.

It is intentionally not a full `72`-feature production sample for the packaged CatBoost bundle. Use a properly aligned `72`-feature JSONL input when validating the real model bundle end to end.

`ids_record_adapter_primary_sample.jsonl` and `ids_record_adapter_secondary_sample.jsonl` are lightweight adapter fixtures for the v1 structured-record adapter.

Each file mixes:
- one valid synthetic profile record
- one quarantine candidate for the same profile

They are intentionally small synthetic samples that exercise profile-specific naming, quarantine behavior, and downstream handoff without copying production traffic or heavy datasets.
