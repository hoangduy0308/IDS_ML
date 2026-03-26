# Kaggle Tuning Notebooks

Ba notebook này dùng để upload thủ công lên Kaggle và chạy tuning cho 3 mô hình chính:

- `01_catboost_tuning.ipynb`
- `02_random_forest_tuning.ipynb`
- `03_hist_gb_tuning.ipynb`

## Accelerator

- `01_catboost_tuning.ipynb`: có hỗ trợ GPU
  - notebook sẽ tự dò GPU bằng `nvidia-smi`
  - nếu runtime Kaggle có GPU, `CatBoost` sẽ bật `task_type="GPU"` và tự điền `devices`
  - nếu runtime có 2 GPU, notebook sẽ cố dùng cả 2 GPU theo danh sách index nhìn thấy
- `02_random_forest_tuning.ipynb`: CPU-only
  - `RandomForestClassifier` của `scikit-learn` không dùng được GPU T4
- `03_hist_gb_tuning.ipynb`: CPU-only
  - `HistGradientBoostingClassifier` của `scikit-learn` không dùng được GPU T4

## Cách dùng

1. Tạo một notebook mới trên Kaggle từ UI.
2. Attach dataset:
   - `cic-iot-diad-2024`
3. Upload một trong ba file notebook ở thư mục này.
4. Chạy notebook.

Layout Kaggle đã xác nhận:

- `/kaggle/input/cic-iot-diad-2024/cic-iot-diad-2024-binary-ids`

Notebook hiện sẽ ưu tiên đúng đường dẫn này trước, rồi mới fallback sang auto-discovery dưới `/kaggle/input`.

## Cách kiểm tra runtime trên Kaggle

Ngay đầu notebook sẽ in `runtime_context.json` ra màn hình. Với `CatBoost`, bạn nên kiểm tra:

- `gpu_count`
- `gpu_names`
- `catboost_device_spec`

Nếu `gpu_count = 0` thì notebook đang chạy CPU.

## Output mong đợi

Notebook sẽ ghi kết quả vào `/kaggle/working/<model>_tuning_results`:

- `reports/trial_results.csv`
- `reports/trial_results_ranked.csv`
- `reports/trial_results.jsonl`
- `reports/best_configs.json`
- `reports/search_space.json`
- `reports/progress.json`
- `reports/selection_rule.md`

## Ghi chú

- Notebook đã là dạng self-contained, không cần import thêm file `scripts/` từ repo local.
- Nếu Kaggle mount dataset theo tên thư mục con khác nhau, notebook sẽ tự dò dưới `/kaggle/input`.
- Đây là lượt `coarse search` với profile `quick`.
