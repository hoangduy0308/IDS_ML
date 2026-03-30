from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml_pipeline.training.posttrain_threshold_analysis import (
    build_threshold_sweep,
    parse_model_specs,
    select_threshold_under_fpr_cap,
)


def test_build_threshold_sweep_computes_expected_metrics() -> None:
    y_true = [0, 0, 1, 1]
    y_score = [0.1, 0.4, 0.35, 0.8]
    thresholds = [0.3, 0.5]

    sweep = build_threshold_sweep(y_true=y_true, y_score=y_score, thresholds=thresholds)

    threshold_03 = sweep.loc[sweep["threshold"] == 0.3].iloc[0]
    assert threshold_03["tp"] == 2
    assert threshold_03["fp"] == 1
    assert threshold_03["tn"] == 1
    assert threshold_03["fn"] == 0
    assert round(float(threshold_03["f1"]), 4) == 0.8000
    assert round(float(threshold_03["fpr"]), 4) == 0.5000

    threshold_05 = sweep.loc[sweep["threshold"] == 0.5].iloc[0]
    assert threshold_05["tp"] == 1
    assert threshold_05["fp"] == 0
    assert threshold_05["tn"] == 2
    assert threshold_05["fn"] == 1
    assert round(float(threshold_05["f1"]), 4) == 0.6667
    assert round(float(threshold_05["fpr"]), 4) == 0.0000


def test_select_threshold_under_fpr_cap_prefers_best_f1_within_cap() -> None:
    sweep = pd.DataFrame(
        [
            {"threshold": 0.2, "f1": 0.82, "fpr": 0.60, "recall": 1.0},
            {"threshold": 0.4, "f1": 0.79, "fpr": 0.10, "recall": 0.75},
            {"threshold": 0.6, "f1": 0.74, "fpr": 0.02, "recall": 0.60},
        ]
    )

    choice = select_threshold_under_fpr_cap(sweep, fpr_cap=0.15)
    assert float(choice["threshold"]) == 0.4

    tighter_choice = select_threshold_under_fpr_cap(sweep, fpr_cap=0.05)
    assert float(tighter_choice["threshold"]) == 0.6


def test_parse_model_specs_parses_scaling_finalist_format() -> None:
    parsed = parse_model_specs(
        "catboost_full|CatBoost Full|a/b/model.cbm|a/b;"
        "hist_gb_8m|HistGB 8M|c/d/model.joblib|c/d"
    )

    assert parsed == [
        ("catboost_full", "CatBoost Full", "a/b/model.cbm", "a/b"),
        ("hist_gb_8m", "HistGB 8M", "c/d/model.joblib", "c/d"),
    ]
