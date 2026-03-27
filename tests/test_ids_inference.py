from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_inference import (  # noqa: E402
    IDSInferencer,
    IDSModelConfig,
    build_inferencer,
    build_model_config,
    main,
)


class DummyInferencer:
    feature_columns = ["f1", "f2"]

    def __init__(self, threshold: float = 0.5) -> None:
        self.config = type("Config", (), {"threshold": threshold, "positive_label": "Attack", "negative_label": "Benign"})()

    align_features = IDSInferencer.align_features

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


def test_model_config_can_load_from_bundle(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    (bundle_root / "feature_columns.json").write_text('{"feature_columns":["f1","f2"]}', encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        '{"model_artifact":"model.cbm","feature_columns_file":"feature_columns.json","threshold":0.5,"positive_label":"Attack","negative_label":"Benign"}',
        encoding="utf-8",
    )

    config = IDSModelConfig.from_bundle(bundle_root)

    assert config.model_path == (bundle_root / "model.cbm").resolve()
    assert config.feature_columns_path == (bundle_root / "feature_columns.json").resolve()
    assert config.threshold == 0.5


def test_build_model_config_prefers_bundle_root(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    (bundle_root / "feature_columns.json").write_text('{"feature_columns":["f1","f2"]}', encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        '{"model_artifact":"model.cbm","feature_columns_file":"feature_columns.json","threshold":0.75,"positive_label":"Attack","negative_label":"Benign"}',
        encoding="utf-8",
    )
    unused_config = tmp_path / "unused.json"
    unused_config.write_text(
        '{"model_artifact":"unused.cbm","feature_columns_file":"unused_columns.json","threshold":0.1}',
        encoding="utf-8",
    )

    config = build_model_config(bundle_root=bundle_root, config_path=unused_config)

    assert config.model_path == (bundle_root / "model.cbm").resolve()
    assert config.feature_columns_path == (bundle_root / "feature_columns.json").resolve()
    assert config.threshold == 0.75


def test_build_model_config_supports_config_path(tmp_path: Path) -> None:
    config_path = tmp_path / "bundle" / "model_bundle.json"
    config_path.parent.mkdir(parents=True)
    (config_path.parent / "model.cbm").write_text("placeholder", encoding="utf-8")
    (config_path.parent / "feature_columns.json").write_text(
        '{"feature_columns":["f1","f2"]}',
        encoding="utf-8",
    )
    config_path.write_text(
        '{"model_artifact":"model.cbm","feature_columns_file":"feature_columns.json","threshold":0.25,"positive_label":"Alert","negative_label":"Benign"}',
        encoding="utf-8",
    )

    config = build_model_config(config_path=config_path)

    assert config.model_path == (config_path.parent / "model.cbm").resolve()
    assert config.feature_columns_path == (config_path.parent / "feature_columns.json").resolve()
    assert config.threshold == 0.25
    assert config.positive_label == "Alert"


def test_build_inferencer_uses_resolved_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    (bundle_root / "feature_columns.json").write_text('{"feature_columns":["f1","f2"]}', encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        '{"model_artifact":"model.cbm","feature_columns_file":"feature_columns.json","threshold":0.5,"positive_label":"Attack","negative_label":"Benign"}',
        encoding="utf-8",
    )

    loaded_models: list[Path] = []

    class DummyModel:
        def load_model(self, path: Path) -> None:
            loaded_models.append(Path(path))

    monkeypatch.setattr("scripts.ids_inference.CatBoostClassifier", DummyModel)

    inferencer = build_inferencer(bundle_root=bundle_root)

    assert inferencer.config.model_path == (bundle_root / "model.cbm").resolve()
    assert inferencer.feature_columns == ["f1", "f2"]
    assert loaded_models == [(bundle_root / "model.cbm").resolve()]


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
        "scripts.ids_inference.build_model_config",
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
    monkeypatch.setattr("scripts.ids_inference.IDSInferencer", DummyCLIInferencer)
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
