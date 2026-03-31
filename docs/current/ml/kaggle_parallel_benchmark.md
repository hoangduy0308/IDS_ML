# Kaggle Parallel Benchmark

Mục tiêu của bộ asset này là giữ nguyên bộ split nhị phân đã freeze và train từng mô hình trên cùng một dataset package khi đưa lên Kaggle.

## Dataset Package

- Nguồn local freeze: `F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary`
- Thư mục staging upload: `F:\Work\IDS_ML_New\artifacts\kaggle\datasets\cic-iot-diad-2024`
- Dataset đang dùng trên Kaggle: `hdiiii/cic-iot-diad-2024`

File trong package upload:

- `train.parquet`
- `val.parquet`
- `test.parquet`
- `ood_attack_holdout.parquet`
- `file_manifest.csv`
- `quarantine_manifest.csv`
- `cleaning_report.json`
- `feature_columns.json`
- `README.md`
- `dataset-metadata.json`

## Kernels

Các kernel được sinh sẵn ở `F:\Work\IDS_ML_New\artifacts\kaggle\kernels`:

- `logreg`
- `random_forest`
- `hist_gb`
- `catboost`
- `mlp`

Mỗi kernel:

- dùng cùng dataset source `hdiiii/cic-iot-diad-2024`
- đọc cùng `feature_columns.json`
- train trên `train.parquet`
- đánh giá trên `val`, `test`, `ood_attack_holdout`
- lưu `metrics.json`, `summary.csv`, `training_summary.json` và model artifact vào `/kaggle/working/<model_name>_results/`

## Trạng thái hiện tại

Tính đến lần chạy Kaggle hiện tại:

- `ids-binary-logistic-regression`: `COMPLETE`
- `ids-binary-random-forest`: `COMPLETE`
- `ids-binary-hist-gradient-boosting`: `COMPLETE`
- `ids-binary-catboost`: `COMPLETE`
- `ids-binary-mlp`: `COMPLETE`

Output đã được tải về:

- `F:\Work\IDS_ML_New\artifacts\kaggle\outputs\logreg`
- `F:\Work\IDS_ML_New\artifacts\kaggle\outputs\random_forest`
- `F:\Work\IDS_ML_New\artifacts\kaggle\outputs\hist_gb`
- `F:\Work\IDS_ML_New\artifacts\kaggle\outputs\catboost`
- `F:\Work\IDS_ML_New\artifacts\kaggle\outputs\mlp`

## Chuẩn bị Asset

```powershell
python .\scripts\stage_kaggle_benchmark.py
```

## Upload Dataset

Tạo dataset private:

```powershell
kaggle datasets create -p .\artifacts\kaggle\datasets\cic-iot-diad-2024 -q
```

Nếu dataset đã tồn tại, cập nhật version:

```powershell
kaggle datasets version -p .\artifacts\kaggle\datasets\cic-iot-diad-2024 -m "refresh frozen binary IDS split" -q
```

## Push Kernel Song Song

```powershell
kaggle kernels push -p .\artifacts\kaggle\kernels\logreg
kaggle kernels push -p .\artifacts\kaggle\kernels\random_forest
kaggle kernels push -p .\artifacts\kaggle\kernels\hist_gb
kaggle kernels push -p .\artifacts\kaggle\kernels\catboost
kaggle kernels push -p .\artifacts\kaggle\kernels\mlp
```

## Theo Dõi Trạng Thái

```powershell
kaggle kernels status hdiiii/ids-binary-logistic-regression
kaggle kernels status hdiiii/ids-binary-random-forest
kaggle kernels status hdiiii/ids-binary-hist-gradient-boosting
kaggle kernels status hdiiii/ids-binary-catboost
kaggle kernels status hdiiii/ids-binary-mlp
```

## Ghi Chú Vận Hành

- `RandomForest`, `HistGradientBoosting`, `CatBoost` đã được chuyển sang chiến lược sampled-in-memory để tránh OOM nhưng vẫn giữ cùng split dataset.
- `MLP` có fallback về CPU khi Kaggle cấp `Tesla P100` không tương thích với build PyTorch hiện tại.
- `CatBoost` là mô hình có `FPR` thấp nhất trong các mô hình hoàn tất.
- Kết quả tổng hợp cuối cùng nằm ở [training_benchmark_results.md](F:/Work/IDS_ML_New/docs/current/ml/training_benchmark_results.md).
