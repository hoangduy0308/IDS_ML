from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from ml_pipeline.data_prep.prepare_iot_diad_family_views import run_pipeline
from ml_pipeline.training import train_iot_diad_family_classifier as train_family
from wrapper_smoke_support import assert_help_smoke, run_python_module_help


FEATURE_COLUMNS = ["f1", "f2"]


def _write_parquet(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(records).to_parquet(path, index=False)


def _make_record(
    *,
    source_file: str,
    attack_family: str,
    attack_scenario: str,
    derived_label_binary: str,
    derived_label_family: str,
    split: str,
    base: float,
) -> dict[str, object]:
    return {
        "f1": base,
        "f2": base + 0.25,
        "source_file": source_file,
        "attack_family": attack_family,
        "attack_scenario": attack_scenario,
        "derived_label_binary": derived_label_binary,
        "derived_label_family": derived_label_family,
        "split": split,
    }


def _build_source_root(source_root: Path) -> Path:
    clean_dir = source_root / "clean"
    manifests_dir = source_root / "manifests"
    clean_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    _write_parquet(
        clean_dir / "train.parquet",
        [
            _make_record(source_file="Benign/b0.csv", attack_family="Benign", attack_scenario="Benign", derived_label_binary="Benign", derived_label_family="Benign", split="train", base=0.0),
            _make_record(source_file="DoS/d0.csv", attack_family="DoS", attack_scenario="DoS", derived_label_binary="Attack", derived_label_family="DoS", split="train", base=1.0),
            _make_record(source_file="Mirai/m0.csv", attack_family="Mirai", attack_scenario="Mirai", derived_label_binary="Attack", derived_label_family="Mirai", split="train", base=2.0),
            _make_record(source_file="Spoofing/s0.csv", attack_family="Spoofing", attack_scenario="Spoofing", derived_label_binary="Attack", derived_label_family="Spoofing", split="train", base=3.0),
            _make_record(source_file="Web-Based/w0.csv", attack_family="Web-Based", attack_scenario="Web-Based", derived_label_binary="Attack", derived_label_family="Web-Based", split="train", base=4.0),
            _make_record(source_file="DDoS/dd0.csv", attack_family="DDoS", attack_scenario="DDoS", derived_label_binary="Attack", derived_label_family="DDoS", split="train", base=5.0),
        ],
    )
    _write_parquet(
        clean_dir / "val.parquet",
        [
            _make_record(source_file="Benign/b1.csv", attack_family="Benign", attack_scenario="Benign", derived_label_binary="Benign", derived_label_family="Benign", split="val", base=0.1),
            _make_record(source_file="DoS/d1.csv", attack_family="DoS", attack_scenario="DoS", derived_label_binary="Attack", derived_label_family="DoS", split="val", base=1.1),
            _make_record(source_file="Mirai/m1.csv", attack_family="Mirai", attack_scenario="Mirai", derived_label_binary="Attack", derived_label_family="Mirai", split="val", base=2.1),
            _make_record(source_file="Spoofing/s1.csv", attack_family="Spoofing", attack_scenario="Spoofing", derived_label_binary="Attack", derived_label_family="Spoofing", split="val", base=3.1),
            _make_record(source_file="Web-Based/w1.csv", attack_family="Web-Based", attack_scenario="Web-Based", derived_label_binary="Attack", derived_label_family="Web-Based", split="val", base=4.1),
            _make_record(source_file="DDoS/dd1.csv", attack_family="DDoS", attack_scenario="DDoS", derived_label_binary="Attack", derived_label_family="DDoS", split="val", base=5.1),
        ],
    )
    _write_parquet(
        clean_dir / "test.parquet",
        [
            _make_record(source_file="Benign/b2.csv", attack_family="Benign", attack_scenario="Benign", derived_label_binary="Benign", derived_label_family="Benign", split="test", base=0.2),
            _make_record(source_file="DoS/d2.csv", attack_family="DoS", attack_scenario="DoS", derived_label_binary="Attack", derived_label_family="DoS", split="test", base=1.2),
            _make_record(source_file="Mirai/m2.csv", attack_family="Mirai", attack_scenario="Mirai", derived_label_binary="Attack", derived_label_family="Mirai", split="test", base=2.2),
            _make_record(source_file="Spoofing/s2.csv", attack_family="Spoofing", attack_scenario="Spoofing", derived_label_binary="Attack", derived_label_family="Spoofing", split="test", base=3.2),
            _make_record(source_file="Web-Based/w2.csv", attack_family="Web-Based", attack_scenario="Web-Based", derived_label_binary="Attack", derived_label_family="Web-Based", split="test", base=4.2),
            _make_record(source_file="DDoS/dd2.csv", attack_family="DDoS", attack_scenario="DDoS", derived_label_binary="Attack", derived_label_family="DDoS", split="test", base=5.2),
        ],
    )
    _write_parquet(
        clean_dir / "ood_attack_holdout.parquet",
        [
            _make_record(source_file="BruteForce/bf0.csv", attack_family="BruteForce", attack_scenario="BruteForce", derived_label_binary="Attack", derived_label_family="BruteForce", split="ood_attack_holdout", base=0.3),
            _make_record(source_file="Recon/r0.csv", attack_family="Recon", attack_scenario="Recon", derived_label_binary="Attack", derived_label_family="Recon", split="ood_attack_holdout", base=0.4),
        ],
    )
    (manifests_dir / "feature_columns.json").write_text(json.dumps({"feature_columns": FEATURE_COLUMNS}), encoding="utf-8")
    (manifests_dir / "cleaning_report.json").write_text(
        json.dumps(
            {
                "label_distribution_by_split": {
                    "train": {"Benign": 1, "Attack": 5},
                    "val": {"Benign": 1, "Attack": 5},
                    "test": {"Benign": 1, "Attack": 5},
                    "ood_attack_holdout": {"Attack": 2},
                },
                "ood_families": ["BruteForce", "Recon"],
            }
        ),
        encoding="utf-8",
    )
    (manifests_dir / "file_manifest.csv").write_text(
        "source_file,attack_family,attack_scenario,split\n"
        "Benign/b0.csv,Benign,Benign,train\n"
        "DoS/d0.csv,DoS,DoS,train\n"
        "Mirai/m0.csv,Mirai,Mirai,train\n"
        "Spoofing/s0.csv,Spoofing,Spoofing,train\n"
        "Web-Based/w0.csv,Web-Based,Web-Based,train\n"
        "DDoS/dd0.csv,DDoS,DDoS,train\n"
        "Benign/b1.csv,Benign,Benign,val\n"
        "DoS/d1.csv,DoS,DoS,val\n"
        "Mirai/m1.csv,Mirai,Mirai,val\n"
        "Spoofing/s1.csv,Spoofing,Spoofing,val\n"
        "Web-Based/w1.csv,Web-Based,Web-Based,val\n"
        "DDoS/dd1.csv,DDoS,DDoS,val\n"
        "Benign/b2.csv,Benign,Benign,test\n"
        "DoS/d2.csv,DoS,DoS,test\n"
        "Mirai/m2.csv,Mirai,Mirai,test\n"
        "Spoofing/s2.csv,Spoofing,Spoofing,test\n"
        "Web-Based/w2.csv,Web-Based,Web-Based,test\n"
        "DDoS/dd2.csv,DDoS,DDoS,test\n"
        "BruteForce/bf0.csv,BruteForce,BruteForce,ood_attack_holdout\n"
        "Recon/r0.csv,Recon,Recon,ood_attack_holdout\n",
        encoding="utf-8",
    )
    return source_root


def test_train_iot_diad_family_classifier_writes_oracle_report(tmp_path: Path) -> None:
    source_root = _build_source_root(tmp_path / "source")
    derived_root = tmp_path / "family_views"
    run_pipeline(Namespace(source_root=source_root, output_root=derived_root))

    output_root = tmp_path / "modeling"
    train_family.run_training(
        Namespace(
            dataset_root=derived_root,
            output_root=output_root,
            view_name="attack_only",
            seed=7,
            batch_size=16,
            max_train_rows=64,
            iterations=20,
            learning_rate=0.2,
            depth=4,
            l2_leaf_reg=1.0,
            thread_count=1,
        )
    )

    report_path = output_root / "reports" / "oracle_family_eval.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["model"]["kind"] == "CatBoostClassifier"
    assert "artifact_path" in report["model"]
    assert "oracle_evaluation" in report
    assert "signal_profiles" in report
    assert "unknown_signal_evidence" in report
    assert "top1_confidence" in report["signal_profiles"]["val"]
    assert "runner_up_margin" in report["signal_profiles"]["val"]
    assert report["oracle_evaluation"]["test"]["rows"] > 0
    assert set(report["oracle_evaluation"]["test"]["per_family"]) == {"DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"}
    assert report["unknown_signal_evidence"]["ood_attack_holdout"]["rows"] == 2
    assert set(report["unknown_signal_evidence"]["ood_attack_holdout"]["by_true_family"]) == {"BruteForce", "Recon"}
    assert (
        report["unknown_signal_evidence"]["ood_attack_holdout"]["top1_confidence"]["mean"]
        < report["signal_profiles"]["test"]["top1_confidence"]["mean"]
    )
    assert (
        report["unknown_signal_evidence"]["ood_attack_holdout"]["runner_up_margin"]["mean"]
        < report["signal_profiles"]["test"]["runner_up_margin"]["mean"]
    )


def test_sample_train_split_preserves_all_present_known_labels(tmp_path: Path) -> None:
    source_root = _build_source_root(tmp_path / "source")
    derived_root = tmp_path / "family_views"
    run_pipeline(Namespace(source_root=source_root, output_root=derived_root))

    index = train_family.load_family_view_index(derived_root)
    feature_columns = train_family.load_feature_columns(derived_root, index)
    label_index = train_family.build_label_index(["DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"])
    train_split_path = train_family.resolve_view_split_path(derived_root, index, "attack_only", "train")

    X_train, y_train, summary = train_family.sample_train_split(
        train_split_path,
        feature_columns,
        label_index,
        seed=7,
        max_rows=5,
        batch_size=16,
    )

    assert len(X_train) == 5
    assert set(y_train.tolist()) == {0, 1, 2, 3, 4}
    assert set(summary["source_label_presence"]) == {"0", "1", "2", "3", "4"}


def test_train_iot_diad_family_classifier_rejects_absolute_feature_schema_path(tmp_path: Path) -> None:
    source_root = _build_source_root(tmp_path / "source")
    derived_root = tmp_path / "family_views"
    run_pipeline(Namespace(source_root=source_root, output_root=derived_root))

    index_path = derived_root / "manifests" / "family_view_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["feature_schema_path"] = str((tmp_path / "outside_feature_columns.json").resolve())
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="relative to dataset_root"):
        train_family.run_training(
            Namespace(
                dataset_root=derived_root,
                output_root=tmp_path / "modeling",
                view_name="attack_only",
                seed=7,
                batch_size=16,
                max_train_rows=64,
                iterations=20,
                learning_rate=0.2,
                depth=4,
                l2_leaf_reg=1.0,
                thread_count=1,
            )
        )


def test_train_iot_diad_family_classifier_rejects_parent_escape_split_path(tmp_path: Path) -> None:
    source_root = _build_source_root(tmp_path / "source")
    derived_root = tmp_path / "family_views"
    run_pipeline(Namespace(source_root=source_root, output_root=derived_root))

    index_path = derived_root / "manifests" / "family_view_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["views"]["attack_only"]["split_paths"]["train"] = r"..\outside\train.parquet"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="must not escape dataset_root"):
        train_family.run_training(
            Namespace(
                dataset_root=derived_root,
                output_root=tmp_path / "modeling",
                view_name="attack_only",
                seed=7,
                batch_size=16,
                max_train_rows=64,
                iterations=20,
                learning_rate=0.2,
                depth=4,
                l2_leaf_reg=1.0,
                thread_count=1,
            )
        )


def test_train_iot_diad_family_classifier_help_smoke() -> None:
    completed = run_python_module_help("scripts.train_iot_diad_family_classifier")
    assert_help_smoke(completed, "scripts.train_iot_diad_family_classifier")
    assert "usage:" in completed.stdout.lower()
