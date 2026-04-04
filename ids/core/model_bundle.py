from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import tempfile

from ids.core.feature_contract import load_feature_columns as _load_feature_columns


DEFAULT_BUNDLE_CONFIG_NAME = "model_bundle.json"
SUPPORTED_BUNDLE_MANIFEST_VERSION = 2
SUPPORTED_FEATURE_SCHEMA_KIND = "feature_columns_json.v1"
SUPPORTED_INFERENCE_CONTRACT_VERSION = "ids_binary_classifier.v1"
SUPPORTED_COMPOSITE_INFERENCE_CONTRACT_VERSION = "ids_two_stage_family_contract.v1"
SUPPORTED_STAGE2_CONTRACT_VERSION = "ids_family_classifier.v1"
DEFAULT_STAGE2_FAMILY_LABELS = ("DDoS", "DoS", "Mirai", "Spoofing", "Web-Based")


class ModelBundleContractError(ValueError):
    """Raised when a model bundle contract is missing or incompatible."""


class ActiveBundleResolutionError(ModelBundleContractError):
    """Raised when the active bundle activation contract cannot be resolved."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_field(payload: dict[str, Any], key: str, *, manifest_path: Path) -> Any:
    if key not in payload:
        raise ModelBundleContractError(f"Bundle manifest missing {key}: {manifest_path}")
    return payload[key]


def _require_int(payload: dict[str, Any], key: str, *, manifest_path: Path) -> int:
    raw_value = _require_field(payload, key, manifest_path=manifest_path)
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ModelBundleContractError(
            f"Bundle manifest has invalid {key}: {manifest_path}"
        ) from exc


def _require_float(payload: dict[str, Any], key: str, *, manifest_path: Path) -> float:
    raw_value = _require_field(payload, key, manifest_path=manifest_path)
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ModelBundleContractError(
            f"Bundle manifest has invalid {key}: {manifest_path}"
        ) from exc


def _require_non_empty_string(payload: dict[str, Any], key: str, *, manifest_path: Path) -> str:
    raw_value = _require_field(payload, key, manifest_path=manifest_path)
    value = str(raw_value).strip()
    if not value:
        raise ModelBundleContractError(f"Bundle manifest missing {key}: {manifest_path}")
    return value


def _require_mapping(payload: dict[str, Any], key: str, *, manifest_path: Path) -> dict[str, Any]:
    raw_value = _require_field(payload, key, manifest_path=manifest_path)
    if not isinstance(raw_value, dict):
        raise ModelBundleContractError(
            f"Bundle manifest has invalid {key}: {manifest_path}"
        )
    return raw_value


def _require_bool(payload: dict[str, Any], key: str, *, manifest_path: Path) -> bool:
    raw_value = _require_field(payload, key, manifest_path=manifest_path)
    if not isinstance(raw_value, bool):
        raise ModelBundleContractError(
            f"Bundle manifest has invalid {key}: {manifest_path}"
        )
    return raw_value


def _require_string_list(payload: dict[str, Any], key: str, *, manifest_path: Path) -> list[str]:
    raw_value = _require_field(payload, key, manifest_path=manifest_path)
    if not isinstance(raw_value, list):
        raise ModelBundleContractError(
            f"Bundle manifest has invalid {key}: {manifest_path}"
        )
    values: list[str] = []
    for item in raw_value:
        value = str(item).strip()
        if not value:
            raise ModelBundleContractError(
                f"Bundle manifest has invalid {key}: {manifest_path}"
            )
        values.append(value)
    if not values:
        raise ModelBundleContractError(
            f"Bundle manifest has invalid {key}: {manifest_path}"
        )
    return values


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_feature_columns(path: Path) -> list[str]:
    try:
        return _load_feature_columns(path)
    except ValueError as exc:
        raise ModelBundleContractError(str(exc)) from exc


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


def build_composite_inference_contract_metadata(
    *,
    positive_label: str,
    negative_label: str,
    threshold: float,
    stage2_model_artifact: str,
    stage2_feature_columns_path: Path,
    top1_confidence_threshold: float,
    runner_up_margin_threshold: float,
    stage2_family_labels: tuple[str, ...] | list[str] = DEFAULT_STAGE2_FAMILY_LABELS,
) -> dict[str, Any]:
    return {
        "version": SUPPORTED_COMPOSITE_INFERENCE_CONTRACT_VERSION,
        "prediction_type": "two_stage_family_classifier",
        "stage1": build_inference_contract_metadata(
            positive_label=positive_label,
            negative_label=negative_label,
            threshold=threshold,
        ),
        "stage2": {
            "version": SUPPORTED_STAGE2_CONTRACT_VERSION,
            "prediction_type": "family_classifier",
            "model_artifact": str(stage2_model_artifact),
            "feature_columns_file": Path(stage2_feature_columns_path).name,
            "feature_schema": build_feature_schema_metadata(stage2_feature_columns_path),
            "closed_set_labels": [str(label).strip() for label in stage2_family_labels],
            "allows_external_model_path": False,
            "allows_external_feature_columns_path": False,
        },
        "abstention": {
            "threshold_source": "bundle",
            "top1_confidence": float(top1_confidence_threshold),
            "runner_up_margin": float(runner_up_margin_threshold),
        },
        "allows_external_stage1_model_path": False,
        "allows_external_stage1_feature_columns_path": False,
        "allows_external_stage1_threshold_override": False,
        "allows_external_stage2_model_path": False,
        "allows_external_stage2_feature_columns_path": False,
        "allows_external_abstention_override": False,
    }


@dataclass(frozen=True)
class ModelBundleManifest:
    bundle_root: Path
    manifest_path: Path
    payload: dict[str, Any]

    @property
    def manifest_version(self) -> int:
        return _require_int(self.payload, "manifest_version", manifest_path=self.manifest_path)

    @property
    def bundle_name(self) -> str:
        return _require_non_empty_string(self.payload, "bundle_name", manifest_path=self.manifest_path)

    @property
    def model_path(self) -> Path:
        model_artifact = _require_non_empty_string(
            self.payload,
            "model_artifact",
            manifest_path=self.manifest_path,
        )
        return (self.bundle_root / model_artifact).resolve()

    @property
    def feature_columns_path(self) -> Path:
        feature_columns_file = _require_non_empty_string(
            self.payload,
            "feature_columns_file",
            manifest_path=self.manifest_path,
        )
        return (self.bundle_root / feature_columns_file).resolve()

    @property
    def threshold(self) -> float:
        return _require_float(self.payload, "threshold", manifest_path=self.manifest_path)

    @property
    def positive_label(self) -> str:
        return _require_non_empty_string(
            self.payload,
            "positive_label",
            manifest_path=self.manifest_path,
        )

    @property
    def negative_label(self) -> str:
        return _require_non_empty_string(
            self.payload,
            "negative_label",
            manifest_path=self.manifest_path,
        )

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

    @property
    def inference_contract_version(self) -> str:
        return str(self.inference_contract.get("version", "")).strip()

    @property
    def is_composite_contract(self) -> bool:
        return self.inference_contract_version == SUPPORTED_COMPOSITE_INFERENCE_CONTRACT_VERSION

    @property
    def stage1_inference_contract(self) -> dict[str, Any]:
        if not self.is_composite_contract:
            raise ModelBundleContractError(
                f"Bundle manifest is not a composite contract: {self.manifest_path}"
            )
        stage1_contract = self.inference_contract.get("stage1")
        if not isinstance(stage1_contract, dict):
            raise ModelBundleContractError(
                f"Bundle manifest missing stage1 compatibility block: {self.manifest_path}"
            )
        return stage1_contract

    @property
    def stage2_inference_contract(self) -> dict[str, Any]:
        if not self.is_composite_contract:
            raise ModelBundleContractError(
                f"Bundle manifest is not a composite contract: {self.manifest_path}"
            )
        stage2_contract = self.inference_contract.get("stage2")
        if not isinstance(stage2_contract, dict):
            raise ModelBundleContractError(
                f"Bundle manifest missing stage2 compatibility block: {self.manifest_path}"
            )
        return stage2_contract

    @property
    def stage2_model_path(self) -> Path:
        stage2_model_artifact = _require_non_empty_string(
            self.stage2_inference_contract,
            "model_artifact",
            manifest_path=self.manifest_path,
        )
        return (self.bundle_root / stage2_model_artifact).resolve()

    @property
    def stage2_feature_columns_path(self) -> Path:
        stage2_feature_columns_file = _require_non_empty_string(
            self.stage2_inference_contract,
            "feature_columns_file",
            manifest_path=self.manifest_path,
        )
        return (self.bundle_root / stage2_feature_columns_file).resolve()

    @property
    def stage2_abstention(self) -> dict[str, Any]:
        if not self.is_composite_contract:
            raise ModelBundleContractError(
                f"Bundle manifest is not a composite contract: {self.manifest_path}"
            )
        abstention = self.inference_contract.get("abstention")
        if not isinstance(abstention, dict):
            raise ModelBundleContractError(
                f"Bundle manifest missing abstention compatibility block: {self.manifest_path}"
            )
        return abstention


def validate_bundle_manifest(manifest: ModelBundleManifest) -> ModelBundleManifest:
    if manifest.manifest_version != SUPPORTED_BUNDLE_MANIFEST_VERSION:
        raise ModelBundleContractError(
            "Unsupported model bundle manifest version "
            f"{manifest.manifest_version}; expected {SUPPORTED_BUNDLE_MANIFEST_VERSION}"
        )
    if not manifest.model_path.is_file():
        raise ModelBundleContractError(f"Bundle model artifact missing: {manifest.model_path}")
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
    if "feature_count" not in feature_schema:
        raise ModelBundleContractError(
            f"Bundle manifest missing feature_count compatibility metadata: {manifest.manifest_path}"
        )
    try:
        expected_feature_count = int(feature_schema["feature_count"])
    except (TypeError, ValueError) as exc:
        raise ModelBundleContractError(
            f"Bundle manifest has invalid feature_count compatibility metadata: {manifest.manifest_path}"
        ) from exc
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
    contract_version = manifest.inference_contract_version
    if contract_version == SUPPORTED_INFERENCE_CONTRACT_VERSION:
        if str(inference_contract.get("threshold_source", "")).strip() != "bundle":
            raise ModelBundleContractError(
                "Inference contract must declare threshold_source='bundle'"
            )
        if bool(inference_contract.get("allows_external_model_path")):
            raise ModelBundleContractError(
                "Inference contract cannot allow external model path overrides"
            )
        if bool(inference_contract.get("allows_external_feature_columns_path")):
            raise ModelBundleContractError(
                "Inference contract cannot allow external feature schema overrides"
            )
        if bool(inference_contract.get("allows_external_threshold_override")):
            raise ModelBundleContractError(
                "Inference contract cannot allow external threshold overrides"
            )
        if "threshold" not in inference_contract:
            contract_threshold = manifest.threshold
        else:
            try:
                contract_threshold = float(inference_contract["threshold"])
            except (TypeError, ValueError) as exc:
                raise ModelBundleContractError(
                    "Inference contract has invalid threshold metadata "
                    f"for {manifest.manifest_path}"
                ) from exc
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

    if contract_version != SUPPORTED_COMPOSITE_INFERENCE_CONTRACT_VERSION:
        raise ModelBundleContractError(
            "Unsupported inference contract version "
            f"{contract_version!r}; expected {SUPPORTED_INFERENCE_CONTRACT_VERSION!r} "
            f"or {SUPPORTED_COMPOSITE_INFERENCE_CONTRACT_VERSION!r}"
        )

    stage1_contract = manifest.stage1_inference_contract
    if str(stage1_contract.get("version", "")).strip() != SUPPORTED_INFERENCE_CONTRACT_VERSION:
        raise ModelBundleContractError(
            "Composite inference contract must embed a binary stage1 contract"
        )
    if str(stage1_contract.get("threshold_source", "")).strip() != "bundle":
        raise ModelBundleContractError(
            "Composite stage1 contract must declare threshold_source='bundle'"
        )
    if bool(stage1_contract.get("allows_external_model_path")):
        raise ModelBundleContractError(
            "Composite stage1 contract cannot allow external model path overrides"
        )
    if bool(stage1_contract.get("allows_external_feature_columns_path")):
        raise ModelBundleContractError(
            "Composite stage1 contract cannot allow external feature schema overrides"
        )
    if bool(stage1_contract.get("allows_external_threshold_override")):
        raise ModelBundleContractError(
            "Composite stage1 contract cannot allow external threshold overrides"
        )
    if "threshold" not in stage1_contract:
        stage1_threshold = manifest.threshold
    else:
        try:
            stage1_threshold = float(stage1_contract["threshold"])
        except (TypeError, ValueError) as exc:
            raise ModelBundleContractError(
                "Composite stage1 contract has invalid threshold metadata "
                f"for {manifest.manifest_path}"
            ) from exc
    if stage1_threshold != manifest.threshold:
        raise ModelBundleContractError(
            "Composite stage1 contract threshold does not match bundle threshold"
        )
    if str(stage1_contract.get("positive_label", "")).strip() != manifest.positive_label:
        raise ModelBundleContractError(
            "Composite stage1 contract positive_label does not match bundle metadata"
        )
    if str(stage1_contract.get("negative_label", "")).strip() != manifest.negative_label:
        raise ModelBundleContractError(
            "Composite stage1 contract negative_label does not match bundle metadata"
        )

    stage2_contract = manifest.stage2_inference_contract
    if str(stage2_contract.get("version", "")).strip() != SUPPORTED_STAGE2_CONTRACT_VERSION:
        raise ModelBundleContractError(
            "Unsupported stage2 contract version "
            f"{stage2_contract.get('version', '')!r}; expected {SUPPORTED_STAGE2_CONTRACT_VERSION!r}"
        )
    if str(stage2_contract.get("prediction_type", "")).strip() != "family_classifier":
        raise ModelBundleContractError(
            "Composite stage2 contract must declare prediction_type='family_classifier'"
        )
    if bool(stage2_contract.get("allows_external_model_path")):
        raise ModelBundleContractError(
            "Composite stage2 contract cannot allow external model path overrides"
        )
    if bool(stage2_contract.get("allows_external_feature_columns_path")):
        raise ModelBundleContractError(
            "Composite stage2 contract cannot allow external feature schema overrides"
        )
    if not manifest.stage2_model_path.is_file():
        raise ModelBundleContractError(
            f"Composite stage2 model artifact missing: {manifest.stage2_model_path}"
        )
    if not manifest.stage2_feature_columns_path.is_file():
        raise ModelBundleContractError(
            f"Composite stage2 feature schema missing: {manifest.stage2_feature_columns_path}"
        )
    stage2_schema = _require_mapping(
        stage2_contract,
        "feature_schema",
        manifest_path=manifest.manifest_path,
    )
    if str(stage2_schema.get("kind", "")).strip() != SUPPORTED_FEATURE_SCHEMA_KIND:
        raise ModelBundleContractError(
            "Unsupported composite stage2 feature schema kind "
            f"{str(stage2_schema.get('kind', '')).strip()!r}; expected {SUPPORTED_FEATURE_SCHEMA_KIND!r}"
        )
    if str(stage2_schema.get("path", "")).strip() != manifest.stage2_feature_columns_path.name:
        raise ModelBundleContractError(
            "Composite stage2 feature schema path does not match bundle metadata"
        )
    if "feature_count" not in stage2_schema:
        raise ModelBundleContractError(
            f"Composite stage2 contract missing feature_count metadata: {manifest.manifest_path}"
        )
    try:
        stage2_feature_count = int(stage2_schema["feature_count"])
    except (TypeError, ValueError) as exc:
        raise ModelBundleContractError(
            f"Composite stage2 contract has invalid feature_count metadata: {manifest.manifest_path}"
        ) from exc
    stage2_feature_columns = load_feature_columns(manifest.stage2_feature_columns_path)
    if stage2_feature_count != len(stage2_feature_columns):
        raise ModelBundleContractError(
            "Composite stage2 feature count mismatch: expected "
            f"{stage2_feature_count}, got {len(stage2_feature_columns)}"
        )
    if str(stage2_schema.get("sha256", "")).strip() != sha256_file(manifest.stage2_feature_columns_path):
        raise ModelBundleContractError(
            f"Composite stage2 feature schema digest mismatch for {manifest.stage2_feature_columns_path}"
        )
    stage2_labels = _require_string_list(
        stage2_contract,
        "closed_set_labels",
        manifest_path=manifest.manifest_path,
    )
    if tuple(stage2_labels) != tuple(DEFAULT_STAGE2_FAMILY_LABELS):
        raise ModelBundleContractError(
            "Composite stage2 closed_set_labels do not match the supported closed set"
        )
    abstention = _require_mapping(
        inference_contract,
        "abstention",
        manifest_path=manifest.manifest_path,
    )
    if str(abstention.get("threshold_source", "")).strip() != "bundle":
        raise ModelBundleContractError(
            "Composite inference contract must declare abstention.threshold_source='bundle'"
        )
    _require_bool(inference_contract, "allows_external_stage1_model_path", manifest_path=manifest.manifest_path)
    _require_bool(
        inference_contract,
        "allows_external_stage1_feature_columns_path",
        manifest_path=manifest.manifest_path,
    )
    _require_bool(
        inference_contract,
        "allows_external_stage1_threshold_override",
        manifest_path=manifest.manifest_path,
    )
    _require_bool(
        inference_contract,
        "allows_external_stage2_model_path",
        manifest_path=manifest.manifest_path,
    )
    _require_bool(
        inference_contract,
        "allows_external_stage2_feature_columns_path",
        manifest_path=manifest.manifest_path,
    )
    _require_bool(
        inference_contract,
        "allows_external_abstention_override",
        manifest_path=manifest.manifest_path,
    )
    try:
        top1_confidence = float(abstention["top1_confidence"])
        runner_up_margin = float(abstention["runner_up_margin"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ModelBundleContractError(
            f"Composite inference contract has invalid abstention metadata: {manifest.manifest_path}"
        ) from exc
    if top1_confidence <= 0.0 or runner_up_margin < 0.0:
        raise ModelBundleContractError(
            "Composite inference contract abstention thresholds must be non-negative"
        )
    return manifest


def load_model_bundle_manifest(bundle_root: Path) -> ModelBundleManifest:
    bundle_root = Path(bundle_root).resolve()
    manifest_path = bundle_root / DEFAULT_BUNDLE_CONFIG_NAME
    if not manifest_path.is_file():
        raise ModelBundleContractError(f"Bundle manifest not found: {manifest_path}")
    try:
        payload = read_json(manifest_path)
    except json.JSONDecodeError as exc:
        raise ModelBundleContractError(f"Bundle manifest is not valid JSON: {manifest_path}") from exc
    manifest = ModelBundleManifest(
        bundle_root=bundle_root,
        manifest_path=manifest_path,
        payload=payload,
    )
    return validate_bundle_manifest(manifest)
