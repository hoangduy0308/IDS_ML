from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


DEFAULT_BUNDLE_CONFIG_NAME = "model_bundle.json"


class ModelBundleContractError(ValueError):
    """Raised when a model bundle contract is missing or incompatible."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_feature_columns(path: Path) -> list[str]:
    payload = read_json(path)
    columns = payload.get("feature_columns")
    if not isinstance(columns, list) or not columns:
        raise ModelBundleContractError(f"Invalid feature_columns payload in {path}")
    normalized = [str(column) for column in columns]
    if any(not column.strip() for column in normalized):
        raise ModelBundleContractError(f"Blank feature column name found in {path}")
    return normalized


@dataclass(frozen=True)
class ModelBundleManifest:
    bundle_root: Path
    manifest_path: Path
    payload: dict[str, Any]

    @property
    def model_path(self) -> Path:
        return (self.bundle_root / str(self.payload["model_artifact"])).resolve()

    @property
    def feature_columns_path(self) -> Path:
        return (self.bundle_root / str(self.payload["feature_columns_file"])).resolve()

    @property
    def threshold(self) -> float:
        return float(self.payload["threshold"])

    @property
    def positive_label(self) -> str:
        return str(self.payload["positive_label"])

    @property
    def negative_label(self) -> str:
        return str(self.payload["negative_label"])


def load_model_bundle_manifest(bundle_root: Path) -> ModelBundleManifest:
    bundle_root = Path(bundle_root).resolve()
    manifest_path = bundle_root / DEFAULT_BUNDLE_CONFIG_NAME
    if not manifest_path.is_file():
        raise ModelBundleContractError(f"Bundle manifest not found: {manifest_path}")
    payload = read_json(manifest_path)
    return ModelBundleManifest(
        bundle_root=bundle_root,
        manifest_path=manifest_path,
        payload=payload,
    )


def resolve_active_model_bundle(activation_path: Path) -> ModelBundleManifest:
    activation_path = Path(activation_path).resolve()
    if not activation_path.is_file():
        raise ModelBundleContractError(f"Activation record not found: {activation_path}")
    payload = read_json(activation_path)
    active_bundle_root = Path(str(payload.get("active_bundle_root", ""))).resolve()
    if not str(active_bundle_root):
        raise ModelBundleContractError(
            f"Activation record missing active_bundle_root: {activation_path}"
        )
    return load_model_bundle_manifest(active_bundle_root)
