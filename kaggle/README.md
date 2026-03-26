# Kaggle Benchmark Assets

Thư mục này chứa template để dựng benchmark Kaggle từ bộ dữ liệu đã freeze tại `artifacts/cic_iot_diad_2024_binary`.

Workflow:

1. Chạy `python scripts/stage_kaggle_benchmark.py`.
2. Script sẽ tạo:
   - bundle dataset Kaggle phẳng, sẵn `dataset-metadata.json`
   - bundle kernel riêng cho từng mô hình, sẵn `kernel-metadata.json`
   - helper PowerShell để upload dataset và push kernels song song
3. Upload dataset lên Kaggle.
4. Push các kernel model riêng lẻ để Kaggle chạy song song.
5. Tải output của từng kernel về và so sánh `metrics.json` hoặc `summary.csv`.

Các kernel dùng cùng một split cố định:

- `train.parquet`
- `val.parquet`
- `test.parquet`
- `ood_attack_holdout.parquet`

Template train chung nằm ở `kaggle/kernel_template/train_binary_ids_template.py`.

Cho hyperparameter tuning trên Kaggle:

1. Chạy `python scripts/stage_kaggle_tuning.py`.
2. Script sẽ tạo 3 kernel tuning riêng trong `artifacts/kaggle_tuning/kernels`.
3. Push các kernel đó lên Kaggle để chạy coarse search song song.
4. Tải output về từ `artifacts/kaggle_tuning/outputs`.
