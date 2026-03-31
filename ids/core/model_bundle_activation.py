from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ids.core.model_bundle import (
    ActiveBundleResolutionError,
    load_model_bundle_manifest,
    read_json,
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


def resolve_active_model_bundle(activation_path: Path):
    record = load_activation_record(activation_path)
    return load_model_bundle_manifest(record.active_bundle_root)


__all__ = [
    "ActiveBundleRecord",
    "ActiveBundleResolutionError",
    "DEFAULT_ACTIVATION_RECORD_NAME",
    "SUPPORTED_ACTIVATION_RECORD_VERSION",
    "load_activation_record",
    "resolve_active_model_bundle",
]
