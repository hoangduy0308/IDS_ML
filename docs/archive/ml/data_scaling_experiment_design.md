# Thiết kế thí nghiệm Data-Scaling cho IDS

> Status: superseded by completed experiment results. Đây là tài liệu thiết kế trước khi chạy thật. Kết quả thực nghiệm đã hoàn thành và nên được dùng làm nguồn chính tại [scaling_experiment_results.md](F:/Work/IDS_ML_New/docs/current/ml/scaling_experiment_results.md).

> Superseded: đây là tài liệu thiết kế trước khi chạy scaling experiment. Kết quả thực tế và kết luận cập nhật đã nằm ở [scaling_experiment_results.md](F:/Work/IDS_ML_New/docs/current/ml/scaling_experiment_results.md), [scaling_threshold_analysis.md](F:/Work/IDS_ML_New/docs/current/ml/scaling_threshold_analysis.md), và [final_model_decision.md](F:/Work/IDS_ML_New/docs/current/ml/final_model_decision.md).

## Mục tiêu

Thí nghiệm này nhằm trả lời trực tiếp câu hỏi:

- nếu tăng dữ liệu train theo cách công bằng, mô hình nào cải thiện tốt hơn?
- liệu `CatBoost` có còn giữ ưu thế khi các mô hình khác được train với cùng quy mô dữ liệu?

## Mô hình tham gia

- `CatBoost`
- `HistGradientBoosting`
- `RandomForest`

Các cấu hình hyperparameter được dùng là cấu hình finalist tốt nhất đã lấy từ vòng tuning/promotion trước đó:

- `CatBoost`: dựa trên `catboost-trial-008`
- `HistGradientBoosting`: dựa trên `hist_gb-trial-003`
- `RandomForest`: dựa trên `random_forest-trial-010`

## Quy tắc công bằng

Ba mô hình sẽ được train trên cùng các mốc dữ liệu:

- `2M`
- `4M`
- `8M`

Quy tắc sampling:

- ưu tiên giữ toàn bộ `Benign` nếu tổng số benign còn nhỏ hơn mốc train
- phần còn lại được lấp bằng `Attack`
- như vậy mỗi model được train với cùng `train_target_rows`

Điều này cho phép so sánh công bằng hơn về khả năng scale theo kích thước dữ liệu, đồng thời giảm rủi ro các mốc quá nhỏ không đủ bao quát dataset.

## Split đánh giá

Tất cả notebook scaling đều dùng chung các split đã freeze từ trước:

- `train`
- `val`
- `test`
- `ood_attack_holdout`

Không thay đổi split và không dùng `test` để chọn hyperparameter.

## Metric chính

Các metric cần trích ra cho mỗi run:

- `Test F1`
- `Test FPR`
- `OOD Recall`
- `Train seconds`

Các metric này sẽ được dùng để dựng các biểu đồ:

- `train_size -> test_f1`
- `train_size -> test_fpr`
- `train_size -> ood_recall`

## Hạ tầng chạy

- `CatBoost` bật GPU nếu Kaggle cấp GPU
- `HistGradientBoosting` và `RandomForest` chạy CPU
- tất cả notebook đều tự tìm dataset root dưới Kaggle theo layout:
  - `/kaggle/input/cic-iot-diad-2024/cic-iot-diad-2024-binary-ids`

## Ý nghĩa của kết quả

Sau thí nghiệm này, nhóm có thể phát biểu chắc hơn:

- model nào đang tốt nhất khi train cùng quy mô dữ liệu
- model nào tăng hiệu năng tốt hơn khi có thêm dữ liệu
- liệu `CatBoost` đang thắng do bản chất mô hình hay chỉ do điều kiện train hiện tại

## Nhánh triển khai song song

Ngoài các mốc scaling công bằng ở trên, nhóm sẽ chạy thêm:

- `CatBoost full-data attempt`

Mục tiêu của notebook này là đánh giá khả năng đi đến cấu hình gần triển khai thực tế. Kết quả của notebook này không nên dùng để thay thế phần so sánh công bằng theo train size.

## Bước tiếp theo sau thí nghiệm

Nếu `CatBoost` vẫn giữ ưu thế sau `data-scaling experiment`, khi đó mới nên chạy:

- `near-full/full-data CatBoost attempt`

để phục vụ hướng triển khai hệ thống IDS.
