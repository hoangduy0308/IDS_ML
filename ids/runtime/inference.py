from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

from ids.core.feature_contract import load_feature_columns
from ids.core.model_bundle import (
    DEFAULT_BUNDLE_CONFIG_NAME,
    ModelBundleContractError,
    load_model_bundle_manifest,
)
from ids.core.model_bundle_activation import ActiveBundleResolutionError, resolve_active_model_bundle
from ids.core.path_defaults import (
    DEFAULT_RUNTIME_ACTIVATION_PATH,
    DEFAULT_RUNTIME_COMPAT_FEATURE_COLUMNS_PATH,
    DEFAULT_RUNTIME_COMPAT_MODEL_PATH,
)


DEFAULT_MODEL_PATH = DEFAULT_RUNTIME_COMPAT_MODEL_PATH
DEFAULT_FEATURE_COLUMNS_PATH = DEFAULT_RUNTIME_COMPAT_FEATURE_COLUMNS_PATH
DEFAULT_ACTIVATION_PATH = DEFAULT_RUNTIME_ACTIVATION_PATH
DEFAULT_THRESHOLD = 0.5


@dataclass(frozen=True)
class IDSModelConfig:
    model_path: Path
    feature_columns_path: Path
    threshold: float = DEFAULT_THRESHOLD
    positive_label: str = "Attack"
    negative_label: str = "Benign"
    bundle_root: Path | None = None
    manifest_path: Path | None = None
    family_model_path: Path | None = None
    family_feature_columns_path: Path | None = None
    family_top1_confidence_threshold: float | None = None
    family_runner_up_margin_threshold: float | None = None
    family_closed_set_labels: tuple[str, ...] | None = None

    @classmethod
    def from_bundle(cls, bundle_root: Path) -> "IDSModelConfig":
        manifest = load_model_bundle_manifest(bundle_root)
        family_model_path: Path | None = None
        family_feature_columns_path: Path | None = None
        family_top1_confidence_threshold: float | None = None
        family_runner_up_margin_threshold: float | None = None
        family_closed_set_labels: tuple[str, ...] | None = None
        if manifest.is_composite_contract:
            family_model_path = manifest.stage2_model_path
            family_feature_columns_path = manifest.stage2_feature_columns_path
            abstention = manifest.stage2_abstention
            family_top1_confidence_threshold = float(abstention["top1_confidence"])
            family_runner_up_margin_threshold = float(abstention["runner_up_margin"])
            family_closed_set_labels = tuple(manifest.stage2_inference_contract["closed_set_labels"])
        return cls(
            model_path=manifest.model_path,
            feature_columns_path=manifest.feature_columns_path,
            threshold=manifest.threshold,
            positive_label=manifest.positive_label,
            negative_label=manifest.negative_label,
            bundle_root=manifest.bundle_root,
            manifest_path=manifest.manifest_path,
            family_model_path=family_model_path,
            family_feature_columns_path=family_feature_columns_path,
            family_top1_confidence_threshold=family_top1_confidence_threshold,
            family_runner_up_margin_threshold=family_runner_up_margin_threshold,
            family_closed_set_labels=family_closed_set_labels,
        )

    @classmethod
    def from_config_path(cls, config_path: Path) -> "IDSModelConfig":
        config_path = config_path.resolve()
        if config_path.name != DEFAULT_BUNDLE_CONFIG_NAME:
            raise ModelBundleContractError(
                f"Expected config path to point to {DEFAULT_BUNDLE_CONFIG_NAME}, got {config_path}"
            )
        return cls.from_bundle(config_path.parent)

    @classmethod
    def from_activation_path(cls, activation_path: Path) -> "IDSModelConfig":
        try:
            manifest = resolve_active_model_bundle(activation_path)
        except ModelBundleContractError as exc:
            raise ActiveBundleResolutionError(str(exc)) from exc
        return cls(
            model_path=manifest.model_path,
            feature_columns_path=manifest.feature_columns_path,
            threshold=manifest.threshold,
            positive_label=manifest.positive_label,
            negative_label=manifest.negative_label,
            bundle_root=manifest.bundle_root,
            manifest_path=manifest.manifest_path,
            family_model_path=manifest.stage2_model_path if manifest.is_composite_contract else None,
            family_feature_columns_path=(
                manifest.stage2_feature_columns_path if manifest.is_composite_contract else None
            ),
            family_top1_confidence_threshold=(
                float(manifest.stage2_abstention["top1_confidence"])
                if manifest.is_composite_contract
                else None
            ),
            family_runner_up_margin_threshold=(
                float(manifest.stage2_abstention["runner_up_margin"])
                if manifest.is_composite_contract
                else None
            ),
            family_closed_set_labels=(
                tuple(manifest.stage2_inference_contract["closed_set_labels"])
                if manifest.is_composite_contract
                else None
            ),
        )


def _build_raw_compat_config(
    *,
    model_path: Path | None,
    feature_columns_path: Path | None,
    threshold: float | None,
) -> IDSModelConfig:
    return IDSModelConfig(
        model_path=(model_path or DEFAULT_MODEL_PATH).resolve(),
        feature_columns_path=(feature_columns_path or DEFAULT_FEATURE_COLUMNS_PATH).resolve(),
        threshold=float(DEFAULT_THRESHOLD if threshold is None else threshold),
    )


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
        self.family_feature_columns = (
            load_feature_columns(config.family_feature_columns_path)
            if config.family_feature_columns_path is not None
            else None
        )
        self.family_model = None
        if config.family_model_path is not None:
            self.family_model = CatBoostClassifier()
            self.family_model.load_model(config.family_model_path)
        self.family_closed_set_labels = config.family_closed_set_labels

    def _align_features(self, frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        missing = [column for column in feature_columns if column not in frame.columns]
        if missing:
            raise ValueError(
                "Input frame is missing required feature columns: " + ", ".join(missing)
            )
        aligned = frame.loc[:, feature_columns].copy()
        for column in feature_columns:
            aligned[column] = pd.to_numeric(aligned[column], errors="coerce")
        if aligned.isna().any().any():
            bad_columns = aligned.columns[aligned.isna().any()].tolist()
            raise ValueError(
                "Input frame contains non-numeric or missing values after alignment in columns: "
                + ", ".join(bad_columns)
            )
        return aligned.astype("float32")

    def align_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        return self._align_features(frame, self.feature_columns)

    def score_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        aligned = self.align_features(frame)
        attack_scores = self.model.predict_proba(aligned)[:, 1]
        alerts = attack_scores >= self.config.threshold
        predicted_labels = [
            self.config.positive_label if is_alert else self.config.negative_label
            for is_alert in alerts
        ]
        result = pd.DataFrame(
            {
                "attack_score": attack_scores,
                "predicted_label": predicted_labels,
                "is_alert": alerts,
                "threshold": self.config.threshold,
            }
        )
        if self.family_model is None or self.family_feature_columns is None:
            return result
        family_frame = self._align_features(frame, self.family_feature_columns)
        family_score_index = np.flatnonzero(alerts.to_numpy() if hasattr(alerts, "to_numpy") else np.asarray(alerts))
        family_attack_family = [None] * len(frame)
        family_attack_confidence = [None] * len(frame)
        family_attack_margin = [None] * len(frame)
        family_status = ["benign" if not is_alert else "unknown" for is_alert in alerts]
        if family_score_index.size:
            family_probabilities = np.asarray(self.family_model.predict_proba(family_frame.iloc[family_score_index]))
            if family_probabilities.ndim != 2 or family_probabilities.shape[0] != family_score_index.size:
                raise ValueError("Stage 2 family model returned an unexpected probability matrix shape")
            top1_indices = np.argmax(family_probabilities, axis=1)
            top1_confidence = family_probabilities[np.arange(family_score_index.size), top1_indices]
            if family_probabilities.shape[1] > 1:
                runner_up_confidence = np.partition(family_probabilities, -2, axis=1)[:, -2]
            else:
                runner_up_confidence = np.zeros(family_score_index.size, dtype=family_probabilities.dtype)
            runner_up_margin = top1_confidence - runner_up_confidence
            top1_threshold = self.config.family_top1_confidence_threshold
            margin_threshold = self.config.family_runner_up_margin_threshold
            if top1_threshold is None or margin_threshold is None:
                raise ValueError("Composite family thresholds are missing from the runtime config")
            if self.family_closed_set_labels is None:
                raise ValueError("Composite family labels are missing from the runtime config")
            known_mask = (top1_confidence >= top1_threshold) & (runner_up_margin >= margin_threshold)
            for output_index, probability_index in enumerate(family_score_index):
                family_attack_confidence[probability_index] = float(top1_confidence[output_index])
                family_attack_margin[probability_index] = float(runner_up_margin[output_index])
                if known_mask[output_index]:
                    family_attack_family[probability_index] = self.family_closed_set_labels[top1_indices[output_index]]
                    family_status[probability_index] = "known"
        result["attack_family"] = family_attack_family
        result["attack_family_confidence"] = family_attack_confidence
        result["attack_family_margin"] = family_attack_margin
        result["family_status"] = family_status
        return result

    def predict(self, frame: pd.DataFrame, include_input: bool = True) -> pd.DataFrame:
        predictions = self.score_frame(frame)
        if include_input:
            return pd.concat([frame.reset_index(drop=True), predictions], axis=1)
        return predictions


def build_model_config(
    *,
    bundle_root: Path | None = None,
    config_path: Path | None = None,
    activation_path: Path | None = None,
    model_path: Path | None = None,
    feature_columns_path: Path | None = None,
    threshold: float | None = None,
) -> IDSModelConfig:
    contract_inputs = [value for value in (bundle_root, config_path, activation_path) if value is not None]
    if len(contract_inputs) > 1:
        raise ModelBundleContractError(
            "Specify only one canonical model contract source: bundle_root, config_path, or activation_path"
        )
    if contract_inputs and any(value is not None for value in (model_path, feature_columns_path, threshold)):
        raise ModelBundleContractError(
            "Canonical bundle resolution cannot be mixed with external model/schema/threshold overrides"
        )
    if activation_path is not None:
        return IDSModelConfig.from_activation_path(activation_path)
    if bundle_root is not None:
        return IDSModelConfig.from_bundle(bundle_root)
    if config_path is not None:
        return IDSModelConfig.from_config_path(config_path)
    raw_override_requested = any(value is not None for value in (model_path, feature_columns_path, threshold))
    if raw_override_requested:
        return _build_raw_compat_config(
            model_path=model_path,
            feature_columns_path=feature_columns_path,
            threshold=threshold,
        )
    return IDSModelConfig.from_activation_path(DEFAULT_ACTIVATION_PATH.resolve())


def build_inferencer(
    *,
    bundle_root: Path | None = None,
    config_path: Path | None = None,
    activation_path: Path | None = None,
    model_path: Path | None = None,
    feature_columns_path: Path | None = None,
    threshold: float | None = None,
) -> IDSInferencer:
    config = build_model_config(
        bundle_root=bundle_root,
        config_path=config_path,
        activation_path=activation_path,
        model_path=model_path,
        feature_columns_path=feature_columns_path,
        threshold=threshold,
    )
    return IDSInferencer(config)


def build_default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_predictions{input_path.suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run IDS inference with the finalized CatBoost model.")
    parser.add_argument("--input-path", required=True, type=Path)
    parser.add_argument("--output-path", type=Path)
    parser.add_argument("--bundle-root", type=Path, default=None)
    parser.add_argument("--config-path", type=Path, default=None)
    parser.add_argument(
        "--activation-path",
        type=Path,
        default=None,
        help=(
            "Canonical production contract input. "
            "Resolved from active_bundle.json and cannot be mixed with raw model/schema/threshold overrides."
        ),
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=None,
        help="Compatibility/dev-only raw model override (non-production).",
    )
    parser.add_argument(
        "--feature-columns-path",
        type=Path,
        default=None,
        help="Compatibility/dev-only raw feature schema override (non-production).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Compatibility/dev-only raw threshold override (non-production).",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--drop-input-columns",
        action="store_true",
        help="Only output prediction columns instead of appending them to the input frame.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = build_model_config(
        bundle_root=args.bundle_root,
        config_path=args.config_path,
        activation_path=args.activation_path,
        model_path=args.model_path,
        feature_columns_path=args.feature_columns_path,
        threshold=args.threshold,
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
