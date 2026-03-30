# Phân tích learning curve cho benchmark IDS

## Mục tiêu

Tài liệu này lưu lại phần bằng chứng trong quá trình train của 5 mô hình benchmark trên bộ dữ liệu `CIC IoT-DIAD 2024` đã được xử lý và freeze. Mục tiêu là phục vụ trực tiếp cho phần báo cáo thực nghiệm, đặc biệt ở các câu hỏi:

- mô hình nào học ổn định hơn,
- mô hình nào có dấu hiệu overfitting,
- vì sao `CatBoost` được chọn làm hướng đi chính dù `Random Forest` nhỉnh hơn rất nhẹ ở `Test F1`.

## Nguồn dữ liệu và cách đọc biểu đồ

Các learning curve được sinh từ output thật của 5 kernel Kaggle:

- `Logistic Regression`
- `Random Forest`
- `HistGradientBoosting`
- `CatBoost`
- `MLP`

Các file gốc nằm trong:

- `artifacts/kaggle/outputs/logreg/logreg_results/training_curve.csv`
- `artifacts/kaggle/outputs/random_forest/random_forest_results/training_curve.csv`
- `artifacts/kaggle/outputs/hist_gb/hist_gb_results/training_curve.csv`
- `artifacts/kaggle/outputs/catboost/catboost_results/training_curve.csv`
- `artifacts/kaggle/outputs/mlp/mlp_results/training_curve.csv`

Lưu ý quan trọng:

- Các chỉ số `Test F1`, `Test FPR`, `OOD Recall` trong phần chọn mô hình được tính trên toàn bộ split thật.
- Learning curve của các mô hình nặng được đo trên một **probe subset cố định** của train/validation để phù hợp giới hạn RAM khi chạy trên Kaggle.
- Vì vậy, giá trị tuyệt đối trên curve không cần trùng hoàn toàn với metric cuối. Curve được dùng chủ yếu để đọc **xu hướng học**, **độ ổn định**, và **generalization gap**.

## Tệp tổng hợp dùng cho báo cáo

- Bảng tóm tắt curve: `artifacts/kaggle/reports/learning_curve_summary.csv`
- Hình tổng hợp 5 mô hình: `docs/figures/all_models_learning_curves.png`
- Hình so sánh generalization gap: `docs/figures/generalization_gap_comparison.png`
- Hình trade-off chọn mô hình: `docs/figures/model_selection_tradeoff.png`

Hình riêng cho từng mô hình:

- `docs/figures/logreg_training_curve.png`
- `docs/figures/random_forest_training_curve.png`
- `docs/figures/hist_gb_training_curve.png`
- `docs/figures/catboost_training_curve.png`
- `docs/figures/mlp_training_curve.png`

## Bảng tóm tắt learning curve

| Mô hình | Điểm curve | Train F1 cuối | Val F1 cuối | Gap cuối | Best Val F1 | Stage tốt nhất |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 2 | 0.9160 | 0.9047 | 0.0113 | 0.9047 | 2 |
| Random Forest | 6 | 0.9854 | 0.9815 | 0.0040 | 0.9815 | 125 |
| HistGradientBoosting | 6 | 0.9854 | 0.9819 | 0.0036 | 0.9819 | 300 |
| CatBoost | 400 | 0.9849 | 0.9787 | 0.0062 | 0.9787 | 400 |
| MLP | 3 | 0.9070 | 0.9074 | -0.0004 | 0.9074 | 3 |

## Phân tích từng mô hình

### 1. Logistic Regression

`Logistic Regression` tăng rất ít sau hai epoch:

- `train_f1`: `0.9134 -> 0.9160`
- `val_f1`: `0.9021 -> 0.9047`

Nhận xét:

- Curve khá phẳng, nghĩa là mô hình tuyến tính nhanh chạm trần biểu diễn.
- `generalization gap = 0.0113`, lớn hơn nhóm cây tăng cường.
- Khi đánh giá trên full test, mô hình cho `Test FPR = 0.7706`, quá cao đối với IDS.

Kết luận:

- Đây là baseline tốt để so sánh.
- Không phù hợp làm mô hình triển khai chính vì biên quyết định tuyến tính không đủ để giữ `FPR` thấp.

### 2. Random Forest

`Random Forest` học khá ổn định:

- `val_f1` tăng từ `0.98135` lên `0.98146`
- đạt tốt nhất ở khoảng `125` cây
- gap cuối chỉ khoảng `0.0040`

Nhận xét:

- Đây là mô hình có đường học ổn định và rất ít dao động.
- Sau khoảng `125` cây, lợi ích thêm gần như bão hòa.
- Trên full test, `Random Forest` đạt `Test F1` cao nhất: `0.990995`.

Kết luận:

- Đây là baseline mạnh nhất để giữ lại trong báo cáo.
- Nếu ưu tiên `F1` thuần túy thì mô hình này rất đáng chú ý.
- Tuy nhiên, `FPR = 0.0153` vẫn cao hơn `CatBoost`.

### 3. HistGradientBoosting

`HistGradientBoosting` là mô hình học đều nhất trong nhóm boosting CPU:

- `val_f1` tăng từ `0.9725` lên `0.9819`
- tốt nhất ở stage cuối `300`
- gap cuối chỉ khoảng `0.0036`, thấp nhất nhóm mô hình hiệu quả

Nhận xét:

- Curve cho thấy mô hình vẫn còn cải thiện đến cuối quá trình train.
- Đây là dấu hiệu rất tốt về mặt ổn định học.
- Trên full test, `Test F1 = 0.990960` và `Test FPR = 0.01446`.

Kết luận:

- Đây là ứng viên rất mạnh để giữ làm baseline đối sánh với `CatBoost`.
- Nếu sau này cần một mô hình CPU-only, đây là hướng đáng cân nhắc.

### 4. CatBoost

`CatBoost` có learning curve chi tiết nhất với `400` iteration:

- `train_f1` tăng từ `0.9550` lên `0.9849`
- `val_f1` tăng từ `0.8800` lên `0.9787`
- best validation đạt ở iteration cuối `400`
- gap cuối khoảng `0.0062`

Nhận xét quan trọng:

- Đúng là đường train nằm trên validation gần như toàn bộ quá trình train.
- Tuy nhiên, điều này **chưa đủ để kết luận overfitting nặng**.
- Dấu hiệu overfitting đáng lo hơn là validation đạt đỉnh rồi giảm dần, trong khi ở đây `val_f1` vẫn tiếp tục tăng đến iteration cuối.

Diễn giải phù hợp hơn:

- `CatBoost` có **generalization gap nhẹ đến vừa**.
- Chưa có bằng chứng mạnh cho thấy mô hình đã overfit nghiêm trọng ở mốc `400` iteration.

Khi kết hợp với metric cuối:

- `Test F1 = 0.990900`
- `Test FPR = 0.01264`, thấp nhất trong toàn bộ các mô hình khả thi
- `train_seconds = 127.68`, nhanh hơn `HistGradientBoosting`

Kết luận:

- `CatBoost` là mô hình **cân bằng nhất** giữa `F1`, `FPR`, và chi phí train.
- Đây vẫn là mô hình nên chọn để đi tiếp sang bước tuning và tích hợp vào IDS.

### 5. MLP

`MLP` có curve khá khác các mô hình còn lại:

- `train_f1` và `val_f1` gần như trùng nhau
- gap cuối âm nhẹ `-0.0004`
- cả train và val đều chỉ tăng rất ít qua `3` epoch

Nếu chỉ nhìn curve, mô hình này có vẻ không overfit. Tuy nhiên kết quả full test lại cho:

- `Test FPR = 0.9781`
- `OOD Recall = 0.9990`

Điều đó cho thấy mô hình đang nghiêng quá mạnh về phía dự đoán tấn công, dẫn đến báo động giả cực lớn.

Kết luận:

- `MLP` không gặp vấn đề kiểu train cao hơn val quá nhiều.
- Nhưng lại thất bại ở tiêu chí triển khai thực tế vì `FPR` gần như không chấp nhận được.

## Kết luận tổng hợp

Từ learning curve và metric cuối trên full test, có thể rút ra:

1. `Random Forest`, `HistGradientBoosting`, và `CatBoost` là ba mô hình học ổn định nhất.
2. `Logistic Regression` chạm trần sớm và không kiểm soát được false positive.
3. `MLP` không overfit theo nghĩa cổ điển, nhưng cho hành vi dự đoán lệch mạnh về attack nên không phù hợp triển khai.
4. `CatBoost` có gap train-val lớn hơn `Random Forest` và `HistGradientBoosting`, nhưng validation vẫn tăng đến cuối. Vì vậy nên mô tả là **có generalization gap nhưng chưa có bằng chứng overfitting nghiêm trọng**.

## Hướng tiếp theo

### Hướng nghiên cứu nên làm ngay

1. Giữ nguyên split hiện tại làm benchmark chính và không thay đổi nữa.
2. Chọn `CatBoost`, `Random Forest`, `HistGradientBoosting` làm 3 mô hình đi tiếp.
3. Thực hiện tuning trên tập validation với mục tiêu ưu tiên `FPR` thấp.
4. Thêm các biểu đồ phục vụ báo cáo và triển khai:
   - confusion matrix,
   - PR curve,
   - ROC curve,
   - threshold sweep theo `FPR`.

### Hướng triển khai hệ thống IDS

Nếu mục tiêu là đưa vào hệ thống IDS, nên đi theo pipeline:

1. `Flow extraction`
2. `Feature alignment` theo `feature_columns.json`
3. `CatBoost inference`
4. `Thresholding / alerting`
5. `Logging và đánh giá drift`

### Hướng viết báo cáo

Trong báo cáo, nên lập luận theo thứ tự:

1. dữ liệu đã được xử lý và split theo `source_file` để tránh leakage,
2. các learning curve cho thấy ba mô hình cây là nhóm ổn định nhất,
3. `CatBoost` không phải mô hình cao nhất ở mọi metric, nhưng là mô hình cân bằng nhất cho IDS thực tế vì `FPR` thấp nhất,
4. do đó `CatBoost` được chọn làm hướng tối ưu để xây dựng hệ thống.
