# IDS_ML_New

Đây là project đồ án xây dựng hệ thống IDS dựa trên machine learning trên bộ dữ liệu `CIC IoT-DIAD 2024` theo hướng:

`flow-based features -> preprocessing -> benchmark/tuning -> final model bundle -> inference/runtime IDS`

## Trạng thái hiện tại

- Dataset nhánh `Anomaly Detection - Flow Based features` đã được làm sạch và freeze thành bộ dữ liệu nhị phân `Benign/Attack`.
- Phần thực nghiệm mô hình đã hoàn thành các bước benchmark, tuning, scaling công bằng, full-data training và threshold analysis.
- Mô hình cuối đã được chốt là `CatBoost full-data` với `threshold = 0.5`.
- Repo đã có batch inference, realtime pre-model pipeline, structured record adapter, live sensor, operator console và test suite đi kèm.

## Quyết định mô hình cuối

- Model: `CatBoost full-data`
- Feature count: `72`
- Threshold vận hành: `0.5`
- Bundle hiện tại: [artifacts/final_model/catboost_full_data_v1](F:/Work/IDS_ML_New/artifacts/final_model/catboost_full_data_v1)
- Tài liệu chốt: [docs/final_model_decision.md](F:/Work/IDS_ML_New/docs/final_model_decision.md)

## Cấu trúc chính

- [docs](F:/Work/IDS_ML_New/docs): cổng vào tài liệu; xem [docs/README.md](F:/Work/IDS_ML_New/docs/README.md) để đi theo luồng `current` trước, `archive` sau
- [scripts](F:/Work/IDS_ML_New/scripts): preprocessing, training, inference, runtime IDS
- [artifacts](F:/Work/IDS_ML_New/artifacts): dataset đã freeze, output thực nghiệm, final model bundle, demo fixtures
- [tests](F:/Work/IDS_ML_New/tests): regression tests cho các thành phần chính
- [deploy](F:/Work/IDS_ML_New/deploy): ví dụ `systemd` và `nginx` cho same-host deployment

## Môi trường

Project hiện dùng Python `3.11.x`.

Cài dependency Python:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Lưu ý:

- `requirements.txt` chỉ cover phần Python.
- Các thành phần live sensor/same-host stack còn cần dependency hệ thống ngoài Python như `dumpcap`, `Java`, CICFlowMeter command-mode wrapper và `jnetpcap`.
- Benchmark Kaggle là môi trường riêng, không được tái tạo hoàn toàn chỉ bằng local `requirements.txt`.

## Kiểm tra nhanh

Chạy một nhóm test tiêu biểu:

```powershell
python -m pytest tests/test_ids_inference.py tests/test_ids_realtime_pipeline.py tests/test_ids_record_adapter.py -q
```

Batch inference với final bundle:

```powershell
python -m scripts.ids_inference `
  --bundle-root artifacts/final_model/catboost_full_data_v1 `
  --input-path artifacts/cic_iot_diad_2024_binary/clean/test.parquet `
  --output-path artifacts/demo/test_predictions_from_bundle.parquet `
  --limit 10000
```

## Đường đọc tài liệu chuẩn

Nếu cần đọc đúng theo logic đồ án, nên đi theo thứ tự sau:

1. [docs/README.md](F:/Work/IDS_ML_New/docs/README.md)
2. [docs/current/README.md](F:/Work/IDS_ML_New/docs/current/README.md)
3. [docs/archive/README.md](F:/Work/IDS_ML_New/docs/archive/README.md)

Tài liệu hiện hành vẫn sống ở `docs/`, nhưng các file đã được nhóm theo vai trò:

- `current`: tài liệu đang dùng để ra quyết định, vận hành, hoặc đọc như nguồn chuẩn
- `archive`: memo, ghi chú lịch sử, và nội dung đã thay thế

## Tài liệu lịch sử và tài liệu đã bị thay thế

Một số file trong `docs/` vẫn được giữ để lưu dấu quá trình phát triển, nhưng không còn là nguồn kết luận chính cho đồ án. Các file này đã được gắn notice `superseded` hoặc `historical` ngay đầu tài liệu.

Ưu tiên dùng các tài liệu trong mục `Đường đọc tài liệu chuẩn` thay vì dựa vào các memo trung gian.
