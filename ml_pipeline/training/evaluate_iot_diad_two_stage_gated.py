from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from catboost import CatBoostClassifier
from sklearn.metrics import classification_report, confusion_matrix

from ids.runtime.inference import IDSInferencer, build_model_config

from ml_pipeline.training.train_iot_diad_family_classifier import (
    build_label_index,
    load_family_view_index,
    load_feature_columns,
    numeric_summary,
    predict_family_batch,
    resolve_dataset_file,
    resolve_view_split_path,
)


DEFAULT_DATASET_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_family_views")
DEFAULT_ORACLE_REPORT = Path(r"F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_family_views\family_classifier\reports\oracle_family_eval.json")
DEFAULT_BINARY_BUNDLE = Path(r"F:\Work\IDS_ML_New\artifacts\final_model\catboost_full_data_v1\model_bundle.json")
DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_family_views\two_stage_gated")
DEFAULT_VIEW_NAME = "attack_only"
DEFAULT_LABEL_COLUMN = "derived_label_family"
DEFAULT_BATCH_SIZE = 100_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the pinned stage-1 binary detector plus the offline family classifier as a gated two-stage pipeline."
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--oracle-report", type=Path, default=DEFAULT_ORACLE_REPORT)
    parser.add_argument("--binary-bundle", type=Path, default=DEFAULT_BINARY_BUNDLE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--view-name", type=str, default=DEFAULT_VIEW_NAME)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def score_stage2_rows(
    model: CatBoostClassifier,
    frame: pd.DataFrame,
    feature_columns: list[str],
    class_names: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return predict_family_batch(model, frame, feature_columns, class_names)


def evaluate_known_split(
    *,
    split_path: Path,
    inferencer: IDSInferencer,
    stage2_model: CatBoostClassifier,
    feature_columns: list[str],
    class_names: list[str],
    label_index: dict[str, int],
    batch_size: int,
) -> dict[str, Any]:
    y_true_parts: list[np.ndarray] = []
    y_pred_parts: list[np.ndarray] = []
    top1_parts: list[np.ndarray] = []
    margin_parts: list[np.ndarray] = []
    total_rows = 0
    stage1_alert_rows = 0

    for batch in pq.ParquetFile(split_path).iter_batches(batch_size=batch_size, columns=feature_columns + [DEFAULT_LABEL_COLUMN]):
        frame = batch.to_pandas()
        total_rows += len(frame)
        stage1_scores = inferencer.score_frame(frame[feature_columns])
        alert_mask = stage1_scores["is_alert"].to_numpy(dtype=bool)
        stage1_alert_rows += int(alert_mask.sum())
        if not alert_mask.any():
            continue
        alert_frame = frame.loc[alert_mask].copy()
        y_true = alert_frame[DEFAULT_LABEL_COLUMN].astype(str).map(label_index).to_numpy(dtype=np.int8)
        y_pred, top1_confidence, runner_up_margin = score_stage2_rows(stage2_model, alert_frame, feature_columns, class_names)
        y_true_parts.append(y_true)
        y_pred_parts.append(y_pred)
        top1_parts.append(top1_confidence)
        margin_parts.append(runner_up_margin)

    if not y_true_parts:
        return {
            "rows": int(total_rows),
            "stage1_alert_rows": int(stage1_alert_rows),
            "stage1_alert_rate": float(stage1_alert_rows / max(1, total_rows)),
            "stage2_scored_rows": 0,
            "family_quality": {label: {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0} for label in class_names},
            "confusion_matrix": {"labels": class_names, "matrix": [[0 for _ in class_names] for _ in class_names]},
            "top1_confidence": numeric_summary(np.array([], dtype=np.float32)),
            "runner_up_margin": numeric_summary(np.array([], dtype=np.float32)),
        }

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
    return {
        "rows": int(total_rows),
        "stage1_alert_rows": int(stage1_alert_rows),
        "stage1_alert_rate": float(stage1_alert_rows / max(1, total_rows)),
        "stage2_scored_rows": int(len(y_true)),
        "family_quality": {
            family: {
                "precision": float(report[family]["precision"]),
                "recall": float(report[family]["recall"]),
                "f1": float(report[family]["f1-score"]),
                "support": int(report[family]["support"]),
            }
            for family in class_names
        },
        "confusion_matrix": {"labels": class_names, "matrix": matrix.tolist()},
        "top1_confidence": numeric_summary(top1_confidence),
        "runner_up_margin": numeric_summary(runner_up_margin),
    }


def evaluate_ood_split(
    *,
    split_path: Path,
    inferencer: IDSInferencer,
    stage2_model: CatBoostClassifier,
    feature_columns: list[str],
    class_names: list[str],
    batch_size: int,
) -> dict[str, Any]:
    total_rows = 0
    stage1_alert_rows = 0
    top1_values: list[float] = []
    margin_values: list[float] = []
    predicted_counts = Counter()
    by_true_family: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"rows": 0, "stage1_alert_rows": 0, "predicted_family_counts": Counter(), "top1_confidence": [], "runner_up_margin": []}
    )

    for batch in pq.ParquetFile(split_path).iter_batches(batch_size=batch_size, columns=feature_columns + [DEFAULT_LABEL_COLUMN]):
        frame = batch.to_pandas()
        total_rows += len(frame)
        stage1_scores = inferencer.score_frame(frame[feature_columns])
        alert_mask = stage1_scores["is_alert"].to_numpy(dtype=bool)
        stage1_alert_rows += int(alert_mask.sum())
        y_true_all = frame[DEFAULT_LABEL_COLUMN].astype(str).to_numpy()
        for family in sorted(set(y_true_all.tolist())):
            family_mask = y_true_all == family
            bucket = by_true_family[family]
            bucket["rows"] += int(family_mask.sum())
            family_alert_mask = family_mask & alert_mask
            bucket["stage1_alert_rows"] += int(family_alert_mask.sum())

            if not family_alert_mask.any():
                continue

            alert_frame = frame.loc[family_alert_mask].copy()
            y_pred, top1_confidence, runner_up_margin = score_stage2_rows(
                stage2_model,
                alert_frame,
                feature_columns,
                class_names,
            )
            predicted_labels = np.asarray(class_names, dtype=object)[y_pred]
            top1_values.extend(top1_confidence.tolist())
            margin_values.extend(runner_up_margin.tolist())
            predicted_counts.update(predicted_labels.tolist())
            bucket["predicted_family_counts"].update(predicted_labels.tolist())
            bucket["top1_confidence"].extend(top1_confidence.tolist())
            bucket["runner_up_margin"].extend(runner_up_margin.tolist())

    family_summary: dict[str, Any] = {}
    for family, payload in sorted(by_true_family.items()):
        family_summary[family] = {
            "rows": int(payload["rows"]),
            "stage1_alert_rows": int(payload["stage1_alert_rows"]),
            "stage1_alert_rate": float(payload["stage1_alert_rows"] / max(1, payload["rows"])),
            "stage2_scored_rows": int(len(payload["top1_confidence"])),
            "zero_pass_through": int(payload["stage1_alert_rows"]) == 0,
            "predicted_family_counts": dict(sorted(payload["predicted_family_counts"].items())),
            "top1_confidence": numeric_summary(np.asarray(payload["top1_confidence"], dtype=np.float32)),
            "runner_up_margin": numeric_summary(np.asarray(payload["runner_up_margin"], dtype=np.float32)),
        }

    return {
        "rows": int(total_rows),
        "stage1_alert_rows": int(stage1_alert_rows),
        "stage1_alert_rate": float(stage1_alert_rows / max(1, total_rows)),
        "stage2_scored_rows": int(sum(item["stage2_scored_rows"] for item in family_summary.values())),
        "predicted_family_counts": dict(sorted(predicted_counts.items())),
        "top1_confidence": numeric_summary(np.asarray(top1_values, dtype=np.float32)),
        "runner_up_margin": numeric_summary(np.asarray(margin_values, dtype=np.float32)),
        "by_true_family": family_summary,
    }


def run_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    dataset_root = args.dataset_root.resolve()
    oracle_report_path = args.oracle_report.resolve()
    binary_bundle_config = args.binary_bundle.resolve()
    output_root = args.output_root.resolve()

    index = load_family_view_index(dataset_root)
    feature_columns = load_feature_columns(dataset_root, index)
    class_names = list(index["views"][args.view_name]["closed_set_families"])
    label_index = build_label_index(class_names)

    oracle_report = read_json(oracle_report_path)
    stage2_model = CatBoostClassifier()
    stage2_model.load_model(oracle_report["model"]["artifact_path"])
    inferencer = IDSInferencer(build_model_config(config_path=binary_bundle_config))

    val_split_path = resolve_view_split_path(dataset_root, index, args.view_name, "val")
    test_split_path = resolve_view_split_path(dataset_root, index, args.view_name, "test")
    ood_split_path = resolve_view_split_path(dataset_root, index, args.view_name, "ood_attack_holdout")

    val_eval = evaluate_known_split(
        split_path=val_split_path,
        inferencer=inferencer,
        stage2_model=stage2_model,
        feature_columns=feature_columns,
        class_names=class_names,
        label_index=label_index,
        batch_size=args.batch_size,
    )
    test_eval = evaluate_known_split(
        split_path=test_split_path,
        inferencer=inferencer,
        stage2_model=stage2_model,
        feature_columns=feature_columns,
        class_names=class_names,
        label_index=label_index,
        batch_size=args.batch_size,
    )
    ood_eval = evaluate_ood_split(
        split_path=ood_split_path,
        inferencer=inferencer,
        stage2_model=stage2_model,
        feature_columns=feature_columns,
        class_names=class_names,
        batch_size=args.batch_size,
    )

    report = {
        "schema_version": "1.0",
        "feature_view": args.view_name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_root": str(dataset_root),
        "output_root": str(output_root),
        "oracle_report_path": str(oracle_report_path),
        "binary_bundle_path": str(binary_bundle_config),
        "dataset_contract": {
            "family_view_index_path": str(resolve_dataset_file(dataset_root, "manifests/family_view_index.json", "family_view_index.json")),
            "feature_schema_path": str(resolve_dataset_file(dataset_root, index.get("feature_schema_path", "manifests/feature_columns.json"), "manifests/feature_columns.json")),
            "split_paths": {
                split_name: str(resolve_view_split_path(dataset_root, index, args.view_name, split_name))
                for split_name in ("train", "val", "test", "ood_attack_holdout")
            },
            "closed_set_families": class_names,
            "ood_probe_families": list(index.get("ood_probe_families", [])),
        },
        "oracle_reference": {
            "val": oracle_report["oracle_evaluation"]["val"],
            "test": oracle_report["oracle_evaluation"]["test"],
            "ood_attack_holdout": oracle_report["unknown_signal_evidence"]["ood_attack_holdout"],
        },
        "gated_evaluation": {
            "val": val_eval,
            "test": test_eval,
            "ood_attack_holdout": ood_eval,
        },
        "comparison": {
            "val": {
                "oracle_rows": int(oracle_report["oracle_evaluation"]["val"]["rows"]),
                "gated_rows": int(val_eval["rows"]),
                "gated_stage1_alert_rate": float(val_eval["stage1_alert_rate"]),
            },
            "test": {
                "oracle_rows": int(oracle_report["oracle_evaluation"]["test"]["rows"]),
                "gated_rows": int(test_eval["rows"]),
                "gated_stage1_alert_rate": float(test_eval["stage1_alert_rate"]),
            },
            "ood_attack_holdout": {
                "oracle_rows": int(oracle_report["unknown_signal_evidence"]["ood_attack_holdout"]["rows"]),
                "gated_rows": int(ood_eval["rows"]),
                "gated_stage1_alert_rate": float(ood_eval["stage1_alert_rate"]),
            },
        },
    }

    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / "reports" / "gated_family_eval.json"
    write_json(report_path, report)
    log(f"Wrote gated family report to {report_path}")
    return report


def main() -> None:
    args = parse_args()
    run_evaluation(args)


if __name__ == "__main__":
    main()
