from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml_pipeline.training.tune_top_models import (
    passes_selection_gate,
    persist_reports,
    select_promoted_trials,
)


def test_passes_selection_gate_requires_low_default_fpr() -> None:
    passing = {"val_fpr_at_default_0.5": 0.019, "val_f1_at_tuned_cap_0.010": 0.98}
    failing = {"val_fpr_at_default_0.5": 0.021, "val_f1_at_tuned_cap_0.010": 0.99}

    assert passes_selection_gate(passing) is True
    assert passes_selection_gate(failing) is False


def test_select_promoted_trials_prefers_best_ranked_gated_trials() -> None:
    trials = pd.DataFrame(
        [
            {
                "trial_id": "cat-1",
                "model_name": "catboost",
                "val_fpr_at_default_0.5": 0.019,
                "val_f1_at_tuned_cap_0.010": 0.984,
                "val_recall_at_tuned_cap_0.020": 0.970,
                "ood_recall_at_tuned_cap_0.020": 0.420,
                "train_seconds": 100.0,
            },
            {
                "trial_id": "cat-2",
                "model_name": "catboost",
                "val_fpr_at_default_0.5": 0.015,
                "val_f1_at_tuned_cap_0.010": 0.986,
                "val_recall_at_tuned_cap_0.020": 0.971,
                "ood_recall_at_tuned_cap_0.020": 0.430,
                "train_seconds": 110.0,
            },
            {
                "trial_id": "cat-3",
                "model_name": "catboost",
                "val_fpr_at_default_0.5": 0.024,
                "val_f1_at_tuned_cap_0.010": 0.990,
                "val_recall_at_tuned_cap_0.020": 0.975,
                "ood_recall_at_tuned_cap_0.020": 0.450,
                "train_seconds": 90.0,
            },
            {
                "trial_id": "rf-1",
                "model_name": "random_forest",
                "val_fpr_at_default_0.5": 0.018,
                "val_f1_at_tuned_cap_0.010": 0.982,
                "val_recall_at_tuned_cap_0.020": 0.968,
                "ood_recall_at_tuned_cap_0.020": 0.425,
                "train_seconds": 80.0,
            },
            {
                "trial_id": "rf-2",
                "model_name": "random_forest",
                "val_fpr_at_default_0.5": 0.017,
                "val_f1_at_tuned_cap_0.010": 0.981,
                "val_recall_at_tuned_cap_0.020": 0.967,
                "ood_recall_at_tuned_cap_0.020": 0.440,
                "train_seconds": 75.0,
            },
        ]
    )

    promoted = select_promoted_trials(trials, promotion_plan={"catboost": 2, "random_forest": 1})

    assert promoted["catboost"] == ["cat-2", "cat-1"]
    assert promoted["random_forest"] == ["rf-1"]


def test_persist_reports_writes_progress_and_partial_outputs(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "trial_id": "cat-1",
            "model_name": "catboost",
            "train_rows": 1000,
            "train_seconds": 12.5,
            "hyperparameters": {"depth": 8},
            "val_fpr_at_default_0.5": 0.01,
            "val_f1_at_tuned_cap_0.010": 0.98,
            "ood_recall_at_tuned_cap_0.020": 0.4,
        }
    ]

    persist_reports(
        reports_dir=reports_dir,
        models=["catboost"],
        trials_out=records,
        promotion_plan={"catboost": 1},
        profile="quick",
        trial_plan={"catboost": 1},
        progress={"status": "running", "completed_trials": 1, "total_trials": 1},
    )

    assert (reports_dir / "trial_results.csv").exists()
    assert (reports_dir / "trial_results_ranked.csv").exists()
    assert (reports_dir / "best_configs.json").exists()
    assert (reports_dir / "progress.json").exists()

    progress = pd.read_json(reports_dir / "progress.json", typ="series")
    assert progress["completed_trials"] == 1
