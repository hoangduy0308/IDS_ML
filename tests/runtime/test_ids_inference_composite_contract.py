from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ids.core.model_bundle import (
    build_composite_inference_contract_metadata,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)
from ids.runtime.inference import IDSInferencer, IDSModelConfig, build_model_config


def _write_legacy_bundle(bundle_root: Path) -> Path:
    bundle_root.mkdir(parents=True, exist_ok=True)
    feature_columns_path = bundle_root / "feature_columns.json"
    feature_columns_path.write_text(json.dumps({"feature_columns": ["f1", "f2"]}), encoding="utf-8")
    (bundle_root / "model.cbm").write_text("legacy", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "bundle_name": "legacy-bundle",
                "created_at": "2026-03-29T00:00:00+07:00",
                "model_key": "catboost_full_data",
                "model_family": "CatBoostClassifier",
                "model_artifact": "model.cbm",
                "feature_columns_file": "feature_columns.json",
                "threshold": 0.5,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "feature_count": 2,
                "train_rows": 123,
                "metrics_file": "metrics.json",
                "training_summary_file": "training_summary.json",
                "compatibility": {
                    "feature_schema": build_feature_schema_metadata(feature_columns_path),
                    "inference_contract": build_inference_contract_metadata(
                        positive_label="Attack",
                        negative_label="Benign",
                        threshold=0.5,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return bundle_root


def _write_composite_bundle(bundle_root: Path) -> Path:
    bundle_root.mkdir(parents=True, exist_ok=True)
    stage1_feature_columns_path = bundle_root / "stage1_feature_columns.json"
    stage2_feature_columns_path = bundle_root / "stage2_feature_columns.json"
    stage1_feature_columns_path.write_text(json.dumps({"feature_columns": ["f1", "f2"]}), encoding="utf-8")
    stage2_feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", "f2", "f3"]}),
        encoding="utf-8",
    )
    (bundle_root / "stage1_model.cbm").write_text("stage1", encoding="utf-8")
    (bundle_root / "stage2_model.cbm").write_text("stage2", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "bundle_name": "composite-bundle",
                "created_at": "2026-03-29T00:00:00+07:00",
                "model_key": "catboost_full_data",
                "model_family": "CatBoostClassifier",
                "model_artifact": "stage1_model.cbm",
                "feature_columns_file": "stage1_feature_columns.json",
                "threshold": 0.5,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "feature_count": 2,
                "train_rows": 123,
                "metrics_file": "metrics.json",
                "training_summary_file": "training_summary.json",
                "compatibility": {
                    "feature_schema": build_feature_schema_metadata(stage1_feature_columns_path),
                    "inference_contract": build_composite_inference_contract_metadata(
                        positive_label="Attack",
                        negative_label="Benign",
                        threshold=0.5,
                        stage2_model_artifact="stage2_model.cbm",
                        stage2_feature_columns_path=stage2_feature_columns_path,
                        top1_confidence_threshold=0.55,
                        runner_up_margin_threshold=0.30,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return bundle_root


class CompositeDummyCatBoost:
    def __init__(self) -> None:
        self.loaded_path: Path | None = None

    def load_model(self, path: Path) -> None:
        self.loaded_path = Path(path)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        assert self.loaded_path is not None
        if self.loaded_path.name in {"stage1_model.cbm", "model.cbm"}:
            attack_scores = frame["f1"].to_numpy(dtype=np.float32)
            return np.column_stack([1.0 - attack_scores, attack_scores])
        if self.loaded_path.name == "stage2_model.cbm":
            rows = []
            for f1, f2, f3 in frame.loc[:, ["f1", "f2", "f3"]].to_numpy(dtype=np.float32):
                if f3 > 0.5:
                    rows.append([0.6, 0.25, 0.15])
                else:
                    rows.append([0.51, 0.3, 0.19])
            return np.asarray(rows, dtype=np.float32)
        raise AssertionError(f"Unexpected model path: {self.loaded_path}")


class ExplodingCompositeDummyCatBoost(CompositeDummyCatBoost):
    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:  # type: ignore[override]
        assert self.loaded_path is not None
        if self.loaded_path.name == "stage2_model.cbm":
            raise RuntimeError("family stage failed")
        return super().predict_proba(frame)


def test_composite_bundle_emits_known_unknown_and_benign_states(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle_root = _write_composite_bundle(tmp_path / "composite")
    monkeypatch.setattr("ids.runtime.inference.CatBoostClassifier", CompositeDummyCatBoost)

    inferencer = IDSInferencer(IDSModelConfig.from_bundle(bundle_root))
    frame = pd.DataFrame(
        {
            "f1": [0.9, 0.8, 0.1],
            "f2": [0.2, 0.2, 0.7],
            "f3": [1.0, 0.0, 1.0],
        }
    )

    result = inferencer.predict(frame, include_input=False)

    assert result.columns.tolist() == [
        "attack_score",
        "predicted_label",
        "is_alert",
        "threshold",
        "attack_family",
        "attack_family_confidence",
        "attack_family_margin",
        "family_status",
    ]
    assert result["family_status"].tolist() == ["known", "unknown", "benign"]
    assert result.loc[0, "attack_family"] == "DDoS"
    assert result.loc[1, "attack_family"] is None or pd.isna(result.loc[1, "attack_family"])
    assert result.loc[2, "attack_family"] is None or pd.isna(result.loc[2, "attack_family"])
    assert result.loc[0, "attack_family_confidence"] == pytest.approx(0.6)
    assert result.loc[0, "attack_family_margin"] == pytest.approx(0.35)
    assert result.loc[1, "attack_family_confidence"] == pytest.approx(0.51)
    assert result.loc[1, "attack_family_margin"] == pytest.approx(0.21)
    assert pd.isna(result.loc[2, "attack_family_confidence"])
    assert pd.isna(result.loc[2, "attack_family_margin"])


def test_composite_bundle_fails_closed_when_stage2_scoring_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle_root = _write_composite_bundle(tmp_path / "composite")
    monkeypatch.setattr("ids.runtime.inference.CatBoostClassifier", ExplodingCompositeDummyCatBoost)

    inferencer = IDSInferencer(IDSModelConfig.from_bundle(bundle_root))
    frame = pd.DataFrame({"f1": [0.9], "f2": [0.2], "f3": [1.0]})

    with pytest.raises(RuntimeError, match="family stage failed"):
        inferencer.predict(frame, include_input=False)


def test_legacy_binary_bundle_stays_binary_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle_root = _write_legacy_bundle(tmp_path / "legacy")
    monkeypatch.setattr("ids.runtime.inference.CatBoostClassifier", CompositeDummyCatBoost)

    inferencer = IDSInferencer(IDSModelConfig.from_bundle(bundle_root))
    frame = pd.DataFrame({"f1": [0.2, 0.8], "f2": [0.5, 0.5]})

    result = inferencer.predict(frame, include_input=False)

    assert result.columns.tolist() == ["attack_score", "predicted_label", "is_alert", "threshold"]
    assert result["predicted_label"].tolist() == ["Benign", "Attack"]
