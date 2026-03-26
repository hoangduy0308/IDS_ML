# Promotion Run Results

## Important Note

- Đây là `promotion run` cho các cấu hình finalist, không phải `full-data final training`.
- Các mô hình hiện không được train trên cùng một số lượng mẫu:
  - `catboost_trial_008`: `1,722,155`
  - `catboost_trial_012`: `1,722,155`
  - `hist_gb_trial_003`: `1,222,330`
  - `random_forest_trial_010`: `822,330`
- Vì vậy, bảng dưới đây chỉ nên được dùng như kết quả `screening/finalist evaluation`, chưa đủ để kết luận mô hình cuối cùng theo nghĩa học thuật chặt chẽ.

| Run | Model | Train Rows | Train Seconds | Test F1 | Test Recall | Test Precision | Test FPR | OOD Recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| catboost_trial_008 | catboost | 1722155 | 70.42 | 0.993068 | 0.986685 | 0.999535 | 0.022092 | 0.479236 |
| hist_gb_trial_003 | hist_gb | 1222330 | 263.41 | 0.992481 | 0.985429 | 0.999635 | 0.017318 | 0.444058 |
| catboost_trial_012 | catboost | 1722155 | 61.92 | 0.992385 | 0.985260 | 0.999614 | 0.018290 | 0.444982 |
| random_forest_trial_010 | random_forest | 822330 | 516.12 | 0.992134 | 0.984767 | 0.999613 | 0.018361 | 0.426019 |

## Initial Conclusion

- `catboost_trial_008` currently has the highest `test_f1` and the highest `ood_recall` among the finalists.
- `hist_gb_trial_003` has the lowest `test_fpr`, but is slower than `catboost_trial_008`.
- `catboost_trial_012` is a conservative CatBoost variant with slightly lower `test_fpr` than `catboost_trial_008`, but also lower `test_f1` and `ood_recall`.
- `random_forest_trial_010` is the slowest CPU candidate and is currently behind both CatBoost variants and HistGB on the final promotion run.
