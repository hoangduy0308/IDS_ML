# Kết quả Scaling Experiment và Full-Data Attempt

## Phạm vi

Bộ thí nghiệm này gồm:

- `9` notebook scaling công bằng cho `CatBoost`, `HistGradientBoosting`, `RandomForest`
- các mốc train size: `2M`, `4M`, `8M`
- `1` notebook `CatBoost full-data attempt`

Toàn bộ các notebook đã chạy thành công trên Kaggle. Dataset root được mount đúng tại:

- `/kaggle/input/datasets/hdiiii/cic-iot-diad-2024/cic-iot-diad-2024-binary-ids`

Riêng `CatBoost full-data attempt` đã train trên toàn bộ tập train:

- `train_rows = 18,679,445`
- GPU runtime: `Tesla T4 x2`

## Kết quả chính

| Run | Train rows | Train seconds | Test F1 | Test FPR | OOD Recall |
|---|---:|---:|---:|---:|---:|
| CatBoost 2M | 1,999,995 | 76.56 | 0.993110 | 0.022921 | 0.481614 |
| CatBoost 4M | 4,000,000 | 81.47 | 0.993191 | 0.026285 | 0.487568 |
| CatBoost 8M | 8,000,000 | 115.26 | 0.993267 | 0.025184 | 0.496530 |
| HistGB 2M | 1,999,092 | 440.36 | 0.992478 | 0.017366 | 0.446567 |
| HistGB 4M | 3,999,006 | 717.47 | 0.992708 | 0.020173 | 0.456310 |
| HistGB 8M | 8,000,000 | 1337.78 | 0.992704 | 0.019889 | 0.457831 |
| RandomForest 2M | 1,999,651 | 1050.82 | 0.993182 | 0.026380 | 0.468480 |
| RandomForest 4M | 4,000,000 | 2135.27 | 0.993852 | 0.033167 | 0.495549 |
| RandomForest 8M | 8,000,000 | 4143.68 | 0.994047 | 0.040287 | 0.508816 |
| CatBoost full | 18,679,445 | 181.01 | 0.993358 | 0.027411 | 0.499575 |

## Diễn giải

### 1. Bây giờ đã có bằng chứng công bằng hơn trước

Khác với vòng `promotion run`, ở đây ba mô hình đã được so sánh trên cùng các mốc train size `2M/4M/8M`. Vì vậy các nhận xét từ bộ này chặt hơn đáng kể.

### 2. RandomForest tăng mạnh theo train size, nhưng trả giá bằng FPR

`RandomForest` là mô hình có `Test F1` và `OOD Recall` cao nhất ở mốc `8M`:

- `Test F1 = 0.994047`
- `OOD Recall = 0.508816`

Nhưng `Test FPR` tăng khá mạnh khi tăng dữ liệu:

- `2M`: `0.026380`
- `4M`: `0.033167`
- `8M`: `0.040287`

Điểm này rất quan trọng với IDS. Nếu FPR cao, hệ thống sẽ phát sinh nhiều báo động giả và khó dùng trong thực tế.

### 3. HistGradientBoosting là baseline bảo thủ nhất về FPR

Trong nhóm scaling công bằng, `HistGB` luôn cho `FPR` thấp hơn `CatBoost` và `RandomForest`:

- `2M`: `0.017366`
- `4M`: `0.020173`
- `8M`: `0.019889`

Đổi lại, `Test F1` và `OOD Recall` không dẫn đầu. `HistGB` phù hợp để giữ làm baseline theo hướng ít báo động giả hơn, nhưng không phải mô hình mạnh nhất về hiệu năng phát hiện tổng thể.

### 4. CatBoost là mô hình cân bằng nhất và có lợi thế tính toán rõ ràng

`CatBoost` không đứng đầu tuyệt đối trên mọi metric, nhưng có ba ưu điểm nổi bật:

- `Test F1` luôn ở mức rất cao và tăng ổn định khi tăng dữ liệu
- `OOD Recall` tăng đều từ `0.481614` lên `0.496530`, và đạt `0.499575` ở full-data
- thời gian train thấp hơn rất nhiều so với `HistGB` và `RandomForest`

So sánh ở mốc `8M`:

- `CatBoost`: `115.26s`
- `HistGB`: `1337.78s`
- `RandomForest`: `4143.68s`

Đây là chênh lệch rất lớn. Với mục tiêu xây dựng IDS có khả năng retrain hoặc cập nhật mô hình thực tế, lợi thế này đáng kể.

### 5. Full-data CatBoost đã chạy được thật và cải thiện nhẹ so với 8M

`CatBoost full-data attempt` đã dùng toàn bộ `18,679,445` dòng train và cho:

- `Test F1 = 0.993358`
- `Test FPR = 0.027411`
- `OOD Recall = 0.499575`

So với `CatBoost 8M`, bản full-data:

- tăng nhẹ `Test F1`
- tăng nhẹ `OOD Recall`
- nhưng `FPR` tăng thêm một chút

Điều này cho thấy việc tăng dữ liệu tiếp tục mang lại lợi ích, nhưng không miễn phí. Mô hình nhạy hơn cũng kéo theo false positive cao hơn.

## Kết luận tạm thời

Từ bộ thí nghiệm này, có thể rút ra ba kết luận an toàn:

1. `RandomForest` không thể bị loại bỏ chỉ vì các vòng screening trước. Ở scaling công bằng, nó scale rất tốt về `F1` và `OOD Recall`.
2. `HistGB` là baseline tốt nếu ưu tiên `FPR` thấp hơn.
3. `CatBoost` hiện là mô hình cân bằng nhất giữa:
   - hiệu năng phát hiện,
   - chi phí train,
   - khả năng train ở quy mô rất lớn,
   - và tính phù hợp để đưa vào pipeline IDS thực tế.

Nói chính xác hơn, bộ kết quả này **không chứng minh CatBoost là tốt nhất trên mọi tiêu chí**, nhưng **ủng hộ CatBoost là lựa chọn triển khai thực dụng nhất** trong ba mô hình hiện tại.

## Hướng tiếp theo

Nên đi tiếp với:

- `CatBoost full-data`
- `RandomForest 8M`
- `HistGB 8M`

và thực hiện thêm:

- threshold tuning ở cùng một protocol so sánh
- confusion matrix
- PR curve / ROC curve
- biểu đồ `threshold -> FPR / Recall / Precision`

Sau bước đó mới chốt mô hình cuối cho hệ thống IDS và phần báo cáo thực nghiệm cuối.
