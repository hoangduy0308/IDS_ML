# Kết quả benchmark IDS trên Kaggle

## Bối cảnh

Bộ dữ liệu dùng để train là bản đã xử lý và freeze từ `CIC IoT-DIAD 2024`, sau đó upload lên Kaggle dưới dataset:

- `hdiiii/cic-iot-diad-2024`

Các kernel đều dùng cùng một split cố định:

- `train.parquet`
- `val.parquet`
- `test.parquet`
- `ood_attack_holdout.parquet`

Số lượng mẫu theo split:

- `train`: `18,679,445`
- `val`: `4,410,064`
- `test`: `4,145,539`
- `ood_attack_holdout`: `444,422`

## Kết quả 5 mô hình

Kết quả được lấy từ output thật của 5 kernel Kaggle:

- [logreg summary.csv](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/logreg/logreg_results/summary.csv)
- [random_forest summary.csv](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/random_forest/random_forest_results/summary.csv)
- [hist_gb summary.csv](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/hist_gb/hist_gb_results/summary.csv)
- [catboost summary.csv](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/catboost/catboost_results/summary.csv)
- [mlp summary.csv](F:/Work/IDS_ML_New/artifacts/kaggle/outputs/mlp/mlp_results/summary.csv)

| Model | Train seconds | Test F1 | Test Recall | Test Precision | Test FPR | OOD Recall |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 165.40 | 0.990002 | 0.995904 | 0.984170 | 0.770623 | 0.816622 |
| Random Forest | 136.63 | 0.990995 | 0.982463 | 0.999676 | 0.015304 | 0.400354 |
| HistGradientBoosting | 306.22 | 0.990960 | 0.982377 | 0.999694 | 0.014463 | 0.397210 |
| CatBoost | 127.68 | 0.990900 | 0.982222 | 0.999733 | 0.012639 | 0.400354 |
| MLP | 566.06 | 0.989924 | 0.999974 | 0.980073 | 0.978086 | 0.998956 |

## Nhận xét chính

### 1. `Random Forest`, `HistGradientBoosting`, `CatBoost` là nhóm mô hình đáng tin cậy nhất

Ba mô hình này cho kết quả rất sát nhau về `Test F1`, nhưng cùng lúc vẫn giữ được:

- `Precision` gần như tuyệt đối
- `FPR` thấp
- hành vi dự đoán ổn định hơn trên dữ liệu IDS mất cân bằng

Trong nhóm này:

- `Random Forest` có `Test F1` cao nhất
- `CatBoost` có `FPR` thấp nhất
- `HistGradientBoosting` nằm rất sát cả hai

### 2. `Logistic Regression` và `MLP` không phù hợp để chọn làm mô hình triển khai chính

Mặc dù `Test F1` nhìn qua vẫn cao, nhưng hai mô hình này có vấn đề lớn:

- `Logistic Regression`: `FPR = 0.770623`
- `MLP`: `FPR = 0.978086`

Điều đó có nghĩa là số lượng false positive quá lớn, không phù hợp cho hệ thống IDS thực tế.  
`OOD Recall` của hai mô hình này cao, nhưng đổi lại bằng mức báo động giả rất cao, nên không thể xem là lựa chọn tốt hơn.

### 3. Nếu ưu tiên triển khai thực tế, `CatBoost` là ứng viên tốt nhất

`CatBoost` có:

- `Test F1` rất cao: `0.990900`
- `Precision` cao nhất nhóm gần tốt nhất: `0.999733`
- `FPR` thấp nhất toàn bộ các mô hình hợp lệ: `0.012639`
- thời gian train ngắn hơn `HistGradientBoosting` và vẫn đủ nhanh để thử nghiệm lặp lại: `127.68s`

Vì vậy, nếu cần chọn một mô hình chính để tiếp tục tối ưu và tích hợp vào IDS, hướng khuyến nghị là:

- `CatBoost`

### 4. `Random Forest` nên được giữ làm baseline mạnh nhất

`Random Forest` đạt `Test F1` tốt nhất: `0.990995`, nên rất phù hợp làm baseline đối chiếu.  
Tuy nhiên, do `FPR` vẫn cao hơn `CatBoost`, nó hợp hơn với vai trò mô hình so sánh hơn là mô hình chính cuối cùng.

## Kết luận

Thứ tự khuyến nghị sau benchmark Kaggle:

1. `CatBoost`
2. `Random Forest`
3. `HistGradientBoosting`
4. `Logistic Regression`
5. `MLP`

Nếu mục tiêu là xây dựng hệ thống IDS có khả năng đưa vào triển khai, mô hình nên đi tiếp là:

- `CatBoost`

Và các baseline nên giữ để so sánh trong báo cáo là:

- `Random Forest`
- `HistGradientBoosting`

## Tài liệu đào sâu

Phần phân tích learning curve, generalization gap, và diễn giải về khả năng overfitting của từng mô hình đã được lưu riêng tại:

- `docs/learning_curve_analysis.md`
- `docs/threshold_tuning_analysis.md`

Các biểu đồ phục vụ báo cáo được lưu trong:

- `docs/figures/`
