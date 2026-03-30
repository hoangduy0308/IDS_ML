# End-to-End Demo Runbook

## Mục tiêu

Runbook này gom các lệnh demo ngắn nhất để chứng minh repo đã có đầy đủ đường đi:

- batch inference từ final model bundle
- structured record adapter
- realtime pipeline
- end-to-end adapter -> pipeline -> alert

Các lệnh dưới đây giả định bạn đang đứng ở root repo `F:\Work\IDS_ML_New`.

## Chuẩn bị

```powershell
python -m pip install -r requirements.txt
```

Nếu muốn kiểm tra nhanh trước khi demo:

```powershell
python -m pytest tests/test_ids_inference.py tests/test_ids_realtime_pipeline.py tests/test_ids_record_adapter.py -q
```

## Demo 1: Batch inference với model cuối

Lệnh:

```powershell
python -m scripts.ids_inference `
  --bundle-root artifacts/final_model/catboost_full_data_v1 `
  --input-path artifacts/cic_iot_diad_2024_binary/clean/test.parquet `
  --output-path artifacts/demo/test_predictions_from_bundle.parquet `
  --limit 10000
```

Kỳ vọng:

- lệnh trả JSON summary
- `feature_count = 72`
- có file output `artifacts/demo/test_predictions_from_bundle.parquet`

Ý nghĩa demo:

- final bundle load được
- schema khớp
- model đã score được dữ liệu thật từ split `test`

## Demo 2: Structured record adapter

Dùng fixture adapter nhỏ:

- [artifacts/demo/ids_record_adapter_primary_sample.jsonl](F:/Work/IDS_ML_New/artifacts/demo/ids_record_adapter_primary_sample.jsonl)

Lệnh:

```powershell
python -m scripts.ids_record_adapter `
  --profile cicflowmeter_primary_v1 `
  --input-path artifacts/demo/ids_record_adapter_primary_sample.jsonl `
  --output-path artifacts/demo/ids_record_adapter_primary_adapted.jsonl `
  --quarantine-output-path artifacts/demo/ids_record_adapter_primary_quarantine.jsonl
```

Kỳ vọng:

- adapted output có `1` record hợp lệ
- quarantine output có `1` record lỗi

Ý nghĩa demo:

- adapter đã normalize record CICFlowMeter-like về canonical 72-feature boundary
- record không hợp lệ bị quarantine riêng

## Demo 3: Realtime pipeline với fixture lỗi

Fixture:

- [artifacts/demo/ids_realtime_pipeline_sample.jsonl](F:/Work/IDS_ML_New/artifacts/demo/ids_realtime_pipeline_sample.jsonl)

Lệnh:

```powershell
python -m scripts.ids_realtime_pipeline `
  --input-path artifacts/demo/ids_realtime_pipeline_sample.jsonl `
  --alerts-output-path artifacts/demo/ids_realtime_pipeline_alerts.jsonl `
  --quarantine-output-path artifacts/demo/ids_realtime_pipeline_quarantine.jsonl `
  --max-batch-size 2 `
  --flush-interval-seconds 0.1
```

Kỳ vọng:

- summary cho thấy `schema_anomaly_records > 0`
- fixture này chủ yếu chứng minh runtime quarantine path

Lưu ý:

- script `ids_realtime_pipeline` hiện có default path trỏ sẵn tới final model local
- trong trạng thái hiện tại, demo ổn định nhất là dùng default path của script thay vì trộn thêm `--bundle-root`

## Demo 4: End-to-end adapter -> pipeline -> alert

### Bước 1

```powershell
python -m scripts.ids_record_adapter `
  --profile cicflowmeter_primary_v1 `
  --input-path artifacts/demo/ids_record_adapter_primary_sample.jsonl `
  --output-path artifacts/demo/e2e_adapted.jsonl `
  --quarantine-output-path artifacts/demo/e2e_adapter_quarantine.jsonl
```

### Bước 2

```powershell
python -m scripts.ids_realtime_pipeline `
  --input-path artifacts/demo/e2e_adapted.jsonl `
  --alerts-output-path artifacts/demo/e2e_alerts.jsonl `
  --quarantine-output-path artifacts/demo/e2e_runtime_quarantine.jsonl `
  --max-batch-size 8 `
  --flush-interval-seconds 0.1
```

Kỳ vọng:

- `e2e_adapter_quarantine.jsonl` có `1` record quarantine từ adapter
- `e2e_alerts.jsonl` có `1` alert record từ runtime/model
- `e2e_runtime_quarantine.jsonl` rỗng hoặc không có record

Ý nghĩa demo:

- record nguồn đi qua adapter
- record hợp lệ được đưa vào realtime pipeline
- final model sinh `model_prediction`/alert thành công

## Demo 5: Final bundle contract

Verify bundle:

```powershell
python -m scripts.ids_model_bundle_manage `
  --activation-path artifacts/runtime/active_bundle.json `
  --json verify `
  --bundle-root artifacts/final_model/catboost_full_data_v1
```

Nếu chưa có `artifacts/runtime/active_bundle.json`, bạn có thể bỏ qua phần này khi demo đồ án vì batch inference và end-to-end demo ở trên đã đủ để chứng minh hệ thống.

## Gợi ý thứ tự trình bày khi demo

1. giới thiệu final model bundle
2. chạy batch inference để chứng minh model cuối hoạt động
3. chạy adapter để cho thấy có lớp chuẩn hóa input
4. chạy realtime pipeline để cho thấy có quarantine path
5. chạy adapter -> pipeline để cho thấy đường end-to-end phát alert

Thứ tự này phù hợp hơn nhiều cho đồ án so với việc cố demo toàn bộ live sensor trên Linux.
