from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import json

import numpy as np
import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.core import path_defaults as path_defaults_module  # noqa: E402
import ids.runtime.inference as inference_module  # noqa: E402
from ids.runtime.inference import (  # noqa: E402
    ActiveBundleResolutionError,
    IDSInferencer,
    IDSModelConfig,
    build_inferencer,
    build_model_config,
    main,
)
from ids.core.model_bundle import (  # noqa: E402
    ModelBundleContractError,
    build_composite_inference_contract_metadata,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)
from ids.ops.model_bundle_lifecycle import (  # noqa: E402
    DEFAULT_ACTIVATION_RECORD_NAME,
    build_activation_record_payload,
    write_activation_record,
)


def write_feature_columns(path: Path) -> None:
    path.write_text(json.dumps({"feature_columns": ["f1", "f2"]}), encoding="utf-8")


def write_bundle_manifest(
    bundle_root: Path,
    *,
    threshold: float = 0.5,
    positive_label: str = "Attack",
    negative_label: str = "Benign",
) -> None:
    feature_columns_path = bundle_root / "feature_columns.json"
    write_feature_columns(feature_columns_path)
    payload = {
        "manifest_version": 2,
        "bundle_name": "bundle-under-test",
        "created_at": "2026-03-29T00:00:00+07:00",
        "model_key": "catboost_full_data",
        "model_family": "CatBoostClassifier",
        "model_artifact": "model.cbm",
        "feature_columns_file": "feature_columns.json",
        "threshold": threshold,
        "positive_label": positive_label,
        "negative_label": negative_label,
        "feature_count": 2,
        "train_rows": 123,
        "metrics_file": "metrics.json",
        "training_summary_file": "training_summary.json",
        "compatibility": {
            "feature_schema": build_feature_schema_metadata(feature_columns_path),
            "inference_contract": build_inference_contract_metadata(
                positive_label=positive_label,
                negative_label=negative_label,
                threshold=threshold,
            ),
        },
    }
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def write_composite_bundle_manifest(bundle_root: Path) -> None:
    stage1_feature_columns_path = bundle_root / "stage1_feature_columns.json"
    stage2_feature_columns_path = bundle_root / "stage2_feature_columns.json"
    stage1_feature_columns_path.write_text(json.dumps({"feature_columns": ["f1", "f2"]}), encoding="utf-8")
    stage2_feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", "f2", "f3"]}),
        encoding="utf-8",
    )
    (bundle_root / "stage1_model.cbm").write_text("placeholder-stage1", encoding="utf-8")
    (bundle_root / "stage2_model.cbm").write_text("placeholder-stage2", encoding="utf-8")
    payload = {
        "manifest_version": 2,
        "bundle_name": "bundle-under-test",
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
                runner_up_margin_threshold=0.3,
            ),
        },
    }
    (bundle_root / "model_bundle.json").write_text(json.dumps(payload), encoding="utf-8")


def _reload_inference_modules(monkeypatch: pytest.MonkeyPatch, repo_root: Path | None) -> None:
    env_var = path_defaults_module.DEFAULT_REPO_ROOT_ENV_VAR
    if repo_root is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, str(repo_root))

    importlib.reload(path_defaults_module)
    importlib.reload(inference_module)


def _load_temp_inference_module() -> object:
    spec = importlib.util.spec_from_file_location(
        "_temp_ids_runtime_inference",
        inference_module.__file__,
    )
    assert spec is not None and spec.loader is not None
    temp_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = temp_module
    spec.loader.exec_module(temp_module)
    return temp_module


class DummyInferencer:
    feature_columns = ["f1", "f2"]

    def __init__(self, threshold: float = 0.5) -> None:
        self.config = type("Config", (), {"threshold": threshold, "positive_label": "Attack", "negative_label": "Benign"})()

    def align_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = [column for column in self.feature_columns if column not in frame.columns]
        if missing:
            raise ValueError(
                "Input frame is missing required feature columns: " + ", ".join(missing)
            )
        aligned = frame.loc[:, self.feature_columns].copy()
        for column in self.feature_columns:
            aligned[column] = pd.to_numeric(aligned[column], errors="coerce")
        if aligned.isna().any().any():
            bad_columns = aligned.columns[aligned.isna().any()].tolist()
            raise ValueError(
                "Input frame contains non-numeric or missing values after alignment in columns: "
                + ", ".join(bad_columns)
            )
        return aligned.astype("float32")

    def score_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        aligned = self.align_features(frame)
        attack_scores = aligned["f1"].to_numpy()
        alerts = attack_scores >= self.config.threshold
        labels = ["Attack" if alert else "Benign" for alert in alerts]
        return pd.DataFrame(
            {
                "attack_score": attack_scores,
                "predicted_label": labels,
                "is_alert": alerts,
                "threshold": self.config.threshold,
            }
        )

    predict = IDSInferencer.predict


class DummyCompositeCatBoost:
    def __init__(self) -> None:
        self.loaded_path: Path | None = None

    def load_model(self, path: Path) -> None:
        self.loaded_path = Path(path)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        assert self.loaded_path is not None
        if self.loaded_path.name == "stage1_model.cbm":
            attack_scores = frame["f1"].to_numpy(dtype=np.float32)
            return np.column_stack([1.0 - attack_scores, attack_scores])
        if self.loaded_path.name == "stage2_model.cbm":
            values = frame.loc[:, ["f1", "f2", "f3"]].to_numpy(dtype=np.float32)
            rows: list[list[float]] = []
            for f1, f2, f3 in values:
                if f3 > 0.5:
                    rows.append([0.6, 0.25, 0.15])
                else:
                    rows.append([0.51, 0.3, 0.19])
            return np.asarray(rows, dtype=np.float32)
        raise AssertionError(f"Unexpected model path: {self.loaded_path}")


def test_align_features_reorders_and_converts_numeric() -> None:
    inferencer = DummyInferencer()
    frame = pd.DataFrame({"f2": ["2"], "f1": ["1"], "extra": [99]})

    aligned = inferencer.align_features(frame)

    assert list(aligned.columns) == ["f1", "f2"]
    assert aligned.iloc[0].tolist() == [1.0, 2.0]


def test_align_features_fails_when_required_column_missing() -> None:
    inferencer = DummyInferencer()
    frame = pd.DataFrame({"f1": [0.1]})

    with pytest.raises(ValueError, match="missing required feature columns"):
        inferencer.align_features(frame)


def test_predict_appends_alert_columns() -> None:
    inferencer = DummyInferencer(threshold=0.5)
    frame = pd.DataFrame({"f1": [0.2, 0.8], "f2": [1, 2]})

    result = inferencer.predict(frame, include_input=True)

    assert result["predicted_label"].tolist() == ["Benign", "Attack"]
    assert result["is_alert"].tolist() == [False, True]
    assert result["threshold"].tolist() == [0.5, 0.5]


def test_predict_appends_family_columns_for_composite_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "stage1_model.cbm").write_text("stage1", encoding="utf-8")
    write_composite_bundle_manifest(bundle_root)

    monkeypatch.setattr("ids.runtime.inference.CatBoostClassifier", DummyCompositeCatBoost)

    inferencer = IDSInferencer(IDSModelConfig.from_bundle(bundle_root))
    frame = pd.DataFrame(
        {
            "f1": [0.9, 0.8, 0.1],
            "f2": [0.2, 0.2, 0.7],
            "f3": [1.0, 0.0, 1.0],
        }
    )

    result = inferencer.predict(frame, include_input=False)

    assert result["predicted_label"].tolist() == ["Attack", "Attack", "Benign"]
    assert result["family_status"].tolist() == ["known", "unknown", "benign"]
    assert result.loc[0, "attack_family"] == "DDoS"
    assert result.loc[0, "attack_family_confidence"] == pytest.approx(0.6)
    assert result.loc[0, "attack_family_margin"] == pytest.approx(0.35)
    assert pd.isna(result.loc[1, "attack_family"])
    assert result.loc[1, "attack_family_confidence"] == pytest.approx(0.51)
    assert result.loc[1, "attack_family_margin"] == pytest.approx(0.21)
    assert pd.isna(result.loc[2, "attack_family"])
    assert pd.isna(result.loc[2, "attack_family_confidence"])
    assert pd.isna(result.loc[2, "attack_family_margin"])


def test_composite_inference_fails_closed_when_family_stage_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "stage1_model.cbm").write_text("stage1", encoding="utf-8")
    write_composite_bundle_manifest(bundle_root)

    class ExplodingCompositeCatBoost(DummyCompositeCatBoost):
        def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:  # type: ignore[override]
            assert self.loaded_path is not None
            if self.loaded_path.name == "stage2_model.cbm":
                raise RuntimeError("family stage failed")
            return super().predict_proba(frame)

    monkeypatch.setattr("ids.runtime.inference.CatBoostClassifier", ExplodingCompositeCatBoost)

    inferencer = IDSInferencer(IDSModelConfig.from_bundle(bundle_root))
    frame = pd.DataFrame({"f1": [0.9], "f2": [0.2], "f3": [1.0]})

    with pytest.raises(RuntimeError, match="family stage failed"):
        inferencer.predict(frame, include_input=False)


def test_model_config_can_load_from_bundle(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    write_bundle_manifest(bundle_root)

    config = IDSModelConfig.from_bundle(bundle_root)

    assert config.model_path == (bundle_root / "model.cbm").resolve()
    assert config.feature_columns_path == (bundle_root / "feature_columns.json").resolve()
    assert config.threshold == 0.5
    assert config.bundle_root == bundle_root.resolve()


def test_model_config_can_load_composite_bundle(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "stage1_model.cbm").write_text("stage1", encoding="utf-8")
    write_composite_bundle_manifest(bundle_root)

    config = IDSModelConfig.from_bundle(bundle_root)

    assert config.model_path == (bundle_root / "stage1_model.cbm").resolve()
    assert config.family_model_path == (bundle_root / "stage2_model.cbm").resolve()
    assert config.family_feature_columns_path == (
        bundle_root / "stage2_feature_columns.json"
    ).resolve()
    assert config.family_top1_confidence_threshold == pytest.approx(0.55)
    assert config.family_runner_up_margin_threshold == pytest.approx(0.3)
    assert config.family_closed_set_labels == ("DDoS", "DoS", "Mirai", "Spoofing", "Web-Based")


def test_build_model_config_rejects_mixed_bundle_and_config_inputs(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    write_bundle_manifest(bundle_root, threshold=0.75)
    unused_config = tmp_path / "unused.json"
    unused_config.write_text(
        '{"model_artifact":"unused.cbm","feature_columns_file":"unused_columns.json","threshold":0.1}',
        encoding="utf-8",
    )

    with pytest.raises(
        ModelBundleContractError,
        match="Specify only one canonical model contract source",
    ):
        build_model_config(bundle_root=bundle_root, config_path=unused_config)


def test_build_model_config_supports_config_path(tmp_path: Path) -> None:
    config_path = tmp_path / "bundle" / "model_bundle.json"
    config_path.parent.mkdir(parents=True)
    (config_path.parent / "model.cbm").write_text("placeholder", encoding="utf-8")
    write_bundle_manifest(config_path.parent, threshold=0.25, positive_label="Alert")

    config = build_model_config(config_path=config_path)

    assert config.model_path == (config_path.parent / "model.cbm").resolve()
    assert config.feature_columns_path == (config_path.parent / "feature_columns.json").resolve()
    assert config.threshold == 0.25
    assert config.positive_label == "Alert"


def test_build_inferencer_uses_resolved_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    write_bundle_manifest(bundle_root)

    loaded_models: list[Path] = []

    class DummyModel:
        def load_model(self, path: Path) -> None:
            loaded_models.append(Path(path))

    monkeypatch.setattr("ids.runtime.inference.CatBoostClassifier", DummyModel)

    inferencer = build_inferencer(bundle_root=bundle_root)

    assert inferencer.config.model_path == (bundle_root / "model.cbm").resolve()
    assert inferencer.feature_columns == ["f1", "f2"]
    assert loaded_models == [(bundle_root / "model.cbm").resolve()]


def test_build_model_config_supports_activation_path(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    write_bundle_manifest(bundle_root, threshold=0.4)
    activation_path = tmp_path / DEFAULT_ACTIVATION_RECORD_NAME
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=bundle_root,
            active_bundle_name="bundle-under-test",
            activated_at="2026-03-29T00:00:00+07:00",
        ),
    )

    config = build_model_config(activation_path=activation_path)

    assert config.bundle_root == bundle_root.resolve()
    assert config.threshold == 0.4


def test_build_model_config_prefers_default_activation_path_when_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    write_bundle_manifest(bundle_root, threshold=0.65)
    activation_path = tmp_path / DEFAULT_ACTIVATION_RECORD_NAME
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=bundle_root,
            active_bundle_name="bundle-under-test",
            activated_at="2026-03-29T00:00:00+07:00",
        ),
    )
    monkeypatch.setattr("ids.runtime.inference.DEFAULT_ACTIVATION_PATH", activation_path)

    config = build_model_config()

    assert config.bundle_root == bundle_root.resolve()
    assert config.threshold == 0.65


def test_build_model_config_fails_closed_when_default_activation_path_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_activation_path = tmp_path / DEFAULT_ACTIVATION_RECORD_NAME
    monkeypatch.setattr("ids.runtime.inference.DEFAULT_ACTIVATION_PATH", missing_activation_path)

    with pytest.raises(ActiveBundleResolutionError, match="Activation record not found"):
        build_model_config()


def test_build_model_config_rejects_external_overrides_when_bundle_used(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    write_bundle_manifest(bundle_root)

    with pytest.raises(
        ModelBundleContractError,
        match="cannot be mixed with external model/schema/threshold overrides",
    ):
        build_model_config(
            bundle_root=bundle_root,
            model_path=tmp_path / "other_model.cbm",
        )


def test_runtime_inference_defaults_follow_repo_root_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = (tmp_path / "override-root").resolve()

    _reload_inference_modules(monkeypatch, repo_root)
    temp_module = _load_temp_inference_module()

    expected_bundle_root = repo_root / "artifacts" / "final_model" / "catboost_full_data_v1"
    assert temp_module.DEFAULT_MODEL_PATH == expected_bundle_root / "model.cbm"
    assert (
        temp_module.DEFAULT_FEATURE_COLUMNS_PATH
        == expected_bundle_root / "feature_columns.json"
    )

    config = temp_module.build_model_config(
        model_path=None,
        feature_columns_path=None,
        threshold=0.42,
    )

    assert config.model_path == expected_bundle_root / "model.cbm"
    assert config.feature_columns_path == expected_bundle_root / "feature_columns.json"


def test_runtime_inference_defaults_fall_back_to_checkout_when_env_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reload_inference_modules(monkeypatch, None)
    temp_module = _load_temp_inference_module()

    checkout_root = REPO_ROOT
    expected_bundle_root = checkout_root / "artifacts" / "final_model" / "catboost_full_data_v1"
    assert temp_module.DEFAULT_MODEL_PATH == expected_bundle_root / "model.cbm"
    assert (
        temp_module.DEFAULT_FEATURE_COLUMNS_PATH
        == expected_bundle_root / "feature_columns.json"
    )

    config = temp_module.build_model_config(
        model_path=None,
        feature_columns_path=None,
        threshold=0.42,
    )

    assert config.model_path == expected_bundle_root / "model.cbm"
    assert config.feature_columns_path == expected_bundle_root / "feature_columns.json"


def test_ids_inference_main_preserves_cli_output_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_path.write_text("f1,f2,trace_id\n0.2,1,row-a\n0.8,2,row-b\n", encoding="utf-8")

    class DummyCLIInferencer(DummyInferencer):
        def __init__(self, config: object) -> None:
            super().__init__(threshold=0.5)
            self.config = type(
                "Config",
                (),
                {
                    "threshold": 0.5,
                    "positive_label": "Attack",
                    "negative_label": "Benign",
                    "model_path": Path("dummy_model.cbm"),
                },
            )()
            self.feature_columns = ["f1", "f2"]

    monkeypatch.setattr(
        "ids.runtime.inference.build_model_config",
        lambda **_: type(
            "Config",
            (),
            {
                "threshold": 0.5,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "model_path": Path("dummy_model.cbm"),
                "feature_columns_path": Path("dummy_features.json"),
            },
        )(),
    )
    monkeypatch.setattr("ids.runtime.inference.IDSInferencer", DummyCLIInferencer)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ids_inference.py",
            "--input-path",
            str(input_path),
            "--output-path",
            str(output_path),
        ],
    )

    main()

    summary = capsys.readouterr().out
    result = pd.read_csv(output_path)

    assert "\"rows_scored\": 2" in summary
    assert "\"alert_rows\": 1" in summary
    assert result["predicted_label"].tolist() == ["Benign", "Attack"]
    assert result["trace_id"].tolist() == ["row-a", "row-b"]
