from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd

from ml_pipeline.data_prep.prepare_iot_diad_family_views import run_pipeline
from ml_pipeline.training import train_iot_diad_direct_multiclass as train_direct
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
            _make_record(source_file="BruteForce/bf0.csv", attack_family="BruteForce", attack_scenario="BruteForce", derived_label_binary="Attack", derived_label_family="BruteForce", split="ood_attack_holdout", base=7.0),
            _make_record(source_file="Recon/r0.csv", attack_family="Recon", attack_scenario="Recon", derived_label_binary="Attack", derived_label_family="Recon", split="ood_attack_holdout", base=8.0),
        ],
    )
    (manifests_dir / "feature_columns.json").write_text(json.dumps({"feature_columns": FEATURE_COLUMNS}), encoding="utf-8")
    (manifests_dir / "cleaning_report.json").write_text(
        json.dumps(
            {
                "label_distribution_by_split": {
                    "train": {"Benign": 1, "Attack": 2},
                    "val": {"Benign": 1, "Attack": 1},
                    "test": {"Benign": 1, "Attack": 1},
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


def test_train_iot_diad_direct_multiclass_writes_comparison_report(tmp_path: Path) -> None:
    source_root = _build_source_root(tmp_path / "source")
    derived_root = tmp_path / "family_views"
    run_pipeline(Namespace(source_root=source_root, output_root=derived_root))

    output_root = tmp_path / "modeling"
    train_direct.run_training(
        Namespace(
            dataset_root=derived_root,
            output_root=output_root,
            view_name="direct_multiclass",
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

    report_path = output_root / "reports" / "direct_multiclass_eval.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["model"]["kind"] == "CatBoostClassifier"
    assert "artifact_path" in report["model"]
    assert "direct_multiclass_evaluation" in report
    assert "comparison_summary" in report
    assert report["source_contract"]["label_space"][0] == "Benign"
    assert report["direct_multiclass_evaluation"]["test"]["rows"] > 0
    assert "top1_confidence" in report["direct_multiclass_evaluation"]["test"]
    assert "runner_up_margin" in report["direct_multiclass_evaluation"]["test"]
    assert set(report["direct_multiclass_evaluation"]["test"]["per_family"]) == {"Benign", "DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"}
    assert report["comparison_summary"]["test"]["rows"] == report["direct_multiclass_evaluation"]["test"]["rows"]
    assert report["comparison_summary"]["test"]["accuracy"] >= 0.0
    assert report["comparison_summary"]["test"]["macro_f1"] >= 0.0
    assert report["comparison_summary"]["test"]["weighted_f1"] >= report["comparison_summary"]["test"]["macro_f1"]
    assert report["comparison_summary"]["ood_attack_holdout"]["rows"] == 2
    assert report["comparison_summary"]["ood_attack_holdout"]["predicted_family_counts"]
    assert set(report["comparison_summary"]["ood_attack_holdout"]["predicted_family_counts"]).issubset(
        {"Benign", "DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"}
    )


def test_train_iot_diad_direct_multiclass_help_smoke() -> None:
    completed = run_python_module_help("scripts.train_iot_diad_direct_multiclass")
    assert_help_smoke(completed, "scripts.train_iot_diad_direct_multiclass")
    assert "usage:" in completed.stdout.lower()
