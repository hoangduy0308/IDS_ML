from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from catboost import CatBoostClassifier
from sklearn.metrics import classification_report, confusion_matrix


DEFAULT_DATASET_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_family_views")
DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_family_views\family_classifier")
DEFAULT_VIEW_NAME = "attack_only"
DEFAULT_LABEL_COLUMN = "derived_label_family"
DEFAULT_BATCH_SIZE = 100_000
DEFAULT_MAX_TRAIN_ROWS = 1_000_000
DEFAULT_ITERATIONS = 300
DEFAULT_LEARNING_RATE = 0.06
DEFAULT_DEPTH = 8
DEFAULT_L2_LEAF_REG = 3.0
DEFAULT_CLASS_WEIGHT_EXPONENT = 1.0
DEFAULT_TASK_TYPE = "CPU"
DEFAULT_DEVICES = ""


@dataclass(frozen=True)
class SplitEvaluation:
    rows: int
    overall: dict[str, Any]
    per_family: dict[str, dict[str, Any]]
    confusion_matrix: dict[str, Any]
    top1_confidence: dict[str, Any]
    runner_up_margin: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the stage-2 family classifier on the derived CIC IoT-DIAD family view."
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--view-name", type=str, default=DEFAULT_VIEW_NAME)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-train-rows", type=int, default=DEFAULT_MAX_TRAIN_ROWS)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--l2-leaf-reg", type=float, default=DEFAULT_L2_LEAF_REG)
    parser.add_argument("--class-weight-exponent", type=float, default=DEFAULT_CLASS_WEIGHT_EXPONENT)
    parser.add_argument("--thread-count", type=int, default=1)
    parser.add_argument("--task-type", choices=("CPU", "GPU"), default=DEFAULT_TASK_TYPE)
    parser.add_argument("--devices", type=str, default=DEFAULT_DEVICES)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalize_dataset_candidate(candidate: str | Path) -> Path:
    candidate_path = Path(candidate)
    if candidate_path.is_absolute():
        raise ValueError(f"Dataset index path must be relative to dataset_root, got absolute path: {candidate}")

    parts = [part for part in candidate_path.parts if part not in ("", ".")]
    if not parts:
        raise ValueError("Dataset index path must not be empty.")
    if any(part == ".." for part in parts):
        raise ValueError(f"Dataset index path must not escape dataset_root: {candidate}")
    return Path(*parts)


def resolve_dataset_file(dataset_root: Path, *candidates: str) -> Path:
    dataset_root = dataset_root.resolve()
    normalized_candidates = [_normalize_dataset_candidate(candidate) for candidate in candidates]
    searched = [str(dataset_root / candidate) for candidate in normalized_candidates]
    for candidate in normalized_candidates:
        path = (dataset_root / candidate).resolve()
        if not _is_relative_to(path, dataset_root):
            raise ValueError(f"Resolved dataset path escapes dataset_root: {candidate}")
        if path.exists():
            return path
    candidate_names = {candidate.name for candidate in normalized_candidates}
    recursive_hits = [
        path.resolve()
        for path in dataset_root.rglob("*")
        if path.is_file() and path.name in candidate_names and _is_relative_to(path.resolve(), dataset_root)
    ]
    if recursive_hits:
        recursive_hits.sort(key=lambda path: (len(path.parts), str(path)))
        return recursive_hits[0]
    raise FileNotFoundError(f"Unable to locate dataset file. Tried: {searched}")


def load_family_view_index(dataset_root: Path) -> dict[str, Any]:
    return read_json(resolve_dataset_file(dataset_root, "manifests/family_view_index.json", "family_view_index.json"))


def load_feature_columns(dataset_root: Path, index: dict[str, Any]) -> list[str]:
    feature_schema_path = index.get("feature_schema_path", "manifests/feature_columns.json")
    payload = read_json(resolve_dataset_file(dataset_root, str(feature_schema_path), "manifests/feature_columns.json"))
    return list(payload["feature_columns"])


def resolve_view_split_path(dataset_root: Path, index: dict[str, Any], view_name: str, split_name: str) -> Path:
    split_path = Path(index["views"][view_name]["split_paths"][split_name])
    return resolve_dataset_file(dataset_root, str(split_path))


def ensure_output_dirs(output_root: Path) -> tuple[Path, Path]:
    models_dir = output_root / "models"
    reports_dir = output_root / "reports"
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    return models_dir, reports_dir


def numeric_summary(values: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return {"count": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "max": 0.0}
    return {
        "count": int(arr.size),
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=0)),
        "min": float(arr.min()),
        "p10": float(np.percentile(arr, 10)),
        "p25": float(np.percentile(arr, 25)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "max": float(arr.max()),
    }


def build_label_index(label_space: list[str]) -> dict[str, int]:
    return {label: index for index, label in enumerate(label_space)}


def sample_train_split(
    split_path: Path,
    feature_columns: list[str],
    label_index: dict[str, int],
    *,
    seed: int,
    max_rows: int,
    batch_size: int,
) -> tuple[pd.DataFrame, np.ndarray, dict[str, Any]]:
    parquet_file = pq.ParquetFile(split_path)
    total_rows = int(parquet_file.metadata.num_rows)
    keep_probability = min(1.0, max_rows / max(1, total_rows))
    rng = np.random.default_rng(seed)

    frames: list[pd.DataFrame] = []
    labels: list[np.ndarray] = []
    mandatory_feature_rows: dict[int, pd.DataFrame] = {}
    source_label_presence: Counter[int] = Counter()
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=feature_columns + [DEFAULT_LABEL_COLUMN]):
        frame = batch.to_pandas()
        mapped_labels = frame[DEFAULT_LABEL_COLUMN].astype(str).map(label_index)
        valid_mask = mapped_labels.notna()
        if not valid_mask.any():
            continue

        valid_indices = frame.index[valid_mask]
        valid_labels = mapped_labels.loc[valid_indices].astype(np.int16)
        source_label_presence.update(int(value) for value in valid_labels.tolist())

        mandatory_indices: list[int] = []
        for row_index, label_value in zip(valid_indices.tolist(), valid_labels.tolist()):
            label_key = int(label_value)
            if label_key not in mandatory_feature_rows:
                mandatory_feature_rows[label_key] = frame.loc[[row_index], feature_columns].astype(np.float32).copy()
                mandatory_indices.append(row_index)

        sampled_frame = frame.loc[valid_indices].drop(index=mandatory_indices, errors="ignore")
        sampled_labels = mapped_labels.loc[sampled_frame.index]
        if keep_probability < 1.0 and not sampled_frame.empty:
            sampled_frame = sampled_frame.loc[rng.random(len(sampled_frame)) < keep_probability]
            sampled_labels = sampled_labels.loc[sampled_frame.index]
        if sampled_frame.empty:
            continue

        frames.append(sampled_frame[feature_columns].astype(np.float32).copy())
        labels.append(sampled_labels.to_numpy(dtype=np.int8))

    mandatory_items = sorted(mandatory_feature_rows.items())
    mandatory_frames = [frame for _, frame in mandatory_items]
    mandatory_labels = np.asarray([label for label, _ in mandatory_items], dtype=np.int8)

    if not frames and not mandatory_frames:
        return pd.DataFrame(columns=feature_columns), np.array([], dtype=np.int8), {
            "source_rows": total_rows,
            "sampled_rows": 0,
            "sample_rate": 0.0,
            "label_counts": {},
        }

    sampled_frames = mandatory_frames + frames
    sampled_label_parts = ([mandatory_labels] if mandatory_labels.size else []) + labels
    X = pd.concat(sampled_frames, ignore_index=True)
    y = np.concatenate(sampled_label_parts)
    if len(X) > max_rows:
        mandatory_count = int(mandatory_labels.size)
        if mandatory_count >= max_rows:
            X = X.iloc[:max_rows].reset_index(drop=True)
            y = y[:max_rows]
        else:
            remaining = len(X) - mandatory_count
            selected_tail = rng.choice(remaining, size=max_rows - mandatory_count, replace=False)
            sampled_idx = np.concatenate(
                [
                    np.arange(mandatory_count, dtype=np.int32),
                    mandatory_count + np.sort(selected_tail.astype(np.int32)),
                ]
            )
            X = X.iloc[sampled_idx].reset_index(drop=True)
            y = y[sampled_idx]

    label_counts = Counter(int(value) for value in y.tolist())
    sampled_rows = int(len(X))
    return X, y, {
        "source_rows": total_rows,
        "sampled_rows": sampled_rows,
        "sample_rate": float(sampled_rows / max(1, total_rows)),
        "label_counts": {str(index): int(count) for index, count in sorted(label_counts.items())},
        "source_label_presence": {str(index): int(count) for index, count in sorted(source_label_presence.items())},
    }


def train_model(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    *,
    classes_count: int,
    seed: int,
    iterations: int,
    learning_rate: float,
    depth: int,
    l2_leaf_reg: float,
    class_weight_exponent: float,
    thread_count: int,
    task_type: str,
    devices: str,
) -> CatBoostClassifier:
    class_counts = np.bincount(y_train, minlength=int(classes_count))
    if class_counts.size == 0:
        raise ValueError("Training split is empty.")
    max_count = max(1, int(class_counts.max()))
    class_weights = [
        float((max_count / max(1, int(count))) ** float(class_weight_exponent))
        for count in class_counts
    ]
    model_kwargs: dict[str, Any] = {
        "iterations": iterations,
        "learning_rate": learning_rate,
        "depth": depth,
        "loss_function": "MultiClass",
        "eval_metric": "MultiClass",
        "random_seed": seed,
        "verbose": False,
        "allow_writing_files": False,
        "class_weights": class_weights,
        "l2_leaf_reg": l2_leaf_reg,
        "thread_count": thread_count,
        "task_type": task_type,
        "classes_count": int(classes_count),
    }
    if task_type == "GPU" and devices.strip():
        model_kwargs["devices"] = devices.strip()
    model = CatBoostClassifier(
        **model_kwargs,
    )
    model.fit(X_train, y_train)
    return model


def predict_family_batch(
    model: CatBoostClassifier,
    frame: pd.DataFrame,
    feature_columns: list[str],
    class_names: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features = frame[feature_columns].astype(np.float32)
    proba = np.asarray(model.predict_proba(features), dtype=np.float32)
    if proba.ndim != 2 or proba.shape[1] != len(class_names):
        raise ValueError(f"Unexpected family-probability shape {proba.shape}; expected rows x {len(class_names)}")
    predicted_index = np.asarray(np.argmax(proba, axis=1), dtype=np.int8)
    top1_confidence = proba[np.arange(len(proba)), predicted_index]
    runner_up = np.partition(proba, -2, axis=1)[:, -2] if proba.shape[1] > 1 else np.zeros(len(proba), dtype=np.float32)
    runner_up_margin = top1_confidence - runner_up
    return predicted_index, top1_confidence, runner_up_margin


def score_known_family_batch(
    model: CatBoostClassifier,
    frame: pd.DataFrame,
    feature_columns: list[str],
    label_index: dict[str, int],
    class_names: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    y_true = frame[DEFAULT_LABEL_COLUMN].astype(str).map(label_index).to_numpy(dtype=np.int8)
    y_pred, top1_confidence, runner_up_margin = predict_family_batch(model, frame, feature_columns, class_names)
    return y_true, y_pred, top1_confidence, runner_up_margin


def evaluate_known_split(
    model: CatBoostClassifier,
    split_path: Path,
    feature_columns: list[str],
    class_names: list[str],
    label_index: dict[str, int],
    *,
    batch_size: int,
) -> SplitEvaluation:
    y_true_parts: list[np.ndarray] = []
    y_pred_parts: list[np.ndarray] = []
    top1_parts: list[np.ndarray] = []
    margin_parts: list[np.ndarray] = []

    for batch in pq.ParquetFile(split_path).iter_batches(batch_size=batch_size, columns=feature_columns + [DEFAULT_LABEL_COLUMN]):
        frame = batch.to_pandas()
        y_true, y_pred, top1_confidence, runner_up_margin = score_known_family_batch(
            model,
            frame,
            feature_columns,
            label_index,
            class_names,
        )
        y_true_parts.append(y_true)
        y_pred_parts.append(y_pred)
        top1_parts.append(top1_confidence)
        margin_parts.append(runner_up_margin)

    if not y_true_parts:
        return SplitEvaluation(
            rows=0,
            overall={"rows": 0},
            per_family={label: {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0} for label in class_names},
            confusion_matrix={"labels": class_names, "matrix": [[0 for _ in class_names] for _ in class_names]},
            top1_confidence=numeric_summary(np.array([], dtype=np.float32)),
            runner_up_margin=numeric_summary(np.array([], dtype=np.float32)),
        )

    y_true = np.concatenate(y_true_parts)
    y_pred = np.concatenate(y_pred_parts)
    top1_confidence = np.concatenate(top1_parts)
    runner_up_margin = np.concatenate(margin_parts)

    report = classification_report(
        y_true,
        y_pred,
        labels=list(range(len(class_names))),
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(y_true, y_pred, labels=list(range(len(class_names)))).astype(int)
    overall = {
        "rows": int(len(y_true)),
        "accuracy": float(report["accuracy"]),
        "macro_precision": float(report["macro avg"]["precision"]),
        "macro_recall": float(report["macro avg"]["recall"]),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "weighted_f1": float(report["weighted avg"]["f1-score"]),
    }
    per_family = {
        family: {
            "precision": float(report[family]["precision"]),
            "recall": float(report[family]["recall"]),
            "f1": float(report[family]["f1-score"]),
            "support": int(report[family]["support"]),
        }
        for family in class_names
    }
    return SplitEvaluation(
        rows=int(len(y_true)),
        overall=overall,
        per_family=per_family,
        confusion_matrix={"labels": class_names, "matrix": matrix.tolist()},
        top1_confidence=numeric_summary(top1_confidence),
        runner_up_margin=numeric_summary(runner_up_margin),
    )


def evaluate_ood_split(
    model: CatBoostClassifier,
    split_path: Path,
    feature_columns: list[str],
    class_names: list[str],
    *,
    batch_size: int,
) -> dict[str, Any]:
    overall_predicted = Counter()
    top1_values: list[float] = []
    margin_values: list[float] = []
    family_details: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"rows": 0, "predicted_family_counts": Counter(), "top1_confidence": [], "runner_up_margin": []}
    )

    for batch in pq.ParquetFile(split_path).iter_batches(batch_size=batch_size, columns=feature_columns + [DEFAULT_LABEL_COLUMN]):
        frame = batch.to_pandas()
        y_true = frame[DEFAULT_LABEL_COLUMN].astype(str).to_numpy()
        y_pred, top1_confidence, runner_up_margin = predict_family_batch(model, frame, feature_columns, class_names)
        predicted_labels = np.asarray(class_names, dtype=object)[y_pred]

        overall_predicted.update(predicted_labels.tolist())
        top1_values.extend(top1_confidence.tolist())
        margin_values.extend(runner_up_margin.tolist())

        for family in sorted(set(y_true.tolist())):
            mask = y_true == family
            bucket = family_details[family]
            bucket["rows"] += int(mask.sum())
            bucket["predicted_family_counts"].update(predicted_labels[mask].tolist())
            bucket["top1_confidence"].extend(top1_confidence[mask].tolist())
            bucket["runner_up_margin"].extend(runner_up_margin[mask].tolist())

    by_true_family: dict[str, Any] = {}
    for family, payload in sorted(family_details.items()):
        by_true_family[family] = {
            "rows": int(payload["rows"]),
            "predicted_family_counts": dict(sorted(payload["predicted_family_counts"].items())),
            "top1_confidence": numeric_summary(np.asarray(payload["top1_confidence"], dtype=np.float32)),
            "runner_up_margin": numeric_summary(np.asarray(payload["runner_up_margin"], dtype=np.float32)),
            "zero_pass_through": int(payload["rows"]) > 0 and not bool(payload["predicted_family_counts"]),
        }

    return {
        "rows": int(sum(payload["rows"] for payload in family_details.values())),
        "predicted_family_counts": dict(sorted(overall_predicted.items())),
        "top1_confidence": numeric_summary(np.asarray(top1_values, dtype=np.float32)),
        "runner_up_margin": numeric_summary(np.asarray(margin_values, dtype=np.float32)),
        "by_true_family": by_true_family,
    }


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    dataset_root = args.dataset_root.resolve()
    output_root = args.output_root.resolve()
    models_dir, reports_dir = ensure_output_dirs(output_root)
    task_type = str(getattr(args, "task_type", DEFAULT_TASK_TYPE))
    devices = str(getattr(args, "devices", DEFAULT_DEVICES))
    class_weight_exponent = float(getattr(args, "class_weight_exponent", DEFAULT_CLASS_WEIGHT_EXPONENT))

    index = load_family_view_index(dataset_root)
    feature_columns = load_feature_columns(dataset_root, index)
    view_spec = index["views"][args.view_name]
    class_names = list(view_spec["closed_set_families"])
    label_index = build_label_index(class_names)
    ood_probe_names = list(index.get("ood_probe_families", []))

    train_split_path = resolve_view_split_path(dataset_root, index, args.view_name, "train")
    val_split_path = resolve_view_split_path(dataset_root, index, args.view_name, "val")
    test_split_path = resolve_view_split_path(dataset_root, index, args.view_name, "test")
    ood_split_path = resolve_view_split_path(dataset_root, index, args.view_name, "ood_attack_holdout")

    log(f"Sampling train rows from {train_split_path}")
    X_train, y_train, train_summary = sample_train_split(
        train_split_path,
        feature_columns,
        label_index,
        seed=args.seed,
        max_rows=args.max_train_rows,
        batch_size=args.batch_size,
    )
    if X_train.empty:
        raise ValueError(f"No training rows found in {train_split_path}")

    max_sampled_count = max((int(v) for v in train_summary["label_counts"].values()), default=1)
    reported_class_weights = {
        class_name: float(
            (max_sampled_count / max(1, int(train_summary["label_counts"].get(str(index), 0)))) ** class_weight_exponent
        )
        for index, class_name in enumerate(class_names)
    }

    log("Training CatBoost family classifier")
    train_start = time.perf_counter()
    model = train_model(
        X_train,
        y_train,
        classes_count=len(class_names),
        seed=args.seed,
        iterations=args.iterations,
        learning_rate=args.learning_rate,
        depth=args.depth,
        l2_leaf_reg=args.l2_leaf_reg,
        class_weight_exponent=class_weight_exponent,
        thread_count=args.thread_count,
        task_type=task_type,
        devices=devices,
    )
    train_seconds = time.perf_counter() - train_start

    model_path = models_dir / "catboost_family_classifier.cbm"
    model.save_model(model_path)

    log("Evaluating oracle splits")
    val_eval = evaluate_known_split(model, val_split_path, feature_columns, class_names, label_index, batch_size=args.batch_size)
    test_eval = evaluate_known_split(model, test_split_path, feature_columns, class_names, label_index, batch_size=args.batch_size)
    ood_eval = evaluate_ood_split(model, ood_split_path, feature_columns, class_names, batch_size=args.batch_size)

    report = {
        "schema_version": "1.0",
        "feature_view": args.view_name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_root": str(dataset_root),
        "output_root": str(output_root),
        "dataset_contract": {
            "family_view_index_path": str(resolve_dataset_file(dataset_root, "manifests/family_view_index.json", "family_view_index.json")),
            "feature_schema_path": str(resolve_dataset_file(dataset_root, index.get("feature_schema_path", "manifests/feature_columns.json"), "manifests/feature_columns.json")),
            "split_paths": {
                split_name: str(resolve_view_split_path(dataset_root, index, args.view_name, split_name))
                for split_name in ("train", "val", "test", "ood_attack_holdout")
            },
            "closed_set_families": class_names,
            "ood_probe_families": ood_probe_names,
        },
        "model": {
            "kind": "CatBoostClassifier",
            "artifact_path": str(model_path),
            "seed": args.seed,
            "train_seconds": float(train_seconds),
            "training": {
                "max_train_rows": int(args.max_train_rows),
                "source_rows": int(train_summary["source_rows"]),
                "sampled_rows": int(train_summary["sampled_rows"]),
                "sample_rate": float(train_summary["sample_rate"]),
                "label_counts": train_summary["label_counts"],
                "class_weights": reported_class_weights,
            },
            "catboost_params": {
                "iterations": int(args.iterations),
                "learning_rate": float(args.learning_rate),
                "depth": int(args.depth),
                "l2_leaf_reg": float(args.l2_leaf_reg),
                "class_weight_exponent": float(class_weight_exponent),
                "thread_count": int(args.thread_count),
                "task_type": task_type,
                "devices": devices,
            },
        },
        "oracle_evaluation": {
            "val": {
                "rows": int(val_eval.rows),
                "overall": val_eval.overall,
                "per_family": val_eval.per_family,
                "confusion_matrix": val_eval.confusion_matrix,
            },
            "test": {
                "rows": int(test_eval.rows),
                "overall": test_eval.overall,
                "per_family": test_eval.per_family,
                "confusion_matrix": test_eval.confusion_matrix,
            },
        },
        "signal_profiles": {
            "val": {"top1_confidence": val_eval.top1_confidence, "runner_up_margin": val_eval.runner_up_margin},
            "test": {"top1_confidence": test_eval.top1_confidence, "runner_up_margin": test_eval.runner_up_margin},
            "ood_attack_holdout": {"top1_confidence": ood_eval["top1_confidence"], "runner_up_margin": ood_eval["runner_up_margin"]},
        },
        "unknown_signal_evidence": {"ood_attack_holdout": ood_eval},
    }

    report_path = reports_dir / "oracle_family_eval.json"
    write_json(report_path, report)
    log(f"Wrote oracle family report to {report_path}")
    return report


def main() -> None:
    args = parse_args()
    run_training(args)


if __name__ == "__main__":
    main()
