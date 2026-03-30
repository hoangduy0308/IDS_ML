from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import joblib
import matplotlib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from catboost import CatBoostClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABEL_MAP = {"Benign": 0, "Attack": 1}
TOP_MODELS = ["catboost", "random_forest", "hist_gb"]
DEFAULT_THRESHOLD_CAPS = [0.005, 0.01, 0.02, 0.05]
SCALING_FINALISTS_SPECS = [
    "catboost_full|CatBoost Full-Data|catboost_full_data_attempt/catboost_full_data_attempt_results/catboost_full_data_attempt.cbm|catboost_full_data_attempt/catboost_full_data_attempt_results",
    "random_forest_8m|Random Forest 8M|scaling_rf_8m/random_forest_8m_scaling_results/random_forest_8m_scaling.joblib|scaling_rf_8m/random_forest_8m_scaling_results",
    "hist_gb_8m|HistGradientBoosting 8M|scaling_histgb_8m/hist_gb_8m_scaling_results/hist_gb_8m_scaling.joblib|scaling_histgb_8m/hist_gb_8m_scaling_results",
]


@dataclass(frozen=True)
class ModelPaths:
    key: str
    label: str
    artifact_path: Path
    result_dir: Path


MODEL_LABELS = {
    "catboost": "CatBoost",
    "random_forest": "Random Forest",
    "hist_gb": "HistGradientBoosting",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze thresholds and report figures for top IDS models.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary"),
    )
    parser.add_argument(
        "--kaggle-outputs-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\kaggle\outputs"),
    )
    parser.add_argument(
        "--analysis-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\posttrain_analysis\top_models"),
    )
    parser.add_argument(
        "--docs-figures-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\docs\figures"),
    )
    parser.add_argument("--models", type=str, default=",".join(TOP_MODELS))
    parser.add_argument(
        "--model-specs",
        type=str,
        default="",
        help=(
            "Semicolon-separated model specs in the form "
            "'key|label|artifact_relative_path|result_dir_relative_path'. "
            "If provided, overrides --models."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=["", "scaling_finalists"],
        default="",
        help="Use a predefined model-spec bundle.",
    )
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--recommended-fpr-cap", type=float, default=0.02)
    parser.add_argument("--threshold-grid-size", type=int, default=401)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_feature_columns(dataset_root: Path) -> list[str]:
    payload = read_json(dataset_root / "manifests" / "feature_columns.json")
    return list(payload["feature_columns"])


def parse_model_specs(raw_specs: str) -> list[tuple[str, str, str, str]]:
    parsed: list[tuple[str, str, str, str]] = []
    for spec in [item.strip() for item in raw_specs.split(";") if item.strip()]:
        parts = [part.strip() for part in spec.split("|")]
        if len(parts) != 4:
            raise ValueError(f"Invalid model spec: {spec}")
        parsed.append((parts[0], parts[1], parts[2], parts[3]))
    return parsed


def model_paths(outputs_root: Path, models: list[str], model_specs: list[tuple[str, str, str, str]] | None = None) -> list[ModelPaths]:
    resolved: list[ModelPaths] = []
    if model_specs:
        for key, label, artifact_relative, result_dir_relative in model_specs:
            resolved.append(
                ModelPaths(
                    key=key,
                    label=label,
                    artifact_path=outputs_root / artifact_relative,
                    result_dir=outputs_root / result_dir_relative,
                )
            )
        return resolved
    for model in models:
        result_dir = outputs_root / model / f"{model}_results"
        if model == "catboost":
            artifact_path = result_dir / "catboost.cbm"
        else:
            artifact_path = result_dir / f"{model}.joblib"
        resolved.append(
            ModelPaths(
                key=model,
                label=MODEL_LABELS[model],
                artifact_path=artifact_path,
                result_dir=result_dir,
            )
        )
    return resolved


def load_model(model_path: Path, model_key: str) -> Any:
    if model_key.startswith("catboost"):
        model = CatBoostClassifier()
        model.load_model(model_path)
        return model
    return joblib.load(model_path)


def unwrap_model_bundle(model: Any) -> tuple[Any, Any | None]:
    if isinstance(model, dict) and "model" in model:
        return model["model"], model.get("scaler")
    return model, None


def model_predict_scores(model: Any, frame: pd.DataFrame) -> np.ndarray:
    estimator, scaler = unwrap_model_bundle(model)
    features: Any = frame
    if scaler is not None:
        features = scaler.transform(frame)
    elif not isinstance(estimator, CatBoostClassifier):
        features = frame.to_numpy(dtype=np.float32, copy=False)

    if hasattr(estimator, "predict_proba"):
        return np.asarray(estimator.predict_proba(features)[:, 1], dtype=np.float32)
    if hasattr(estimator, "decision_function"):
        decision = np.asarray(estimator.decision_function(features), dtype=np.float32)
        return (1.0 / (1.0 + np.exp(-decision))).astype(np.float32)
    raise TypeError("Model does not support probability scoring.")


def score_parquet_split(
    model: Any,
    split_path: Path,
    feature_columns: list[str],
    batch_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    parquet_file = pq.ParquetFile(split_path)
    y_true_all: list[np.ndarray] = []
    y_score_all: list[np.ndarray] = []
    columns = feature_columns + ["derived_label_binary"]
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        frame = batch.to_pandas()
        y_true = frame["derived_label_binary"].map(LABEL_MAP).to_numpy(dtype=np.int8)
        X = frame[feature_columns].astype(np.float32)
        y_score = model_predict_scores(model, X)
        y_true_all.append(y_true)
        y_score_all.append(y_score)
    return np.concatenate(y_true_all), np.concatenate(y_score_all)


def build_threshold_sweep(
    y_true: Iterable[int],
    y_score: Iterable[float],
    thresholds: Iterable[float],
) -> pd.DataFrame:
    labels = np.asarray(list(y_true), dtype=np.int8)
    scores = np.asarray(list(y_score), dtype=np.float32)
    threshold_array = np.asarray(sorted({round(float(t), 10) for t in thresholds}, reverse=True), dtype=np.float64)

    order = np.argsort(scores)[::-1]
    scores_sorted = scores[order]
    labels_sorted = labels[order]

    positives = int(labels_sorted.sum())
    negatives = int(len(labels_sorted) - positives)
    tp = 0
    fp = 0
    cursor = 0

    rows: list[dict[str, float | int]] = []
    for threshold in threshold_array:
        while cursor < len(scores_sorted) and scores_sorted[cursor] >= threshold:
            if labels_sorted[cursor] == 1:
                tp += 1
            else:
                fp += 1
            cursor += 1

        fn = positives - tp
        tn = negatives - fp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / positives if positives else 0.0
        fpr = fp / negatives if negatives else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0
        rows.append(
            {
                "threshold": float(threshold),
                "tp": int(tp),
                "fp": int(fp),
                "tn": int(tn),
                "fn": int(fn),
                "precision": float(precision),
                "recall": float(recall),
                "tpr": float(recall),
                "fpr": float(fpr),
                "f1": float(f1),
            }
        )

    return pd.DataFrame(rows).sort_values(by="threshold").reset_index(drop=True)


def select_threshold_under_fpr_cap(sweep_df: pd.DataFrame, fpr_cap: float) -> pd.Series:
    eligible = sweep_df.loc[sweep_df["fpr"] <= fpr_cap].copy()
    if eligible.empty:
        eligible = sweep_df.copy()
        return eligible.sort_values(
            by=["fpr", "f1", "recall", "threshold"],
            ascending=[True, False, False, False],
        ).iloc[0]
    return eligible.sort_values(
        by=["f1", "recall", "fpr", "threshold"],
        ascending=[False, False, True, False],
    ).iloc[0]


def confusion_counts(y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> dict[str, int]:
    y_pred = (y_score >= threshold).astype(np.int8)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp}


def metrics_from_confusion(counts: dict[str, int]) -> dict[str, float]:
    tn, fp, fn, tp = counts["tn"], counts["fp"], counts["fn"], counts["tp"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / max(1, tp + tn + fp + fn)
    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "fpr": float(fpr),
        "f1": float(f1),
    }


def evaluate_at_threshold(y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> dict[str, Any]:
    counts = confusion_counts(y_true, y_score, threshold)
    return {**metrics_from_confusion(counts), **counts, "threshold": float(threshold)}


def downsample_frame(frame: pd.DataFrame, max_points: int = 200) -> pd.DataFrame:
    if len(frame) <= max_points:
        return frame.copy()
    indices = np.linspace(0, len(frame) - 1, num=max_points, dtype=int)
    return frame.iloc[indices].reset_index(drop=True)


def plot_threshold_sweep(
    sweep_df: pd.DataFrame,
    model_label: str,
    output_path: Path,
    chosen_threshold: float,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(sweep_df["threshold"], sweep_df["f1"], label="F1", color="#1f77b4")
    ax.plot(sweep_df["threshold"], sweep_df["recall"], label="Recall", color="#2ca02c")
    ax.plot(sweep_df["threshold"], sweep_df["fpr"], label="FPR", color="#d62728")
    ax.axvline(chosen_threshold, color="#111827", linestyle="--", linewidth=1.5, label=f"Chosen threshold = {chosen_threshold:.3f}")
    ax.set_title(f"{model_label} Threshold Sweep on Validation")
    ax.set_xlabel("Threshold")
    ax.set_ylabel("Metric value")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_pr_roc(
    sweep_df: pd.DataFrame,
    model_label: str,
    output_path: Path,
    roc_auc: float,
    average_precision: float,
) -> None:
    sampled = downsample_frame(sweep_df.sort_values(by="threshold", ascending=False), max_points=250)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    pr_frame = sampled.sort_values(by="recall")
    axes[0].plot(pr_frame["recall"], pr_frame["precision"], color="#1f77b4")
    axes[0].set_title(f"{model_label} Precision-Recall")
    axes[0].set_xlabel("Recall")
    axes[0].set_ylabel("Precision")
    axes[0].grid(alpha=0.3)
    axes[0].text(0.03, 0.08, f"AP = {average_precision:.4f}", transform=axes[0].transAxes)

    roc_frame = sampled.sort_values(by="fpr")
    axes[1].plot(roc_frame["fpr"], roc_frame["tpr"], color="#ff7f0e")
    axes[1].plot([0, 1], [0, 1], linestyle="--", color="#9ca3af", linewidth=1)
    axes[1].set_title(f"{model_label} ROC")
    axes[1].set_xlabel("FPR")
    axes[1].set_ylabel("TPR")
    axes[1].grid(alpha=0.3)
    axes[1].text(0.03, 0.08, f"ROC-AUC = {roc_auc:.4f}", transform=axes[1].transAxes)

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_confusion_matrix(
    counts: dict[str, int],
    model_label: str,
    threshold_label: str,
    output_path: Path,
) -> None:
    matrix = np.array([[counts["tn"], counts["fp"]], [counts["fn"], counts["tp"]]], dtype=np.int64)
    fig, ax = plt.subplots(figsize=(5, 4.5))
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks([0, 1], labels=["Pred Benign", "Pred Attack"])
    ax.set_yticks([0, 1], labels=["True Benign", "True Attack"])
    ax.set_title(f"{model_label} Confusion Matrix\n{threshold_label}")

    for row_idx in range(2):
        for col_idx in range(2):
            ax.text(col_idx, row_idx, f"{matrix[row_idx, col_idx]:,}", ha="center", va="center", color="#111827")

    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def save_split_artifacts(
    model_label: str,
    split_name: str,
    sweep_df: pd.DataFrame,
    y_true: np.ndarray,
    y_score: np.ndarray,
    chosen_threshold: float,
    reports_dir: Path,
    figures_dir: Path,
    figure_prefix: str,
) -> dict[str, float]:
    sweep_output = reports_dir / f"{figure_prefix}_{split_name}_threshold_sweep.csv"
    sweep_df.to_csv(sweep_output, index=False)

    roc_auc = float(roc_auc_score(y_true, y_score))
    average_precision = float(average_precision_score(y_true, y_score))

    if split_name == "test":
        plot_pr_roc(
            sweep_df=sweep_df,
            model_label=model_label,
            output_path=figures_dir / f"{figure_prefix}_pr_roc.png",
            roc_auc=roc_auc,
            average_precision=average_precision,
        )

    return {"roc_auc": roc_auc, "average_precision": average_precision}


def run_analysis(args: argparse.Namespace) -> None:
    dataset_root = args.dataset_root.resolve()
    outputs_root = args.kaggle_outputs_root.resolve()
    analysis_root = args.analysis_root.resolve()
    docs_figures_root = args.docs_figures_root.resolve()
    reports_dir = analysis_root / "reports"
    docs_analysis_figures_dir = docs_figures_root
    ensure_dirs(analysis_root, reports_dir, docs_analysis_figures_dir)

    feature_columns = load_feature_columns(dataset_root)
    if args.preset == "scaling_finalists":
        model_specs = parse_model_specs(";".join(SCALING_FINALISTS_SPECS))
        models = [item[0] for item in model_specs]
    elif args.model_specs:
        model_specs = parse_model_specs(args.model_specs)
        models = [item[0] for item in model_specs]
    else:
        model_specs = None
        models = [name.strip() for name in args.models.split(",") if name.strip()]
    threshold_grid = np.linspace(0.0, 1.0, num=args.threshold_grid_size)
    model_records: list[dict[str, Any]] = []
    threshold_choice_records: list[dict[str, Any]] = []

    split_paths = {
        "val": dataset_root / "clean" / "val.parquet",
        "test": dataset_root / "clean" / "test.parquet",
        "ood_attack_holdout": dataset_root / "clean" / "ood_attack_holdout.parquet",
    }

    for model_path_info in model_paths(outputs_root, models, model_specs=model_specs):
        model = load_model(model_path_info.artifact_path, model_path_info.key)
        figure_prefix = f"{model_path_info.key}_threshold_analysis"

        y_val, score_val = score_parquet_split(model, split_paths["val"], feature_columns, args.batch_size)
        val_sweep = build_threshold_sweep(y_true=y_val, y_score=score_val, thresholds=threshold_grid)
        val_sweep.to_csv(reports_dir / f"{model_path_info.key}_val_threshold_sweep.csv", index=False)

        selected_caps: dict[str, float] = {}
        for fpr_cap in DEFAULT_THRESHOLD_CAPS:
            chosen = select_threshold_under_fpr_cap(val_sweep, fpr_cap=fpr_cap)
            threshold_choice_records.append(
                {
                    "model": model_path_info.key,
                    "model_label": model_path_info.label,
                    "selection_type": f"fpr_cap_{fpr_cap:.3f}",
                    "threshold": float(chosen["threshold"]),
                    "val_f1": float(chosen["f1"]),
                    "val_recall": float(chosen["recall"]),
                    "val_fpr": float(chosen["fpr"]),
                }
            )
            selected_caps[f"{fpr_cap:.3f}"] = float(chosen["threshold"])

        chosen_threshold = float(select_threshold_under_fpr_cap(val_sweep, fpr_cap=args.recommended_fpr_cap)["threshold"])
        evaluated_thresholds: dict[str, float] = {"default_0.5": 0.5}
        for fpr_cap_key, threshold_value in selected_caps.items():
            evaluated_thresholds[f"tuned_fpr_cap_{fpr_cap_key}"] = threshold_value
        plot_threshold_sweep(
            sweep_df=val_sweep,
            model_label=model_path_info.label,
            output_path=docs_analysis_figures_dir / f"{model_path_info.key}_threshold_sweep.png",
            chosen_threshold=chosen_threshold,
        )
        save_split_artifacts(
            model_label=model_path_info.label,
            split_name="val",
            sweep_df=val_sweep,
            y_true=y_val,
            y_score=score_val,
            chosen_threshold=chosen_threshold,
            reports_dir=reports_dir,
            figures_dir=docs_analysis_figures_dir,
            figure_prefix=model_path_info.key,
        )

        y_test, score_test = score_parquet_split(model, split_paths["test"], feature_columns, args.batch_size)
        test_sweep = build_threshold_sweep(y_true=y_test, y_score=score_test, thresholds=threshold_grid)
        test_curve_metrics = save_split_artifacts(
            model_label=model_path_info.label,
            split_name="test",
            sweep_df=test_sweep,
            y_true=y_test,
            y_score=score_test,
            chosen_threshold=chosen_threshold,
            reports_dir=reports_dir,
            figures_dir=docs_analysis_figures_dir,
            figure_prefix=model_path_info.key,
        )
        default_test_metrics = evaluate_at_threshold(y_test, score_test, threshold=0.5)
        recommended_test_metrics = evaluate_at_threshold(y_test, score_test, threshold=chosen_threshold)

        plot_confusion_matrix(
            counts={key: int(default_test_metrics[key]) for key in ["tn", "fp", "fn", "tp"]},
            model_label=model_path_info.label,
            threshold_label="Default threshold = 0.500",
            output_path=docs_analysis_figures_dir / f"{model_path_info.key}_confusion_matrix_default.png",
        )
        plot_confusion_matrix(
            counts={key: int(recommended_test_metrics[key]) for key in ["tn", "fp", "fn", "tp"]},
            model_label=model_path_info.label,
            threshold_label=f"Tuned threshold = {chosen_threshold:.3f}",
            output_path=docs_analysis_figures_dir / f"{model_path_info.key}_confusion_matrix_tuned.png",
        )

        y_ood, score_ood = score_parquet_split(model, split_paths["ood_attack_holdout"], feature_columns, args.batch_size)
        for threshold_type, threshold_value in evaluated_thresholds.items():
            val_metrics = evaluate_at_threshold(y_val, score_val, threshold=threshold_value)
            test_metrics = evaluate_at_threshold(y_test, score_test, threshold=threshold_value)
            ood_metrics = evaluate_at_threshold(y_ood, score_ood, threshold=threshold_value)
            is_recommended = threshold_type == f"tuned_fpr_cap_{args.recommended_fpr_cap:.3f}"

            model_records.append(
                {
                    "model": model_path_info.key,
                    "model_label": model_path_info.label,
                    "split": "val",
                    "threshold_type": threshold_type,
                    "is_recommended": is_recommended,
                    **val_metrics,
                }
            )
            model_records.append(
                {
                    "model": model_path_info.key,
                    "model_label": model_path_info.label,
                    "split": "test",
                    "threshold_type": threshold_type,
                    "is_recommended": is_recommended,
                    **test_metrics,
                    **test_curve_metrics,
                }
            )
            model_records.append(
                {
                    "model": model_path_info.key,
                    "model_label": model_path_info.label,
                    "split": "ood_attack_holdout",
                    "threshold_type": threshold_type,
                    "is_recommended": is_recommended,
                    **ood_metrics,
                }
            )

        write_json(
            reports_dir / f"{model_path_info.key}_threshold_selection.json",
            {
                "model": model_path_info.key,
                "model_label": model_path_info.label,
                "recommended_fpr_cap": args.recommended_fpr_cap,
                "recommended_threshold": chosen_threshold,
                "thresholds_by_cap": selected_caps,
            },
        )

    pd.DataFrame(threshold_choice_records).to_csv(reports_dir / "threshold_selection_summary.csv", index=False)
    pd.DataFrame(model_records).to_csv(reports_dir / "threshold_evaluation_summary.csv", index=False)


def main() -> None:
    args = parse_args()
    run_analysis(args)


if __name__ == "__main__":
    main()
