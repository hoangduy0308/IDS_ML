# Kiến trúc Inference Cho IDS

## Mục tiêu

Tầng này chịu trách nhiệm nhận `flow-based features` đã được trích xuất, chuẩn hóa đúng schema khi train, chạy mô hình `CatBoost full-data`, áp `threshold = 0.5`, và trả ra quyết định cảnh báo cho IDS.

Mô hình được dùng:

- [catboost_full_data_attempt.cbm](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/catboost_full_data_attempt/catboost_full_data_attempt_results/catboost_full_data_attempt.cbm)

Schema feature:

- [feature_columns.json](F:/Work/IDS_ML_New/artifacts/cic_iot_diad_2024_binary/manifests/feature_columns.json)

Quyết định chốt:

- [final_model_decision.md](F:/Work/IDS_ML_New/docs/final_model_decision.md)

## Luồng xử lý

```mermaid
flowchart LR
    A["Network traffic / flow records"] --> B["Feature extraction"]
    B --> C["Schema alignment (72 features)"]
    C --> D["CatBoost full-data inference"]
    D --> E["Thresholding (0.5)"]
    E --> F["Predicted label / score / alert"]
    F --> G["IDS event log / alert sink / dashboard"]
```

## Ranh giới trách nhiệm

### 1. Feature extraction layer

Lớp này không nằm trong model inference script hiện tại. Nó có nhiệm vụ:

- nhận packet hoặc flow gốc
- tính ra đúng các cột feature đã dùng khi train
- bảo đảm tên cột và đơn vị đo nhất quán

Nếu lớp này sinh sai schema, model layer phải fail sớm thay vì đoán.

### 2. Inference layer

Inference layer chịu trách nhiệm:

- load model
- load danh sách feature columns
- kiểm tra input có đủ cột không
- ép dữ liệu về numeric
- chạy `predict_proba`
- lấy `attack_score`
- áp `threshold = 0.5`
- trả ra:
  - `attack_score`
  - `predicted_label`
  - `is_alert`

### 3. Alerting layer

Sau khi có kết quả inference, IDS có thể:

- ghi log JSON
- đẩy event vào SIEM
- hiện dashboard
- hoặc kích hoạt rule phản ứng tiếp theo

Ở giai đoạn hiện tại, lớp này mới dừng ở output dự đoán, chưa gắn vào message bus hay service runtime.

## File triển khai

Module inference:

- [ids_inference.py](F:/Work/IDS_ML_New/scripts/ids_inference.py)

Script này hỗ trợ:

- input `CSV`
- input `Parquet`
- output kèm toàn bộ input + cột dự đoán
- hoặc chỉ output cột dự đoán

CLI cơ bản:

```powershell
python F:\Work\IDS_ML_New\scripts\ids_inference.py `
  --input-path F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary\clean\test.parquet `
  --output-path F:\Work\IDS_ML_New\artifacts\demo\test_predictions.parquet `
  --limit 1000
```

## Hành vi hệ thống

### Input hợp lệ

Input phải có đủ đúng `72` feature đã train. Có thể có thêm cột khác, nhưng inference layer chỉ dùng các cột trong schema.

### Input lỗi

Script sẽ fail sớm nếu:

- thiếu cột bắt buộc
- có cột bắt buộc nhưng không ép được sang numeric
- file input không phải `CSV` hoặc `Parquet`

Điều này là chủ ý để tránh silent mismatch giữa train và deploy.

## Output

Output tối thiểu gồm:

- `attack_score`: xác suất thuộc lớp `Attack`
- `predicted_label`: `Attack` hoặc `Benign`
- `is_alert`: `True/False`
- `threshold`: ngưỡng đang dùng

## Gợi ý tích hợp thực tế

### Prototype / demo

- chạy batch từ file `CSV/Parquet`
- dùng output để làm dashboard hoặc báo cáo minh họa

### Near-real-time IDS

- feature extractor ghi flow record vào queue hoặc file sink
- inference service đọc từng batch nhỏ
- service append `attack_score` và `is_alert`
- event được gửi đến alert pipeline

### Production-hardening cần làm thêm

- đóng gói model + schema + threshold vào config versioned
- thêm logging chuẩn và health check
- đo latency / throughput
- giám sát data drift
- đánh giá lại threshold trên traffic thật
