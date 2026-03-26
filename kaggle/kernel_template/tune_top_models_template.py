from __future__ import annotations

import gc
import json
import math
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from catboost import CatBoostClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import confusion_matrix


MODEL_KEY = "%%MODEL_KEY%%"
MODEL_TITLE = "%%MODEL_TITLE%%"
EXPECTED_DATASET_SLUG = "%%DATASET_SLUG%%"
EXPECTED_DATASET_SUBDIR = "cic-iot-diad-2024-binary-ids"
BASE_INPUT_ROOT = Path("/kaggle/input")
OUTPUT_ROOT = Path("/kaggle/working") / f"{MODEL_KEY}_tuning_results"
PROFILE = "%%PROFILE%%"
BATCH_SIZE = int(%%BATCH_SIZE%%)
EVAL_MAX_ROWS = int(%%EVAL_MAX_ROWS%%)
OOD_MAX_ROWS = int(%%OOD_MAX_ROWS%%)
SEED = int(%%SEED%%)
TRIALS = int(%%TRIALS%%)
PROMOTE = int(%%PROMOTE%%)
CHECKPOINT_EVERY = int(%%CHECKPOINT_EVERY%%)
THRESHOLD_GRID_SIZE = 401
THRESHOLD_CAPS = [0.005, 0.01, 0.02]
LABEL_MAP = {"Benign": 0, "Attack": 1}


@dataclass(frozen=True)
class ModelSpec:
    name: str
    attack_ratio: int
    max_attack_rows: int


QUICK_MODE_OVERRIDES = {
    "random_forest": ModelSpec("random_forest", attack_ratio=3, max_attack_rows=150_000),
    "hist_gb": ModelSpec("hist_gb", attack_ratio=4, max_attack_rows=250_000),
    "catboost": ModelSpec("catboost", attack_ratio=4, max_attack_rows=300_000),
}

FULL_MODE_SPECS = {
    "random_forest": ModelSpec("random_forest", attack_ratio=6, max_attack_rows=600_000),
    "hist_gb": ModelSpec("hist_gb", attack_ratio=8, max_attack_rows=1_000_000),
    "catboost": ModelSpec("catboost", attack_ratio=10, max_attack_rows=1_500_000),
}


def detect_gpu_devices() -> tuple[list[str], list[str]]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name", "--format=csv,noheader"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [], []

    gpu_indices: list[str] = []
    gpu_names: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",", 1)]
        if not parts:
            continue
        gpu_indices.append(parts[0])
        gpu_names.append(parts[1] if len(parts) > 1 else "unknown")
    return gpu_indices, gpu_names


GPU_INDICES, GPU_NAMES = detect_gpu_devices()
CATBOOST_DEVICE_SPEC = ":".join(GPU_INDICES)


def runtime_context() -> dict[str, object]:
    return {
        "model_key": MODEL_KEY,
        "base_input_root": str(BASE_INPUT_ROOT),
        "expected_dataset_slug": EXPECTED_DATASET_SLUG,
        "expected_dataset_subdir": EXPECTED_DATASET_SUBDIR,
        "dataset_root": str(DATASET_ROOT),
        "output_root": str(OUTPUT_ROOT),
        "gpu_count": len(GPU_INDICES),
        "gpu_indices": GPU_INDICES,
        "gpu_names": GPU_NAMES,
        "catboost_device_spec": CATBOOST_DEVICE_SPEC,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "kaggle_kernel_run_type": os.environ.get("KAGGLE_KERNEL_RUN_TYPE"),
    }


def contains_dataset_markers(path: Path) -> bool:
    markers = [
        path / "feature_columns.json",
        path / "cleaning_report.json",
        path / "train.parquet",
    ]
    return any(marker.exists() for marker in markers)


def summarize_input_tree(base_root: Path, max_entries: int = 20) -> list[str]:
    if not base_root.exists():
        return [f"{base_root} <missing>"]
    entries: list[str] = []
    for path in sorted(base_root.rglob("*"), key=lambda item: (len(item.parts), str(item))):
        rel_path = path.relative_to(base_root)
        label = f"{rel_path}/" if path.is_dir() else str(rel_path)
        entries.append(label)
        if len(entries) >= max_entries:
            break
    return entries


def discover_dataset_root(base_root: Path, expected_slug: str) -> Path:
    if not base_root.exists():
        raise FileNotFoundError(f"Input root does not exist: {base_root}")

    expected_root = base_root / expected_slug
    preferred_nested_root = expected_root / EXPECTED_DATASET_SUBDIR
    candidate_roots: list[Path] = []
    if preferred_nested_root.exists():
        candidate_roots.append(preferred_nested_root)
    if expected_root.exists():
        candidate_roots.append(expected_root)
    candidate_roots.extend(sorted([path for path in base_root.rglob("*") if path.is_dir()], key=lambda path: (len(path.parts), str(path))))

    seen: set[str] = set()
    for root in candidate_roots:
        if str(root) in seen:
            continue
        seen.add(str(root))
        if contains_dataset_markers(root):
            return root
    tree_hint = summarize_input_tree(base_root)
    raise FileNotFoundError(
        "Unable to locate dataset root under "
        f"{base_root}. Attach the Kaggle dataset before running. "
        f"Expected slug hint: {expected_slug}. "
        f"Visible input entries: {tree_hint}"
    )


DATASET_ROOT = discover_dataset_root(BASE_INPUT_ROOT, EXPECTED_DATASET_SLUG)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def resolve_split_path(split_name: str) -> Path:
    return resolve_dataset_file(DATASET_ROOT, f"clean/{split_name}", split_name)


def load_feature_columns() -> list[str]:
    payload = read_json(resolve_dataset_file(DATASET_ROOT, "manifests/feature_columns.json", "feature_columns.json"))
    return list(payload["feature_columns"])


def load_label_counts() -> dict[str, dict[str, int]]:
    payload = read_json(resolve_dataset_file(DATASET_ROOT, "manifests/cleaning_report.json", "cleaning_report.json"))
    return payload["label_distribution_by_split"]


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
        x = frame[feature_columns].astype(np.float32)

        benign_mask = y == 0
        if benign_mask.any():
            benign_frames.append(x.loc[benign_mask].copy())
            selected_benign_rows += int(benign_mask.sum())

        attack_mask = y == 1
        if attack_mask.any():
            attack_idx = np.flatnonzero(attack_mask)
            if keep_attack_probability < 1.0:
                keep_mask = rng.random(len(attack_idx)) < keep_attack_probability
                attack_idx = attack_idx[keep_mask]
            if attack_idx.size:
                attack_frames.append(x.iloc[attack_idx].copy())
                selected_attack_rows += int(attack_idx.size)

    benign_df = pd.concat(benign_frames, ignore_index=True) if benign_frames else pd.DataFrame(columns=feature_columns)
    attack_df = pd.concat(attack_frames, ignore_index=True) if attack_frames else pd.DataFrame(columns=feature_columns)

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
    gc.collect()
    return train_df, train_y, {
        "selected_benign_rows": int(selected_benign_rows),
        "selected_attack_rows": int(selected_attack_rows),
        "final_train_rows": int(len(train_df)),
    }


def load_eval_subset(split_path: Path, feature_columns: list[str], max_rows: int, seed: int, batch_size: int) -> tuple[pd.DataFrame, np.ndarray]:
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
            "max_depth": None if rng.random() < 0.15 else int(choose_option(rng, [14, 18, 24])),
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
        catboost_kwargs = {
            "iterations": params["iterations"],
            "learning_rate": params["learning_rate"],
            "depth": params["depth"],
            "l2_leaf_reg": params["l2_leaf_reg"],
            "random_strength": params["random_strength"],
            "bagging_temperature": params["bagging_temperature"],
            "border_count": params["border_count"],
            "loss_function": "Logloss",
            "eval_metric": "F1",
            "random_seed": seed,
            "verbose": False,
        }
        if GPU_INDICES:
            catboost_kwargs["task_type"] = "GPU"
            catboost_kwargs["devices"] = CATBOOST_DEVICE_SPEC
        return CatBoostClassifier(
            **catboost_kwargs,
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


def fit_model(model_name: str, model: Any, x_train: pd.DataFrame, y_train: np.ndarray, x_val: pd.DataFrame, y_val: np.ndarray) -> Any:
    if model_name == "hist_gb":
        class_counts = np.bincount(y_train, minlength=2)
        weights = np.where(y_train == 0, max(class_counts) / max(1, class_counts[0]), max(class_counts) / max(1, class_counts[1]))
        model.fit(x_train, y_train, sample_weight=weights)
        return model
    if model_name == "catboost":
        if model.get_param("class_weights") is None:
            class_counts = np.bincount(y_train, minlength=2)
            benign_weight = max(class_counts) / max(1, class_counts[0])
            attack_weight = max(class_counts) / max(1, class_counts[1])
            model.set_params(class_weights=[float(benign_weight), float(attack_weight)])
        if len(x_val):
            model.fit(x_train, y_train, eval_set=(x_val, y_val), use_best_model=False)
        else:
            model.fit(x_train, y_train)
        return model
    model.fit(x_train, y_train)
    return model


def predict_scores(model: Any, frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict_proba(frame)[:, 1], dtype=np.float32)


def evaluate_at_threshold(y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> dict[str, float]:
    y_pred = (y_score >= threshold).astype(np.int8)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall) / max(1e-12, precision + recall)
    fpr = fp / max(1, fp + tn)
    return {
        "threshold": float(threshold),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "fpr": float(fpr),
    }


def build_threshold_sweep(y_true: np.ndarray, y_score: np.ndarray, thresholds: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame([evaluate_at_threshold(y_true, y_score, float(threshold)) for threshold in thresholds])


def select_threshold_under_fpr_cap(sweep_df: pd.DataFrame, fpr_cap: float) -> dict[str, float]:
    valid = sweep_df.loc[sweep_df["fpr"] <= fpr_cap]
    if valid.empty:
        return sweep_df.sort_values(by=["fpr", "threshold"], ascending=[True, True]).iloc[0].to_dict()
    return valid.sort_values(by=["f1", "recall", "threshold"], ascending=[False, False, True]).iloc[0].to_dict()


def sweep_metrics(y_true: np.ndarray, y_score: np.ndarray, threshold_grid: np.ndarray) -> dict[str, Any]:
    sweep_df = build_threshold_sweep(y_true=y_true, y_score=y_score, thresholds=threshold_grid)
    payload: dict[str, Any] = {"default_0.5": evaluate_at_threshold(y_true, y_score, threshold=0.5)}
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
        flat[f"val_threshold_at_tuned_{key}"] = metrics["val"][key]["threshold"]
        flat[f"val_f1_at_tuned_{key}"] = metrics["val"][key]["f1"]
        flat[f"val_recall_at_tuned_{key}"] = metrics["val"][key]["recall"]
        flat[f"val_fpr_at_tuned_{key}"] = metrics["val"][key]["fpr"]
        flat[f"ood_recall_at_tuned_{key}"] = metrics["ood"][key]["recall"]
    return flat


def passes_selection_gate(row: dict[str, Any] | pd.Series) -> bool:
    return float(row["val_fpr_at_default_0.5"]) <= 0.02


def rank_trials(trials_df: pd.DataFrame) -> pd.DataFrame:
    ranked = trials_df.copy()
    if ranked.empty:
        return ranked
    ranked["passes_gate"] = ranked.apply(passes_selection_gate, axis=1)
    return ranked.sort_values(
        by=[
            "passes_gate",
            "val_f1_at_tuned_cap_0.010",
            "val_fpr_at_default_0.5",
            "ood_recall_at_tuned_cap_0.020",
            "train_seconds",
        ],
        ascending=[False, False, True, False, True],
    ).reset_index(drop=True)


def search_space_payload() -> dict[str, Any]:
    return {
        "models": [MODEL_KEY],
        "profile": PROFILE,
        "trial_plan": {MODEL_KEY: TRIALS},
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


def selection_rule_markdown() -> str:
    return (
        "# Selection Rule\n\n"
        "- Hard gate: `val_fpr_at_default_0.5 <= 0.02`\n"
        "- Primary rank: `val_f1_at_tuned_cap_0.010`\n"
        "- Tie-break 1: lower `val_fpr_at_default_0.5`\n"
        "- Tie-break 2: higher `ood_recall_at_tuned_cap_0.020`\n"
        "- Tie-break 3: lower `train_seconds`\n"
    )


def persist_reports(reports_dir: Path, trials_out: list[dict[str, Any]], progress: dict[str, Any]) -> None:
    if trials_out:
        trials_df = pd.DataFrame(trials_out)
        ranked_df = rank_trials(trials_df)
        promoted_trials = ranked_df.head(PROMOTE)["trial_id"].tolist()
    else:
        trials_df = pd.DataFrame()
        ranked_df = pd.DataFrame()
        promoted_trials = []
    trials_df.to_csv(reports_dir / "trial_results.csv", index=False)
    ranked_df.to_csv(reports_dir / "trial_results_ranked.csv", index=False)
    write_jsonl(reports_dir / "trial_results.jsonl", trials_out)
    write_json(
        reports_dir / "best_configs.json",
        {
            "promotion_plan": {MODEL_KEY: PROMOTE},
            "promoted_trials": {MODEL_KEY: promoted_trials},
            "top_trials_by_model": {MODEL_KEY: ranked_df.head(PROMOTE).to_dict(orient="records")},
        },
    )
    write_json(reports_dir / "search_space.json", search_space_payload())
    write_json(reports_dir / "progress.json", progress)
    (reports_dir / "selection_rule.md").write_text(selection_rule_markdown(), encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    reports_dir = OUTPUT_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_ROOT / "runtime_context.json", runtime_context())
    print(json.dumps(runtime_context(), indent=2), flush=True)
    print(f"Starting tuning kernel: {MODEL_TITLE}", flush=True)

    feature_columns = load_feature_columns()
    split_counts = load_label_counts()
    train_path = resolve_split_path("train.parquet")
    val_path = resolve_split_path("val.parquet")
    ood_path = resolve_split_path("ood_attack_holdout.parquet")

    spec_table = QUICK_MODE_OVERRIDES if PROFILE == "quick" else FULL_MODE_SPECS
    spec = spec_table[MODEL_KEY]
    benign_rows, target_attack_rows = compute_sampling_target(spec, split_counts)
    threshold_grid = np.linspace(0.0, 1.0, num=THRESHOLD_GRID_SIZE)
    rng = np.random.default_rng(SEED + 1009)

    x_train, y_train, sample_info = sample_train_frame(
        train_path=train_path,
        feature_columns=feature_columns,
        benign_rows=benign_rows,
        target_attack_rows=target_attack_rows,
        seed=SEED + 101,
        batch_size=BATCH_SIZE,
    )
    x_val_probe, y_val_probe = load_eval_subset(
        split_path=val_path,
        feature_columns=feature_columns,
        max_rows=EVAL_MAX_ROWS,
        seed=SEED + 103,
        batch_size=BATCH_SIZE,
    )
    x_ood_probe, y_ood_probe = load_eval_subset(
        split_path=ood_path,
        feature_columns=feature_columns,
        max_rows=OOD_MAX_ROWS,
        seed=SEED + 107,
        batch_size=BATCH_SIZE,
    )

    trials_out: list[dict[str, Any]] = []
    progress = {
        "profile": PROFILE,
        "models": [MODEL_KEY],
        "trial_plan": {MODEL_KEY: TRIALS},
        "completed_trials": 0,
        "total_trials": TRIALS,
        "last_completed_trial_id": None,
        "status": "running",
    }
    persist_reports(reports_dir, trials_out, progress)

    for trial_number in range(1, TRIALS + 1):
        params = sample_hyperparameters(MODEL_KEY, rng)
        model = build_tuned_model(MODEL_KEY, params, seed=SEED + trial_number)
        fit_params = params.copy()
        if MODEL_KEY == "catboost":
            attack_count = int((y_train == 1).sum())
            benign_count = int((y_train == 0).sum())
            baseline_attack_weight = max(attack_count, benign_count) / max(1, attack_count)
            benign_weight = max(attack_count, benign_count) / max(1, benign_count)
            attack_weight = baseline_attack_weight * params["attack_weight_multiplier"]
            model.set_params(class_weights=[float(benign_weight), float(attack_weight)])
            fit_params["class_weights"] = [float(benign_weight), float(attack_weight)]

        start = time.perf_counter()
        model = fit_model(MODEL_KEY, model, x_train, y_train, x_val_probe, y_val_probe)
        train_seconds = float(time.perf_counter() - start)
        val_scores = predict_scores(model, x_val_probe)
        ood_scores = predict_scores(model, x_ood_probe)
        metrics = {
            "val": sweep_metrics(y_val_probe, val_scores, threshold_grid),
            "ood": sweep_metrics(y_ood_probe, ood_scores, threshold_grid),
        }
        record = {
            "trial_id": f"{MODEL_KEY}-trial-{trial_number:03d}",
            "model_name": MODEL_KEY,
            "train_rows": int(len(x_train)),
            "train_seconds": train_seconds,
            "hyperparameters": fit_params,
            **flatten_trial_metrics(metrics),
            "sample_info": sample_info,
        }
        trials_out.append(record)
        progress["completed_trials"] = len(trials_out)
        progress["last_completed_trial_id"] = record["trial_id"]
        progress["current_model"] = MODEL_KEY
        progress["current_trial_number"] = trial_number
        if CHECKPOINT_EVERY > 0 and len(trials_out) % CHECKPOINT_EVERY == 0:
            persist_reports(reports_dir, trials_out, progress)
        del model, val_scores, ood_scores
        gc.collect()

    progress["status"] = "completed"
    persist_reports(reports_dir, trials_out, progress)
    print(f"Completed tuning kernel: {MODEL_TITLE}", flush=True)


if __name__ == "__main__":
    main()
