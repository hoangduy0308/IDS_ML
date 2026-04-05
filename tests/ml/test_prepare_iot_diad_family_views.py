from __future__ import annotations

import json
import tempfile
from argparse import Namespace
from pathlib import Path

import pandas as pd

import pytest

from ml_pipeline.data_prep.prepare_iot_diad_family_views import (
    assert_safe_output_root,
    run_pipeline,
)
from wrapper_smoke_support import assert_help_smoke, run_python_module_help


FEATURE_COLUMNS = ["f1", "f2"]
METADATA_COLUMNS = [
    "source_file",
    "attack_family",
    "attack_scenario",
    "derived_label_binary",
    "derived_label_family",
    "split",
]


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
        "f2": base + 0.5,
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
            _make_record(
                source_file="Benign/benign.csv",
                attack_family="Benign",
                attack_scenario="Benign",
                derived_label_binary="Benign",
                derived_label_family="Benign",
                split="train",
                base=0.0,
            ),
            _make_record(
                source_file="DoS/dos.csv",
                attack_family="DoS",
                attack_scenario="DoS",
                derived_label_binary="Attack",
                derived_label_family="DoS",
                split="train",
                base=1.0,
            ),
            _make_record(
                source_file="Mirai/mirai.csv",
                attack_family="Mirai",
                attack_scenario="Mirai",
                derived_label_binary="Attack",
                derived_label_family="Mirai",
                split="train",
                base=2.0,
            ),
        ],
    )
    _write_parquet(
        clean_dir / "val.parquet",
        [
            _make_record(
                source_file="Benign/benign_val.csv",
                attack_family="Benign",
                attack_scenario="Benign",
                derived_label_binary="Benign",
                derived_label_family="Benign",
                split="val",
                base=3.0,
            ),
            _make_record(
                source_file="Spoofing/spoof.csv",
                attack_family="Spoofing",
                attack_scenario="Spoofing",
                derived_label_binary="Attack",
                derived_label_family="Spoofing",
                split="val",
                base=4.0,
            ),
        ],
    )
    _write_parquet(
        clean_dir / "test.parquet",
        [
            _make_record(
                source_file="Benign/benign_test.csv",
                attack_family="Benign",
                attack_scenario="Benign",
                derived_label_binary="Benign",
                derived_label_family="Benign",
                split="test",
                base=5.0,
            ),
            _make_record(
                source_file="Web-Based/web.csv",
                attack_family="Web-Based",
                attack_scenario="Web-Based",
                derived_label_binary="Attack",
                derived_label_family="Web-Based",
                split="test",
                base=6.0,
            ),
        ],
    )
    _write_parquet(
        clean_dir / "ood_attack_holdout.parquet",
        [
            _make_record(
                source_file="BruteForce/brute.csv",
                attack_family="BruteForce",
                attack_scenario="BruteForce",
                derived_label_binary="Attack",
                derived_label_family="BruteForce",
                split="ood_attack_holdout",
                base=7.0,
            ),
            _make_record(
                source_file="Recon/recon.csv",
                attack_family="Recon",
                attack_scenario="Recon",
                derived_label_binary="Attack",
                derived_label_family="Recon",
                split="ood_attack_holdout",
                base=8.0,
            ),
        ],
    )
    (manifests_dir / "feature_columns.json").write_text(
        json.dumps({"feature_columns": FEATURE_COLUMNS}),
        encoding="utf-8",
    )
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
        "Benign/benign.csv,Benign,Benign,train\n"
        "DoS/dos.csv,DoS,DoS,train\n"
        "Mirai/mirai.csv,Mirai,Mirai,train\n"
        "Benign/benign_val.csv,Benign,Benign,val\n"
        "Spoofing/spoof.csv,Spoofing,Spoofing,val\n"
        "Benign/benign_test.csv,Benign,Benign,test\n"
        "Web-Based/web.csv,Web-Based,Web-Based,test\n"
        "BruteForce/brute.csv,BruteForce,BruteForce,ood_attack_holdout\n"
        "Recon/recon.csv,Recon,Recon,ood_attack_holdout\n",
        encoding="utf-8",
    )
    return source_root


def test_prepare_iot_diad_family_views_derives_attack_only_and_multiclass_views(tmp_path: Path) -> None:
    source_root = _build_source_root(tmp_path / "source")
    output_root = tmp_path / "derived"

    run_pipeline(
        Namespace(
            source_root=source_root,
            output_root=output_root,
        )
    )

    index = json.loads((output_root / "manifests" / "family_view_index.json").read_text(encoding="utf-8"))
    assert index["feature_schema_path"] == "manifests/feature_columns.json"
    assert index["views"]["attack_only"]["split_paths"]["train"] == "attack_only/clean/train.parquet"
    assert index["views"]["direct_multiclass"]["split_paths"]["train"] == "direct_multiclass/clean/train.parquet"
    assert index["views"]["attack_only"]["label_space"] == ["DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"]
    assert index["views"]["direct_multiclass"]["label_space"] == [
        "Benign",
        "DDoS",
        "DoS",
        "Mirai",
        "Spoofing",
        "Web-Based",
    ]

    attack_train = pd.read_parquet(output_root / "attack_only" / "clean" / "train.parquet")
    direct_train = pd.read_parquet(output_root / "direct_multiclass" / "clean" / "train.parquet")
    ood_holdout = pd.read_parquet(output_root / "attack_only" / "clean" / "ood_attack_holdout.parquet")

    assert set(attack_train["derived_label_family"]) == {"DoS", "Mirai"}
    assert "Benign" not in set(attack_train["derived_label_family"])
    assert set(direct_train["derived_label_family"]) == {"Benign", "DoS", "Mirai"}
    assert set(ood_holdout["derived_label_family"]) == {"BruteForce", "Recon"}
    assert index["views"]["attack_only"]["split_semantics"]["ood_attack_holdout"].startswith("Rows from source ood_attack_holdout")


def test_prepare_iot_diad_family_views_help_smoke() -> None:
    completed = run_python_module_help("scripts.prepare_iot_diad_family_views")
    assert_help_smoke(completed, "scripts.prepare_iot_diad_family_views")
    assert completed.stdout.strip()
    assert "usage:" in completed.stdout.lower()


def test_prepare_iot_diad_family_views_rejects_unexpected_known_split_label(tmp_path: Path) -> None:
    source_root = _build_source_root(tmp_path / "source")
    output_root = tmp_path / "derived"
    train_path = source_root / "clean" / "train.parquet"
    train_frame = pd.read_parquet(train_path)
    injected = _make_record(
        source_file="Recon/recon-train.csv",
        attack_family="Recon",
        attack_scenario="Recon",
        derived_label_binary="Attack",
        derived_label_family="Recon",
        split="train",
        base=9.0,
    )
    pd.concat([train_frame, pd.DataFrame([injected])], ignore_index=True).to_parquet(train_path, index=False)

    with pytest.raises(ValueError, match="unexpected labels"):
        run_pipeline(Namespace(source_root=source_root, output_root=output_root))


def test_prepare_iot_diad_family_views_fails_when_split_filters_to_empty(tmp_path: Path) -> None:
    source_root = _build_source_root(tmp_path / "source")
    output_root = tmp_path / "derived"
    train_path = source_root / "clean" / "train.parquet"
    train_frame = pd.read_parquet(train_path)
    benign_only = train_frame[train_frame["derived_label_family"] == "Benign"].copy()
    benign_only.to_parquet(train_path, index=False)

    with pytest.raises(ValueError, match="produced no rows for split train"):
        run_pipeline(Namespace(source_root=source_root, output_root=output_root))


def test_prepare_iot_diad_family_views_rejects_unsafe_output_root() -> None:
    unsafe_root = Path(tempfile.gettempdir()).resolve()

    with pytest.raises(ValueError, match="Refusing to operate on approved root directly"):
        assert_safe_output_root(unsafe_root)
