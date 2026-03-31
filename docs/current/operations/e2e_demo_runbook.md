# End-to-End Demo Runbook

## Purpose

This runbook collects the shortest commands needed to show the repo has the full path:

- offline closed-window extractor
- batch inference from the final model bundle
- structured record adapter
- realtime pipeline
- end-to-end adapter -> pipeline -> alert

The commands below assume you are at the repo root `F:\Work\IDS_ML_New`.

## Preparation

```powershell
python -m pip install -r requirements.txt
```

For a quick smoke check before demoing:

```powershell
python -m pytest tests/runtime/test_ids_inference.py tests/runtime/test_ids_realtime_pipeline.py tests/runtime/test_ids_record_adapter.py -q
```

## Demo 0: Offline closed-window extractor

This demo shows the replacement extractor path directly.

Golden output artifacts:

- [artifacts/demo/flows/capture-00001_Flow.csv](F:/Work/IDS_ML_New/artifacts/demo/flows/capture-00001_Flow.csv)
- [artifacts/demo/ids_offline_window_extractor_expected.csv](F:/Work/IDS_ML_New/artifacts/demo/ids_offline_window_extractor_expected.csv)

Command:

```powershell
python -m scripts.ids_offline_window_extractor `
  <closed-window.pcap> `
  artifacts/demo/flows `
  --profile-id cicflowmeter_primary_v1
```

Expected result:

- the extractor writes one `*_Flow.csv` file into `artifacts/demo/flows/`
- the output matches the golden closed-window CSV shape used by the adapter layer
- the generated rows remain consumable by the bridge and adapter path without inventing missing model features

Meaning:

- this is the first proof that the replacement extractor can turn a closed pcap window into the downstream contract shape
- the demo intentionally stops at the extractor boundary; adapter and runtime checks come next

## Demo 1: Batch inference with the final model

Command:

```powershell
python -m scripts.ids_inference `
  --bundle-root artifacts/final_model/catboost_full_data_v1 `
  --input-path artifacts/cic_iot_diad_2024_binary/clean/test.parquet `
  --output-path artifacts/demo/test_predictions_from_bundle.parquet `
  --limit 10000
```

Expected result:

- the command returns a JSON summary
- `feature_count = 72`
- output file `artifacts/demo/test_predictions_from_bundle.parquet` exists

Meaning:

- the final bundle loads
- the schema matches
- the model scores real data from the `test` split

## Demo 2: Structured record adapter

Fixture:

- [artifacts/demo/ids_record_adapter_primary_sample.jsonl](F:/Work/IDS_ML_New/artifacts/demo/ids_record_adapter_primary_sample.jsonl)

Command:

```powershell
python -m scripts.ids_record_adapter `
  --profile cicflowmeter_primary_v1 `
  --input-path artifacts/demo/ids_record_adapter_primary_sample.jsonl `
  --output-path artifacts/demo/ids_record_adapter_primary_adapted.jsonl `
  --quarantine-output-path artifacts/demo/ids_record_adapter_primary_quarantine.jsonl
```

Expected result:

- the adapted output has `1` valid record
- the quarantine output has `1` invalid record

Meaning:

- the adapter normalizes CICFlowMeter-like input into the canonical 72-feature boundary
- invalid records are quarantined separately

## Demo 3: Realtime pipeline with error fixture

Fixture:

- [artifacts/demo/ids_realtime_pipeline_sample.jsonl](F:/Work/IDS_ML_New/artifacts/demo/ids_realtime_pipeline_sample.jsonl)

Command:

```powershell
python -m scripts.ids_realtime_pipeline `
  --input-path artifacts/demo/ids_realtime_pipeline_sample.jsonl `
  --alerts-output-path artifacts/demo/ids_realtime_pipeline_alerts.jsonl `
  --quarantine-output-path artifacts/demo/ids_realtime_pipeline_quarantine.jsonl `
  --max-batch-size 2 `
  --flush-interval-seconds 0.1
```

Expected result:

- the summary shows `schema_anomaly_records > 0`
- the fixture primarily proves the runtime quarantine path

Note:

- `ids_realtime_pipeline` has a default path that points at the final model bundle
- for the demo, the default path is usually simpler than overriding `--bundle-root`

## Demo 4: End-to-end adapter -> pipeline -> alert

Step 1:

```powershell
python -m scripts.ids_record_adapter `
  --profile cicflowmeter_primary_v1 `
  --input-path artifacts/demo/ids_record_adapter_primary_sample.jsonl `
  --output-path artifacts/demo/e2e_adapted.jsonl `
  --quarantine-output-path artifacts/demo/e2e_adapter_quarantine.jsonl
```

Step 2:

```powershell
python -m scripts.ids_realtime_pipeline `
  --input-path artifacts/demo/e2e_adapted.jsonl `
  --alerts-output-path artifacts/demo/e2e_alerts.jsonl `
  --quarantine-output-path artifacts/demo/e2e_runtime_quarantine.jsonl `
  --max-batch-size 8 `
  --flush-interval-seconds 0.1
```

Expected result:

- `e2e_adapter_quarantine.jsonl` contains `1` quarantined adapter record
- `e2e_alerts.jsonl` contains `1` alert record from runtime/model
- `e2e_runtime_quarantine.jsonl` is empty or contains no records

Meaning:

- the source record passes through the adapter
- the valid record enters the realtime pipeline
- the final model produces `model_prediction` / alert output successfully

## Demo 5: Final bundle contract

Verify the bundle:

```powershell
python -m scripts.ids_model_bundle_manage `
  --activation-path artifacts/runtime/active_bundle.json `
  --json verify `
  --bundle-root artifacts/final_model/catboost_full_data_v1
```

If `artifacts/runtime/active_bundle.json` does not exist, you can skip this part during a repo demo because the batch inference and end-to-end demos above already prove the system path.

## Suggested Demo Order

1. Introduce the final model bundle.
2. Run the offline closed-window extractor demo.
3. Run batch inference to show the final model works.
4. Run the adapter demo to show input normalization.
5. Run the realtime pipeline demo to show the quarantine path.
6. Run the adapter -> pipeline demo to show the end-to-end alert path.

This order reads more clearly than trying to demo the entire live sensor stack on Linux first.
