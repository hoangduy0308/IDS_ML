# Final IDS Model Bundle

## Model

- model key: `catboost_full_data`
- model family: `CatBoostClassifier`
- threshold: `0.5`
- positive label: `Attack`
- negative label: `Benign`

## Bundle contents

- `model.cbm`
- `feature_columns.json`
- `model_bundle.json`
- `metrics.json`
- `training_summary.json`

## Training scope

- train rows: `18,679,445`
- feature count: `72`

## Selected operating point

- threshold: `0.5`
- reason: selected as the final deployment operating point because it keeps the model package simple and avoids the slight FPR increase seen at the tuned threshold.

## Final metrics

- test_f1: `0.993358`
- test_recall: `0.987366`
- test_precision: `0.999423`
- test_fpr: `0.027411`
- ood_recall: `0.499575`

## Source references

- final decision: [final_model_decision.md](F:/Work/IDS_ML_New/docs/final_model_decision.md)
- scaling experiment: [scaling_experiment_results.md](F:/Work/IDS_ML_New/docs/scaling_experiment_results.md)
- threshold analysis: [scaling_threshold_analysis.md](F:/Work/IDS_ML_New/docs/scaling_threshold_analysis.md)
