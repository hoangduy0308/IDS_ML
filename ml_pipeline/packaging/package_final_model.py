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
    DEFAULT_STAGE2_FAMILY_LABELS,
    build_composite_inference_contract_metadata,
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
    resolve_repo_path,
)


DEFAULT_MODEL_PATH = DEFAULT_PACKAGING_MODEL_PATH
DEFAULT_FEATURE_COLUMNS_PATH = DEFAULT_PACKAGING_FEATURE_COLUMNS_PATH
DEFAULT_SUMMARY_PATH = DEFAULT_PACKAGING_SUMMARY_PATH
DEFAULT_TRAINING_SUMMARY_PATH = DEFAULT_PACKAGING_TRAINING_SUMMARY_PATH
DEFAULT_THRESHOLD_SELECTION_PATH = DEFAULT_PACKAGING_THRESHOLD_SELECTION_PATH
DEFAULT_BUNDLE_ROOT = DEFAULT_PACKAGING_BUNDLE_ROOT
DEFAULT_COMPOSITE_BUNDLE_ROOT = resolve_repo_path(
    "artifacts",
    "final_model",
    "catboost_two_stage_family_v1",
)
DEFAULT_COMPOSITE_STAGE2_MODEL_PATH = resolve_repo_path(
    "artifacts",
    "modeling",
    "cic_iot_diad_2024_family_views",
    "family_classifier",
    "models",
    "catboost_family_classifier.cbm",
)
DEFAULT_COMPOSITE_STAGE2_REPORT_PATH = resolve_repo_path(
    "artifacts",
    "modeling",
    "cic_iot_diad_2024_family_views",
    "family_classifier",
    "reports",
    "oracle_family_eval.json",
)
DEFAULT_COMPOSITE_STAGE2_FEATURE_COLUMNS_PATH = DEFAULT_FEATURE_COLUMNS_PATH
DEFAULT_COMPOSITE_BUNDLE_NAME = "catboost_two_stage_family_v1"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_summary_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_model_card(bundle_root: Path, metadata: dict[str, Any]) -> str:
    if metadata.get("bundle_kind") == "composite":
        stage2_metadata = metadata["stage2"]
        return f"""# Final IDS Model Bundle

## Model

- bundle kind: `composite`
- model key: `{metadata['model_key']}`
- model family: `{metadata['model_family']}`
- threshold: `{metadata['threshold']}`
- positive label: `{metadata['positive_label']}`
- negative label: `{metadata['negative_label']}`

## Bundle contents

- `model.cbm`
- `feature_columns.json`
- `stage2_model.cbm`
- `stage2_feature_columns.json`
- `stage2_report.json`
- `model_bundle.json`
- `metrics.json`
- `training_summary.json`

## Training scope

- train rows: `{metadata['train_rows']:,}`
- feature count: `{metadata['feature_count']}`

## Selected operating point

- stage 2 model: `{stage2_metadata['model_artifact']}`
- closed-set labels: `{', '.join(stage2_metadata['closed_set_labels'])}`
- abstention top1_confidence: `{stage2_metadata['top1_confidence_threshold']}`
- abstention runner_up_margin: `{stage2_metadata['runner_up_margin_threshold']}`

## Final metrics

- test_f1: `{metadata['metrics']['test_f1']:.6f}`
- test_recall: `{metadata['metrics']['test_recall']:.6f}`
- test_precision: `{metadata['metrics']['test_precision']:.6f}`
- test_fpr: `{metadata['metrics']['test_fpr']:.6f}`
- ood_recall: `{metadata['metrics']['ood_recall']:.6f}`

## Source references

- stage 2 report: `{stage2_metadata['report_path']}`
- stage 2 checkpoint: `{stage2_metadata['model_path']}`
- stage 2 feature schema: `{stage2_metadata['feature_columns_path']}`
"""
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


def _read_stage2_family_report(path: Path) -> dict[str, Any]:
    report = read_json(path)
    if "signal_profiles" not in report:
        raise ValueError(f"Composite family report missing signal_profiles: {path}")
    return report


def _extract_stage2_closed_set_labels(report: dict[str, Any]) -> list[str]:
    dataset_contract = report.get("dataset_contract")
    if isinstance(dataset_contract, dict):
        closed_set_families = dataset_contract.get("closed_set_families")
        if isinstance(closed_set_families, list) and closed_set_families:
            return [str(label).strip() for label in closed_set_families if str(label).strip()]
    raw_closed_set = report.get("closed_set_families")
    if isinstance(raw_closed_set, list) and raw_closed_set:
        return [str(label).strip() for label in raw_closed_set if str(label).strip()]
    return [str(label).strip() for label in DEFAULT_STAGE2_FAMILY_LABELS]


def _extract_stage2_abstention_thresholds(report: dict[str, Any]) -> tuple[float, float]:
    signal_profiles = report["signal_profiles"]["ood_attack_holdout"]
    top1_confidence = float(signal_profiles["top1_confidence"]["mean"])
    runner_up_margin = float(signal_profiles["runner_up_margin"]["mean"])
    return top1_confidence, runner_up_margin


def _resolve_path(value: Path | None, default: Path) -> Path:
    return Path(value if value is not None else default).resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package the finalized CatBoost IDS model into a self-contained bundle."
    )
    parser.add_argument("--bundle-kind", choices=("binary", "composite"), default="binary")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--feature-columns-path", type=Path)
    parser.add_argument("--summary-path", type=Path)
    parser.add_argument("--training-summary-path", type=Path)
    parser.add_argument("--threshold-selection-path", type=Path)
    parser.add_argument("--bundle-root", type=Path)
    parser.add_argument("--bundle-name", type=str)
    parser.add_argument("--stage2-model-path", type=Path)
    parser.add_argument("--stage2-feature-columns-path", type=Path)
    parser.add_argument("--stage2-report-path", type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_kind = str(args.bundle_kind)
    model_path = _resolve_path(args.model_path, DEFAULT_MODEL_PATH)
    feature_columns_path = _resolve_path(args.feature_columns_path, DEFAULT_FEATURE_COLUMNS_PATH)
    summary_path = _resolve_path(args.summary_path, DEFAULT_SUMMARY_PATH)
    training_summary_path = _resolve_path(args.training_summary_path, DEFAULT_TRAINING_SUMMARY_PATH)
    threshold_selection_path = _resolve_path(args.threshold_selection_path, DEFAULT_THRESHOLD_SELECTION_PATH)
    bundle_root = _resolve_path(
        args.bundle_root,
        DEFAULT_BUNDLE_ROOT if bundle_kind == "binary" else DEFAULT_COMPOSITE_BUNDLE_ROOT,
    )
    bundle_root.mkdir(parents=True, exist_ok=True)

    model_target = bundle_root / "model.cbm"
    feature_target = bundle_root / "feature_columns.json"
    metrics_target = bundle_root / "metrics.json"
    training_target = bundle_root / "training_summary.json"
    bundle_config_target = bundle_root / "model_bundle.json"
    model_card_target = bundle_root / "MODEL_CARD.md"

    shutil.copy2(model_path, model_target)
    shutil.copy2(feature_columns_path, feature_target)

    summary = read_summary_row(summary_path)
    training_summary = read_json(training_summary_path)
    threshold_selection = read_json(threshold_selection_path)
    feature_columns_payload = read_json(feature_columns_path)
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

    bundle_name = (
        str(args.bundle_name).strip()
        if args.bundle_name is not None and str(args.bundle_name).strip()
        else ("catboost_full_data_v1" if bundle_kind == "binary" else DEFAULT_COMPOSITE_BUNDLE_NAME)
    )
    bundle_payload = {
        "manifest_version": SUPPORTED_BUNDLE_MANIFEST_VERSION,
        "bundle_name": bundle_name,
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
            "model_path": str(model_path),
            "feature_columns_path": str(feature_columns_path),
            "summary_path": str(summary_path),
            "training_summary_path": str(training_summary_path),
            "threshold_selection_path": str(threshold_selection_path),
        },
    }

    if bundle_kind == "composite":
        stage2_model_path = _resolve_path(
            args.stage2_model_path,
            DEFAULT_COMPOSITE_STAGE2_MODEL_PATH,
        )
        stage2_feature_columns_source = _resolve_path(
            args.stage2_feature_columns_path,
            DEFAULT_COMPOSITE_STAGE2_FEATURE_COLUMNS_PATH,
        )
        stage2_report_path = _resolve_path(
            args.stage2_report_path,
            DEFAULT_COMPOSITE_STAGE2_REPORT_PATH,
        )

        stage2_model_target = bundle_root / "stage2_model.cbm"
        stage2_feature_columns_target = bundle_root / "stage2_feature_columns.json"
        stage2_report_target = bundle_root / "stage2_report.json"

        shutil.copy2(stage2_model_path, stage2_model_target)
        shutil.copy2(stage2_feature_columns_source, stage2_feature_columns_target)
        shutil.copy2(stage2_report_path, stage2_report_target)

        stage2_report = _read_stage2_family_report(stage2_report_path)
        closed_set_labels = _extract_stage2_closed_set_labels(stage2_report)
        top1_confidence_threshold, runner_up_margin_threshold = _extract_stage2_abstention_thresholds(
            stage2_report
        )

        bundle_payload["bundle_name"] = bundle_name
        bundle_payload["bundle_kind"] = "composite"
        bundle_payload["stage2_report_file"] = stage2_report_target.name
        bundle_payload["stage2_report_summary"] = {
            "closed_set_labels": closed_set_labels,
            "top1_confidence_threshold": top1_confidence_threshold,
            "runner_up_margin_threshold": runner_up_margin_threshold,
        }
        bundle_payload["compatibility"]["inference_contract"] = build_composite_inference_contract_metadata(
            positive_label="Attack",
            negative_label="Benign",
            threshold=float(args.threshold),
            stage2_model_artifact=stage2_model_target.name,
            stage2_feature_columns_path=stage2_feature_columns_target,
            top1_confidence_threshold=top1_confidence_threshold,
            runner_up_margin_threshold=runner_up_margin_threshold,
            stage2_family_labels=closed_set_labels,
        )
        bundle_payload["source_artifacts"].update(
            {
                "stage2_model_path": str(stage2_model_path),
                "stage2_feature_columns_path": str(stage2_feature_columns_source),
                "stage2_report_path": str(stage2_report_path),
            }
        )
        model_card_payload = {
            **bundle_payload,
            "metrics": metrics_payload,
            "stage2": {
                "model_artifact": stage2_model_target.name,
                "model_path": str(stage2_model_path),
                "feature_columns_path": str(stage2_feature_columns_source),
                "report_path": str(stage2_report_path),
                "closed_set_labels": closed_set_labels,
                "top1_confidence_threshold": top1_confidence_threshold,
                "runner_up_margin_threshold": runner_up_margin_threshold,
            },
        }
    else:
        bundle_payload["bundle_kind"] = "binary"
        model_card_payload = {**bundle_payload, "metrics": metrics_payload}

    write_json(bundle_config_target, bundle_payload)
    model_card_target.write_text(build_model_card(bundle_root, model_card_payload), encoding="utf-8")

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
