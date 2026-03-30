# System Evaluation

## Phạm vi

Tài liệu này ghi lại các số đo kiểm tra nhanh cho hệ thống hiện tại ở mức:

- batch inference
- realtime pipeline
- adapter -> runtime end-to-end
- regression tests

Đây là **sanity/performance snapshot** trên workspace hiện tại, không phải benchmark hạ tầng độc lập phần cứng.

## Môi trường Python đã kiểm tra

Các phiên bản đang có trên máy lúc rà soát:

| Thành phần | Version |
|---|---:|
| Python | `3.11.9` |
| numpy | `2.4.2` |
| pandas | `3.0.1` |
| pyarrow | `22.0.0` |
| scikit-learn | `1.6.1` |
| catboost | `1.2.10` |
| fastapi | `0.115.12` |
| uvicorn | `0.34.0` |
| pytest | `8.3.5` |

## Kết quả đo nhanh

### 1. Batch inference core

Đo trực tiếp bằng Python trên `10,000` dòng đầu của `test.parquet`, chỉ tính phần load model đã sẵn và scoring:

- rows: `10,000`
- elapsed: `0.5881s`
- throughput xấp xỉ: `17,002.68 rows/s`
- feature count: `72`

Diễn giải:

- lõi scoring của final model đủ nhanh cho demo và kiểm thử local
- con số này chưa tính full overhead của process CLI và ghi file output

### 2. Batch inference CLI end-to-end

Lệnh:

```powershell
python -m scripts.ids_inference `
  --bundle-root artifacts/final_model/catboost_full_data_v1 `
  --input-path artifacts/cic_iot_diad_2024_binary/clean/test.parquet `
  --output-path artifacts/demo/_tmp_eval_predictions_cli.parquet `
  --limit 10000
```

Kết quả:

- return code: `0`
- rows scored: `10,000`
- alert rows: `9,596`
- elapsed end-to-end: `4.0241s`

Diễn giải:

- phần lớn overhead nằm ở startup process, đọc parquet và ghi output
- nếu chỉ xét logic scoring thì tốc độ thực tế tốt hơn nhiều như mục trên

### 3. Realtime pipeline dry-run trên fixture lỗi

Lệnh:

```powershell
python -m scripts.ids_realtime_pipeline `
  --input-path artifacts/demo/ids_realtime_pipeline_sample.jsonl `
  --alerts-output-path <temp_alerts.jsonl> `
  --quarantine-output-path <temp_quarantine.jsonl> `
  --max-batch-size 2 `
  --flush-interval-seconds 0.1
```

Kết quả:

- total records: `4`
- valid records: `0`
- schema anomaly records: `4`
- alert records: `0`
- elapsed: `1.6221s`

Ý nghĩa:

- runtime quarantine path đang hoạt động đúng với fixture chứa record lỗi và invalid JSON
- đường này phù hợp để chứng minh fail-closed behavior của pipeline trước model

### 4. Adapter -> runtime end-to-end demo

Đầu vào:

- [artifacts/demo/ids_record_adapter_primary_sample.jsonl](F:/Work/IDS_ML_New/artifacts/demo/ids_record_adapter_primary_sample.jsonl)

Kết quả chạy adapter:

- adapted records: `1`
- adapter quarantine records: `1`
- elapsed: `0.0975s`

Kết quả chạy tiếp qua realtime pipeline:

- alert records: `1`
- runtime quarantine records: `0`
- elapsed: `0.9407s`

Tổng end-to-end:

- elapsed: `1.0383s`

Ý nghĩa:

- đường adapter -> canonical 72-feature record -> model prediction đang thông suốt
- đây là bằng chứng demo rất phù hợp cho đồ án vì không cần traffic thật hoặc packet capture

## Kết quả test

Nhóm test tiêu biểu đã chạy:

```powershell
python -m pytest tests/test_ids_inference.py tests/test_ids_realtime_pipeline.py tests/test_ids_record_adapter.py -q
```

Kết quả:

- `98 passed in 8.96s`

Có một cảnh báo từ `pytest-asyncio` về `asyncio_default_fixture_loop_scope`, nhưng không làm fail test.

## Giới hạn của phần đánh giá hiện tại

- chưa có đo RAM/CPU theo từng service
- chưa có đo sustained throughput trên stream dài hoặc capture live thật
- chưa có đánh giá drift trên traffic thực tế ngoài dataset
- chưa có benchmark Linux deployment đầy đủ cho `ids_live_sensor` và `ids_operator_console`

## Kết luận

Ở mức đồ án môn học, hệ thống hiện đã có:

- bằng chứng batch inference chạy được với final bundle
- bằng chứng runtime quarantine hoạt động đúng
- bằng chứng adapter và realtime pipeline nối được với model
- regression tests khá dày cho các thành phần chính

Phần còn thiếu nếu muốn đi theo hướng nghiên cứu sâu hơn là benchmark hạ tầng dài hạn, không phải thiếu nền tảng để chứng minh hệ thống IDS đã được xây dựng.
