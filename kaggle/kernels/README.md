# Kaggle IDS Benchmark Kernels

Each kernel in this folder trains one binary IDS model against the same frozen Kaggle dataset.

## Dataset Source

- `hdiiii/cic-iot-diad-2024-binary-ids` after upload

## Kernels

- `ids-binary-logistic-regression`
- `ids-binary-random-forest`
- `ids-binary-hist-gradient-boosting`
- `ids-binary-catboost`
- `ids-binary-mlp`

Every kernel reads the same `train.parquet`, `val.parquet`, `test.parquet`, `ood_attack_holdout.parquet`, and `feature_columns.json` files so the comparison stays aligned.
