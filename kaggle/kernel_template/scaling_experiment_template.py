from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.utils.class_weight import compute_sample_weight


RUN_KEY = "%%RUN_KEY%%"
MODEL_KEY = "%%MODEL_KEY%%"
MODEL_TITLE = "%%MODEL_TITLE%%"
EXPECTED_DATASET_SLUG = "%%DATASET_SLUG%%"
EXPECTED_DATASET_SUBDIR = "cic-iot-diad-2024-binary-ids"
BASE_INPUT_ROOT = Path("/kaggle/input")
OUTPUT_ROOT = Path("/kaggle/working") / f"{RUN_KEY}_results"
SEED = int(%%SEED%%)
BATCH_SIZE = int(%%BATCH_SIZE%%)
TRAIN_TARGET_ROWS = %%TRAIN_TARGET_ROWS%%
FIT_VAL_ATTACK_CAP = %%FIT_VAL_ATTACK_CAP%%
FIT_VAL_BENIGN_CAP = %%FIT_VAL_BENIGN_CAP%%
MODEL_PARAMS = json.loads(r'''%%MODEL_PARAMS_JSON%%''')

LABEL_MAP = {"Benign": 0, "Attack": 1}
SPLITS = ["val", "test", "ood_attack_holdout"]


def log(message: str) -> None:
    print(message, flush=True)


def detect_gpu_devices() -> tuple[list[str], list[str]]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [], []
    indices: list[str] = []
    names: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",", maxsplit=1)]
        if not parts:
            continue
        indices.append(parts[0])
        names.append(parts[1] if len(parts) > 1 else "Unknown GPU")
    return indices, names


GPU_INDICES, GPU_NAMES = detect_gpu_devices()
CATBOOST_DEVICE_SPEC = ":".join(GPU_INDICES)


def runtime_context() -> dict[str, object]:
    return {
        "run_key": RUN_KEY,
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
        "train_target_rows": TRAIN_TARGET_ROWS,
        "fit_val_attack_cap": FIT_VAL_ATTACK_CAP,
        "fit_val_benign_cap": FIT_VAL_BENIGN_CAP,
    }


def contains_dataset_markers(path: Path) -> bool:
    marker_names = {"train.parquet", "val.parquet", "test.parquet", "feature_columns.json", "cleaning_report.json"}
    try:
        child_names = {child.name for child in path.iterdir()}
    except OSError:
        return False
    return bool(marker_names & child_names)


def summarize_input_tree(base_root: Path, max_entries: int = 20) -> list[str]:
    if not base_root.exists():
        return []
    entries = sorted(base_root.rglob("*"))
    return [str(path) for path in entries[:max_entries]]


def discover_dataset_root(base_root: Path, expected_slug: str) -> Path:
    expected_root = base_root / expected_slug
    candidate_roots: list[Path] = []
    preferred_nested_root = expected_root / EXPECTED_DATASET_SUBDIR
    if preferred_nested_root.exists():
        candidate_roots.append(preferred_nested_root)
    if expected_root.exists():
        candidate_roots.append(expected_root)
    datasets_root = base_root / "datasets"
    if datasets_root.exists():
        candidate_roots.extend(sorted(datasets_root.rglob(expected_slug)))
        candidate_roots.extend(sorted(datasets_root.rglob(EXPECTED_DATASET_SUBDIR)))
    for root in candidate_roots:
        if root.is_dir() and contains_dataset_markers(root):
            return root
    if base_root.exists():
        for child in sorted(base_root.rglob("*")):
            if child.is_dir() and contains_dataset_markers(child):
                return child
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


def resolve_dataset_file(*candidates: str) -> Path:
    searched = [str(DATASET_ROOT / candidate) for candidate in candidates]
    for candidate in candidates:
        path = DATASET_ROOT / candidate
        if path.exists():
            return path
    candidate_names = {Path(candidate).name for candidate in candidates}
    recursive_hits = [path for path in DATASET_ROOT.rglob("*") if path.is_file() and path.name in candidate_names]
    if recursive_hits:
        recursive_hits.sort(key=lambda path: (len(path.parts), str(path)))
        return recursive_hits[0]
    raise FileNotFoundError(f"Unable to locate dataset file. Tried: {searched}")


def parquet_path(split_name: str) -> Path:
    return resolve_dataset_file(f"{split_name}.parquet", f"clean/{split_name}.parquet")


def load_feature_columns() -> list[str]:
    payload = read_json(resolve_dataset_file("feature_columns.json", "manifests/feature_columns.json"))
    return list(payload["feature_columns"])


def load_label_distribution() -> dict[str, dict[str, int]]:
    payload = read_json(resolve_dataset_file("cleaning_report.json", "manifests/cleaning_report.json"))
    return payload["label_distribution_by_split"]


def iter_split_batches(split_name: str, feature_columns: list[str], batch_size: int):
    parquet_file = pq.ParquetFile(parquet_path(split_name))
    columns = feature_columns + ["derived_label_binary"]
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        frame = batch.to_pandas()
        X = frame[feature_columns].astype(np.float32, copy=False).to_numpy(copy=False)
        y = frame["derived_label_binary"].map(LABEL_MAP).to_numpy(dtype=np.int8)
        yield X, y


def compute_train_caps() -> tuple[int | None, int | None]:
    distribution = load_label_distribution()["train"]
    total_benign = int(distribution.get("Benign", 0))
    if TRAIN_TARGET_ROWS is None:
        return None, None
    if TRAIN_TARGET_ROWS <= total_benign:
        return 0, TRAIN_TARGET_ROWS
    attack_cap = TRAIN_TARGET_ROWS - total_benign
    return attack_cap, None


def sample_split(
    split_name: str,
    feature_columns: list[str],
    attack_cap: int | None = None,
    benign_cap: int | None = None,
    log_summary: bool = True,
) -> tuple[np.ndarray, np.ndarray, dict[str, int | float]]:
    label_distribution = load_label_distribution()[split_name]
    total_attack = int(label_distribution.get("Attack", 0))
    total_benign = int(label_distribution.get("Benign", 0))
    attack_keep_prob = 1.0 if attack_cap is None else min(1.0, attack_cap / max(1, total_attack))
    benign_keep_prob = 1.0 if benign_cap is None else min(1.0, benign_cap / max(1, total_benign))
    rng = np.random.default_rng(SEED + sum(ord(ch) for ch in split_name) + len(RUN_KEY))

    attack_parts: list[np.ndarray] = []
    benign_parts: list[np.ndarray] = []
    for X_batch, y_batch in iter_split_batches(split_name, feature_columns, BATCH_SIZE):
        benign_mask = y_batch == 0
        if benign_mask.any():
            benign_idx = np.flatnonzero(benign_mask)
            if benign_keep_prob < 1.0:
                benign_idx = benign_idx[rng.random(len(benign_idx)) < benign_keep_prob]
            if benign_idx.size:
                benign_parts.append(X_batch[benign_idx])

        attack_mask = y_batch == 1
        if attack_mask.any():
            attack_idx = np.flatnonzero(attack_mask)
            if attack_keep_prob < 1.0:
                attack_idx = attack_idx[rng.random(len(attack_idx)) < attack_keep_prob]
            if attack_idx.size:
                attack_parts.append(X_batch[attack_idx])

    benign_array = (
        np.concatenate(benign_parts, axis=0) if benign_parts else np.empty((0, len(feature_columns)), dtype=np.float32)
    )
    attack_array = (
        np.concatenate(attack_parts, axis=0) if attack_parts else np.empty((0, len(feature_columns)), dtype=np.float32)
    )

    if benign_cap is not None and len(benign_array) > benign_cap:
        benign_array = benign_array[rng.choice(len(benign_array), size=benign_cap, replace=False)]
    if attack_cap is not None and len(attack_array) > attack_cap:
        attack_array = attack_array[rng.choice(len(attack_array), size=attack_cap, replace=False)]

    X = np.concatenate([benign_array, attack_array], axis=0)
    y = np.concatenate(
        [
            np.zeros(len(benign_array), dtype=np.int8),
            np.ones(len(attack_array), dtype=np.int8),
        ]
    )
    if len(y):
        order = rng.permutation(len(y))
        X = X[order]
        y = y[order]

    sampling_info = {
        "total_attack_rows": total_attack,
        "total_benign_rows": total_benign,
        "sampled_attack_rows": int(len(attack_array)),
        "sampled_benign_rows": int(len(benign_array)),
        "attack_keep_prob": float(attack_keep_prob),
        "benign_keep_prob": float(benign_keep_prob),
    }
    if log_summary:
        log(f"{split_name} sampled summary: {json.dumps(sampling_info)}")
    return X, y, sampling_info


def ensure_catboost() -> type:
    try:
        from catboost import CatBoostClassifier
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "catboost"])
        from catboost import CatBoostClassifier
    return CatBoostClassifier


def build_model(y_train: np.ndarray) -> object:
    if MODEL_KEY == "catboost":
        CatBoostClassifier = ensure_catboost()
        model_kwargs = dict(MODEL_PARAMS)
        counts = np.bincount(y_train, minlength=2)
        max_count = max(1, int(counts.max()))
        benign_weight = float(max_count / max(1, int(counts[0])))
        attack_weight = float(max_count / max(1, int(counts[1])))
        if "attack_weight_multiplier" in model_kwargs:
            attack_weight *= float(model_kwargs.pop("attack_weight_multiplier"))
        model_kwargs["class_weights"] = [benign_weight, attack_weight]
        model_kwargs["loss_function"] = "Logloss"
        model_kwargs["eval_metric"] = "F1"
        model_kwargs["allow_writing_files"] = False
        model_kwargs["random_seed"] = SEED
        model_kwargs["verbose"] = 100
        if GPU_INDICES:
            model_kwargs["task_type"] = "GPU"
            model_kwargs["devices"] = CATBOOST_DEVICE_SPEC
        else:
            model_kwargs["task_type"] = "CPU"
        return CatBoostClassifier(**model_kwargs)

    if MODEL_KEY == "hist_gb":
        return HistGradientBoostingClassifier(
            loss="log_loss",
            learning_rate=float(MODEL_PARAMS["learning_rate"]),
            max_iter=int(MODEL_PARAMS["max_iter"]),
            max_leaf_nodes=int(MODEL_PARAMS["max_leaf_nodes"]),
            min_samples_leaf=int(MODEL_PARAMS["min_samples_leaf"]),
            l2_regularization=float(MODEL_PARAMS["l2_regularization"]),
            max_bins=int(MODEL_PARAMS["max_bins"]),
            early_stopping=False,
            random_state=SEED,
        )

    if MODEL_KEY == "random_forest":
        return RandomForestClassifier(
            n_estimators=int(MODEL_PARAMS["n_estimators"]),
            max_depth=MODEL_PARAMS["max_depth"],
            min_samples_leaf=int(MODEL_PARAMS["min_samples_leaf"]),
            min_samples_split=int(MODEL_PARAMS["min_samples_split"]),
            max_features=MODEL_PARAMS["max_features"],
            max_samples=MODEL_PARAMS["max_samples"],
            class_weight="balanced_subsample",
            n_jobs=2,
            random_state=SEED,
        )

    raise ValueError(f"Unsupported MODEL_KEY: {MODEL_KEY}")


def fit_model(feature_columns: list[str]) -> tuple[object, dict[str, Any], str]:
    train_attack_cap, train_benign_cap = compute_train_caps()
    X_train, y_train, train_sampling = sample_split(
        "train",
        feature_columns,
        attack_cap=train_attack_cap,
        benign_cap=train_benign_cap,
    )
    model = build_model(y_train)
    fit_context = {
        "train_sampling": train_sampling,
        "train_target_rows": TRAIN_TARGET_ROWS,
        "resolved_train_attack_cap": train_attack_cap,
        "resolved_train_benign_cap": train_benign_cap,
    }

    if MODEL_KEY == "catboost":
        X_val_fit, y_val_fit, fit_val_sampling = sample_split(
            "val",
            feature_columns,
            attack_cap=FIT_VAL_ATTACK_CAP,
            benign_cap=FIT_VAL_BENIGN_CAP,
        )
        fit_context["fit_val_sampling"] = fit_val_sampling
        model.fit(X_train, y_train, eval_set=(X_val_fit, y_val_fit), use_best_model=False)
        backend = "catboost"
    elif MODEL_KEY == "hist_gb":
        sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)
        model.fit(X_train, y_train, sample_weight=sample_weight)
        backend = "sklearn"
    else:
        model.fit(X_train, y_train)
        backend = "sklearn"

    fit_context["train_rows"] = int(len(y_train))
    return model, fit_context, backend


def predict_scores(model: object, X: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return np.asarray(model.predict_proba(X))[:, 1]
    raise ValueError("Model does not expose predict_proba")


def evaluate_split(split_name: str, feature_columns: list[str], model: object) -> dict[str, Any]:
    total_rows = 0
    y_true_all: list[np.ndarray] = []
    y_pred_all: list[np.ndarray] = []
    y_score_all: list[np.ndarray] = []
    start = time.perf_counter()
    for X_batch, y_batch in iter_split_batches(split_name, feature_columns, BATCH_SIZE):
        y_score = predict_scores(model, X_batch)
        y_pred = (y_score >= 0.5).astype(np.int8)
        total_rows += len(y_batch)
        y_true_all.append(y_batch)
        y_pred_all.append(y_pred)
        y_score_all.append(y_score)
    elapsed = time.perf_counter() - start

    y_true = np.concatenate(y_true_all)
    y_pred = np.concatenate(y_pred_all)
    y_score = np.concatenate(y_score_all)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    accuracy = (tp + tn) / max(1, total_rows)
    f1 = (2 * precision * recall) / max(1e-12, precision + recall)
    fpr = fp / max(1, fp + tn)

    return {
        "rows": int(total_rows),
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "specificity": float(specificity),
        "f1": float(f1),
        "fpr": float(fpr),
        "mean_score": float(np.mean(y_score)),
        "inference_seconds": float(elapsed),
        "rows_per_second": float(total_rows / max(elapsed, 1e-9)),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def save_artifacts(
    feature_columns: list[str],
    model: object,
    backend: str,
    fit_context: dict[str, Any],
    metrics: dict[str, Any],
    train_seconds: float,
) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    reports_dir = OUTPUT_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if backend == "catboost":
        model_path = OUTPUT_ROOT / f"{RUN_KEY}.cbm"
        model.save_model(model_path)
    else:
        model_path = OUTPUT_ROOT / f"{RUN_KEY}.joblib"
        joblib.dump({"model": model, "feature_columns": feature_columns}, model_path)

    write_json(OUTPUT_ROOT / "runtime_context.json", runtime_context())
    write_json(
        OUTPUT_ROOT / "scaling_config.json",
        {
            "run_key": RUN_KEY,
            "model_key": MODEL_KEY,
            "model_title": MODEL_TITLE,
            "dataset_slug": EXPECTED_DATASET_SLUG,
            "train_target_rows": TRAIN_TARGET_ROWS,
            "fit_val_attack_cap": FIT_VAL_ATTACK_CAP,
            "fit_val_benign_cap": FIT_VAL_BENIGN_CAP,
            "model_params": MODEL_PARAMS,
        },
    )
    write_json(reports_dir / "metrics.json", metrics)
    write_json(
        reports_dir / "training_summary.json",
        {
            "run_key": RUN_KEY,
            "model_key": MODEL_KEY,
            "model_title": MODEL_TITLE,
            "dataset_slug": EXPECTED_DATASET_SLUG,
            "backend": backend,
            "train_seconds": float(train_seconds),
            "feature_count": len(feature_columns),
            "train_rows": fit_context["train_rows"],
            "fit_context": fit_context,
            "runtime": runtime_context(),
        },
    )
    pd.DataFrame(
        [
            {
                "run_key": RUN_KEY,
                "model": MODEL_KEY,
                "train_target_rows": TRAIN_TARGET_ROWS,
                "train_rows": fit_context["train_rows"],
                "train_seconds": float(train_seconds),
                "val_f1": metrics["splits"]["val"]["f1"],
                "test_f1": metrics["splits"]["test"]["f1"],
                "test_recall": metrics["splits"]["test"]["recall"],
                "test_precision": metrics["splits"]["test"]["precision"],
                "test_fpr": metrics["splits"]["test"]["fpr"],
                "ood_recall": metrics["splits"]["ood_attack_holdout"]["recall"],
            }
        ]
    ).to_csv(reports_dir / "summary.csv", index=False)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_ROOT / "runtime_context.json", runtime_context())
    print(json.dumps(runtime_context(), indent=2, ensure_ascii=False))

    feature_columns = load_feature_columns()
    log(f"Starting scaling experiment: {MODEL_TITLE}")
    train_start = time.perf_counter()
    model, fit_context, backend = fit_model(feature_columns)
    train_seconds = time.perf_counter() - train_start

    log("Evaluating on validation, test, and OOD holdout splits")
    split_metrics = {split_name: evaluate_split(split_name, feature_columns, model) for split_name in SPLITS}
    metrics = {
        "run_key": RUN_KEY,
        "model": MODEL_KEY,
        "model_title": MODEL_TITLE,
        "dataset_slug": EXPECTED_DATASET_SLUG,
        "splits": split_metrics,
    }
    save_artifacts(feature_columns, model, backend, fit_context, metrics, train_seconds)
    log(f"Completed scaling experiment: {MODEL_TITLE}")
    log(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
