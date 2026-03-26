# Kaggle Scaling Notebooks

Bộ notebook này dùng để chạy `data-scaling experiment` cho 3 mô hình chính:

- `CatBoost`
- `HistGradientBoosting`
- `RandomForest`

Dataset cần attach:

- `hdiiii/cic-iot-diad-2024`

Các mốc dữ liệu:

- `2M`
- `4M`
- `8M`

Ngoài ra có thêm:

- `CatBoost full-data attempt`

Tổng cộng có 10 notebook, mỗi notebook đại diện cho một cặp:

- `model x train_size`

Mỗi notebook sẽ:

- dùng đúng một cấu hình hyperparameter finalist theo model
- train với `train_target_rows` cố định
- evaluate full `val`, `test`, `ood_attack_holdout`
- ghi output vào `/kaggle/working/<run_key>_results`

Ghi chú:

- đây là thí nghiệm công bằng theo `train size`
- `CatBoost` sẽ bật GPU nếu Kaggle cấp GPU
- `HistGB` và `RandomForest` vẫn là CPU-only
- notebook `CatBoost full-data attempt` là nhánh triển khai, không dùng để so sánh công bằng theo train size
