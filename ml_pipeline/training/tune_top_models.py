from __future__ import annotations

import argparse
import gc
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier

from scripts.posttrain_threshold_analysis import (
    build_threshold_sweep,
    evaluate_at_threshold,
    select_threshold_under_fpr_cap,
)
from .train_iot_diad_binary import (
    QUICK_MODE_OVERRIDES,
    MODEL_SPECS,
    compute_sampling_target,
    fit_model,
    load_eval_subset,
    load_feature_columns,
    load_label_counts,
    resolve_split_path,
    sample_train_frame,
)


TOP_MODELS = ["catboost", "random_forest", "hist_gb"]
DEFAULT_TRIALS = {"catboost": 20, "random_forest": 16, "hist_gb": 16}
PROMOTION_PLAN = {"catboost": 2, "random_forest": 1, "hist_gb": 1}
THRESHOLD_CAPS = [0.005, 0.01, 0.02]


@dataclass(frozen=True)
class TrialBundle:
    trial_id: str
    model_name: str
    params: dict[str, Any]
    train_rows: int
    train_seconds: float
    metrics: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Random-search tuning for top IDS models.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\tuning\top_models"),
    )
    parser.add_argument("--models", type=str, default=",".join(TOP_MODELS))
    parser.add_argument("--profile", choices=["quick", "full"], default="quick")
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--eval-max-rows", type=int, default=300_000)
    parser.add_argument("--ood-max-rows", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--trials",
        type=str,
        default=",".join(f"{name}={count}" for name, count in DEFAULT_TRIALS.items()),
        help="Comma-separated mapping, e.g. catboost=20,random_forest=16,hist_gb=16",
    )
    parser.add_argument("--threshold-grid-size", type=int, default=401)
    parser.add_argument("--promotion-plan", type=str, default=",".join(f"{name}={count}" for name, count in PROMOTION_PLAN.items()))
    parser.add_argument("--checkpoint-every", type=int, default=1)
    return parser.parse_args()


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_mapping_arg(raw: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        key, value = item.split("=", 1)
        result[key.strip()] = int(value.strip())
    return result


def candidate_models(raw: str) -> list[str]:
    return [name.strip() for name in raw.split(",") if name.strip()]


def model_sampling_specs(profile: str) -> dict[str, Any]:
    return QUICK_MODE_OVERRIDES if profile == "quick" else MODEL_SPECS


def loguniform(rng: np.random.Generator, low: float, high: float) -> float:
    return float(math.exp(rng.uniform(math.log(low), math.log(high))))


def choose_option(rng: np.random.Generator, options: list[Any]) -> Any:
    return options[int(rng.integers(0, len(options)))]


def sample_hyperparameters(model_name: str, rng: np.random.Generator) -> dict[str, Any]:
    if model_name == "catboost":
        return {
            "depth": int(choose_option(rng, [6, 8, 10])),
            "learning_rate": round(loguniform(rng, 0.02, 0.15), 5),
            "iterations": int(choose_option(rng, [300, 500, 700, 900])),
            "l2_leaf_reg": int(choose_option(rng, [1, 3, 5, 7, 9, 12])),
            "random_strength": float(choose_option(rng, [0.0, 0.5, 1.0, 1.5, 2.0])),
            "bagging_temperature": float(choose_option(rng, [0.0, 0.5, 1.0, 2.0, 3.0])),
            "border_count": int(choose_option(rng, [64, 128, 254])),
            "attack_weight_multiplier": float(choose_option(rng, [1.0, 1.15, 1.3])),
        }
    if model_name == "random_forest":
        return {
            "n_estimators": int(choose_option(rng, [200, 400, 600])),
            "max_depth": None if rng.random() < 0.2 else int(choose_option(rng, [14, 18, 24])),
            "min_samples_leaf": int(choose_option(rng, [1, 2, 4, 8])),
            "min_samples_split": int(choose_option(rng, [2, 10, 20])),
            "max_features": choose_option(rng, ["sqrt", 0.2, 0.35, 0.5]),
            "max_samples": None if rng.random() < 0.15 else float(choose_option(rng, [0.1, 0.2, 0.35])),
        }
    if model_name == "hist_gb":
        return {
            "learning_rate": float(choose_option(rng, [0.02, 0.05, 0.08, 0.1])),
            "max_iter": int(choose_option(rng, [200, 400, 600, 800])),
            "max_leaf_nodes": int(choose_option(rng, [15, 31, 63, 127])),
            "min_samples_leaf": int(choose_option(rng, [20, 50, 100, 200])),
            "l2_regularization": float(choose_option(rng, [0.0, 0.1, 1.0, 5.0, 10.0])),
            "max_bins": int(choose_option(rng, [64, 128, 255])),
        }
    raise ValueError(f"Unsupported model: {model_name}")


def build_tuned_model(model_name: str, params: dict[str, Any], seed: int) -> Any:
    if model_name == "catboost":
        return CatBoostClassifier(
            iterations=params["iterations"],
            learning_rate=params["learning_rate"],
            depth=params["depth"],
            l2_leaf_reg=params["l2_leaf_reg"],
            random_strength=params["random_strength"],
            bagging_temperature=params["bagging_temperature"],
            border_count=params["border_count"],
            loss_function="Logloss",
            eval_metric="F1",
            random_seed=seed,
            verbose=False,
        )
    if model_name == "random_forest":
        return RandomForestClassifier(
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            min_samples_leaf=params["min_samples_leaf"],
            min_samples_split=params["min_samples_split"],
            max_features=params["max_features"],
            max_samples=params["max_samples"],
            class_weight="balanced_subsample",
            n_jobs=2,
            random_state=seed,
        )
    if model_name == "hist_gb":
        return HistGradientBoostingClassifier(
            loss="log_loss",
            learning_rate=params["learning_rate"],
            max_iter=params["max_iter"],
            max_leaf_nodes=params["max_leaf_nodes"],
            min_samples_leaf=params["min_samples_leaf"],
            l2_regularization=params["l2_regularization"],
            max_bins=params["max_bins"],
            early_stopping=True,
            random_state=seed,
        )
    raise ValueError(f"Unsupported model: {model_name}")


def predict_scores(model_name: str, model: Any, frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict_proba(frame)[:, 1], dtype=np.float32)


def sweep_metrics(
    y_true: np.ndarray,
    y_score: np.ndarray,
    threshold_grid: np.ndarray,
) -> dict[str, Any]:
    sweep_df = build_threshold_sweep(y_true=y_true, y_score=y_score, thresholds=threshold_grid)
    payload: dict[str, Any] = {}
    default_metrics = evaluate_at_threshold(y_true, y_score, threshold=0.5)
    payload["default_0.5"] = default_metrics

    for cap in THRESHOLD_CAPS:
        chosen = select_threshold_under_fpr_cap(sweep_df, fpr_cap=cap)
        threshold = float(chosen["threshold"])
        payload[f"cap_{cap:.3f}"] = {
            "threshold": threshold,
            **evaluate_at_threshold(y_true, y_score, threshold=threshold),
        }
    return payload


def flatten_trial_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    flat = {
        "val_f1_at_default_0.5": metrics["val"]["default_0.5"]["f1"],
        "val_recall_at_default_0.5": metrics["val"]["default_0.5"]["recall"],
        "val_fpr_at_default_0.5": metrics["val"]["default_0.5"]["fpr"],
        "ood_recall_at_default_0.5": metrics["ood"]["default_0.5"]["recall"],
    }
    for cap in THRESHOLD_CAPS:
        key = f"cap_{cap:.3f}"
        flat[f"val_threshold_at_{key}"] = metrics["val"][key]["threshold"]
        flat[f"val_f1_at_tuned_{key}"] = metrics["val"][key]["f1"]
        flat[f"val_recall_at_tuned_{key}"] = metrics["val"][key]["recall"]
        flat[f"val_fpr_at_tuned_{key}"] = metrics["val"][key]["fpr"]
        flat[f"ood_recall_at_tuned_{key}"] = metrics["ood"][key]["recall"]
    return flat


def passes_selection_gate(row: dict[str, Any] | pd.Series) -> bool:
    return float(row["val_fpr_at_default_0.5"]) <= 0.02


def rank_trials(trials_df: pd.DataFrame) -> pd.DataFrame:
    ranked = trials_df.copy()
    ranked["passes_gate"] = ranked.apply(passes_selection_gate, axis=1)
    ranked = ranked.sort_values(
        by=[
            "passes_gate",
            "val_f1_at_tuned_cap_0.010",
            "val_fpr_at_default_0.5",
            "ood_recall_at_tuned_cap_0.020",
            "train_seconds",
        ],
        ascending=[False, False, True, False, True],
    ).reset_index(drop=True)
    return ranked


def select_promoted_trials(trials_df: pd.DataFrame, promotion_plan: dict[str, int]) -> dict[str, list[str]]:
    promoted: dict[str, list[str]] = {}
    for model_name, top_k in promotion_plan.items():
        model_trials = rank_trials(trials_df.loc[trials_df["model_name"] == model_name])
        promoted[model_name] = model_trials.head(top_k)["trial_id"].tolist()
    return promoted


def selection_rule_markdown() -> str:
    return (
        "# Selection Rule\n\n"
        "- Hard gate: `val_fpr_at_default_0.5 <= 0.02`\n"
        "- Primary rank: `val_f1_at_tuned_cap_0.010`\n"
        "- Tie-break 1: lower `val_fpr_at_default_0.5`\n"
        "- Tie-break 2: higher `ood_recall_at_tuned_cap_0.020`\n"
        "- Tie-break 3: lower `train_seconds`\n"
    )


def search_space_payload(models: list[str], profile: str, trial_plan: dict[str, int]) -> dict[str, Any]:
    return {
        "models": models,
        "profile": profile,
        "trial_plan": trial_plan,
        "threshold_caps": THRESHOLD_CAPS,
        "catboost": {
            "depth": [6, 8, 10],
            "learning_rate": [0.02, 0.15],
            "iterations": [300, 500, 700, 900],
            "l2_leaf_reg": [1, 3, 5, 7, 9, 12],
            "random_strength": [0.0, 0.5, 1.0, 1.5, 2.0],
            "bagging_temperature": [0.0, 0.5, 1.0, 2.0, 3.0],
            "border_count": [64, 128, 254],
            "attack_weight_multiplier": [1.0, 1.15, 1.3],
        },
        "random_forest": {
            "n_estimators": [200, 400, 600],
            "max_depth": [14, 18, 24, None],
            "min_samples_leaf": [1, 2, 4, 8],
            "min_samples_split": [2, 10, 20],
            "max_features": ["sqrt", 0.2, 0.35, 0.5],
            "max_samples": [0.1, 0.2, 0.35, None],
        },
        "hist_gb": {
            "learning_rate": [0.02, 0.05, 0.08, 0.1],
            "max_iter": [200, 400, 600, 800],
            "max_leaf_nodes": [15, 31, 63, 127],
            "min_samples_leaf": [20, 50, 100, 200],
            "l2_regularization": [0.0, 0.1, 1.0, 5.0, 10.0],
            "max_bins": [64, 128, 255],
        },
    }


def trial_record(bundle: TrialBundle) -> dict[str, Any]:
    return {
        "trial_id": bundle.trial_id,
        "model_name": bundle.model_name,
        "train_rows": bundle.train_rows,
        "train_seconds": bundle.train_seconds,
        "hyperparameters": bundle.params,
        **flatten_trial_metrics(bundle.metrics),
    }


def persist_reports(
    reports_dir: Path,
    models: list[str],
    trials_out: list[dict[str, Any]],
    promotion_plan: dict[str, int],
    profile: str,
    trial_plan: dict[str, int],
    progress: dict[str, Any],
) -> None:
    if trials_out:
        trials_df = pd.DataFrame(trials_out)
        ranked_frames = [
            rank_trials(trials_df.loc[trials_df["model_name"] == name])
            for name in models
            if not trials_df.loc[trials_df["model_name"] == name].empty
        ]
        ranked_df = pd.concat(ranked_frames, ignore_index=True) if ranked_frames else pd.DataFrame()
        promoted = select_promoted_trials(trials_df, promotion_plan)
    else:
        trials_df = pd.DataFrame()
        ranked_df = pd.DataFrame()
        promoted = {model_name: [] for model_name in promotion_plan}

    trials_df.to_csv(reports_dir / "trial_results.csv", index=False)
    ranked_df.to_csv(reports_dir / "trial_results_ranked.csv", index=False)
    write_jsonl(reports_dir / "trial_results.jsonl", trials_out)
    write_json(
        reports_dir / "best_configs.json",
        {
            "promotion_plan": promotion_plan,
            "promoted_trials": promoted,
            "top_trials_by_model": {
                model_name: rank_trials(trials_df.loc[trials_df["model_name"] == model_name]).head(
                    promotion_plan.get(model_name, 1)
                ).to_dict(orient="records")
                if not trials_df.empty
                else []
                for model_name in models
            },
        },
    )
    write_json(reports_dir / "search_space.json", search_space_payload(models, profile, trial_plan))
    write_json(reports_dir / "progress.json", progress)
    (reports_dir / "selection_rule.md").write_text(selection_rule_markdown(), encoding="utf-8")


def run_tuning(args: argparse.Namespace) -> None:
    dataset_root = args.dataset_root.resolve()
    output_root = args.output_root.resolve()
    reports_dir = output_root / "reports"
    ensure_dirs(output_root, reports_dir)

    models = candidate_models(args.models)
    trial_plan = parse_mapping_arg(args.trials)
    promotion_plan = parse_mapping_arg(args.promotion_plan)
    sampling_specs = model_sampling_specs(args.profile)

    feature_columns = load_feature_columns(dataset_root)
    split_counts = load_label_counts(dataset_root)
    threshold_grid = np.linspace(0.0, 1.0, num=args.threshold_grid_size)

    train_path = resolve_split_path(dataset_root, "train.parquet")
    val_path = resolve_split_path(dataset_root, "val.parquet")
    ood_path = resolve_split_path(dataset_root, "ood_attack_holdout.parquet")

    trials_out: list[dict[str, Any]] = []
    total_requested_trials = int(sum(trial_plan.get(model_name, DEFAULT_TRIALS[model_name]) for model_name in models))
    progress = {
        "profile": args.profile,
        "models": models,
        "trial_plan": trial_plan,
        "completed_trials": 0,
        "total_trials": total_requested_trials,
        "last_completed_trial_id": None,
        "status": "running",
    }
    persist_reports(reports_dir, models, trials_out, promotion_plan, args.profile, trial_plan, progress)

    for model_index, model_name in enumerate(models, start=1):
        spec = sampling_specs[model_name]
        benign_rows, target_attack_rows = compute_sampling_target(spec, split_counts)
        train_seed = args.seed + model_index * 101
        X_train, y_train, sample_info = sample_train_frame(
            train_path=train_path,
            feature_columns=feature_columns,
            benign_rows=benign_rows,
            target_attack_rows=target_attack_rows,
            seed=train_seed,
            batch_size=args.batch_size,
        )
        X_val_probe, y_val_probe = load_eval_subset(
            val_path,
            feature_columns,
            max_rows=args.eval_max_rows,
            seed=args.seed + model_index * 103,
            batch_size=args.batch_size,
        )
        X_ood_probe, y_ood_probe = load_eval_subset(
            ood_path,
            feature_columns,
            max_rows=args.ood_max_rows,
            seed=args.seed + model_index * 107,
            batch_size=args.batch_size,
        )

        rng = np.random.default_rng(args.seed + model_index * 1009)
        total_trials = trial_plan.get(model_name, DEFAULT_TRIALS[model_name])

        for trial_number in range(1, total_trials + 1):
            params = sample_hyperparameters(model_name, rng)
            model = build_tuned_model(model_name, params, seed=args.seed + trial_number)

            fit_params = params.copy()
            if model_name == "catboost":
                attack_count = int((y_train == 1).sum())
                benign_count = int((y_train == 0).sum())
                baseline_attack_weight = max(attack_count, benign_count) / max(1, attack_count)
                benign_weight = max(attack_count, benign_count) / max(1, benign_count)
                attack_weight = baseline_attack_weight * params["attack_weight_multiplier"]
                model.set_params(class_weights=[float(benign_weight), float(attack_weight)])
                fit_params["class_weights"] = [float(benign_weight), float(attack_weight)]

            start = time.perf_counter()
            model = fit_model(model_name, model, X_train, y_train, X_val_probe, y_val_probe)
            train_seconds = float(time.perf_counter() - start)

            val_scores = predict_scores(model_name, model, X_val_probe)
            ood_scores = predict_scores(model_name, model, X_ood_probe)
            metrics = {
                "val": sweep_metrics(y_val_probe, val_scores, threshold_grid),
                "ood": sweep_metrics(y_ood_probe, ood_scores, threshold_grid),
            }
            bundle = TrialBundle(
                trial_id=f"{model_name}-trial-{trial_number:03d}",
                model_name=model_name,
                params=fit_params,
                train_rows=int(len(X_train)),
                train_seconds=train_seconds,
                metrics=metrics,
            )
            record = trial_record(bundle)
            record["sample_info"] = sample_info
            trials_out.append(record)
            progress["completed_trials"] = len(trials_out)
            progress["last_completed_trial_id"] = bundle.trial_id
            progress["current_model"] = model_name
            progress["current_trial_number"] = trial_number
            if args.checkpoint_every > 0 and len(trials_out) % args.checkpoint_every == 0:
                persist_reports(reports_dir, models, trials_out, promotion_plan, args.profile, trial_plan, progress)
            del model, val_scores, ood_scores
            gc.collect()

    progress["status"] = "completed"
    persist_reports(reports_dir, models, trials_out, promotion_plan, args.profile, trial_plan, progress)


def main() -> None:
    args = parse_args()
    run_tuning(args)


if __name__ == "__main__":
    main()
