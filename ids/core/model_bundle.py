from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import tempfile


DEFAULT_BUNDLE_CONFIG_NAME = "model_bundle.json"
SUPPORTED_BUNDLE_MANIFEST_VERSION = 2
SUPPORTED_ACTIVATION_RECORD_VERSION = 1
SUPPORTED_FEATURE_SCHEMA_KIND = "feature_columns_json.v1"
SUPPORTED_INFERENCE_CONTRACT_VERSION = "ids_binary_classifier.v1"


class ModelBundleContractError(ValueError):
    """Raised when a model bundle contract is missing or incompatible."""


class ActiveBundleResolutionError(ModelBundleContractError):
    """Raised when the active bundle activation contract cannot be resolved."""


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


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_feature_schema_metadata(path: Path) -> dict[str, Any]:
    feature_columns = load_feature_columns(path)
    return {
        "kind": SUPPORTED_FEATURE_SCHEMA_KIND,
        "path": path.name,
        "feature_count": len(feature_columns),
        "sha256": sha256_file(path),
    }


def build_inference_contract_metadata(
    *,
    positive_label: str,
    negative_label: str,
    threshold: float,
) -> dict[str, Any]:
    return {
        "version": SUPPORTED_INFERENCE_CONTRACT_VERSION,
        "prediction_type": "binary_classifier",
        "score_field": "attack_score",
        "alert_field": "is_alert",
        "threshold_source": "bundle",
        "threshold": float(threshold),
        "positive_label": str(positive_label),
        "negative_label": str(negative_label),
        "allows_external_model_path": False,
        "allows_external_feature_columns_path": False,
        "allows_external_threshold_override": False,
    }


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


@dataclass(frozen=True)
class ActiveBundleRecord:
    activation_path: Path
    active_bundle_root: Path
    payload: dict[str, Any]

    @property
    def previous_bundle_root(self) -> Path | None:
        raw = self.payload.get("previous_bundle_root")
        if raw in (None, ""):
            return None
        return Path(str(raw)).resolve()


def build_activation_record_payload(
    *,
    active_bundle_root: Path,
    active_bundle_name: str,
    activated_at: str,
    previous_bundle_root: Path | None = None,
    previous_bundle_name: str | None = None,
    verification_status: str = "verified",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "record_version": SUPPORTED_ACTIVATION_RECORD_VERSION,
        "active_bundle_root": str(Path(active_bundle_root).resolve()),
        "active_bundle_name": str(active_bundle_name),
        "activated_at": str(activated_at),
        "verification_status": str(verification_status),
    }
    if previous_bundle_root is not None:
        payload["previous_bundle_root"] = str(Path(previous_bundle_root).resolve())
    if previous_bundle_name:
        payload["previous_bundle_name"] = str(previous_bundle_name)
    return payload


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


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.stem}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


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
