from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from catboost import CatBoostClassifier


DEFAULT_MODEL_PATH = Path(
    r"F:\Work\IDS_ML_New\artifacts\kaggle\outputs\catboost_full_data_attempt"
    r"\catboost_full_data_attempt_results\catboost_full_data_attempt.cbm"
)
DEFAULT_FEATURE_COLUMNS_PATH = Path(
    r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary\manifests\feature_columns.json"
)
DEFAULT_BUNDLE_CONFIG_NAME = "model_bundle.json"
DEFAULT_THRESHOLD = 0.5

PREDICTION_COLUMNS = ["attack_score", "predicted_label", "is_alert", "threshold"]


@dataclass(frozen=True)
class IDSModelConfig:
    model_path: Path
    feature_columns_path: Path
    threshold: float = DEFAULT_THRESHOLD
    positive_label: str = "Attack"
    negative_label: str = "Benign"

    @classmethod
    def from_bundle(cls, bundle_root: Path) -> "IDSModelConfig":
        bundle_root = bundle_root.resolve()
        config_path = bundle_root / DEFAULT_BUNDLE_CONFIG_NAME
        payload = read_json(config_path)
        return cls(
            model_path=(bundle_root / payload["model_artifact"]).resolve(),
            feature_columns_path=(bundle_root / payload["feature_columns_file"]).resolve(),
            threshold=float(payload.get("threshold", DEFAULT_THRESHOLD)),
            positive_label=str(payload.get("positive_label", "Attack")),
            negative_label=str(payload.get("negative_label", "Benign")),
        )

    @classmethod
    def from_config_path(cls, config_path: Path) -> "IDSModelConfig":
        config_path = config_path.resolve()
        payload = read_json(config_path)
        base_dir = config_path.parent
        return cls(
            model_path=(base_dir / payload["model_artifact"]).resolve(),
            feature_columns_path=(base_dir / payload["feature_columns_file"]).resolve(),
            threshold=float(payload.get("threshold", DEFAULT_THRESHOLD)),
            positive_label=str(payload.get("positive_label", "Attack")),
            negative_label=str(payload.get("negative_label", "Benign")),
        )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_feature_columns(path: Path) -> list[str]:
    payload = read_json(path)
    columns = payload.get("feature_columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError(f"Invalid feature_columns payload in {path}")
    return [str(column) for column in columns]


def load_input_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported input format for {path}. Expected CSV or Parquet.")


def save_output_frame(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame.to_csv(path, index=False)
        return
    if suffix in {".parquet", ".pq"}:
        frame.to_parquet(path, index=False)
        return
    raise ValueError(f"Unsupported output format for {path}. Expected CSV or Parquet.")


class IDSInferencer:
    def __init__(self, config: IDSModelConfig) -> None:
        self.config = config
        self.feature_columns = load_feature_columns(config.feature_columns_path)
        self.model = CatBoostClassifier()
        self.model.load_model(config.model_path)

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
        attack_scores = self.model.predict_proba(aligned)[:, 1]
        alerts = attack_scores >= self.config.threshold
        predicted_labels = [
            self.config.positive_label if is_alert else self.config.negative_label
            for is_alert in alerts
        ]
        return pd.DataFrame(
            {
                "attack_score": attack_scores,
                "predicted_label": predicted_labels,
                "is_alert": alerts,
                "threshold": self.config.threshold,
            }
        )

    def predict(self, frame: pd.DataFrame, include_input: bool = True) -> pd.DataFrame:
        predictions = self.score_frame(frame)
        if include_input:
            return pd.concat([frame.reset_index(drop=True), predictions], axis=1)
        return predictions


def build_default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_predictions{input_path.suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run IDS inference with the finalized CatBoost model.")
    parser.add_argument("--input-path", required=True, type=Path)
    parser.add_argument("--output-path", type=Path)
    parser.add_argument("--bundle-root", type=Path, default=None)
    parser.add_argument("--config-path", type=Path, default=None)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--feature-columns-path", type=Path, default=DEFAULT_FEATURE_COLUMNS_PATH)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--drop-input-columns",
        action="store_true",
        help="Only output prediction columns instead of appending them to the input frame.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.bundle_root is not None:
        config = IDSModelConfig.from_bundle(args.bundle_root)
    elif args.config_path is not None:
        config = IDSModelConfig.from_config_path(args.config_path)
    else:
        config = IDSModelConfig(
            model_path=args.model_path.resolve(),
            feature_columns_path=args.feature_columns_path.resolve(),
            threshold=float(args.threshold),
        )
    input_path = args.input_path.resolve()
    output_path = args.output_path.resolve() if args.output_path else build_default_output_path(input_path)

    frame = load_input_frame(input_path)
    if args.limit is not None:
        frame = frame.head(args.limit).copy()

    inferencer = IDSInferencer(config)
    result = inferencer.predict(frame, include_input=not args.drop_input_columns)
    save_output_frame(result, output_path)

    summary = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "rows_scored": int(len(result)),
        "threshold": float(config.threshold),
        "alert_rows": int(result["is_alert"].sum()),
        "feature_count": len(inferencer.feature_columns),
        "model_path": str(config.model_path),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
