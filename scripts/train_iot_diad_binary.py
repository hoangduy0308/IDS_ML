from __future__ import annotations

import argparse
import gc
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from catboost import CatBoostClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight


LABEL_MAP = {"Benign": 0, "Attack": 1}
DEFAULT_MODELS = ["logreg", "random_forest", "hist_gb", "catboost", "mlp"]


@dataclass(frozen=True)
class ModelSpec:
    name: str
    attack_ratio: int
    max_attack_rows: int


MODEL_SPECS = {
    "logreg": ModelSpec("logreg", attack_ratio=4, max_attack_rows=400_000),
    "random_forest": ModelSpec("random_forest", attack_ratio=6, max_attack_rows=600_000),
    "hist_gb": ModelSpec("hist_gb", attack_ratio=8, max_attack_rows=1_000_000),
    "catboost": ModelSpec("catboost", attack_ratio=10, max_attack_rows=1_500_000),
    "mlp": ModelSpec("mlp", attack_ratio=4, max_attack_rows=300_000),
}

QUICK_MODE_OVERRIDES = {
    "logreg": ModelSpec("logreg", attack_ratio=2, max_attack_rows=120_000),
    "random_forest": ModelSpec("random_forest", attack_ratio=3, max_attack_rows=150_000),
    "hist_gb": ModelSpec("hist_gb", attack_ratio=4, max_attack_rows=250_000),
    "catboost": ModelSpec("catboost", attack_ratio=4, max_attack_rows=300_000),
    "mlp": ModelSpec("mlp", attack_ratio=2, max_attack_rows=100_000),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train binary IDS baselines on preprocessed CIC IoT-DIAD parquet splits.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_binary"),
    )
    parser.add_argument("--models", type=str, default=",".join(DEFAULT_MODELS))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", choices=["quick", "full"], default="full")
    parser.add_argument("--batch-size", type=int, default=100_000)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_dataset_file(dataset_root: Path, *candidates: str) -> Path:
    searched = [str(dataset_root / candidate) for candidate in candidates]
    for candidate in candidates:
        path = dataset_root / candidate
        if path.exists():
            return path
    candidate_names = {Path(candidate).name for candidate in candidates}
    recursive_hits = [path for path in dataset_root.rglob("*") if path.is_file() and path.name in candidate_names]
    if recursive_hits:
        recursive_hits.sort(key=lambda path: (len(path.parts), str(path)))
        return recursive_hits[0]
    raise FileNotFoundError(f"Unable to locate dataset file. Tried: {searched}")


def load_feature_columns(dataset_root: Path) -> list[str]:
    payload = read_json(resolve_dataset_file(dataset_root, "manifests/feature_columns.json", "feature_columns.json"))
    return list(payload["feature_columns"])


def load_label_counts(dataset_root: Path) -> dict[str, dict[str, int]]:
    payload = read_json(resolve_dataset_file(dataset_root, "manifests/cleaning_report.json", "cleaning_report.json"))
    return payload["label_distribution_by_split"]


def resolve_split_path(dataset_root: Path, split_name: str) -> Path:
    return resolve_dataset_file(dataset_root, f"clean/{split_name}", split_name)


def get_model_specs(model_names: list[str], profile: str) -> dict[str, ModelSpec]:
    specs: dict[str, ModelSpec] = {}
    overrides = QUICK_MODE_OVERRIDES if profile == "quick" else MODEL_SPECS
    for model_name in model_names:
        if model_name not in overrides:
            raise ValueError(f"Unsupported model: {model_name}")
        specs[model_name] = overrides[model_name]
    return specs


def compute_sampling_target(spec: ModelSpec, split_counts: dict[str, dict[str, int]]) -> tuple[int, int]:
    benign_rows = int(split_counts["train"]["Benign"])
    attack_rows = int(split_counts["train"]["Attack"])
    target_attack_rows = min(attack_rows, benign_rows * spec.attack_ratio, spec.max_attack_rows)
    return benign_rows, int(target_attack_rows)


def sample_train_frame(
    train_path: Path,
    feature_columns: list[str],
    benign_rows: int,
    target_attack_rows: int,
    seed: int,
    batch_size: int,
) -> tuple[pd.DataFrame, np.ndarray, dict[str, int]]:
    parquet_file = pq.ParquetFile(train_path)
    rng = np.random.default_rng(seed)
    keep_attack_probability = min(1.0, target_attack_rows / max(1, (parquet_file.metadata.num_rows - benign_rows)))

    benign_frames: list[pd.DataFrame] = []
    attack_frames: list[pd.DataFrame] = []

    selected_attack_rows = 0
    selected_benign_rows = 0

    columns = feature_columns + ["derived_label_binary"]
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        frame = batch.to_pandas()
        y = frame["derived_label_binary"].map(LABEL_MAP).to_numpy(dtype=np.int8)
        X = frame[feature_columns].astype(np.float32)

        benign_mask = y == 0
        if benign_mask.any():
            benign_frames.append(X.loc[benign_mask].copy())
            selected_benign_rows += int(benign_mask.sum())

        attack_mask = y == 1
        if attack_mask.any():
            attack_idx = np.flatnonzero(attack_mask)
            if keep_attack_probability < 1.0:
                keep_mask = rng.random(len(attack_idx)) < keep_attack_probability
                attack_idx = attack_idx[keep_mask]
            if attack_idx.size:
                attack_frames.append(X.iloc[attack_idx].copy())
                selected_attack_rows += int(attack_idx.size)

    if benign_frames:
        benign_df = pd.concat(benign_frames, ignore_index=True)
    else:
        benign_df = pd.DataFrame(columns=feature_columns)

    if attack_frames:
        attack_df = pd.concat(attack_frames, ignore_index=True)
    else:
        attack_df = pd.DataFrame(columns=feature_columns)

    if len(attack_df) > target_attack_rows:
        attack_df = attack_df.sample(n=target_attack_rows, random_state=seed).reset_index(drop=True)
        selected_attack_rows = len(attack_df)

    train_df = pd.concat([benign_df, attack_df], ignore_index=True)
    train_y = np.concatenate(
        [
            np.zeros(len(benign_df), dtype=np.int8),
            np.ones(len(attack_df), dtype=np.int8),
        ]
    )

    shuffle_idx = rng.permutation(len(train_df))
    train_df = train_df.iloc[shuffle_idx].reset_index(drop=True)
    train_y = train_y[shuffle_idx]

    summary = {
        "selected_benign_rows": int(selected_benign_rows),
        "selected_attack_rows": int(selected_attack_rows),
        "final_train_rows": int(len(train_df)),
    }
    return train_df, train_y, summary


def load_eval_subset(
    split_path: Path,
    feature_columns: list[str],
    max_rows: int,
    seed: int,
    batch_size: int,
) -> tuple[pd.DataFrame, np.ndarray]:
    parquet_file = pq.ParquetFile(split_path)
    rng = np.random.default_rng(seed)
    total_rows = max(1, parquet_file.metadata.num_rows)
    keep_probability = min(1.0, max_rows / total_rows)
    frames: list[pd.DataFrame] = []
    labels: list[np.ndarray] = []
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=feature_columns + ["derived_label_binary"]):
        frame = batch.to_pandas()
        if keep_probability < 1.0:
            keep_mask = rng.random(len(frame)) < keep_probability
            frame = frame.loc[keep_mask]
        if frame.empty:
            continue
        frames.append(frame[feature_columns].astype(np.float32).copy())
        labels.append(frame["derived_label_binary"].map(LABEL_MAP).to_numpy(dtype=np.int8))
    if not frames:
        return pd.DataFrame(columns=feature_columns), np.array([], dtype=np.int8)
    eval_df = pd.concat(frames, ignore_index=True)
    eval_y = np.concatenate(labels)
    if len(eval_df) > max_rows:
        sampled_idx = rng.choice(len(eval_df), size=max_rows, replace=False)
        eval_df = eval_df.iloc[sampled_idx].reset_index(drop=True)
        eval_y = eval_y[sampled_idx]
    gc.collect()
    return eval_df, eval_y


def build_model(model_name: str, seed: int) -> Any:
    if model_name == "logreg":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        solver="saga",
                        max_iter=200,
                        class_weight="balanced",
                        random_state=seed,
                    ),
                ),
            ]
        )
    if model_name == "random_forest":
        return RandomForestClassifier(
            n_estimators=200,
            n_jobs=-1,
            class_weight="balanced_subsample",
            min_samples_leaf=2,
            random_state=seed,
        )
    if model_name == "hist_gb":
        return HistGradientBoostingClassifier(
            loss="log_loss",
            learning_rate=0.05,
            max_iter=200,
            max_leaf_nodes=31,
            early_stopping=True,
            random_state=seed,
        )
    if model_name == "catboost":
        return CatBoostClassifier(
            iterations=300,
            learning_rate=0.05,
            depth=8,
            loss_function="Logloss",
            eval_metric="F1",
            random_seed=seed,
            verbose=False,
        )
    if model_name == "mlp":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    MLPClassifier(
                        hidden_layer_sizes=(256, 128),
                        batch_size=4096,
                        early_stopping=True,
                        max_iter=50,
                        random_state=seed,
                    ),
                ),
            ]
        )
    raise ValueError(f"Unsupported model: {model_name}")


def fit_model(
    model_name: str,
    model: Any,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val_small: pd.DataFrame,
    y_val_small: np.ndarray,
) -> Any:
    if model_name == "hist_gb":
        sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)
        model.fit(X_train, y_train, sample_weight=sample_weight)
        return model
    if model_name == "catboost":
        existing_class_weights = model.get_param("class_weights")
        if existing_class_weights is None:
            class_counts = np.bincount(y_train, minlength=2)
            benign_weight = max(class_counts) / max(1, class_counts[0])
            attack_weight = max(class_counts) / max(1, class_counts[1])
            model.set_params(class_weights=[float(benign_weight), float(attack_weight)])
        if len(X_val_small):
            model.fit(X_train, y_train, eval_set=(X_val_small, y_val_small), use_best_model=False)
        else:
            model.fit(X_train, y_train)
        return model
    model.fit(X_train, y_train)
    return model


def evaluate_split(
    model: Any,
    split_path: Path,
    feature_columns: list[str],
    batch_size: int,
) -> dict[str, Any]:
    parquet_file = pq.ParquetFile(split_path)
    total_rows = 0
    y_true_all: list[np.ndarray] = []
    y_pred_all: list[np.ndarray] = []

    start = time.perf_counter()
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=feature_columns + ["derived_label_binary"]):
        frame = batch.to_pandas()
        X = frame[feature_columns].astype(np.float32)
        y_true = frame["derived_label_binary"].map(LABEL_MAP).to_numpy(dtype=np.int8)
        y_pred = np.asarray(model.predict(X), dtype=np.int8)
        total_rows += len(frame)
        y_true_all.append(y_true)
        y_pred_all.append(y_pred)
    elapsed = time.perf_counter() - start

    y_true = np.concatenate(y_true_all)
    y_pred = np.concatenate(y_pred_all)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    accuracy = (tp + tn) / max(1, total_rows)
    balanced_accuracy = (recall + specificity) / 2
    f1 = (2 * precision * recall) / max(1e-12, precision + recall)
    fpr = fp / max(1, fp + tn)
    tpr = recall

    return {
        "rows": int(total_rows),
        "accuracy": float(accuracy),
        "balanced_accuracy": float(balanced_accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "fpr": float(fpr),
        "tpr": float(tpr),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "inference_seconds": float(elapsed),
        "rows_per_second": float(total_rows / max(elapsed, 1e-9)),
    }


def save_model(model_name: str, model: Any, output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    if model_name == "catboost":
        path = output_dir / f"{model_name}.cbm"
        model.save_model(path)
        return str(path)
    path = output_dir / f"{model_name}.joblib"
    joblib.dump(model, path)
    return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_training(args: argparse.Namespace) -> None:
    dataset_root = args.dataset_root.resolve()
    output_root = args.output_root.resolve()
    models_dir = output_root / "models"
    reports_dir = output_root / "reports"
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    feature_columns = load_feature_columns(dataset_root)
    split_counts = load_label_counts(dataset_root)

    model_names = [name.strip() for name in args.models.split(",") if name.strip()]
    model_specs = get_model_specs(model_names, args.profile)

    train_path = resolve_split_path(dataset_root, "train.parquet")
    val_path = resolve_split_path(dataset_root, "val.parquet")
    test_path = resolve_split_path(dataset_root, "test.parquet")
    ood_path = resolve_split_path(dataset_root, "ood_attack_holdout.parquet")

    metrics_summary: list[dict[str, Any]] = []
    metrics_detail: dict[str, Any] = {}
    sampling_summary: dict[str, Any] = {}

    for model_index, model_name in enumerate(model_names, start=1):
        spec = model_specs[model_name]
        benign_rows, target_attack_rows = compute_sampling_target(spec, split_counts)
        log(f"[{model_index}/{len(model_names)}] Sampling train set for {model_name}")
        X_train, y_train, sample_info = sample_train_frame(
            train_path,
            feature_columns,
            benign_rows=benign_rows,
            target_attack_rows=target_attack_rows,
            seed=args.seed + model_index,
            batch_size=args.batch_size,
        )
        sampling_summary[model_name] = {
            "attack_ratio": spec.attack_ratio,
            "max_attack_rows": spec.max_attack_rows,
            **sample_info,
        }

        X_val_small, y_val_small = load_eval_subset(
            val_path,
            feature_columns,
            max_rows=200_000 if args.profile == "full" else 50_000,
            seed=args.seed + model_index,
            batch_size=args.batch_size,
        )

        model = build_model(model_name, args.seed)
        log(f"[{model_index}/{len(model_names)}] Training {model_name} on {len(X_train):,} rows")
        train_start = time.perf_counter()
        model = fit_model(model_name, model, X_train, y_train, X_val_small, y_val_small)
        train_seconds = time.perf_counter() - train_start

        model_path = save_model(model_name, model, models_dir)
        log(f"[{model_index}/{len(model_names)}] Evaluating {model_name}")
        split_metrics = {
            "val": evaluate_split(model, val_path, feature_columns, args.batch_size),
            "test": evaluate_split(model, test_path, feature_columns, args.batch_size),
            "ood_attack_holdout": evaluate_split(model, ood_path, feature_columns, args.batch_size),
        }

        metrics_detail[model_name] = {
            "model_path": model_path,
            "train_seconds": float(train_seconds),
            "train_rows": int(len(X_train)),
            "sampling": sampling_summary[model_name],
            "splits": split_metrics,
        }
        metrics_summary.append(
            {
                "model": model_name,
                "train_rows": int(len(X_train)),
                "train_seconds": float(train_seconds),
                "val_f1": split_metrics["val"]["f1"],
                "test_f1": split_metrics["test"]["f1"],
                "test_recall": split_metrics["test"]["recall"],
                "test_precision": split_metrics["test"]["precision"],
                "test_fpr": split_metrics["test"]["fpr"],
                "ood_recall": split_metrics["ood_attack_holdout"]["recall"],
            }
        )

    pd.DataFrame(metrics_summary).sort_values(by="test_f1", ascending=False).to_csv(
        reports_dir / "metrics_summary.csv",
        index=False,
    )
    write_json(reports_dir / "metrics_detail.json", metrics_detail)
    write_json(reports_dir / "sampling_summary.json", sampling_summary)


def main() -> None:
    args = parse_args()
    run_training(args)


if __name__ == "__main__":
    main()
