# Thiết lập hyperparameter tuning cho 3 mô hình chính

## Mục tiêu

Thiết lập một pipeline tuning tái lập được cho:

- `CatBoost`
- `Random Forest`
- `HistGradientBoosting`

Pipeline này được thiết kế để:

1. không dùng `test` trong quá trình chọn config,
2. ưu tiên `FPR` thấp trước khi tối đa `F1`,
3. lưu đầy đủ artifact phục vụ báo cáo.

## Script chính

- `scripts/tune_top_models.py`

## Selection rule

Selection rule được lưu tại:

- `artifacts/tuning/smoke_top_models/reports/selection_rule.md`

Nội dung chính:

- hard gate: `val_fpr_at_default_0.5 <= 0.02`
- rank theo `val_f1_at_tuned_cap_0.010`
- tie-break:
  - thấp hơn `val_fpr_at_default_0.5`
  - cao hơn `ood_recall_at_tuned_cap_0.020`
  - thấp hơn `train_seconds`

## Search space

Search space chi tiết được lưu tự động tại:

- `search_space.json`

Script hiện hỗ trợ:

- `CatBoost`: tune sâu hơn
- `Random Forest`: tune đối chiếu
- `HistGradientBoosting`: tune đối chiếu

## Lượt smoke run đã chạy

Mình đã chạy một lượt smoke end-to-end để xác minh pipeline:

- output: `artifacts/tuning/smoke_top_models/reports/`

Artifacts đã có:

- `trial_results.csv`
- `trial_results_ranked.csv`
- `trial_results.jsonl`
- `best_configs.json`
- `search_space.json`
- `selection_rule.md`

## Workflow hiện tại

Không tiếp tục chạy `coarse search` đầy đủ trên máy local vì thời gian quá dài và dễ mất kết quả nếu job bị dừng giữa chừng.

Workflow mới:

1. `scripts/tune_top_models.py` vẫn là script lõi.
2. Script đã được thêm `checkpoint per trial` vào `progress.json`, `trial_results.csv`, `trial_results_ranked.csv` và `best_configs.json`.
3. Dùng `scripts/stage_kaggle_tuning.py` để tạo 3 kernel Kaggle riêng cho:
   - `CatBoost`
   - `Random Forest`
   - `HistGradientBoosting`
4. Chạy tuning trên Kaggle rồi tải output về để so sánh.

Trial count mặc định cho phase coarse trên Kaggle:

- `CatBoost`: `16`
- `Random Forest`: `10`
- `HistGradientBoosting`: `12`

## Cách chạy tiếp

### 1. Pilot run nhanh

```powershell
python F:\Work\IDS_ML_New\scripts\tune_top_models.py `
  --models catboost,random_forest,hist_gb `
  --trials catboost=4,random_forest=3,hist_gb=3 `
  --profile quick `
  --eval-max-rows 50000 `
  --ood-max-rows 20000 `
  --output-root F:\Work\IDS_ML_New\artifacts\tuning\pilot_top_models
```

### 2. Coarse search khuyến nghị

```powershell
python F:\Work\IDS_ML_New\scripts\stage_kaggle_tuning.py
```

Sau đó push 3 kernel:

```powershell
F:\Work\IDS_ML_New\artifacts\kaggle_tuning\push_tuning_kernels.ps1
```

Theo dõi trạng thái:

```powershell
F:\Work\IDS_ML_New\artifacts\kaggle_tuning\tuning_kernel_status.ps1
```

Tải output về:

```powershell
F:\Work\IDS_ML_New\artifacts\kaggle_tuning\download_tuning_outputs.ps1
```

### 3. Promotion run

Sau khi có `coarse_top_models`, chọn:

- top `2` trial của `CatBoost`
- top `1` trial của `Random Forest`
- top `1` trial của `HistGradientBoosting`

Rồi đem nhóm này qua bước:

1. train lại nghiêm túc hơn,
2. chạy `threshold tuning`,
3. đánh giá cuối trên `test`.

## Ghi chú cho báo cáo

Khi viết báo cáo, nên mô tả rõ:

1. tuning được thực hiện trên `train` và `validation subset`,
2. `test` không được dùng để chọn hyperparameter,
3. selection rule ưu tiên `FPR` thấp ở threshold mặc định,
4. `CatBoost` là mô hình được tune sâu nhất vì là ứng viên triển khai chính.
