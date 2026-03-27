# Demo Fixtures

`ids_realtime_pipeline_sample.jsonl` is a lightweight dry-run fixture for the v1 IDS realtime path.

It intentionally mixes:
- valid structured flow events
- a record that fails numeric feature validation
- an invalid JSON line

The fixture exists so local review can demonstrate `JSONL -> alert/quarantine` behavior without heavy datasets or live network capture.
