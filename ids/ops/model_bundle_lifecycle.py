from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ids.core.model_bundle import load_model_bundle_manifest
from ids.core.model_bundle_activation import (
    ActiveBundleRecord,
    ActiveBundleResolutionError,
    DEFAULT_ACTIVATION_RECORD_NAME,
    SUPPORTED_ACTIVATION_RECORD_VERSION,
    load_activation_record,
    resolve_active_model_bundle,
)
from ids.core.model_bundle import write_json_atomic


def verify_candidate_bundle(bundle_root: Path) -> dict[str, Any]:
    manifest = load_model_bundle_manifest(bundle_root)
    return {
        "compatible": True,
        "bundle_root": str(manifest.bundle_root),
        "bundle_name": manifest.bundle_name,
        "manifest_version": manifest.manifest_version,
        "threshold": manifest.threshold,
        "model_path": str(manifest.model_path),
        "feature_columns_path": str(manifest.feature_columns_path),
    }


def utc_now_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_activation_record(path: Path, payload: dict[str, Any]) -> None:
    write_json_atomic(Path(path).resolve(), payload)


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


def build_bundle_status_payload(activation_path: Path) -> dict[str, Any]:
    activation_path = Path(activation_path).resolve()
    payload: dict[str, Any] = {
        "activation_path": str(activation_path),
        "activation_record_exists": activation_path.is_file(),
    }
    if not activation_path.is_file():
        payload["runtime_ready"] = False
        payload["detail"] = "activation record not found"
        return payload

    record = load_activation_record(activation_path)
    manifest = load_model_bundle_manifest(record.active_bundle_root)
    payload.update(
        {
            "runtime_ready": True,
            "active_bundle_root": str(record.active_bundle_root),
            "active_bundle_name": record.payload.get("active_bundle_name", manifest.bundle_name),
            "activated_at": record.payload.get("activated_at"),
            "verification_status": record.payload.get("verification_status"),
            "manifest_version": manifest.manifest_version,
            "threshold": manifest.threshold,
            "feature_columns_path": str(manifest.feature_columns_path),
            "model_path": str(manifest.model_path),
        }
    )
    if record.previous_bundle_root is not None:
        payload["previous_bundle_root"] = str(record.previous_bundle_root)
        payload["previous_bundle_name"] = record.payload.get("previous_bundle_name")
    return payload


def promote_candidate_bundle(
    *,
    candidate_bundle_root: Path,
    activation_path: Path,
    activated_at: str | None = None,
) -> dict[str, Any]:
    candidate_manifest = load_model_bundle_manifest(candidate_bundle_root)
    activation_path = Path(activation_path).resolve()
    previous_record: ActiveBundleRecord | None = None
    if activation_path.is_file():
        previous_record = load_activation_record(activation_path)
    payload = build_activation_record_payload(
        active_bundle_root=candidate_manifest.bundle_root,
        active_bundle_name=candidate_manifest.bundle_name,
        activated_at=activated_at or utc_now_isoformat(),
        previous_bundle_root=previous_record.active_bundle_root if previous_record else None,
        previous_bundle_name=(
            str(previous_record.payload.get("active_bundle_name"))
            if previous_record and previous_record.payload.get("active_bundle_name")
            else None
        ),
        verification_status="verified",
    )
    write_activation_record(activation_path, payload)
    return build_bundle_status_payload(activation_path)


def rollback_active_bundle(
    *,
    activation_path: Path,
    activated_at: str | None = None,
) -> dict[str, Any]:
    record = load_activation_record(activation_path)
    if record.previous_bundle_root is None:
        raise ActiveBundleResolutionError(
            f"Activation record does not contain a previous known-good bundle: {record.activation_path}"
        )
    previous_manifest = load_model_bundle_manifest(record.previous_bundle_root)
    payload = build_activation_record_payload(
        active_bundle_root=previous_manifest.bundle_root,
        active_bundle_name=previous_manifest.bundle_name,
        activated_at=activated_at or utc_now_isoformat(),
        previous_bundle_root=record.active_bundle_root,
        previous_bundle_name=str(record.payload.get("active_bundle_name", "")) or None,
        verification_status="verified",
    )
    write_activation_record(Path(activation_path).resolve(), payload)
    return build_bundle_status_payload(activation_path)


__all__ = [
    "ActiveBundleRecord",
    "ActiveBundleResolutionError",
    "DEFAULT_ACTIVATION_RECORD_NAME",
    "SUPPORTED_ACTIVATION_RECORD_VERSION",
    "build_activation_record_payload",
    "build_bundle_status_payload",
    "promote_candidate_bundle",
    "resolve_active_model_bundle",
    "rollback_active_bundle",
    "utc_now_isoformat",
    "verify_candidate_bundle",
    "write_activation_record",
]
