from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from ml_pipeline.training.train_iot_diad_family_classifier import (
    DEFAULT_CLASS_WEIGHT_EXPONENT,
    build_label_index,
    ensure_output_dirs,
    evaluate_known_split,
    evaluate_ood_split,
    load_family_view_index,
    load_feature_columns,
    resolve_dataset_file,
    resolve_view_split_path,
    sample_train_split,
    train_model,
)


DEFAULT_DATASET_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_family_views")
DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_family_views\direct_multiclass")
DEFAULT_VIEW_NAME = "direct_multiclass"
DEFAULT_BATCH_SIZE = 100_000
DEFAULT_MAX_TRAIN_ROWS = 1_000_000
DEFAULT_ITERATIONS = 300
DEFAULT_LEARNING_RATE = 0.06
DEFAULT_DEPTH = 8
DEFAULT_L2_LEAF_REG = 3.0
DEFAULT_TASK_TYPE = "CPU"
DEFAULT_DEVICES = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the direct multiclass baseline on the derived CIC IoT-DIAD family view."
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
    parser.add_argument("--thread-count", type=int, default=1)
    parser.add_argument("--task-type", choices=("CPU", "GPU"), default=DEFAULT_TASK_TYPE)
    parser.add_argument("--devices", type=str, default=DEFAULT_DEVICES)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    dataset_root = args.dataset_root.resolve()
    output_root = args.output_root.resolve()
    models_dir, reports_dir = ensure_output_dirs(output_root)
    task_type = str(getattr(args, "task_type", DEFAULT_TASK_TYPE))
    devices = str(getattr(args, "devices", DEFAULT_DEVICES))

    index = load_family_view_index(dataset_root)
    feature_columns = load_feature_columns(dataset_root, index)
    view_spec = index["views"][args.view_name]
    class_names = list(view_spec["label_space"])
    label_index = build_label_index(class_names)

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

    log("Training CatBoost direct multiclass baseline")
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
        class_weight_exponent=DEFAULT_CLASS_WEIGHT_EXPONENT,
        thread_count=args.thread_count,
        task_type=task_type,
        devices=devices,
    )
    train_seconds = time.perf_counter() - train_start

    model_path = models_dir / "catboost_direct_multiclass.cbm"
    model.save_model(model_path)

    log("Evaluating direct multiclass splits")
    val_eval = evaluate_known_split(model, val_split_path, feature_columns, class_names, label_index, batch_size=args.batch_size)
    test_eval = evaluate_known_split(model, test_split_path, feature_columns, class_names, label_index, batch_size=args.batch_size)
    ood_eval = evaluate_ood_split(model, ood_split_path, feature_columns, class_names, batch_size=args.batch_size)

    report = {
        "schema_version": "1.0",
        "feature_view": args.view_name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_root": str(dataset_root),
        "output_root": str(output_root),
        "source_contract": {
            "family_view_index_path": str(resolve_dataset_file(dataset_root, "manifests/family_view_index.json", "family_view_index.json")),
            "feature_schema_path": str(resolve_dataset_file(dataset_root, index.get("feature_schema_path", "manifests/feature_columns.json"), "manifests/feature_columns.json")),
            "split_paths": {
                split_name: str(resolve_view_split_path(dataset_root, index, args.view_name, split_name))
                for split_name in ("train", "val", "test", "ood_attack_holdout")
            },
            "label_space": class_names,
            "closed_set_families": list(view_spec["closed_set_families"]),
            "ood_probe_families": list(index.get("ood_probe_families", [])),
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
                "class_weights": {
                    class_name: float(
                        max(1, max((int(v) for v in train_summary["label_counts"].values()), default=1))
                        / max(1, int(train_summary["label_counts"].get(str(index), 0)))
                    )
                    for index, class_name in enumerate(class_names)
                },
            },
            "catboost_params": {
                "iterations": int(args.iterations),
                "learning_rate": float(args.learning_rate),
                "depth": int(args.depth),
                "l2_leaf_reg": float(args.l2_leaf_reg),
                "thread_count": int(args.thread_count),
                "task_type": task_type,
                "devices": devices,
            },
        },
        "direct_multiclass_evaluation": {
            "val": {
                "rows": int(val_eval.rows),
                "overall": val_eval.overall,
                "per_family": val_eval.per_family,
                "confusion_matrix": val_eval.confusion_matrix,
                "top1_confidence": val_eval.top1_confidence,
                "runner_up_margin": val_eval.runner_up_margin,
            },
            "test": {
                "rows": int(test_eval.rows),
                "overall": test_eval.overall,
                "per_family": test_eval.per_family,
                "confusion_matrix": test_eval.confusion_matrix,
                "top1_confidence": test_eval.top1_confidence,
                "runner_up_margin": test_eval.runner_up_margin,
            },
            "ood_attack_holdout": {
                "rows": int(ood_eval["rows"]),
                "predicted_family_counts": ood_eval["predicted_family_counts"],
                "top1_confidence": ood_eval["top1_confidence"],
                "runner_up_margin": ood_eval["runner_up_margin"],
                "by_true_family": ood_eval["by_true_family"],
            },
        },
        "comparison_summary": {
            "val": {
                "rows": int(val_eval.rows),
                "accuracy": float(val_eval.overall["accuracy"]),
                "macro_f1": float(val_eval.overall["macro_f1"]),
                "weighted_f1": float(val_eval.overall["weighted_f1"]),
                "top1_confidence": val_eval.top1_confidence,
                "runner_up_margin": val_eval.runner_up_margin,
            },
            "test": {
                "rows": int(test_eval.rows),
                "accuracy": float(test_eval.overall["accuracy"]),
                "macro_f1": float(test_eval.overall["macro_f1"]),
                "weighted_f1": float(test_eval.overall["weighted_f1"]),
                "top1_confidence": test_eval.top1_confidence,
                "runner_up_margin": test_eval.runner_up_margin,
            },
            "ood_attack_holdout": {
                "rows": int(ood_eval["rows"]),
                "predicted_family_counts": ood_eval["predicted_family_counts"],
                "top1_confidence": ood_eval["top1_confidence"],
                "runner_up_margin": ood_eval["runner_up_margin"],
            },
        },
    }

    report_path = reports_dir / "direct_multiclass_eval.json"
    write_json(report_path, report)
    log(f"Wrote direct multiclass report to {report_path}")
    return report


def main() -> None:
    args = parse_args()
    run_training(args)


if __name__ == "__main__":
    main()
