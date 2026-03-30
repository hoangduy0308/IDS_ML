from __future__ import annotations

from ids.core.model_bundle import (
    DEFAULT_BUNDLE_CONFIG_NAME,
    SUPPORTED_BUNDLE_MANIFEST_VERSION,
    SUPPORTED_FEATURE_SCHEMA_KIND,
    SUPPORTED_INFERENCE_CONTRACT_VERSION,
    ModelBundleContractError,
    ModelBundleManifest,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
    load_feature_columns,
    load_model_bundle_manifest,
    read_json,
    sha256_file,
    write_json,
    write_json_atomic,
)
from ids.ops.model_bundle_lifecycle import (
    DEFAULT_ACTIVATION_RECORD_NAME,
    SUPPORTED_ACTIVATION_RECORD_VERSION,
    ActiveBundleRecord,
    ActiveBundleResolutionError,
    build_activation_record_payload,
    build_bundle_status_payload,
    load_activation_record,
    resolve_active_model_bundle,
    rollback_active_bundle,
    verify_candidate_bundle,
    write_activation_record,
)
