from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ids.core.model_bundle import (
    ActiveBundleResolutionError,
    load_model_bundle_manifest,
    read_json,
    write_json_atomic,
)


DEFAULT_ACTIVATION_RECORD_NAME = "active_bundle.json"
SUPPORTED_ACTIVATION_RECORD_VERSION = 1


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
    raw_active_bundle_root = str(payload.get("active_bundle_root", "")).strip()
    if not raw_active_bundle_root:
        raise ActiveBundleResolutionError(
            f"Activation record missing active_bundle_root: {activation_path}"
        )
    active_bundle_root = Path(raw_active_bundle_root).resolve()
    return ActiveBundleRecord(
        activation_path=activation_path,
        active_bundle_root=active_bundle_root,
        payload=payload,
    )


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


def resolve_active_model_bundle(activation_path: Path):
    record = load_activation_record(activation_path)
    return load_model_bundle_manifest(record.active_bundle_root)


__all__ = [
    "ActiveBundleRecord",
    "ActiveBundleResolutionError",
    "DEFAULT_ACTIVATION_RECORD_NAME",
    "SUPPORTED_ACTIVATION_RECORD_VERSION",
    "build_activation_record_payload",
    "build_bundle_status_payload",
    "load_activation_record",
    "resolve_active_model_bundle",
    "write_activation_record",
]
