from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ids.core.model_bundle import (
    SUPPORTED_BUNDLE_MANIFEST_VERSION,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)
from ml_pipeline.packaging.path_defaults import (
    DEFAULT_PACKAGING_BUNDLE_ROOT,
    DEFAULT_PACKAGING_FEATURE_COLUMNS_PATH,
    DEFAULT_PACKAGING_MODEL_PATH,
    DEFAULT_PACKAGING_SUMMARY_PATH,
    DEFAULT_PACKAGING_THRESHOLD_SELECTION_PATH,
    DEFAULT_PACKAGING_TRAINING_SUMMARY_PATH,
)


DEFAULT_MODEL_PATH = DEFAULT_PACKAGING_MODEL_PATH
DEFAULT_FEATURE_COLUMNS_PATH = DEFAULT_PACKAGING_FEATURE_COLUMNS_PATH
DEFAULT_SUMMARY_PATH = DEFAULT_PACKAGING_SUMMARY_PATH
DEFAULT_TRAINING_SUMMARY_PATH = DEFAULT_PACKAGING_TRAINING_SUMMARY_PATH
DEFAULT_THRESHOLD_SELECTION_PATH = DEFAULT_PACKAGING_THRESHOLD_SELECTION_PATH
DEFAULT_BUNDLE_ROOT = DEFAULT_PACKAGING_BUNDLE_ROOT


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_summary_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_model_card(bundle_root: Path, metadata: dict[str, Any]) -> str:
    return f"""# Final IDS Model Bundle

## Model

- model key: `{metadata['model_key']}`
- model family: `{metadata['model_family']}`
- threshold: `{metadata['threshold']}`
- positive label: `{metadata['positive_label']}`
- negative label: `{metadata['negative_label']}`

## Bundle contents

- `model.cbm`
- `feature_columns.json`
- `model_bundle.json`
- `metrics.json`
- `training_summary.json`

## Training scope

- train rows: `{metadata['train_rows']:,}`
- feature count: `{metadata['feature_count']}`

## Selected operating point

- threshold: `{metadata['threshold']}`
- reason: selected as the final deployment operating point because it keeps the model package simple and avoids the slight FPR increase seen at the tuned threshold.

## Final metrics

- test_f1: `{metadata['metrics']['test_f1']:.6f}`
- test_recall: `{metadata['metrics']['test_recall']:.6f}`
- test_precision: `{metadata['metrics']['test_precision']:.6f}`
- test_fpr: `{metadata['metrics']['test_fpr']:.6f}`
- ood_recall: `{metadata['metrics']['ood_recall']:.6f}`

## Source references

- final decision: `docs/final_model_decision.md`
- scaling experiment: `docs/scaling_experiment_results.md`
- threshold analysis: `docs/scaling_threshold_analysis.md`
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package the finalized CatBoost IDS model into a self-contained bundle.")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--feature-columns-path", type=Path, default=DEFAULT_FEATURE_COLUMNS_PATH)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--training-summary-path", type=Path, default=DEFAULT_TRAINING_SUMMARY_PATH)
    parser.add_argument("--threshold-selection-path", type=Path, default=DEFAULT_THRESHOLD_SELECTION_PATH)
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)

    model_target = bundle_root / "model.cbm"
    feature_target = bundle_root / "feature_columns.json"
    metrics_target = bundle_root / "metrics.json"
    training_target = bundle_root / "training_summary.json"
    bundle_config_target = bundle_root / "model_bundle.json"
    model_card_target = bundle_root / "MODEL_CARD.md"

    shutil.copy2(args.model_path.resolve(), model_target)
    shutil.copy2(args.feature_columns_path.resolve(), feature_target)

    summary = read_summary_row(args.summary_path.resolve())
    training_summary = read_json(args.training_summary_path.resolve())
    threshold_selection = read_json(args.threshold_selection_path.resolve())
    feature_columns_payload = read_json(args.feature_columns_path.resolve())
    feature_schema_metadata = build_feature_schema_metadata(feature_target)

    metrics_payload = {
        "val_f1": float(summary["val_f1"]),
        "test_f1": float(summary["test_f1"]),
        "test_recall": float(summary["test_recall"]),
        "test_precision": float(summary["test_precision"]),
        "test_fpr": float(summary["test_fpr"]),
        "ood_recall": float(summary["ood_recall"]),
    }
    write_json(metrics_target, metrics_payload)
    write_json(training_target, training_summary)

    bundle_payload = {
        "manifest_version": SUPPORTED_BUNDLE_MANIFEST_VERSION,
        "bundle_name": "catboost_full_data_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "model_key": "catboost_full_data",
        "model_family": "CatBoostClassifier",
        "model_artifact": model_target.name,
        "feature_columns_file": feature_target.name,
        "threshold": float(args.threshold),
        "positive_label": "Attack",
        "negative_label": "Benign",
        "feature_count": len(feature_columns_payload["feature_columns"]),
        "train_rows": int(training_summary["train_rows"]),
        "recommended_threshold_from_validation_fpr_cap_0_02": float(threshold_selection["recommended_threshold"]),
        "decision": {
            "selected_threshold": float(args.threshold),
            "selected_model": "CatBoost full-data",
            "reason": "Chosen as the final IDS model because it balances detection quality, FPR, scalability, and training cost.",
        },
        "metrics_file": metrics_target.name,
        "training_summary_file": training_target.name,
        "compatibility": {
            "feature_schema": feature_schema_metadata,
            "inference_contract": build_inference_contract_metadata(
                positive_label="Attack",
                negative_label="Benign",
                threshold=float(args.threshold),
            ),
        },
        "source_artifacts": {
            "model_path": str(args.model_path.resolve()),
            "feature_columns_path": str(args.feature_columns_path.resolve()),
            "summary_path": str(args.summary_path.resolve()),
            "training_summary_path": str(args.training_summary_path.resolve()),
            "threshold_selection_path": str(args.threshold_selection_path.resolve()),
        },
    }
    write_json(bundle_config_target, bundle_payload)
    model_card_target.write_text(build_model_card(bundle_root, {**bundle_payload, "metrics": metrics_payload}), encoding="utf-8")

    print(
        json.dumps(
            {
                "bundle_root": str(bundle_root),
                "model_artifact": str(model_target),
                "feature_columns_file": str(feature_target),
                "bundle_config": str(bundle_config_target),
                "threshold": float(args.threshold),
                "train_rows": int(training_summary["train_rows"]),
            },
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
