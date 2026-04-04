from __future__ import annotations

import importlib
import csv
import json
from argparse import Namespace
from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from ml_pipeline.data_prep.preprocess_iot_diad import run_pipeline
from ml_pipeline.packaging import package_final_model
from ml_pipeline.packaging import path_defaults as packaging_path_defaults
from ml_pipeline.training.posttrain_threshold_analysis import run_analysis
from ml_pipeline.training.train_iot_diad_binary import run_training


FLOW_COLUMNS = (
    ["Flow ID"]
    + [f"feature_{index}" for index in range(1, 80)]
    + ["Src IP", "Dst IP", "Timestamp", "Label"]
)
FEATURE_COLUMNS = ["f1", "f2"]
REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE2_MODEL_PATH = (
    REPO_ROOT
    / "artifacts"
    / "modeling"
    / "cic_iot_diad_2024_family_views"
    / "family_classifier"
    / "models"
    / "catboost_family_classifier.cbm"
)
STAGE2_REPORT_PATH = (
    REPO_ROOT
    / "artifacts"
    / "modeling"
    / "cic_iot_diad_2024_family_views"
    / "family_classifier"
    / "reports"
    / "oracle_family_eval.json"
)


def _write_flow_csv(path: Path, *, base_value: float, rows: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for row_index in range(rows):
        record: dict[str, object] = {"Flow ID": f"{path.stem}-{row_index}"}
        for feature_index in range(1, 80):
            record[f"feature_{feature_index}"] = base_value + feature_index + row_index
        record["Src IP"] = f"10.0.0.{row_index + 1}"
        record["Dst IP"] = f"10.0.1.{row_index + 1}"
        record["Timestamp"] = f"2026-03-31T00:00:0{row_index}Z"
        record["Label"] = "Attack" if base_value > 100 else "Benign"
        records.append(record)
    pd.DataFrame.from_records(records, columns=FLOW_COLUMNS).to_csv(path, index=False)


def _build_preprocess_input(input_root: Path) -> None:
    for index in range(3):
        _write_flow_csv(input_root / "Benign" / f"benign_{index}.csv", base_value=1 + index)
        _write_flow_csv(
            input_root / "DoS" / "DoS-UDP_Flood" / f"dos_{index}.csv",
            base_value=101 + index,
        )
    _write_flow_csv(
        input_root / "BruteForce" / "SSH" / "bruteforce_0.csv",
        base_value=201,
    )


def _split_frame(rows: list[tuple[float, float, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["f1", "f2", "derived_label_binary"])


def _build_training_dataset_root(dataset_root: Path) -> Path:
    clean_dir = dataset_root / "clean"
    manifests_dir = dataset_root / "manifests"
    clean_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    train = _split_frame(
        [
            (0.0, 0.0, "Benign"),
            (0.1, 0.2, "Benign"),
            (0.2, 0.1, "Benign"),
            (0.3, 0.2, "Benign"),
            (0.4, 0.3, "Benign"),
            (2.0, 2.1, "Attack"),
            (2.1, 2.0, "Attack"),
            (2.2, 2.1, "Attack"),
            (2.3, 2.2, "Attack"),
            (2.4, 2.3, "Attack"),
        ]
    )
    val = _split_frame(
        [
            (0.05, 0.05, "Benign"),
            (0.15, 0.1, "Benign"),
            (2.05, 2.0, "Attack"),
            (2.15, 2.1, "Attack"),
        ]
    )
    test = _split_frame(
        [
            (0.12, 0.08, "Benign"),
            (0.18, 0.16, "Benign"),
            (2.12, 2.08, "Attack"),
            (2.22, 2.18, "Attack"),
        ]
    )
    ood = _split_frame(
        [
            (2.5, 2.4, "Attack"),
            (2.6, 2.5, "Attack"),
        ]
    )

    train.to_parquet(clean_dir / "train.parquet", index=False)
    val.to_parquet(clean_dir / "val.parquet", index=False)
    test.to_parquet(clean_dir / "test.parquet", index=False)
    ood.to_parquet(clean_dir / "ood_attack_holdout.parquet", index=False)

    (manifests_dir / "feature_columns.json").write_text(
        json.dumps({"feature_columns": FEATURE_COLUMNS}),
        encoding="utf-8",
    )
    (manifests_dir / "cleaning_report.json").write_text(
        json.dumps(
            {
                "label_distribution_by_split": {
                    "train": {"Benign": 5, "Attack": 5},
                    "val": {"Benign": 2, "Attack": 2},
                    "test": {"Benign": 2, "Attack": 2},
                    "ood_attack_holdout": {"Attack": 2},
                }
            }
        ),
        encoding="utf-8",
    )
    return dataset_root


def _reload_packaging_defaults(monkeypatch: pytest.MonkeyPatch, repo_root: Path | None) -> None:
    env_var = packaging_path_defaults.DEFAULT_REPO_ROOT_ENV_VAR
    if repo_root is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, str(repo_root))

    importlib.reload(packaging_path_defaults)
    importlib.reload(package_final_model)


def _train_tiny_logistic_model(path: Path) -> Path:
    frame = pd.DataFrame(
        [
            (0.0, 0.0, 0),
            (0.1, 0.1, 0),
            (0.2, 0.2, 0),
            (2.0, 2.0, 1),
            (2.1, 2.1, 1),
            (2.2, 2.2, 1),
        ],
        columns=["f1", "f2", "label"],
    )
    model = LogisticRegression(max_iter=200)
    model.fit(frame[FEATURE_COLUMNS], frame["label"])
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


def test_preprocess_run_pipeline_writes_clean_splits_and_manifests(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    _build_preprocess_input(input_root)

    run_pipeline(
        Namespace(
            input_root=input_root,
            output_root=output_root,
            task="binary",
            seed=7,
            chunk_size=10,
            hash_buckets=4,
        )
    )

    assert (output_root / "clean" / "train.parquet").is_file()
    assert (output_root / "clean" / "val.parquet").is_file()
    assert (output_root / "clean" / "test.parquet").is_file()
    assert (output_root / "clean" / "ood_attack_holdout.parquet").is_file()
    assert (output_root / "manifests" / "feature_columns.json").is_file()
    report = json.loads((output_root / "manifests" / "cleaning_report.json").read_text(encoding="utf-8"))
    assert report["valid_file_count"] >= 6
    assert report["quarantine_file_count"] == 0
    assert report["rows_by_split"]["ood_attack_holdout"] > 0


def test_preprocess_run_pipeline_fails_without_input_csvs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No CSV files found"):
        run_pipeline(
            Namespace(
                input_root=tmp_path / "empty-input",
                output_root=tmp_path / "output",
                task="binary",
                seed=7,
                chunk_size=10,
                hash_buckets=4,
            )
        )


def test_run_training_writes_model_and_report_artifacts(tmp_path: Path) -> None:
    dataset_root = _build_training_dataset_root(tmp_path / "dataset")
    output_root = tmp_path / "training-output"

    run_training(
        Namespace(
            dataset_root=dataset_root,
            output_root=output_root,
            models="logreg",
            seed=13,
            profile="quick",
            batch_size=4,
        )
    )

    assert (output_root / "models" / "logreg.joblib").is_file()
    assert (output_root / "reports" / "metrics_summary.csv").is_file()
    assert (output_root / "reports" / "metrics_detail.json").is_file()
    summary = pd.read_csv(output_root / "reports" / "metrics_summary.csv")
    assert summary.loc[0, "model"] == "logreg"
    assert float(summary.loc[0, "test_f1"]) >= 0.0


def test_run_training_rejects_unknown_model(tmp_path: Path) -> None:
    dataset_root = _build_training_dataset_root(tmp_path / "dataset")

    with pytest.raises(ValueError, match="Unsupported model"):
        run_training(
            Namespace(
                dataset_root=dataset_root,
                output_root=tmp_path / "training-output",
                models="unknown_model",
                seed=13,
                profile="quick",
                batch_size=4,
            )
        )


def test_package_final_model_main_writes_bundle_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model_path = tmp_path / "source-model.cbm"
    feature_columns_path = tmp_path / "feature_columns.json"
    summary_path = tmp_path / "summary.csv"
    training_summary_path = tmp_path / "training_summary.json"
    threshold_selection_path = tmp_path / "threshold_selection.json"
    bundle_root = tmp_path / "bundle"

    model_path.write_text("placeholder-model\n", encoding="utf-8")
    feature_columns_path.write_text(json.dumps({"feature_columns": FEATURE_COLUMNS}), encoding="utf-8")
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["val_f1", "test_f1", "test_recall", "test_precision", "test_fpr", "ood_recall"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "val_f1": "0.91",
                "test_f1": "0.92",
                "test_recall": "0.93",
                "test_precision": "0.94",
                "test_fpr": "0.01",
                "ood_recall": "0.88",
            }
        )
    training_summary_path.write_text(json.dumps({"train_rows": 10}), encoding="utf-8")
    threshold_selection_path.write_text(
        json.dumps({"recommended_threshold": 0.42}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "package_final_model.py",
            "--model-path",
            str(model_path),
            "--feature-columns-path",
            str(feature_columns_path),
            "--summary-path",
            str(summary_path),
            "--training-summary-path",
            str(training_summary_path),
            "--threshold-selection-path",
            str(threshold_selection_path),
            "--bundle-root",
            str(bundle_root),
        ],
    )

    package_final_model.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["bundle_root"] == str(bundle_root.resolve())
    assert (bundle_root / "model_bundle.json").is_file()
    assert (bundle_root / "MODEL_CARD.md").is_file()
    manifest = json.loads((bundle_root / "model_bundle.json").read_text(encoding="utf-8"))
    assert manifest["feature_count"] == len(FEATURE_COLUMNS)
    assert manifest["recommended_threshold_from_validation_fpr_cap_0_02"] == 0.42


def test_package_final_model_main_writes_composite_bundle_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model_path = tmp_path / "stage1-model.cbm"
    feature_columns_path = tmp_path / "feature_columns.json"
    stage2_feature_columns_path = tmp_path / "stage2_feature_columns.json"
    summary_path = tmp_path / "summary.csv"
    training_summary_path = tmp_path / "training_summary.json"
    threshold_selection_path = tmp_path / "threshold_selection.json"
    bundle_root = tmp_path / "composite-bundle"

    model_path.write_text("placeholder-stage1-model\n", encoding="utf-8")
    feature_columns_path.write_text(json.dumps({"feature_columns": FEATURE_COLUMNS}), encoding="utf-8")
    stage2_feature_columns_path.write_text(
        json.dumps({"feature_columns": FEATURE_COLUMNS}),
        encoding="utf-8",
    )
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["val_f1", "test_f1", "test_recall", "test_precision", "test_fpr", "ood_recall"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "val_f1": "0.91",
                "test_f1": "0.92",
                "test_recall": "0.93",
                "test_precision": "0.94",
                "test_fpr": "0.01",
                "ood_recall": "0.88",
            }
        )
    training_summary_path.write_text(json.dumps({"train_rows": 10}), encoding="utf-8")
    threshold_selection_path.write_text(
        json.dumps({"recommended_threshold": 0.42}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "package_final_model.py",
            "--bundle-kind",
            "composite",
            "--model-path",
            str(model_path),
            "--feature-columns-path",
            str(feature_columns_path),
            "--summary-path",
            str(summary_path),
            "--training-summary-path",
            str(training_summary_path),
            "--threshold-selection-path",
            str(threshold_selection_path),
            "--stage2-model-path",
            str(STAGE2_MODEL_PATH),
            "--stage2-feature-columns-path",
            str(stage2_feature_columns_path),
            "--stage2-report-path",
            str(STAGE2_REPORT_PATH),
            "--bundle-root",
            str(bundle_root),
        ],
    )

    package_final_model.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["bundle_root"] == str(bundle_root.resolve())
    assert (bundle_root / "model_bundle.json").is_file()
    assert (bundle_root / "stage2_model.cbm").is_file()
    assert (bundle_root / "stage2_feature_columns.json").is_file()
    assert (bundle_root / "stage2_report.json").is_file()
    assert (bundle_root / "MODEL_CARD.md").is_file()

    manifest = json.loads((bundle_root / "model_bundle.json").read_text(encoding="utf-8"))
    inference_contract = manifest["compatibility"]["inference_contract"]
    stage2_contract = inference_contract["stage2"]

    assert manifest["bundle_kind"] == "composite"
    assert manifest["bundle_name"] == "catboost_two_stage_family_v1"
    assert inference_contract["version"] == "ids_two_stage_family_contract.v1"
    assert stage2_contract["model_artifact"] == "stage2_model.cbm"
    assert stage2_contract["feature_columns_file"] == "stage2_feature_columns.json"
    assert stage2_contract["closed_set_labels"] == ["DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"]
    assert inference_contract["abstention"]["top1_confidence"] == pytest.approx(0.5588587362527666)
    assert inference_contract["abstention"]["runner_up_margin"] == pytest.approx(0.3097277574209342)
    assert manifest["source_artifacts"]["stage2_model_path"] == str(STAGE2_MODEL_PATH.resolve())
    assert manifest["source_artifacts"]["stage2_report_path"] == str(STAGE2_REPORT_PATH.resolve())
    card = (bundle_root / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "bundle kind: `composite`" in card
    assert "stage 2 model:" in card
    assert "closed-set labels:" in card


def test_package_final_model_defaults_follow_repo_root_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = (tmp_path / "override-root").resolve()
    _reload_packaging_defaults(monkeypatch, repo_root)

    expected_source_root = repo_root / "artifacts" / "kaggle" / "outputs" / "catboost_full_data_attempt" / "catboost_full_data_attempt_results"
    assert packaging_path_defaults.resolve_repo_root() == repo_root
    assert package_final_model.DEFAULT_MODEL_PATH == expected_source_root / "catboost_full_data_attempt.cbm"
    assert package_final_model.DEFAULT_FEATURE_COLUMNS_PATH == repo_root / "artifacts" / "cic_iot_diad_2024_binary" / "manifests" / "feature_columns.json"
    assert package_final_model.DEFAULT_SUMMARY_PATH == expected_source_root / "reports" / "summary.csv"
    assert package_final_model.DEFAULT_TRAINING_SUMMARY_PATH == expected_source_root / "reports" / "training_summary.json"
    assert package_final_model.DEFAULT_THRESHOLD_SELECTION_PATH == repo_root / "artifacts" / "posttrain_analysis" / "scaling_finalists" / "reports" / "catboost_full_threshold_selection.json"
    assert package_final_model.DEFAULT_BUNDLE_ROOT == repo_root / "artifacts" / "final_model" / "catboost_full_data_v1"


def test_package_final_model_defaults_fall_back_to_checkout_when_env_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reload_packaging_defaults(monkeypatch, None)

    checkout_root = Path(package_final_model.__file__).resolve().parents[2]
    expected_source_root = checkout_root / "artifacts" / "kaggle" / "outputs" / "catboost_full_data_attempt" / "catboost_full_data_attempt_results"
    assert packaging_path_defaults.resolve_repo_root() == checkout_root
    assert package_final_model.DEFAULT_MODEL_PATH == expected_source_root / "catboost_full_data_attempt.cbm"
    assert package_final_model.DEFAULT_FEATURE_COLUMNS_PATH == checkout_root / "artifacts" / "cic_iot_diad_2024_binary" / "manifests" / "feature_columns.json"
    assert package_final_model.DEFAULT_SUMMARY_PATH == expected_source_root / "reports" / "summary.csv"
    assert package_final_model.DEFAULT_TRAINING_SUMMARY_PATH == expected_source_root / "reports" / "training_summary.json"
    assert package_final_model.DEFAULT_THRESHOLD_SELECTION_PATH == checkout_root / "artifacts" / "posttrain_analysis" / "scaling_finalists" / "reports" / "catboost_full_threshold_selection.json"
    assert package_final_model.DEFAULT_BUNDLE_ROOT == checkout_root / "artifacts" / "final_model" / "catboost_full_data_v1"


def test_package_final_model_main_fails_when_source_model_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_columns_path = tmp_path / "feature_columns.json"
    summary_path = tmp_path / "summary.csv"
    training_summary_path = tmp_path / "training_summary.json"
    threshold_selection_path = tmp_path / "threshold_selection.json"
    feature_columns_path.write_text(json.dumps({"feature_columns": FEATURE_COLUMNS}), encoding="utf-8")
    summary_path.write_text(
        "val_f1,test_f1,test_recall,test_precision,test_fpr,ood_recall\n"
        "0.91,0.92,0.93,0.94,0.01,0.88\n",
        encoding="utf-8",
    )
    training_summary_path.write_text(json.dumps({"train_rows": 10}), encoding="utf-8")
    threshold_selection_path.write_text(json.dumps({"recommended_threshold": 0.42}), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "package_final_model.py",
            "--model-path",
            str(tmp_path / "missing-model.cbm"),
            "--feature-columns-path",
            str(feature_columns_path),
            "--summary-path",
            str(summary_path),
            "--training-summary-path",
            str(training_summary_path),
            "--threshold-selection-path",
            str(threshold_selection_path),
            "--bundle-root",
            str(tmp_path / "bundle"),
        ],
    )

    with pytest.raises(FileNotFoundError):
        package_final_model.main()


def test_run_analysis_writes_threshold_reports_and_figures(tmp_path: Path) -> None:
    dataset_root = _build_training_dataset_root(tmp_path / "dataset")
    outputs_root = tmp_path / "kaggle-outputs"
    analysis_root = tmp_path / "analysis"
    figures_root = tmp_path / "figures"
    _train_tiny_logistic_model(outputs_root / "tiny" / "model.joblib")

    run_analysis(
        Namespace(
            dataset_root=dataset_root,
            kaggle_outputs_root=outputs_root,
            analysis_root=analysis_root,
            docs_figures_root=figures_root,
            models="",
            model_specs="tiny_logreg|Tiny Logistic|tiny/model.joblib|tiny/results",
            preset="",
            batch_size=4,
            recommended_fpr_cap=0.02,
            threshold_grid_size=11,
        )
    )

    assert (analysis_root / "reports" / "threshold_selection_summary.csv").is_file()
    assert (analysis_root / "reports" / "threshold_evaluation_summary.csv").is_file()
    assert (analysis_root / "reports" / "tiny_logreg_threshold_selection.json").is_file()
    assert (figures_root / "tiny_logreg_threshold_sweep.png").is_file()
    assert (figures_root / "tiny_logreg_pr_roc.png").is_file()


def test_run_analysis_rejects_invalid_model_specs(tmp_path: Path) -> None:
    dataset_root = _build_training_dataset_root(tmp_path / "dataset")

    with pytest.raises(ValueError, match="Invalid model spec"):
        run_analysis(
            Namespace(
                dataset_root=dataset_root,
                kaggle_outputs_root=tmp_path / "outputs",
                analysis_root=tmp_path / "analysis",
                docs_figures_root=tmp_path / "figures",
                models="",
                model_specs="broken-spec",
                preset="",
                batch_size=4,
                recommended_fpr_cap=0.02,
                threshold_grid_size=11,
            )
        )
