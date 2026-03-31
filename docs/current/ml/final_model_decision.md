# Quyết định Mô Hình Cuối Cùng Cho IDS

## Quyết định chốt

Mô hình được chọn để đi tiếp vào hệ thống IDS là:

- `CatBoost full-data`

Operating point được chọn:

- `threshold = 0.5`

## Lý do chốt

### 1. Đây là mô hình cân bằng nhất

So với hai đối thủ cuối:

- `RandomForest 8M` mạnh hơn về `Test F1` và `OOD Recall`, nhưng `FPR` cao hơn rõ rệt
- `HistGB 8M` có `FPR` thấp hơn, nhưng thua về `F1` và `OOD Recall`

`CatBoost full-data` là điểm cân bằng tốt nhất giữa:

- chất lượng phát hiện
- khả năng tổng quát hóa
- chi phí huấn luyện
- khả năng scale
- và tính phù hợp cho hệ thống IDS thực tế

### 2. Mô hình đã train full-data thật

Khác với các vòng `promotion run` trước đó, bản này đã train trên toàn bộ:

- `18,679,445` dòng train

Điều này giúp quyết định cuối cùng có cơ sở chắc hơn cho mục tiêu triển khai.

### 3. Threshold tune không mang lại lợi ích đủ lớn để đổi operating point

So sánh `CatBoost full-data`:

| Threshold | Test F1 | Test FPR | OOD Recall |
|---|---:|---:|---:|
| `0.500` | `0.993358` | `0.027411` | `0.499575` |
| `0.475` | `0.993411` | `0.028358` | `0.503949` |

Threshold `0.475` có cải thiện rất nhỏ về `Test F1` và `OOD Recall`, nhưng đổi lại `Test FPR` tăng.

Với IDS, mình ưu tiên:

- operating point đơn giản
- dễ giải thích
- dễ tái lập
- ít nhiễu hơn

Vì vậy `threshold = 0.5` là lựa chọn tốt hơn.

## Kết luận dùng trong báo cáo

Cách phát biểu an toàn và đúng:

> Sau các vòng benchmark, hyperparameter tuning, scaling experiment công bằng ở các mốc `2M/4M/8M`, full-data training, và threshold analysis, mô hình `CatBoost full-data` với threshold mặc định `0.5` được chọn làm mô hình cuối cùng để tích hợp vào hệ thống IDS. Mô hình này không đứng đầu tuyệt đối trên mọi metric, nhưng là lựa chọn cân bằng nhất giữa hiệu năng phát hiện, false positive rate, chi phí huấn luyện và khả năng triển khai thực tế.

## Tài liệu liên quan

- [scaling_experiment_results.md](F:/Work/IDS_ML_New/docs/current/ml/scaling_experiment_results.md)
- [scaling_threshold_analysis.md](F:/Work/IDS_ML_New/docs/current/ml/scaling_threshold_analysis.md)
- [experiment_progress_checkpoint.md](F:/Work/IDS_ML_New/docs/archive/ml/experiment_progress_checkpoint.md)
