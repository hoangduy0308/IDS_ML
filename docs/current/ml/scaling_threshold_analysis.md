# Phân tích Threshold cho 3 Finalist Sau Scaling

## Phạm vi

Phân tích này dùng đúng 3 mô hình mạnh nhất ở vòng sau scaling:

- `CatBoost full-data`
- `RandomForest 8M`
- `HistGradientBoosting 8M`

Artifact nguồn:

- [catboost_full_data_attempt](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/catboost_full_data_attempt)
- [scaling_rf_8m](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/scaling_rf_8m)
- [scaling_histgb_8m](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/scaling_histgb_8m)

Artifact phân tích:

- [threshold_selection_summary.csv](F:/Work/IDS_ML_New/artifacts/posttrain_analysis/scaling_finalists/reports/threshold_selection_summary.csv)
- [threshold_evaluation_summary.csv](F:/Work/IDS_ML_New/artifacts/posttrain_analysis/scaling_finalists/reports/threshold_evaluation_summary.csv)

## Ngưỡng được chọn trên validation

Ở protocol hiện tại, ngưỡng khuyến nghị được chọn theo:

- `FPR cap = 2%` trên tập `validation`

Ngưỡng được chọn:

| Model | Threshold | Validation F1 | Validation Recall | Validation FPR |
|---|---:|---:|---:|---:|
| CatBoost full-data | `0.4750` | `0.988916` | `0.978485` | `0.019898` |
| RandomForest 8M | `0.6175` | `0.986680` | `0.974118` | `0.019854` |
| HistGB 8M | `0.3350` | `0.988570` | `0.977803` | `0.019624` |

## Kết quả trên test

### Threshold mặc định `0.5`

| Model | Test F1 | Test Recall | Test FPR | OOD Recall |
|---|---:|---:|---:|---:|
| CatBoost full-data | `0.993358` | `0.987366` | `0.027411` | `0.499575` |
| RandomForest 8M | `0.994047` | `0.988991` | `0.040287` | `0.508816` |
| HistGB 8M | `0.992704` | `0.985920` | `0.019889` | `0.457831` |

### Threshold tune theo `FPR cap = 2%`

| Model | Threshold | Test F1 | Test Recall | Test FPR | OOD Recall |
|---|---:|---:|---:|---:|---:|
| CatBoost full-data | `0.4750` | `0.993411` | `0.987490` | `0.028358` | `0.503949` |
| RandomForest 8M | `0.6175` | `0.993500` | `0.987653` | `0.027790` | `0.472598` |
| HistGB 8M | `0.3350` | `0.993397` | `0.987472` | `0.028832` | `0.491587` |

## Điều cần đọc đúng

### 1. Tune trên validation không đảm bảo test vẫn giữ đúng `2%`

Cả ba mô hình đều được chọn threshold để giữ `validation FPR <= 2%`, nhưng khi chuyển sang `test`, FPR đều tăng lên khoảng `2.78%` đến `2.88%`.

Điều này không phải lỗi code. Đây là khác biệt phân phối giữa `validation` và `test`, và là lý do không nên mô tả threshold cap như một ràng buộc tuyệt đối trên mọi split.

### 2. Threshold tuning chỉ cải thiện nhẹ ở nhóm finalist

So với threshold mặc định `0.5`:

- `CatBoost full-data`: `Test F1` tăng nhẹ, `OOD Recall` tăng nhẹ, nhưng `Test FPR` cũng tăng nhẹ
- `RandomForest 8M`: `Test FPR` giảm mạnh từ `0.040287` xuống `0.027790`, nhưng `Test F1` lại giảm
- `HistGB 8M`: `Test F1` tăng, `OOD Recall` tăng đáng kể, nhưng `Test FPR` tăng từ `0.019889` lên `0.028832`

Vì vậy threshold tuning ở giai đoạn này không tạo ra mô hình “thắng tuyệt đối”, mà chủ yếu dịch operating point giữa:

- ít false positive hơn
- hay recall / OOD recall tốt hơn

### 3. RandomForest vẫn rất mạnh nhưng mang rủi ro vận hành cao hơn

`RandomForest 8M` dẫn đầu ở threshold mặc định về:

- `Test F1`
- `Test Recall`
- `OOD Recall`

Nhưng đổi lại:

- `Test FPR` cao nhất
- thời gian train dài nhất

Đây là trade-off rất điển hình cho IDS: nếu ưu tiên phát hiện tối đa, `RandomForest` hấp dẫn; nếu ưu tiên hệ thống ít nhiễu hơn và dễ vận hành hơn, nó trở nên kém hấp dẫn hơn.

### 4. CatBoost full-data hiện là điểm cân bằng dễ bảo vệ nhất

`CatBoost full-data` không thắng tuyệt đối, nhưng có lợi thế kết hợp:

- train full-data thật
- train nhanh hơn rất nhiều
- `Test F1` và `OOD Recall` rất sát `RandomForest`
- `Test FPR` thấp hơn đáng kể so với `RandomForest`

Với mục tiêu đưa vào hệ thống IDS, đây vẫn là lựa chọn cân bằng và thực dụng nhất.

## Biểu đồ đã sinh

- [catboost_full_threshold_sweep.png](F:/Work/IDS_ML_New/docs/figures/catboost_full_threshold_sweep.png)
- [catboost_full_pr_roc.png](F:/Work/IDS_ML_New/docs/figures/catboost_full_pr_roc.png)
- [catboost_full_confusion_matrix_default.png](F:/Work/IDS_ML_New/docs/figures/catboost_full_confusion_matrix_default.png)
- [catboost_full_confusion_matrix_tuned.png](F:/Work/IDS_ML_New/docs/figures/catboost_full_confusion_matrix_tuned.png)
- [random_forest_8m_threshold_sweep.png](F:/Work/IDS_ML_New/docs/figures/random_forest_8m_threshold_sweep.png)
- [random_forest_8m_pr_roc.png](F:/Work/IDS_ML_New/docs/figures/random_forest_8m_pr_roc.png)
- [random_forest_8m_confusion_matrix_default.png](F:/Work/IDS_ML_New/docs/figures/random_forest_8m_confusion_matrix_default.png)
- [random_forest_8m_confusion_matrix_tuned.png](F:/Work/IDS_ML_New/docs/figures/random_forest_8m_confusion_matrix_tuned.png)
- [hist_gb_8m_threshold_sweep.png](F:/Work/IDS_ML_New/docs/figures/hist_gb_8m_threshold_sweep.png)
- [hist_gb_8m_pr_roc.png](F:/Work/IDS_ML_New/docs/figures/hist_gb_8m_pr_roc.png)
- [hist_gb_8m_confusion_matrix_default.png](F:/Work/IDS_ML_New/docs/figures/hist_gb_8m_confusion_matrix_default.png)
- [hist_gb_8m_confusion_matrix_tuned.png](F:/Work/IDS_ML_New/docs/figures/hist_gb_8m_confusion_matrix_tuned.png)

## Kết luận và quyết định sử dụng

Sau khi có scaling công bằng, full-data attempt và threshold analysis cuối:

1. `RandomForest 8M` là mô hình mạnh nhất nếu chỉ ưu tiên `F1` và `OOD Recall`.
2. `HistGB 8M` là baseline tốt nếu chỉ ưu tiên `FPR` thấp hơn.
3. `CatBoost full-data` là mô hình cân bằng nhất nếu nhìn đồng thời:
   - chất lượng phát hiện
   - chi phí train
   - khả năng scale
   - mức độ phù hợp cho hệ thống IDS thực tế

Quyết định cuối cùng được chốt là:

- `CatBoost full-data`
- `threshold = 0.5`

Lý do không chọn threshold `0.475`:

- lợi ích tăng `Test F1` và `OOD Recall` là rất nhỏ
- nhưng `Test FPR` lại tăng
- trong bối cảnh IDS, operating point mặc định `0.5` đơn giản hơn, ổn định hơn và dễ bảo vệ hơn
