# Checkpoint Thực Nghiệm IDS

## Mục đích tài liệu

Tài liệu này ghi lại những gì đã hoàn thành trong quá trình xây dựng và đánh giá mô hình IDS trên `CIC IoT-DIAD 2024`, đồng thời phân biệt rõ:

- phần nào là `benchmark ban đầu`,
- phần nào là `tuning/screening`,
- phần nào là `promotion run`,
- và phần nào **chưa được xem là thực nghiệm cuối cùng**.

Mục tiêu là giữ một mốc tham chiếu rõ ràng trước khi chuyển sang thí nghiệm tiếp theo.

## 1. Dataset đã chọn

Dataset chính đã chốt:

- `CIC IoT-DIAD 2024`

Lý do chọn:

- mới hơn các dataset kinh điển như `KDD99`, `NSL-KDD`, `UNSW-NB15`
- đúng hướng bài toán `IDS` dựa trên `flow-based features`
- phù hợp để đưa vào pipeline kiểu `traffic -> flow features -> model -> alert`

Dataset Kaggle đang dùng:

- `hdiiii/cic-iot-diad-2024`

Layout mount trên Kaggle đã xác nhận:

- `/kaggle/input/cic-iot-diad-2024/cic-iot-diad-2024-binary-ids`

## 2. Tiền xử lý dữ liệu đã hoàn thành

Pipeline preprocessing đã được triển khai cho nhánh:

- `Anomaly Detection - Flow Based features`

Đầu ra đã freeze thành bộ dữ liệu binary IDS:

- `Benign`
- `Attack`

Các split đã cố định:

- `train.parquet`
- `val.parquet`
- `test.parquet`
- `ood_attack_holdout.parquet`

Phân bố số dòng:

- `train`: `18,679,445`
- `val`: `4,410,064`
- `test`: `4,145,539`
- `ood_attack_holdout`: `444,422`

Các bước clean chính đã làm:

- gán nhãn lại từ cấu trúc thư mục
- loại file lỗi sang `quarantine`
- bỏ các cột leakage như `Flow ID`, `Src IP`, `Dst IP`, `Timestamp`, `Label`
- chuyển feature sang numeric
- loại `NaN/inf`
- loại duplicate exact rows
- tạo manifest và báo cáo cleaning

## 3. Benchmark Kaggle ban đầu đã hoàn thành

5 mô hình đã được benchmark trên Kaggle:

- `Logistic Regression`
- `Random Forest`
- `HistGradientBoosting`
- `CatBoost`
- `MLP`

Mục đích của vòng này:

- sàng lọc nhóm mô hình mạnh
- loại các mô hình có `FPR` không phù hợp cho IDS

Kết luận từ benchmark ban đầu:

- nhóm mạnh nhất là `CatBoost`, `Random Forest`, `HistGradientBoosting`
- `Logistic Regression` và `MLP` không phù hợp để triển khai vì `FPR` quá cao

Tài liệu liên quan:

- [training_benchmark_results.md](F:/Work/IDS_ML_New/docs/training_benchmark_results.md)
- [learning_curve_analysis.md](F:/Work/IDS_ML_New/docs/learning_curve_analysis.md)
- [threshold_tuning_analysis.md](F:/Work/IDS_ML_New/docs/threshold_tuning_analysis.md)

## 4. Coarse hyperparameter tuning đã hoàn thành

3 mô hình đã được tune trên Kaggle:

- `CatBoost`
- `Random Forest`
- `HistGradientBoosting`

Số trial đã chạy:

- `CatBoost`: `16`
- `Random Forest`: `10`
- `HistGradientBoosting`: `12`

Selection rule của tuning:

- hard gate: `val_fpr_at_default_0.5 <= 0.02`
- rank chính theo `val_f1_at_tuned_cap_0.010`
- tie-break theo:
  - `val_fpr_at_default_0.5`
  - `ood_recall_at_tuned_cap_0.020`
  - `train_seconds`

Kết quả finalist đã chọn:

- `catboost-trial-008`
- `catboost-trial-012`
- `hist_gb-trial-003`
- `random_forest-trial-010`

Tài liệu liên quan:

- [hyperparameter_tuning_setup.md](F:/Work/IDS_ML_New/docs/hyperparameter_tuning_setup.md)

## 5. Promotion run đã hoàn thành

Đã chạy `promotion run` cho 4 finalist:

- `catboost_trial_008`
- `catboost_trial_012`
- `hist_gb_trial_003`
- `random_forest_trial_010`

Kết quả tóm tắt hiện tại:

| Run | Model | Train Rows | Train Seconds | Test F1 | Test FPR | OOD Recall |
|---|---:|---:|---:|---:|---:|---:|
| `catboost_trial_008` | `catboost` | `1,722,155` | `70.42` | `0.993068` | `0.022092` | `0.479236` |
| `hist_gb_trial_003` | `hist_gb` | `1,222,330` | `263.41` | `0.992481` | `0.017318` | `0.444058` |
| `catboost_trial_012` | `catboost` | `1,722,155` | `61.92` | `0.992385` | `0.018290` | `0.444982` |
| `random_forest_trial_010` | `random_forest` | `822,330` | `516.12` | `0.992134` | `0.018361` | `0.426019` |

Tài liệu liên quan:

- [promotion_run_results.md](F:/Work/IDS_ML_New/docs/promotion_run_results.md)

## 6. Diễn giải đúng về promotion run

Đây là điểm rất quan trọng.

`Promotion run` hiện tại **không phải** là `full-data final training`.

Bằng chứng:

- `catboost_trial_008`: train trên `1.72M` dòng
- `catboost_trial_012`: train trên `1.72M` dòng
- `hist_gb_trial_003`: train trên `1.22M` dòng
- `random_forest_trial_010`: train trên `0.82M` dòng

Trong khi full train split thực tế là:

- `18.68M` dòng

Vì vậy, các kết luận hiện tại chỉ được phép phát biểu theo dạng:

- `Trong thiết lập screening/promotion hiện tại, CatBoost trial 008 đang cho kết quả tốt nhất về Test F1 và OOD recall.`

Không được phát biểu theo dạng:

- `CatBoost chắc chắn là mô hình tốt nhất cuối cùng.`

Lý do:

- 4 finalist chưa được train với cùng quy mô dữ liệu
- `HistGB` và `RandomForest` có thể thay đổi hành vi nếu được tăng số mẫu train
- hiện tại chưa có bằng chứng đủ mạnh để kết luận về khả năng scale của từng mô hình

## 7. Điều đã biết và điều chưa biết

### Điều đã biết

- `CatBoost` đang rất mạnh trong benchmark và tuning
- `HistGB` là đối trọng đáng tin cậy nhất về `FPR`
- `RandomForest` hiện yếu hơn 2 lựa chọn trên trong vòng finalist
- pipeline từ preprocessing đến benchmark/tuning/promotion đã hoạt động ổn định trên Kaggle

### Điều chưa biết

- nếu tăng dữ liệu train theo cách công bằng, liệu `HistGB` hoặc `RandomForest` có vượt lên không
- nếu train `CatBoost` trên dữ liệu lớn hơn nhiều hoặc full-data, kết quả có tiếp tục tốt hơn không
- đường tăng trưởng hiệu năng theo `train size` của từng mô hình hiện chưa được đo trực tiếp

## 8. Kết luận checkpoint hiện tại

Đến thời điểm này, nhóm đã hoàn thành:

1. chọn dataset
2. preprocessing và freeze split
3. benchmark 5 mô hình
4. tuning 3 mô hình mạnh nhất
5. promotion run cho 4 finalist

Tuy nhiên, phần **thực nghiệm cuối cùng để chốt mô hình** vẫn chưa hoàn tất.

Điểm còn thiếu để kết luận chắc hơn:

- hoặc `data-scaling experiment` công bằng giữa 3 mô hình mạnh nhất
- hoặc `full/near-full data final run` với protocol được mô tả rõ

## 9. Khuyến nghị cho bước tiếp theo

Bước tiếp theo nên là một trong hai hướng:

### Hướng A: công bằng nhất

Chạy `data-scaling experiment` cho:

- `CatBoost`
- `HistGradientBoosting`
- `RandomForest`

ở cùng các mốc dữ liệu:

- `2M`
- `4M`
- `8M`

Mục tiêu:

- đo trực tiếp khả năng scale của từng mô hình
- trả lời câu hỏi liệu mô hình khác có vượt lên khi tăng dữ liệu hay không

### Hướng B: phục vụ triển khai hệ thống

- chạy `CatBoost` ở quy mô dữ liệu lớn nhất có thể hoặc full-data attempt
- giữ `HistGB` làm baseline đối chứng
- ghi rõ hạn chế tài nguyên tính toán trong báo cáo

Nếu mục tiêu là báo cáo chặt và dễ bảo vệ, hiện tại nên ưu tiên:

- `Hướng A`

## 10. Protocol đã chốt cho bước tiếp theo

Sau khi phân tích thêm cùng `machine-learning-engineer`, protocol đang được chốt để chạy tiếp là:

1. `equal-size scaling` cho:
   - `CatBoost`
   - `HistGradientBoosting`
   - `RandomForest`
2. các mốc dữ liệu:
   - `2M`
   - `4M`
   - `8M`
3. evaluate full:
   - `val`
   - `test`
   - `ood_attack_holdout`
4. chạy thêm:
   - `CatBoost full-data attempt`

## 11. Scaling experiment công bằng đã hoàn thành

`10` notebook scaling/final đã chạy xong:

- `CatBoost` ở `2M`, `4M`, `8M`
- `HistGradientBoosting` ở `2M`, `4M`, `8M`
- `RandomForest` ở `2M`, `4M`, `8M`
- `CatBoost full-data attempt`

Kết quả chính đã được ghi ở:

- [scaling_experiment_results.md](F:/Work/IDS_ML_New/docs/scaling_experiment_results.md)
- [scaling_experiment_summary.csv](F:/Work/IDS_ML_New/artifacts/kaggle/reports/scaling_experiment_summary.csv)

Điểm đã xác nhận:

- `CatBoost full-data attempt` đã train trên toàn bộ `18,679,445` dòng train
- `RandomForest 8M` có `Test F1` và `OOD Recall` cao nhất, nhưng `Test FPR` cũng cao nhất
- `HistGB 8M` có `FPR` thấp hơn rõ rệt, nhưng không dẫn đầu về `F1` hoặc `OOD Recall`
- `CatBoost` là mô hình cân bằng nhất giữa chất lượng, chi phí train và khả năng scale

## 12. Threshold analysis cho 3 finalist cuối đã hoàn thành

Ba mô hình được phân tích tiếp:

- `CatBoost full-data`
- `RandomForest 8M`
- `HistGB 8M`

Artifact:

- [scaling_threshold_analysis.md](F:/Work/IDS_ML_New/docs/scaling_threshold_analysis.md)
- [threshold_selection_summary.csv](F:/Work/IDS_ML_New/artifacts/posttrain_analysis/scaling_finalists/reports/threshold_selection_summary.csv)
- [threshold_evaluation_summary.csv](F:/Work/IDS_ML_New/artifacts/posttrain_analysis/scaling_finalists/reports/threshold_evaluation_summary.csv)

Kết quả chính:

- threshold được chọn trên `validation` với `FPR cap = 2%` không giữ nguyên đúng `2%` trên `test`
- `RandomForest 8M` vẫn mạnh nhất về `F1` và `OOD Recall`, nhưng `FPR` vận hành cao hơn
- `HistGB 8M` tiếp tục là baseline bảo thủ hơn về `FPR`
- `CatBoost full-data` tiếp tục là điểm cân bằng dễ bảo vệ nhất cho bài toán triển khai IDS

## 13. Trạng thái hiện tại

Đến thời điểm này, phần thực nghiệm cốt lõi đã đủ dày để chuyển sang giai đoạn chốt mô hình và thiết kế hệ thống IDS:

1. preprocessing và freeze split
2. benchmark 5 mô hình
3. tuning 3 mô hình mạnh nhất
4. promotion run cho finalist
5. scaling công bằng `2M/4M/8M`
6. `CatBoost full-data attempt`
7. threshold analysis, PR/ROC, confusion matrix cho 3 finalist cuối

Điểm chưa làm tiếp theo không còn là “so sánh model nào mạnh hơn” ở mức thô, mà là:

- chốt operating point cuối cùng cho mô hình triển khai
- mô tả kiến trúc inference/alerting của IDS
- viết phần báo cáo thực nghiệm cuối cùng theo logic đã có

## 14. Quyết định cuối cùng đã chốt

Mô hình đi tiếp vào hệ thống IDS:

- `CatBoost full-data`

Operating point:

- `threshold = 0.5`

Lý do chốt:

- cân bằng tốt nhất giữa `F1`, `FPR`, `OOD Recall`, thời gian train và khả năng scale
- đã train full-data thật trên `18,679,445` dòng
- threshold tune `0.475` chỉ cải thiện rất nhỏ `F1/OOD Recall` nhưng làm `FPR` tăng

Tài liệu chính để tham chiếu từ đây về sau:

- [final_model_decision.md](F:/Work/IDS_ML_New/docs/final_model_decision.md)
