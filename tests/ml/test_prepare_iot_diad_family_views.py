from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ml_pipeline.data_prep.prepare_iot_diad_family_views import run_pipeline
from wrapper_smoke_support import assert_help_smoke, run_python_module_help


FEATURE_COLUMNS = ["f1", "f2"]


def _frame(rows: list[tuple[float, float, str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=[
            "f1",
            "f2",
            "derived_label_binary",
            "derived_label_family",
            "split",
        ],
    ).assign(attack_family=lambda frame: frame["derived_label_family"], attack_scenario=lambda frame: frame["derived_label_family"])


def _build_binary_artifact_root(root: Path) -> Path:
    clean_dir = root / "clean"
    manifests_dir = root / "manifests"
    clean_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    train = _frame(
        [
            (0.0, 0.1, "Benign", "Benign", "train"),
            (0.1, 0.2, "Attack", "DDoS", "train"),
            (0.2, 0.3, "Attack", "Mirai", "train"),
        ]
    )
    val = _frame(
        [
            (0.3, 0.4, "Benign", "Benign", "val"),
            (0.4, 0.5, "Attack", "DoS", "val"),
        ]
    )
    test = _frame(
        [
            (0.5, 0.6, "Benign", "Benign", "test"),
            (0.6, 0.7, "Attack", "Spoofing", "test"),
        ]
    )
    ood = _frame(
        [
            (0.7, 0.8, "Attack", "BruteForce", "ood_attack_holdout"),
            (0.8, 0.9, "Attack", "Recon", "ood_attack_holdout"),
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
        json.dumps({"label_distribution_by_split": {}}),
        encoding="utf-8",
    )
    return root


def test_prepare_iot_diad_family_views_derives_distinct_views(tmp_path: Path) -> None:
    source_root = _build_binary_artifact_root(tmp_path / "binary")
    output_root = tmp_path / "family_views"

    summary = run_pipeline(source_root=source_root, output_root=output_root, batch_size=2)

    index_path = output_root / "manifests" / "family_view_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))

    assert summary["family_view_index"] == str(index_path.resolve())
    assert index["views"]["attack_only_family"]["includes_benign"] is False
    assert index["views"]["direct_multiclass"]["includes_benign"] is True
    assert index["views"]["attack_only_family"]["closed_set_labels"] == ["DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"]
    assert index["views"]["direct_multiclass"]["closed_set_labels"][0] == "Benign"
    assert index["ood_probe_families"] == ["BruteForce", "Recon"]

    attack_only_train = pd.read_parquet(output_root / "clean" / "attack_only_family" / "train.parquet")
    direct_train = pd.read_parquet(output_root / "clean" / "direct_multiclass" / "train.parquet")
    ood_attack_only = pd.read_parquet(output_root / "clean" / "attack_only_family" / "ood_attack_holdout.parquet")

    assert list(attack_only_train["derived_label_family"]) == ["DDoS", "Mirai"]
    assert list(direct_train["derived_label_family"]) == ["Benign", "DDoS", "Mirai"]
    assert set(ood_attack_only["derived_label_family"]) == {"BruteForce", "Recon"}

    attack_counts = json.loads((output_root / "reports" / "attack_only_family_counts.json").read_text(encoding="utf-8"))
    direct_counts = json.loads((output_root / "reports" / "direct_multiclass_counts.json").read_text(encoding="utf-8"))

    assert attack_counts["split_summaries"]["train"]["written_label_counts"] == {"DDoS": 1, "Mirai": 1}
    assert direct_counts["split_summaries"]["train"]["written_label_counts"] == {"Benign": 1, "DDoS": 1, "Mirai": 1}
    assert attack_counts["split_summaries"]["ood_attack_holdout"]["written_label_counts"] == {"BruteForce": 1, "Recon": 1}


def test_prepare_iot_diad_family_views_help_smoke() -> None:
    completed = run_python_module_help("scripts.prepare_iot_diad_family_views")
    assert_help_smoke(completed, "scripts.prepare_iot_diad_family_views")
    assert completed.stdout.strip()
    assert "usage:" in completed.stdout.lower()
