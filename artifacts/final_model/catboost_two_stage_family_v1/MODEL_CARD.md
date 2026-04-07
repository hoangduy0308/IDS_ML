# Final IDS Model Bundle

## Model

- bundle kind: `composite`
- model key: `catboost_full_data`
- model family: `CatBoostClassifier`
- threshold: `0.5`
- positive label: `Attack`
- negative label: `Benign`

## Bundle contents

- `model.cbm`
- `feature_columns.json`
- `stage2_model.cbm`
- `stage2_feature_columns.json`
- `stage2_report.json`
- `model_bundle.json`
- `metrics.json`
- `training_summary.json`

## Training scope

- train rows: `18,679,445`
- feature count: `72`

## Selected operating point

- stage 2 model: `stage2_model.cbm`
- closed-set labels: `DDoS, DoS, Mirai, Spoofing, Web-Based`
- abstention top1_confidence: `0.5588587362527666`
- abstention runner_up_margin: `0.3097277574209342`

## Final metrics

- test_f1: `0.993358`
- test_recall: `0.987366`
- test_precision: `0.999423`
- test_fpr: `0.027411`
- ood_recall: `0.499575`

## Source references

- stage 2 report: `F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_family_views\family_classifier\reports\oracle_family_eval.json`
- stage 2 checkpoint: `F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_family_views\family_classifier\models\catboost_family_classifier.cbm`
- stage 2 feature schema: `F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary\manifests\feature_columns.json`
