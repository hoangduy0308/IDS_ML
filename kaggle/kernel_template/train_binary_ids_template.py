from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import confusion_matrix
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MODEL_KEY = "%%MODEL_KEY%%"
MODEL_TITLE = "%%MODEL_TITLE%%"
DATASET_SLUG = "%%DATASET_SLUG%%"
SEED = 42
BATCH_SIZE = 131_072
TORCH_BATCH_SIZE = 32_768

LABEL_MAP = {"Benign": 0, "Attack": 1}
SPLITS = ["val", "test", "ood_attack_holdout"]
OUTPUT_DIR = Path("/kaggle/working") / f"{MODEL_KEY}_results"
DATASET_DIR = Path("/kaggle/input") / DATASET_SLUG

MODEL_CONFIG = {
    "logreg": {"epochs": 2, "training_mode": "streaming_full"},
    "random_forest": {"training_mode": "stream_sampled_in_memory", "train_attack_cap": 400_000},
    "hist_gb": {"training_mode": "stream_sampled_in_memory", "train_attack_cap": 700_000},
    "catboost": {
        "training_mode": "gpu_stream_sampled_in_memory",
        "train_attack_cap": 600_000,
        "val_attack_cap": 150_000,
    },
    "mlp": {"epochs": 3, "training_mode": "streaming_full"},
}
GPU_ENABLED_MODELS = {"catboost", "mlp"}
CURVE_TRAIN_ATTACK_CAP = 120_000
CURVE_VAL_ATTACK_CAP = 120_000
CURVE_BENIGN_CAP = 25_000
RANDOM_FOREST_STEPS = [25, 50, 75, 100, 125, 150]
HIST_GB_STEPS = [50, 100, 150, 200, 250, 300]


@dataclass
class ModelBundle:
    model: object
    scaler: StandardScaler | None
    backend: str
    extra: dict[str, Any]


def log(message: str) -> None:
    print(message, flush=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_dataset_file(*relative_candidates: str) -> Path:
    for candidate in relative_candidates:
        path = DATASET_DIR / candidate
        if path.exists():
            return path
    for candidate in relative_candidates:
        candidate_name = Path(candidate).name
        matches = sorted(DATASET_DIR.rglob(candidate_name))
        if matches:
            return matches[0]
    searched = ", ".join(str(DATASET_DIR / candidate) for candidate in relative_candidates)
    sample_entries = [str(path) for path in sorted(DATASET_DIR.rglob("*"))[:20]]
    raise FileNotFoundError(
        "Unable to locate dataset file. "
        f"Tried direct paths: {searched}. "
        f"Sample dataset entries: {sample_entries}"
    )


def load_feature_columns() -> list[str]:
    payload = read_json(resolve_dataset_file("feature_columns.json", "manifests/feature_columns.json"))
    return list(payload["feature_columns"])


def load_label_distribution() -> dict[str, dict[str, int]]:
    payload = read_json(resolve_dataset_file("cleaning_report.json", "manifests/cleaning_report.json"))
    return payload["label_distribution_by_split"]


def parquet_path(split_name: str) -> Path:
    return resolve_dataset_file(f"{split_name}.parquet", f"clean/{split_name}.parquet")


def iter_split_batches(split_name: str, feature_columns: list[str], batch_size: int) -> tuple[np.ndarray, np.ndarray]:
    parquet_file = pq.ParquetFile(parquet_path(split_name))
    columns = feature_columns + ["derived_label_binary"]
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        frame = batch.to_pandas()
        X = frame[feature_columns].astype(np.float32, copy=False).to_numpy(copy=False)
        y = frame["derived_label_binary"].map(LABEL_MAP).to_numpy(dtype=np.int8)
        yield X, y


def load_full_split(split_name: str, feature_columns: list[str]) -> tuple[np.ndarray, np.ndarray]:
    log(f"Loading {split_name} split into memory")
    table = pq.read_table(parquet_path(split_name), columns=feature_columns + ["derived_label_binary"])
    frame = table.to_pandas()
    X = frame[feature_columns].astype(np.float32, copy=False).to_numpy(copy=False)
    y = frame["derived_label_binary"].map(LABEL_MAP).to_numpy(dtype=np.int8)
    return X, y


def load_sampled_split(
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
    rng = np.random.default_rng(SEED + sum(ord(ch) for ch in split_name))

    attack_frames: list[np.ndarray] = []
    benign_frames: list[np.ndarray] = []

    for X_batch, y_batch in iter_split_batches(split_name, feature_columns, BATCH_SIZE):
        benign_mask = y_batch == 0
        if benign_mask.any():
            benign_idx = np.flatnonzero(benign_mask)
            if benign_keep_prob < 1.0:
                benign_idx = benign_idx[rng.random(len(benign_idx)) < benign_keep_prob]
            if benign_idx.size:
                benign_frames.append(X_batch[benign_idx])

        attack_mask = y_batch == 1
        if attack_mask.any():
            attack_idx = np.flatnonzero(attack_mask)
            if attack_keep_prob < 1.0:
                attack_idx = attack_idx[rng.random(len(attack_idx)) < attack_keep_prob]
            if attack_idx.size:
                attack_frames.append(X_batch[attack_idx])

    benign_array = (
        np.concatenate(benign_frames, axis=0) if benign_frames else np.empty((0, len(feature_columns)), dtype=np.float32)
    )
    attack_array = (
        np.concatenate(attack_frames, axis=0) if attack_frames else np.empty((0, len(feature_columns)), dtype=np.float32)
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


def build_curve_probe_sets(feature_columns: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    X_train_probe, y_train_probe, _ = load_sampled_split(
        "train",
        feature_columns,
        attack_cap=CURVE_TRAIN_ATTACK_CAP,
        benign_cap=CURVE_BENIGN_CAP,
        log_summary=False,
    )
    X_val_probe, y_val_probe, _ = load_sampled_split(
        "val",
        feature_columns,
        attack_cap=CURVE_VAL_ATTACK_CAP,
        benign_cap=CURVE_BENIGN_CAP,
        log_summary=False,
    )
    return X_train_probe, y_train_probe, X_val_probe, y_val_probe


def binary_f1_from_arrays(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return float((2 * precision * recall) / max(1e-12, precision + recall))


def append_curve_row(
    curve_rows: list[dict[str, float | int | str]],
    stage_type: str,
    stage_index: int,
    train_f1: float,
    val_f1: float,
    elapsed_seconds: float,
) -> None:
    curve_rows.append(
        {
            "stage_type": stage_type,
            "stage_index": int(stage_index),
            "train_f1": float(train_f1),
            "val_f1": float(val_f1),
            "elapsed_seconds": float(elapsed_seconds),
        }
    )


def fit_scaler(feature_columns: list[str]) -> StandardScaler:
    log("Fitting StandardScaler over full train split in streaming mode")
    scaler = StandardScaler()
    for X_batch, _ in iter_split_batches("train", feature_columns, BATCH_SIZE):
        scaler.partial_fit(X_batch)
    return scaler


def ensure_torch() -> Any:
    try:
        import torch
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "torch"])
        import torch
    return torch


def get_torch_runtime() -> dict[str, Any]:
    torch = ensure_torch()
    gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    device = torch.device("cuda:0" if gpu_count else "cpu")
    gpu_name = None
    gpu_capability = None
    uses_gpu = False

    if gpu_count > 0 and MODEL_KEY in GPU_ENABLED_MODELS:
        try:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_capability = torch.cuda.get_device_capability(0)
            if gpu_capability[0] >= 7:
                test_tensor = torch.zeros(1, device=device)
                _ = test_tensor.cpu()
                uses_gpu = True
            else:
                device = torch.device("cpu")
        except Exception as exc:
            log(f"Falling back to CPU for torch runtime due to GPU incompatibility: {exc}")
            device = torch.device("cpu")
            uses_gpu = False

    runtime = {
        "gpu_count": int(gpu_count),
        "device": str(device),
        "uses_gpu": uses_gpu,
        "gpu_name": gpu_name,
        "gpu_capability": gpu_capability,
    }
    log(f"Runtime context: {json.dumps(runtime)}")
    return {"torch": torch, **runtime}


def runtime_metadata(runtime: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in runtime.items() if key != "torch"}


def predict_sklearn_arrays(model: object, scaler: StandardScaler | None, X: np.ndarray) -> np.ndarray:
    if scaler is not None:
        X = scaler.transform(X)
    return np.asarray(model.predict(X), dtype=np.int8)


def predict_torch_arrays(
    model: object,
    runtime: dict[str, Any],
    scaler: StandardScaler | None,
    X: np.ndarray,
) -> np.ndarray:
    torch = runtime["torch"]
    if scaler is not None:
        X = scaler.transform(X)
    model.eval()
    preds: list[np.ndarray] = []
    with torch.no_grad():
        x_tensor = torch.from_numpy(X)
        for start in range(0, len(x_tensor), TORCH_BATCH_SIZE):
            end = start + TORCH_BATCH_SIZE
            x_mb = x_tensor[start:end].to(runtime["device"], dtype=torch.float32, non_blocking=True)
            with torch.cuda.amp.autocast(enabled=runtime["uses_gpu"]):
                logits = model(x_mb)
            preds.append(torch.argmax(logits, dim=1).detach().cpu().numpy().astype(np.int8, copy=False))
    return np.concatenate(preds) if preds else np.array([], dtype=np.int8)


def fit_streaming_logreg(feature_columns: list[str]) -> tuple[SGDClassifier, StandardScaler, list[dict[str, float | int | str]]]:
    label_distribution = load_label_distribution()["train"]
    benign_count = max(1, int(label_distribution["Benign"]))
    attack_count = max(1, int(label_distribution["Attack"]))
    total_count = benign_count + attack_count
    class_weight = {
        0: total_count / (2 * benign_count),
        1: total_count / (2 * attack_count),
    }
    scaler = fit_scaler(feature_columns)
    model = SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=1e-4,
        class_weight=class_weight,
        learning_rate="optimal",
        random_state=SEED,
    )
    X_train_probe, y_train_probe, X_val_probe, y_val_probe = build_curve_probe_sets(feature_columns)
    curve_rows: list[dict[str, float | int | str]] = []
    fit_start = time.perf_counter()
    classes = np.array([0, 1], dtype=np.int8)
    epochs = MODEL_CONFIG["logreg"]["epochs"]
    for epoch in range(epochs):
        log(f"Logistic regression epoch {epoch + 1}/{epochs}")
        for batch_index, (X_batch, y_batch) in enumerate(iter_split_batches("train", feature_columns, BATCH_SIZE), start=1):
            X_scaled = scaler.transform(X_batch)
            if epoch == 0 and batch_index == 1:
                model.partial_fit(X_scaled, y_batch, classes=classes)
            else:
                model.partial_fit(X_scaled, y_batch)
        train_f1 = binary_f1_from_arrays(y_train_probe, predict_sklearn_arrays(model, scaler, X_train_probe))
        val_f1 = binary_f1_from_arrays(y_val_probe, predict_sklearn_arrays(model, scaler, X_val_probe))
        append_curve_row(curve_rows, "epoch", epoch + 1, train_f1, val_f1, time.perf_counter() - fit_start)
    return model, scaler, curve_rows


def fit_torch_logreg(feature_columns: list[str]) -> ModelBundle:
    runtime = get_torch_runtime()
    torch = runtime["torch"]
    scaler = fit_scaler(feature_columns)
    label_distribution = load_label_distribution()["train"]
    class_weights = torch.tensor(
        [
            label_distribution["Attack"] / max(1, label_distribution["Benign"]),
            label_distribution["Benign"] / max(1, label_distribution["Attack"]),
        ],
        dtype=torch.float32,
        device=runtime["device"],
    )
    model = torch.nn.Linear(len(feature_columns), 2)
    if runtime["gpu_count"] > 1:
        model = torch.nn.DataParallel(model)
    model = model.to(runtime["device"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    scaler_amp = torch.cuda.amp.GradScaler(enabled=runtime["uses_gpu"])
    X_train_probe, y_train_probe, X_val_probe, y_val_probe = build_curve_probe_sets(feature_columns)
    curve_rows: list[dict[str, float | int | str]] = []
    fit_start = time.perf_counter()
    epochs = MODEL_CONFIG["logreg"]["epochs"]

    for epoch in range(epochs):
        log(f"GPU logistic regression epoch {epoch + 1}/{epochs}")
        for X_batch, y_batch in iter_split_batches("train", feature_columns, BATCH_SIZE):
            X_scaled = scaler.transform(X_batch)
            x_tensor = torch.from_numpy(X_scaled).to(runtime["device"], dtype=torch.float32, non_blocking=True)
            y_tensor = torch.from_numpy(y_batch.astype(np.int64, copy=False)).to(runtime["device"], non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=runtime["uses_gpu"]):
                logits = model(x_tensor)
                loss = criterion(logits, y_tensor)
            scaler_amp.scale(loss).backward()
            scaler_amp.step(optimizer)
            scaler_amp.update()
        train_f1 = binary_f1_from_arrays(y_train_probe, predict_torch_arrays(model, runtime, scaler, X_train_probe))
        val_f1 = binary_f1_from_arrays(y_val_probe, predict_torch_arrays(model, runtime, scaler, X_val_probe))
        append_curve_row(curve_rows, "epoch", epoch + 1, train_f1, val_f1, time.perf_counter() - fit_start)

    return ModelBundle(
        model=model,
        scaler=scaler,
        backend="torch",
        extra={
            "runtime": {key: value for key, value in runtime.items() if key != "torch"},
            "architecture": "linear",
            "feature_count": len(feature_columns),
            "training_curve": curve_rows,
        },
    )


def fit_streaming_mlp(feature_columns: list[str]) -> tuple[MLPClassifier, StandardScaler, list[dict[str, float | int | str]]]:
    scaler = fit_scaler(feature_columns)
    model = MLPClassifier(
        hidden_layer_sizes=(256, 128),
        activation="relu",
        solver="adam",
        batch_size=8192,
        learning_rate_init=1e-3,
        random_state=SEED,
    )
    X_train_probe, y_train_probe, X_val_probe, y_val_probe = build_curve_probe_sets(feature_columns)
    curve_rows: list[dict[str, float | int | str]] = []
    fit_start = time.perf_counter()
    classes = np.array([0, 1], dtype=np.int8)
    epochs = MODEL_CONFIG["mlp"]["epochs"]
    for epoch in range(epochs):
        log(f"MLP epoch {epoch + 1}/{epochs}")
        for batch_index, (X_batch, y_batch) in enumerate(iter_split_batches("train", feature_columns, BATCH_SIZE), start=1):
            X_scaled = scaler.transform(X_batch)
            if epoch == 0 and batch_index == 1:
                model.partial_fit(X_scaled, y_batch, classes=classes)
            else:
                model.partial_fit(X_scaled, y_batch)
        train_f1 = binary_f1_from_arrays(y_train_probe, predict_sklearn_arrays(model, scaler, X_train_probe))
        val_f1 = binary_f1_from_arrays(y_val_probe, predict_sklearn_arrays(model, scaler, X_val_probe))
        append_curve_row(curve_rows, "epoch", epoch + 1, train_f1, val_f1, time.perf_counter() - fit_start)
    return model, scaler, curve_rows


def fit_torch_mlp(feature_columns: list[str]) -> ModelBundle:
    runtime = get_torch_runtime()
    torch = runtime["torch"]
    scaler = fit_scaler(feature_columns)
    label_distribution = load_label_distribution()["train"]
    class_weights = torch.tensor(
        [
            label_distribution["Attack"] / max(1, label_distribution["Benign"]),
            label_distribution["Benign"] / max(1, label_distribution["Attack"]),
        ],
        dtype=torch.float32,
        device=runtime["device"],
    )
    model = torch.nn.Sequential(
        torch.nn.Linear(len(feature_columns), 512),
        torch.nn.ReLU(),
        torch.nn.Dropout(p=0.1),
        torch.nn.Linear(512, 128),
        torch.nn.ReLU(),
        torch.nn.Dropout(p=0.1),
        torch.nn.Linear(128, 2),
    )
    if runtime["gpu_count"] > 1:
        model = torch.nn.DataParallel(model)
    model = model.to(runtime["device"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    scaler_amp = torch.cuda.amp.GradScaler(enabled=runtime["uses_gpu"])
    X_train_probe, y_train_probe, X_val_probe, y_val_probe = build_curve_probe_sets(feature_columns)
    curve_rows: list[dict[str, float | int | str]] = []
    fit_start = time.perf_counter()
    epochs = MODEL_CONFIG["mlp"]["epochs"]

    for epoch in range(epochs):
        log(f"GPU MLP epoch {epoch + 1}/{epochs}")
        for X_batch, y_batch in iter_split_batches("train", feature_columns, BATCH_SIZE):
            X_scaled = scaler.transform(X_batch)
            x_tensor = torch.from_numpy(X_scaled)
            y_tensor = torch.from_numpy(y_batch.astype(np.int64, copy=False))
            for start in range(0, len(x_tensor), TORCH_BATCH_SIZE):
                end = start + TORCH_BATCH_SIZE
                x_mb = x_tensor[start:end].to(runtime["device"], dtype=torch.float32, non_blocking=True)
                y_mb = y_tensor[start:end].to(runtime["device"], non_blocking=True)
                optimizer.zero_grad(set_to_none=True)
                with torch.cuda.amp.autocast(enabled=runtime["uses_gpu"]):
                    logits = model(x_mb)
                    loss = criterion(logits, y_mb)
                scaler_amp.scale(loss).backward()
                scaler_amp.step(optimizer)
                scaler_amp.update()
        train_f1 = binary_f1_from_arrays(y_train_probe, predict_torch_arrays(model, runtime, scaler, X_train_probe))
        val_f1 = binary_f1_from_arrays(y_val_probe, predict_torch_arrays(model, runtime, scaler, X_val_probe))
        append_curve_row(curve_rows, "epoch", epoch + 1, train_f1, val_f1, time.perf_counter() - fit_start)

    return ModelBundle(
        model=model,
        scaler=scaler,
        backend="torch",
        extra={
            "runtime": {key: value for key, value in runtime.items() if key != "torch"},
            "architecture": "mlp_512_128",
            "feature_count": len(feature_columns),
            "training_curve": curve_rows,
        },
    )


def fit_random_forest(
    feature_columns: list[str],
) -> tuple[RandomForestClassifier, list[dict[str, float | int | str]]]:
    X_train, y_train, _ = load_sampled_split(
        "train",
        feature_columns,
        attack_cap=int(MODEL_CONFIG["random_forest"]["train_attack_cap"]),
    )
    _, _, X_val_probe, y_val_probe = build_curve_probe_sets(feature_columns)
    curve_rows: list[dict[str, float | int | str]] = []
    fit_start = time.perf_counter()
    model = RandomForestClassifier(
        n_estimators=RANDOM_FOREST_STEPS[0],
        max_depth=18,
        min_samples_leaf=2,
        max_samples=0.20,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=SEED,
        warm_start=True,
    )
    for step in RANDOM_FOREST_STEPS:
        model.set_params(n_estimators=step)
        model.fit(X_train, y_train)
        train_f1 = binary_f1_from_arrays(y_train, np.asarray(model.predict(X_train), dtype=np.int8))
        val_f1 = binary_f1_from_arrays(y_val_probe, np.asarray(model.predict(X_val_probe), dtype=np.int8))
        append_curve_row(curve_rows, "trees", step, train_f1, val_f1, time.perf_counter() - fit_start)
    return model, curve_rows


def fit_hist_gb(
    feature_columns: list[str],
) -> tuple[HistGradientBoostingClassifier, list[dict[str, float | int | str]]]:
    X_train, y_train, _ = load_sampled_split(
        "train",
        feature_columns,
        attack_cap=int(MODEL_CONFIG["hist_gb"]["train_attack_cap"]),
    )
    _, _, X_val_probe, y_val_probe = build_curve_probe_sets(feature_columns)
    curve_rows: list[dict[str, float | int | str]] = []
    fit_start = time.perf_counter()
    model = HistGradientBoostingClassifier(
        loss="log_loss",
        learning_rate=0.05,
        max_iter=HIST_GB_STEPS[0],
        max_leaf_nodes=31,
        early_stopping=False,
        random_state=SEED,
        warm_start=True,
    )
    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)
    for step in HIST_GB_STEPS:
        model.set_params(max_iter=step)
        model.fit(X_train, y_train, sample_weight=sample_weight)
        train_f1 = binary_f1_from_arrays(y_train, np.asarray(model.predict(X_train), dtype=np.int8))
        val_f1 = binary_f1_from_arrays(y_val_probe, np.asarray(model.predict(X_val_probe), dtype=np.int8))
        append_curve_row(curve_rows, "boost_iter", step, train_f1, val_f1, time.perf_counter() - fit_start)
    return model, curve_rows


def ensure_catboost() -> type:
    try:
        from catboost import CatBoostClassifier
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "catboost"])
        from catboost import CatBoostClassifier
    return CatBoostClassifier


def fit_catboost(
    feature_columns: list[str],
) -> tuple[object, list[dict[str, float | int | str]]]:
    CatBoostClassifier = ensure_catboost()
    runtime = get_torch_runtime()
    X_train, y_train, _ = load_sampled_split(
        "train",
        feature_columns,
        attack_cap=int(MODEL_CONFIG["catboost"]["train_attack_cap"]),
    )
    X_val, y_val, _ = load_sampled_split(
        "val",
        feature_columns,
        attack_cap=int(MODEL_CONFIG["catboost"]["val_attack_cap"]),
    )
    counts = np.bincount(y_train, minlength=2)
    max_count = max(1, int(counts.max()))
    class_weights = [float(max_count / max(1, int(count))) for count in counts]
    devices = ":".join(str(index) for index in range(runtime["gpu_count"])) if runtime["gpu_count"] > 1 else "0"
    model_kwargs = {
        "iterations": 400,
        "learning_rate": 0.05,
        "depth": 8,
        "loss_function": "Logloss",
        "eval_metric": "F1",
        "class_weights": class_weights,
        "allow_writing_files": False,
        "random_seed": SEED,
        "verbose": 100,
    }
    if runtime["uses_gpu"]:
        model_kwargs["task_type"] = "GPU"
        model_kwargs["devices"] = devices
    else:
        model_kwargs["task_type"] = "CPU"
    model = CatBoostClassifier(
        **model_kwargs,
    )
    model.fit(X_train, y_train, eval_set=(X_val, y_val), use_best_model=False)
    evals_result = model.get_evals_result()
    learn_metrics = evals_result.get("learn", {})
    validation_metrics = evals_result.get("validation", evals_result.get("validation_0", {}))
    learn_key = "F1" if "F1" in learn_metrics else next(iter(learn_metrics.keys()))
    val_key = "F1" if "F1" in validation_metrics else next(iter(validation_metrics.keys()))
    curve_rows = []
    for iteration, (learn_value, val_value) in enumerate(zip(learn_metrics[learn_key], validation_metrics[val_key]), start=1):
        append_curve_row(curve_rows, "iteration", iteration, float(learn_value), float(val_value), float(iteration))
    return model, curve_rows


def fit_model(feature_columns: list[str]) -> ModelBundle:
    if MODEL_KEY == "logreg":
        runtime = get_torch_runtime()
        if runtime["uses_gpu"]:
            return fit_torch_logreg(feature_columns)
        model, scaler, curve_rows = fit_streaming_logreg(feature_columns)
        return ModelBundle(
            model=model,
            scaler=scaler,
            backend="sklearn",
            extra={"runtime": runtime_metadata(runtime), "training_curve": curve_rows},
        )
    if MODEL_KEY == "mlp":
        runtime = get_torch_runtime()
        if runtime["uses_gpu"]:
            return fit_torch_mlp(feature_columns)
        model, scaler, curve_rows = fit_streaming_mlp(feature_columns)
        return ModelBundle(
            model=model,
            scaler=scaler,
            backend="sklearn",
            extra={"runtime": runtime_metadata(runtime), "training_curve": curve_rows},
        )
    if MODEL_KEY == "random_forest":
        model, curve_rows = fit_random_forest(feature_columns)
        return ModelBundle(
            model=model,
            scaler=None,
            backend="sklearn",
            extra={
                "runtime": {"device": "cpu", "gpu_count": 0, "uses_gpu": False},
                "training_curve": curve_rows,
            },
        )
    if MODEL_KEY == "hist_gb":
        model, curve_rows = fit_hist_gb(feature_columns)
        return ModelBundle(
            model=model,
            scaler=None,
            backend="sklearn",
            extra={
                "runtime": {"device": "cpu", "gpu_count": 0, "uses_gpu": False},
                "training_curve": curve_rows,
            },
        )
    if MODEL_KEY == "catboost":
        model, curve_rows = fit_catboost(feature_columns)
        return ModelBundle(
            model=model,
            scaler=None,
            backend="catboost",
            extra={"runtime": runtime_metadata(get_torch_runtime()), "training_curve": curve_rows},
        )
    raise ValueError(f"Unsupported MODEL_KEY: {MODEL_KEY}")


def predict_with_optional_scaler(
    bundle: ModelBundle,
    X_batch: np.ndarray,
) -> np.ndarray:
    if bundle.backend == "torch":
        runtime = bundle.extra["runtime"]
        torch = ensure_torch()
        model = bundle.model
        model.eval()
        if bundle.scaler is not None:
            X_batch = bundle.scaler.transform(X_batch)
        with torch.no_grad():
            x_tensor = torch.from_numpy(X_batch).to(runtime["device"], dtype=torch.float32, non_blocking=True)
            with torch.cuda.amp.autocast(enabled=runtime["uses_gpu"]):
                logits = model(x_tensor)
            return torch.argmax(logits, dim=1).detach().cpu().numpy().astype(np.int8, copy=False)
    if bundle.scaler is not None:
        X_batch = bundle.scaler.transform(X_batch)
    return np.asarray(bundle.model.predict(X_batch), dtype=np.int8)


def evaluate_split(
    split_name: str,
    feature_columns: list[str],
    bundle: ModelBundle,
) -> dict[str, float | int | dict[str, int]]:
    total_rows = 0
    y_true_all: list[np.ndarray] = []
    y_pred_all: list[np.ndarray] = []
    start = time.perf_counter()
    for X_batch, y_batch in iter_split_batches(split_name, feature_columns, BATCH_SIZE):
        y_pred = predict_with_optional_scaler(bundle, X_batch)
        total_rows += len(y_batch)
        y_true_all.append(y_batch)
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

    return {
        "rows": int(total_rows),
        "accuracy": float(accuracy),
        "balanced_accuracy": float(balanced_accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "fpr": float(fpr),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "inference_seconds": float(elapsed),
        "rows_per_second": float(total_rows / max(elapsed, 1e-9)),
    }


def save_training_curve_artifacts(curve_rows: list[dict[str, float | int | str]]) -> None:
    if not curve_rows:
        return
    curve_df = pd.DataFrame(curve_rows)
    curve_csv_path = OUTPUT_DIR / "training_curve.csv"
    curve_png_path = OUTPUT_DIR / "training_curve.png"
    curve_df.to_csv(curve_csv_path, index=False)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(curve_df["stage_index"], curve_df["train_f1"], marker="o", label="Train F1")
    ax.plot(curve_df["stage_index"], curve_df["val_f1"], marker="o", label="Validation F1")
    x_label = str(curve_df["stage_type"].iloc[0]).replace("_", " ").title()
    ax.set_title(f"{MODEL_TITLE} Learning Curve")
    ax.set_xlabel(x_label)
    ax.set_ylabel("F1")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(curve_png_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_artifacts(
    feature_columns: list[str],
    bundle: ModelBundle,
    metrics: dict,
    train_seconds: float,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if bundle.backend == "catboost":
        model_path = OUTPUT_DIR / f"{MODEL_KEY}.cbm"
        bundle.model.save_model(model_path)
    elif bundle.backend == "torch":
        torch = ensure_torch()
        model_path = OUTPUT_DIR / f"{MODEL_KEY}.pt"
        state_dict = bundle.model.module.state_dict() if hasattr(bundle.model, "module") else bundle.model.state_dict()
        torch.save(
            {
                "state_dict": state_dict,
                "feature_columns": feature_columns,
                "extra": bundle.extra,
            },
            model_path,
        )
    else:
        model_path = OUTPUT_DIR / f"{MODEL_KEY}.joblib"
        joblib.dump({"model": bundle.model, "scaler": bundle.scaler, "feature_columns": feature_columns}, model_path)

    metrics_path = OUTPUT_DIR / "metrics.json"
    summary_path = OUTPUT_DIR / "summary.csv"
    training_summary_path = OUTPUT_DIR / "training_summary.json"

    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    save_training_curve_artifacts(bundle.extra.get("training_curve", []))
    pd.DataFrame(
        [
            {
                "model": MODEL_KEY,
                "train_seconds": float(train_seconds),
                "val_f1": metrics["splits"]["val"]["f1"],
                "test_f1": metrics["splits"]["test"]["f1"],
                "test_recall": metrics["splits"]["test"]["recall"],
                "test_precision": metrics["splits"]["test"]["precision"],
                "test_fpr": metrics["splits"]["test"]["fpr"],
                "ood_recall": metrics["splits"]["ood_attack_holdout"]["recall"],
            }
        ]
    ).to_csv(summary_path, index=False)
    training_summary_path.write_text(
        json.dumps(
            {
                "model": MODEL_KEY,
                "model_title": MODEL_TITLE,
                "dataset_slug": DATASET_SLUG,
                "training_mode": MODEL_CONFIG[MODEL_KEY]["training_mode"],
                "train_seconds": float(train_seconds),
                "feature_count": len(feature_columns),
                "backend": bundle.backend,
                "runtime": bundle.extra["runtime"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> None:
    if not DATASET_DIR.exists():
        raise FileNotFoundError(f"Dataset directory not found: {DATASET_DIR}")
    feature_columns = load_feature_columns()
    train_start = time.perf_counter()
    bundle = fit_model(feature_columns)
    train_seconds = time.perf_counter() - train_start

    log("Evaluating on validation, test, and OOD holdout splits")
    split_metrics = {
        split_name: evaluate_split(split_name, feature_columns, bundle)
        for split_name in SPLITS
    }
    metrics = {
        "model": MODEL_KEY,
        "model_title": MODEL_TITLE,
        "dataset_slug": DATASET_SLUG,
        "splits": split_metrics,
    }
    save_artifacts(feature_columns, bundle, metrics, train_seconds)
    log(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
