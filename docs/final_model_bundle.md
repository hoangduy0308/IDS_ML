# Gói Model Cuối Cùng

## Mục tiêu

Sau bước này, model cuối không còn là tập hợp các file rời rạc trong `artifacts`, mà được đóng gói thành một bundle tự chứa để dùng lại cho inference.

Script đóng gói:

- [package_final_model.py](F:/Work/IDS_ML_New/scripts/package_final_model.py)

Script inference hỗ trợ bundle:

- [ids_inference.py](F:/Work/IDS_ML_New/scripts/ids_inference.py)

## Bundle gồm gì

Bundle cuối được đóng tại:

- `F:\\Work\\IDS_ML_New\\artifacts\\final_model\\catboost_full_data_v1`

Nội dung:

- `model.cbm`
- `feature_columns.json`
- `model_bundle.json`
- `metrics.json`
- `training_summary.json`
- `MODEL_CARD.md`

## Ý nghĩa từng file

### `model.cbm`

Artifact mô hình `CatBoost full-data` đã chốt.

### `feature_columns.json`

Schema `72` feature phải có để inference chạy đúng.

### `model_bundle.json`

Config trung tâm của bundle, gồm:

- vị trí model artifact
- vị trí feature schema
- threshold đang dùng
- nhãn `Attack/Benign`
- train rows
- metrics chính
- metadata nguồn

### `metrics.json`

Tóm tắt các metric cuối dùng cho model card hoặc báo cáo nhanh.

### `training_summary.json`

Thông tin train full-data gốc.

### `MODEL_CARD.md`

Tài liệu mô tả model cuối dưới dạng ngắn gọn, dễ tra cứu.

## Cách dựng bundle

```powershell
python F:\Work\IDS_ML_New\scripts\package_final_model.py
```

## Cách dùng bundle để chạy inference

```powershell
python F:\Work\IDS_ML_New\scripts\ids_inference.py `
  --bundle-root F:\Work\IDS_ML_New\artifacts\final_model\catboost_full_data_v1 `
  --input-path F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary\clean\test.parquet `
  --output-path F:\Work\IDS_ML_New\artifacts\demo\test_predictions_from_bundle.parquet `
  --limit 1000
```

## Kết luận

Bundle này là hình thức “đầy đủ” của model ở giai đoạn hiện tại:

- có artifact
- có schema
- có threshold
- có metadata
- có metrics
- có model card
- có CLI inference dùng trực tiếp

Nó chưa phải service triển khai IDS, nhưng đã đủ để coi là một model package hoàn chỉnh.

## Vai trò của bundle trong realtime pipeline

Bundle này cũng là nguồn cấu hình chuẩn cho lớp realtime pre-model pipeline:

- [ids_realtime_pipeline.py](F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py)
- [ids_realtime_pipeline_architecture.md](F:/Work/IDS_ML_New/docs/ids_realtime_pipeline_architecture.md)

Trong pipeline mới:

- `feature_columns.json` là contract chuẩn của đúng `72` model features
- `model_bundle.json` giữ threshold, label names, và metadata bundle
- `model.cbm` vẫn là artifact scoring trung tâm

Lớp realtime chỉ được phép dùng bundle để:

- validate và align record vào canonical feature order
- build inferencer dùng lại logic batch hiện có
- chấm điểm các record hợp lệ

Lớp realtime không được dùng bundle để hợp thức hóa record lỗi bằng cách:

- tự điền feature bị thiếu
- suy diễn feature mới
- đưa passthrough metadata vào model scoring

Metadata ngoài schema vẫn có thể đi cùng alert/quarantine output để trace pipeline, nhưng chúng không phải thành phần của contract model. Điều này giúp giữ rõ ranh giới giữa:

- `model alerts` được sinh bởi `72` canonical features hợp lệ
- `schema/pipeline anomaly alerts` được sinh khi input không khớp contract bundle
