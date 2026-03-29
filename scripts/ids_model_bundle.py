from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


DEFAULT_BUNDLE_CONFIG_NAME = "model_bundle.json"
DEFAULT_ACTIVATION_RECORD_NAME = "active_bundle.json"
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_feature_columns(path: Path) -> list[str]:
    payload = read_json(path)
    columns = payload.get("feature_columns")
    if not isinstance(columns, list) or not columns:
        raise ModelBundleContractError(f"Invalid feature_columns payload in {path}")
    normalized = [str(column) for column in columns]
    if any(not column.strip() for column in normalized):
        raise ModelBundleContractError(f"Blank feature column name found in {path}")
    return normalized


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
    def manifest_version(self) -> int:
        return int(self.payload["manifest_version"])

    @property
    def bundle_name(self) -> str:
        return str(self.payload["bundle_name"])

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

    @property
    def compatibility(self) -> dict[str, Any]:
        compatibility = self.payload.get("compatibility")
        if not isinstance(compatibility, dict):
            raise ModelBundleContractError(
                f"Bundle manifest missing compatibility block: {self.manifest_path}"
            )
        return compatibility

    @property
    def feature_schema(self) -> dict[str, Any]:
        feature_schema = self.compatibility.get("feature_schema")
        if not isinstance(feature_schema, dict):
            raise ModelBundleContractError(
                f"Bundle manifest missing feature_schema compatibility block: {self.manifest_path}"
            )
        return feature_schema

    @property
    def inference_contract(self) -> dict[str, Any]:
        inference_contract = self.compatibility.get("inference_contract")
        if not isinstance(inference_contract, dict):
            raise ModelBundleContractError(
                f"Bundle manifest missing inference_contract compatibility block: {self.manifest_path}"
            )
        return inference_contract


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


def validate_bundle_manifest(manifest: ModelBundleManifest) -> ModelBundleManifest:
    if manifest.manifest_version != SUPPORTED_BUNDLE_MANIFEST_VERSION:
        raise ModelBundleContractError(
            "Unsupported model bundle manifest version "
            f"{manifest.manifest_version}; expected {SUPPORTED_BUNDLE_MANIFEST_VERSION}"
        )
    if not manifest.model_path.is_file():
        raise ModelBundleContractError(
            f"Bundle model artifact missing: {manifest.model_path}"
        )
    if not manifest.feature_columns_path.is_file():
        raise ModelBundleContractError(
            f"Bundle feature schema missing: {manifest.feature_columns_path}"
        )

    feature_schema = manifest.feature_schema
    schema_kind = str(feature_schema.get("kind", "")).strip()
    if schema_kind != SUPPORTED_FEATURE_SCHEMA_KIND:
        raise ModelBundleContractError(
            "Unsupported feature schema kind "
            f"{schema_kind!r}; expected {SUPPORTED_FEATURE_SCHEMA_KIND!r}"
        )
    if str(feature_schema.get("path", "")).strip() != manifest.feature_columns_path.name:
        raise ModelBundleContractError(
            "Feature schema path in compatibility metadata does not match "
            f"{manifest.feature_columns_path.name!r}"
        )
    expected_feature_count = int(feature_schema.get("feature_count", 0))
    actual_feature_columns = load_feature_columns(manifest.feature_columns_path)
    if expected_feature_count != len(actual_feature_columns):
        raise ModelBundleContractError(
            "Bundle feature count mismatch: expected "
            f"{expected_feature_count}, got {len(actual_feature_columns)}"
        )
    expected_schema_digest = str(feature_schema.get("sha256", "")).strip()
    actual_schema_digest = sha256_file(manifest.feature_columns_path)
    if expected_schema_digest != actual_schema_digest:
        raise ModelBundleContractError(
            f"Bundle feature schema digest mismatch for {manifest.feature_columns_path}"
        )

    inference_contract = manifest.inference_contract
    contract_version = str(inference_contract.get("version", "")).strip()
    if contract_version != SUPPORTED_INFERENCE_CONTRACT_VERSION:
        raise ModelBundleContractError(
            "Unsupported inference contract version "
            f"{contract_version!r}; expected {SUPPORTED_INFERENCE_CONTRACT_VERSION!r}"
        )
    if str(inference_contract.get("threshold_source", "")).strip() != "bundle":
        raise ModelBundleContractError("Inference contract must declare threshold_source='bundle'")
    if bool(inference_contract.get("allows_external_model_path")):
        raise ModelBundleContractError("Inference contract cannot allow external model path overrides")
    if bool(inference_contract.get("allows_external_feature_columns_path")):
        raise ModelBundleContractError(
            "Inference contract cannot allow external feature schema overrides"
        )
    if bool(inference_contract.get("allows_external_threshold_override")):
        raise ModelBundleContractError(
            "Inference contract cannot allow external threshold overrides"
        )
    contract_threshold = float(inference_contract.get("threshold", manifest.threshold))
    if contract_threshold != manifest.threshold:
        raise ModelBundleContractError(
            "Inference contract threshold does not match bundle threshold"
        )
    if str(inference_contract.get("positive_label", "")).strip() != manifest.positive_label:
        raise ModelBundleContractError(
            "Inference contract positive_label does not match bundle metadata"
        )
    if str(inference_contract.get("negative_label", "")).strip() != manifest.negative_label:
        raise ModelBundleContractError(
            "Inference contract negative_label does not match bundle metadata"
        )
    return manifest


def load_model_bundle_manifest(bundle_root: Path) -> ModelBundleManifest:
    bundle_root = Path(bundle_root).resolve()
    manifest_path = bundle_root / DEFAULT_BUNDLE_CONFIG_NAME
    if not manifest_path.is_file():
        raise ModelBundleContractError(f"Bundle manifest not found: {manifest_path}")
    manifest = ModelBundleManifest(
        bundle_root=bundle_root,
        manifest_path=manifest_path,
        payload=read_json(manifest_path),
    )
    return validate_bundle_manifest(manifest)


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


def write_activation_record(path: Path, payload: dict[str, Any]) -> None:
    write_json(Path(path).resolve(), payload)


def load_activation_record(path: Path) -> ActiveBundleRecord:
    activation_path = Path(path).resolve()
    if not activation_path.is_file():
        raise ActiveBundleResolutionError(f"Activation record not found: {activation_path}")
    payload = read_json(activation_path)
    record_version = int(payload.get("record_version", 0))
    if record_version != SUPPORTED_ACTIVATION_RECORD_VERSION:
        raise ActiveBundleResolutionError(
            "Unsupported activation record version "
            f"{record_version}; expected {SUPPORTED_ACTIVATION_RECORD_VERSION}"
        )
    active_bundle_root = Path(str(payload.get("active_bundle_root", ""))).resolve()
    if not str(active_bundle_root):
        raise ActiveBundleResolutionError(
            f"Activation record missing active_bundle_root: {activation_path}"
        )
    return ActiveBundleRecord(
        activation_path=activation_path,
        active_bundle_root=active_bundle_root,
        payload=payload,
    )


def resolve_active_model_bundle(activation_path: Path) -> ModelBundleManifest:
    record = load_activation_record(activation_path)
    return load_model_bundle_manifest(record.active_bundle_root)
