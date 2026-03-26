# Phân tích threshold tuning cho 3 mô hình mạnh nhất

## Mục tiêu

Sau khi benchmark 5 mô hình, ba mô hình được giữ lại để đi tiếp là:

- `CatBoost`
- `Random Forest`
- `HistGradientBoosting`

Tài liệu này lưu lại phần tuning ngưỡng dự đoán để phục vụ hai mục tiêu:

1. chọn operating point phù hợp cho hệ thống IDS,
2. viết phần thảo luận giữa `FPR`, `Recall`, `F1`, và khả năng phát hiện `OOD attack`.

## Cách thực hiện

Phân tích được chạy trên local bằng chính model artifact tải về từ Kaggle:

- `artifacts/kaggle/outputs/catboost/catboost_results/catboost.cbm`
- `artifacts/kaggle/outputs/random_forest/random_forest_results/random_forest.joblib`
- `artifacts/kaggle/outputs/hist_gb/hist_gb_results/hist_gb.joblib`

Script dùng để sinh lại toàn bộ artifact:

- `scripts/posttrain_threshold_analysis.py`

Kiểm thử logic threshold:

- `tests/test_posttrain_threshold_analysis.py`

Nguyên tắc tuning:

- tune threshold trên tập `val`,
- dùng các ràng buộc `FPR cap`: `0.5%`, `1%`, `2%`, `5%`,
- sau đó đánh giá các ngưỡng này trên `test` và `ood_attack_holdout`.

## Artifact đã lưu

### Bảng số liệu

- `artifacts/posttrain_analysis/top_models/reports/threshold_selection_summary.csv`
- `artifacts/posttrain_analysis/top_models/reports/threshold_evaluation_summary.csv`

### Biểu đồ

- `docs/figures/catboost_threshold_sweep.png`
- `docs/figures/catboost_pr_roc.png`
- `docs/figures/catboost_confusion_matrix_default.png`
- `docs/figures/catboost_confusion_matrix_tuned.png`
- `docs/figures/random_forest_threshold_sweep.png`
- `docs/figures/random_forest_pr_roc.png`
- `docs/figures/random_forest_confusion_matrix_default.png`
- `docs/figures/random_forest_confusion_matrix_tuned.png`
- `docs/figures/hist_gb_threshold_sweep.png`
- `docs/figures/hist_gb_pr_roc.png`
- `docs/figures/hist_gb_confusion_matrix_default.png`
- `docs/figures/hist_gb_confusion_matrix_tuned.png`

## Ngưỡng được chọn trên tập validation

| Model | FPR cap 0.5% | FPR cap 1% | FPR cap 2% | FPR cap 5% |
|---|---:|---:|---:|---:|
| CatBoost | 0.5050 | 0.3400 | 0.2275 | 0.1250 |
| Random Forest | 0.5700 | 0.4475 | 0.3250 | 0.1925 |
| HistGradientBoosting | 0.5750 | 0.5000 | 0.3000 | 0.1400 |

Nhận xét:

- `CatBoost` có xu hướng chấp nhận ngưỡng thấp hơn để tăng recall mà vẫn giữ được `FPR` trong giới hạn.
- `Random Forest` và `HistGradientBoosting` cần ngưỡng cao hơn một chút để giữ cùng mức `FPR`.

## Kết quả trên test set

### 1. Ngưỡng mặc định `0.5`

| Model | Test F1 | Test Recall | Test FPR |
|---|---:|---:|---:|
| CatBoost | 0.990900 | 0.982222 | 0.012639 |
| Random Forest | 0.990995 | 0.982463 | 0.015304 |
| HistGradientBoosting | 0.990960 | 0.982377 | 0.014463 |

Nhận xét:

- Ở ngưỡng mặc định, `CatBoost` vẫn có `FPR` thấp nhất.
- `Random Forest` vẫn nhỉnh nhất về `F1`.
- Cả ba đều đã đủ mạnh để làm benchmark nghiêm túc.

### 2. Operating point cân bằng: tune theo `FPR cap = 2%` trên validation

| Model | Threshold | Test F1 | Test Recall | Test FPR | OOD Recall |
|---|---:|---:|---:|---:|---:|
| CatBoost | 0.2275 | 0.992877 | 0.986387 | 0.025965 | 0.444692 |
| Random Forest | 0.3250 | 0.992752 | 0.986187 | 0.028252 | 0.446438 |
| HistGradientBoosting | 0.3000 | 0.992690 | 0.985987 | 0.024425 | 0.448279 |

Nhận xét:

- Tuning threshold làm `F1` và `Recall` tăng rõ ở cả ba mô hình.
- `OOD Recall` cũng tăng từ khoảng `0.40` lên khoảng `0.44 - 0.45`.
- Nhưng `Test FPR` đều tăng lên khoảng `2.4% - 2.8%`.

Điểm cần nhấn mạnh trong báo cáo:

- `FPR cap = 2%` được đảm bảo trên `validation`, nhưng sang `test` thì `FPR` thực tế tăng thêm. Đây là hiện tượng bình thường khi operating point được chọn trên một split rồi đem sang split khác.
- Vì vậy, khi viết báo cáo nên phân biệt rõ:
  - **ngưỡng tune trên validation**,
  - **hiệu năng thực tế trên test**.

## Diễn giải quan trọng

### 1. `CatBoost` vẫn là lựa chọn cân bằng nhất

Ở cả hai chế độ:

- mặc định `0.5`,
- và tune ở `FPR cap = 2%`,

`CatBoost` đều cho kết quả rất mạnh:

- `FPR` thấp nhất ở chế độ mặc định,
- `F1` và `Recall` tăng tốt khi hạ threshold,
- chi phí train và suy luận vẫn hợp lý.

### 2. `Random Forest` vẫn là baseline đối chiếu rất mạnh

`Random Forest` có:

- `Test F1` cao nhất ở ngưỡng mặc định,
- kết quả sau tuning cũng rất sát `CatBoost`.

Tuy nhiên:

- `FPR` của nó luôn nhỉnh hơn `CatBoost`,
- nên vẫn phù hợp hơn với vai trò baseline mạnh thay vì mô hình triển khai chính.

### 3. `HistGradientBoosting` là phương án CPU-only rất đáng giữ

`HistGradientBoosting` có:

- `ROC-AUC` và `Average Precision` rất cao,
- kết quả sau tuning gần như ngang với `Random Forest`,
- và sau tuning ở `2% cap` còn có `OOD Recall` cao nhất nhóm.

Nhưng:

- thời gian train của nó chậm hơn,
- nên nếu ưu tiên vòng lặp thử nghiệm nhanh thì `CatBoost` vẫn thuận lợi hơn.

## Chọn operating mode như thế nào

### Phương án 1: Conservative

Giữ threshold mặc định `0.5`.

Phù hợp khi:

- ưu tiên giảm báo động giả,
- demo hệ thống cần ít nhiễu,
- hoặc muốn giữ `FPR` càng thấp càng tốt.

Khuyến nghị nếu chọn hướng này:

- dùng `CatBoost` với threshold `0.5`.

### Phương án 2: Balanced

Tune threshold theo `FPR cap = 2%` trên `validation`.

Phù hợp khi:

- chấp nhận tăng thêm một phần false positive,
- muốn nâng `Recall` và `OOD Recall`,
- cần chứng minh hệ thống có thể đổi operating point theo nhu cầu vận hành.

Khuyến nghị nếu chọn hướng này:

- dùng `CatBoost` với threshold khoảng `0.2275`.

### Phương án 3: Aggressive detection

Tune gần vùng `FPR cap = 5%`.

Phù hợp khi:

- ưu tiên bắt được nhiều attack hơn,
- chấp nhận alert noise lớn hơn nhiều.

Phương án này hợp cho nghiên cứu so sánh, nhưng không phải lựa chọn đầu tiên để triển khai thực tế.

## Kết luận

Từ kết quả tuning threshold có thể kết luận:

1. `CatBoost` vẫn là mô hình nên đi tiếp để tích hợp vào IDS.
2. Nếu ưu tiên hệ thống ít nhiễu, nên giữ threshold mặc định `0.5`.
3. Nếu muốn một operating point cân bằng hơn giữa `Recall` và `FPR`, nên dùng `CatBoost` với threshold khoảng `0.2275`, nhưng cần nói rõ trong báo cáo rằng `Test FPR` khi đó tăng lên khoảng `2.60%`.
4. `Random Forest` và `HistGradientBoosting` nên được giữ lại làm baseline mạnh ở cả hai chế độ: mặc định và tuned.

## Hướng tiếp theo

1. Vẽ và chèn vào báo cáo bảng so sánh giữa `default threshold` và `tuned threshold`.
2. Chọn một operating mode chính cho luận văn:
   - `Conservative` nếu ưu tiên triển khai sạch,
   - `Balanced` nếu muốn thể hiện khả năng tuning của hệ thống.
3. Sau đó chuyển sang bước mô tả pipeline IDS hoàn chỉnh:
   - `Flow extraction`
   - `Feature alignment`
   - `CatBoost inference`
   - `Thresholding`
   - `Alert logging`
