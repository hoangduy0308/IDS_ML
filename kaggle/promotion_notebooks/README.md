# Kaggle Promotion Notebooks

Bộ notebook này dùng để chạy `promotion run` cho 4 cấu hình finalist sau vòng coarse tuning.

Dataset cần attach:

- `hdiiii/cic-iot-diad-2024`

Các notebook:

- `01_catboost_trial_008_promotion.ipynb`
- `02_catboost_trial_012_promotion.ipynb`
- `03_hist_gb_trial_003_promotion.ipynb`
- `04_random_forest_trial_010_promotion.ipynb`

Mỗi notebook sẽ:

- gắn sẵn hyperparameter finalist
- train trên tập train mở rộng hơn vòng coarse
- evaluate full `val`, `test`, `ood_attack_holdout`
- ghi output vào `/kaggle/working/<run_key>_promotion_results`

Lưu ý:

- Đây là `promotion run`, không còn random search
- `CatBoost` sẽ bật GPU nếu Kaggle cấp GPU
- `Random Forest` và `HistGB` vẫn là CPU-only
- Các notebook train trên train sample mở rộng có cap để phù hợp RAM/CPU/GPU của Kaggle, không ép nạp toàn bộ 18M+ dòng vào memory
