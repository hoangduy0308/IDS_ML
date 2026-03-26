from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(r"F:\Work\IDS_ML_New")
OUTPUTS_ROOT = REPO_ROOT / "artifacts" / "kaggle" / "outputs"
REPORTS_ROOT = REPO_ROOT / "artifacts" / "kaggle" / "reports"
FIGURES_ROOT = REPO_ROOT / "docs" / "figures"

MODELS = ["logreg", "random_forest", "hist_gb", "catboost", "mlp"]
MODEL_LABELS = {
    "logreg": "LogReg",
    "random_forest": "RandomForest",
    "hist_gb": "HistGB",
    "catboost": "CatBoost",
    "mlp": "MLP",
}
CURVE_STYLE = {
    "logreg": {"color": "#1f77b4", "marker": "o"},
    "random_forest": {"color": "#2ca02c", "marker": "s"},
    "hist_gb": {"color": "#ff7f0e", "marker": "^"},
    "catboost": {"color": "#9467bd", "marker": None},
    "mlp": {"color": "#d62728", "marker": "D"},
}


def ensure_dirs() -> None:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)


def model_result_dir(model: str) -> Path:
    return OUTPUTS_ROOT / model / f"{model}_results"


def load_summary_rows() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for model in MODELS:
        summary_path = model_result_dir(model) / "summary.csv"
        frame = pd.read_csv(summary_path)
        frame["model_key"] = model
        frame["model_label"] = MODEL_LABELS[model]
        rows.append(frame)
    combined = pd.concat(rows, ignore_index=True)
    return combined[
        [
            "model_key",
            "model_label",
            "train_seconds",
            "val_f1",
            "test_f1",
            "test_recall",
            "test_precision",
            "test_fpr",
            "ood_recall",
        ]
    ].sort_values(by="test_f1", ascending=False)


def write_combined_summary(summary_df: pd.DataFrame) -> None:
    summary_df.to_csv(REPORTS_ROOT / "kaggle_benchmark_summary.csv", index=False)


def load_training_curve(model: str) -> pd.DataFrame:
    curve_path = model_result_dir(model) / "training_curve.csv"
    frame = pd.read_csv(curve_path)
    frame["model_key"] = model
    frame["model_label"] = MODEL_LABELS[model]
    return frame


def load_all_training_curves() -> dict[str, pd.DataFrame]:
    return {model: load_training_curve(model) for model in MODELS}


def save_single_training_curve(model: str, curve_df: pd.DataFrame) -> None:
    style = CURVE_STYLE[model]
    label = MODEL_LABELS[model]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(
        curve_df["stage_index"],
        curve_df["train_f1"],
        label="Train F1",
        color=style["color"],
        marker=style["marker"],
        linewidth=2,
        markersize=5 if style["marker"] else 0,
    )
    ax.plot(
        curve_df["stage_index"],
        curve_df["val_f1"],
        label="Validation F1",
        color="#ff8c00",
        marker=style["marker"],
        linewidth=2,
        markersize=5 if style["marker"] else 0,
        alpha=0.9,
    )
    ax.set_title(f"{label} Training Curve")
    ax.set_xlabel(curve_df["stage_type"].iloc[0].replace("_", " ").title())
    ax.set_ylabel("F1")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / f"{model}_training_curve.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_all_training_curves(curves: dict[str, pd.DataFrame]) -> None:
    for model, curve_df in curves.items():
        save_single_training_curve(model, curve_df)


def save_learning_curve_grid(curves: dict[str, pd.DataFrame]) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(14, 13))
    ordered_axes = axes.flatten()
    for idx, model in enumerate(MODELS):
        ax = ordered_axes[idx]
        curve_df = curves[model]
        style = CURVE_STYLE[model]
        ax.plot(
            curve_df["stage_index"],
            curve_df["train_f1"],
            label="Train F1",
            color=style["color"],
            marker=style["marker"],
            linewidth=1.8,
            markersize=4 if style["marker"] else 0,
        )
        ax.plot(
            curve_df["stage_index"],
            curve_df["val_f1"],
            label="Validation F1",
            color="#ff8c00",
            marker=style["marker"],
            linewidth=1.8,
            markersize=4 if style["marker"] else 0,
            alpha=0.9,
        )
        ax.set_title(MODEL_LABELS[model])
        ax.set_xlabel(curve_df["stage_type"].iloc[0].replace("_", " ").title())
        ax.set_ylabel("F1")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    ordered_axes[-1].axis("off")
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "all_models_learning_curves.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_learning_curve_summary(
    summary_df: pd.DataFrame, curves: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    metric_lookup = summary_df.set_index("model_key").to_dict(orient="index")
    rows = []
    for model, curve_df in curves.items():
        start_row = curve_df.iloc[0]
        end_row = curve_df.iloc[-1]
        best_row = curve_df.loc[curve_df["val_f1"].idxmax()]
        metrics = metric_lookup[model]
        rows.append(
            {
                "model": model,
                "curve_points": int(len(curve_df)),
                "train_f1_start": float(start_row["train_f1"]),
                "val_f1_start": float(start_row["val_f1"]),
                "train_f1_end": float(end_row["train_f1"]),
                "val_f1_end": float(end_row["val_f1"]),
                "generalization_gap_end": float(end_row["train_f1"] - end_row["val_f1"]),
                "best_val_f1": float(best_row["val_f1"]),
                "best_stage_index": int(best_row["stage_index"]),
                "val_gain": float(end_row["val_f1"] - start_row["val_f1"]),
                "train_gain": float(end_row["train_f1"] - start_row["train_f1"]),
                "test_f1": float(metrics["test_f1"]),
                "test_fpr": float(metrics["test_fpr"]),
                "ood_recall": float(metrics["ood_recall"]),
                "train_seconds": float(metrics["train_seconds"]),
            }
        )
    return pd.DataFrame(rows).sort_values(by="test_fpr", ascending=True)


def write_learning_curve_summary(curve_summary_df: pd.DataFrame) -> None:
    curve_summary_df.to_csv(REPORTS_ROOT / "learning_curve_summary.csv", index=False)


def save_generalization_gap_chart(curve_summary_df: pd.DataFrame) -> None:
    ordered = curve_summary_df.sort_values(by="generalization_gap_end", ascending=True)
    labels = [MODEL_LABELS[key] for key in ordered["model"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, ordered["generalization_gap_end"], color="#6b7280")
    ax.set_title("Train-Validation F1 Gap at Final Stage")
    ax.set_ylabel("Train F1 - Validation F1")
    ax.tick_params(axis="x", rotation=20)
    ax.axhline(0.0, color="black", linewidth=1)
    for bar, value in zip(bars, ordered["generalization_gap_end"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + (0.0008 if value >= 0 else -0.0015),
            f"{value:.4f}",
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "generalization_gap_comparison.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_selection_tradeoff(summary_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for _, row in summary_df.iterrows():
        model = row["model_key"]
        ax.scatter(
            row["test_fpr"],
            row["test_f1"],
            s=max(90, row["train_seconds"] * 1.3),
            color=CURVE_STYLE[model]["color"],
            alpha=0.8,
            label=MODEL_LABELS[model],
        )
        ax.text(
            row["test_fpr"],
            row["test_f1"] + 0.00008,
            MODEL_LABELS[model],
            fontsize=9,
            ha="center",
        )
    ax.set_title("Model Selection Trade-off")
    ax.set_xlabel("Test FPR")
    ax.set_ylabel("Test F1")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "model_selection_tradeoff.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_metric_overview(summary_df: pd.DataFrame) -> None:
    ordered = summary_df.sort_values(by="test_f1", ascending=False)
    labels = ordered["model_label"].tolist()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    axes[0].bar(labels, ordered["test_f1"], color="#2f5d8c")
    axes[0].set_title("Test F1 by Model")
    axes[0].set_ylim(0.98, 0.9925)
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].bar(labels, ordered["test_fpr"], color="#b24646")
    axes[1].set_title("Test FPR by Model")
    axes[1].tick_params(axis="x", rotation=20)

    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "kaggle_metric_overview.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_training_time_chart(summary_df: pd.DataFrame) -> None:
    ordered = summary_df.sort_values(by="train_seconds", ascending=True)
    labels = ordered["model_label"].tolist()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, ordered["train_seconds"], color="#4a8f5b")
    ax.set_title("Training Time on Kaggle")
    ax.set_ylabel("Seconds")
    ax.tick_params(axis="x", rotation=20)

    for idx, value in enumerate(ordered["train_seconds"]):
        ax.text(idx, value + 5, f"{value:.1f}", ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "kaggle_training_time.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def load_log_events(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_catboost_learning_curve() -> None:
    log_path = OUTPUTS_ROOT / "catboost" / "ids-binary-catboost.log"
    events = load_log_events(log_path)
    pattern = re.compile(
        r"^(?P<iteration>\d+):\s+learn:\s(?P<learn>[0-9.]+)\s+test:\s(?P<test>[0-9.]+)"
    )
    rows = []
    for event in events:
        data = event.get("data", "").strip()
        match = pattern.match(data)
        if not match:
            continue
        rows.append(
            {
                "iteration": int(match.group("iteration")),
                "learn_f1": float(match.group("learn")),
                "val_f1": float(match.group("test")),
                "wall_time_seconds": float(event["time"]),
            }
        )
    if not rows:
        return

    curve_df = pd.DataFrame(rows)
    curve_df.to_csv(REPORTS_ROOT / "catboost_learning_curve.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(curve_df["iteration"], curve_df["learn_f1"], marker="o", label="Train F1")
    ax.plot(curve_df["iteration"], curve_df["val_f1"], marker="o", label="Validation F1")
    ax.set_title("CatBoost Learning Curve")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("F1")
    ax.legend()
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "catboost_learning_curve.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_epoch_timeline() -> None:
    log_specs = {
        "logreg": (OUTPUTS_ROOT / "logreg" / "ids-binary-logistic-regression.log", "Logistic regression epoch"),
        "mlp": (OUTPUTS_ROOT / "mlp" / "ids-binary-mlp.log", "MLP epoch"),
    }
    rows = []
    for model, (path, marker) in log_specs.items():
        events = load_log_events(path)
        for event in events:
            data = event.get("data", "").strip()
            if marker in data:
                rows.append(
                    {
                        "model": MODEL_LABELS[model],
                        "event": data,
                        "wall_time_seconds": float(event["time"]),
                    }
                )
    if not rows:
        return

    timeline_df = pd.DataFrame(rows)
    timeline_df.to_csv(REPORTS_ROOT / "epoch_timeline.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 4))
    for model_name, group in timeline_df.groupby("model"):
        ax.plot(group["wall_time_seconds"], [model_name] * len(group), marker="o", linestyle="-", label=model_name)
        for _, row in group.iterrows():
            ax.text(row["wall_time_seconds"], row["model"], row["event"].split()[-1], fontsize=8, va="bottom")
    ax.set_title("Epoch Timeline from Kaggle Logs")
    ax.set_xlabel("Wall time (s)")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "epoch_timeline.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    summary_df = load_summary_rows()
    curves = load_all_training_curves()
    write_combined_summary(summary_df)
    curve_summary_df = build_learning_curve_summary(summary_df, curves)
    write_learning_curve_summary(curve_summary_df)
    save_metric_overview(summary_df)
    save_training_time_chart(summary_df)
    save_all_training_curves(curves)
    save_learning_curve_grid(curves)
    save_generalization_gap_chart(curve_summary_df)
    save_selection_tradeoff(summary_df)
    save_catboost_learning_curve()
    save_epoch_timeline()


if __name__ == "__main__":
    main()
