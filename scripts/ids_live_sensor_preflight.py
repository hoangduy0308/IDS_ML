from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scripts.ids_model_bundle import resolve_active_model_bundle


@dataclass(frozen=True)
class LiveSensorPreflightConfig:
    interface: str
    dumpcap_binary: Path
    java_binary: Path
    extractor_binary: Path
    jnetpcap_path: Path
    activation_path: Path
    spool_dir: Path
    alerts_output_path: Path
    quarantine_output_path: Path
    summary_output_path: Path


def _require_non_blank(value: str, *, name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} must not be blank")
    return normalized


def _require_existing_file(path: Path, *, name: str, executable: bool = False) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if not resolved.is_file():
        raise FileNotFoundError(f"{name} not found: {resolved}")
    if executable and not _is_executable_file(resolved):
            raise PermissionError(f"{name} is not executable: {resolved}")
    if not executable and not os.access(resolved, os.R_OK):
        raise PermissionError(f"{name} is not readable: {resolved}")
    return resolved


def _is_executable_file(path: Path) -> bool:
    return bool(path.stat().st_mode & 0o111)


def _require_existing_path(path: Path, *, name: str) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if not resolved.exists():
        raise FileNotFoundError(f"{name} not found: {resolved}")
    return resolved


def _require_writable_directory(path: Path, *, name: str) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if not resolved.is_dir():
        raise FileNotFoundError(f"{name} not found: {resolved}")
    if not os.access(resolved, os.W_OK):
        raise PermissionError(f"{name} is not writable: {resolved}")
    return resolved


def _require_writable_parent(path: Path, *, name: str) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    parent = resolved.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"{name} parent directory not found: {parent}")
    if not os.access(parent, os.W_OK):
        raise PermissionError(f"{name} parent directory is not writable: {parent}")
    return resolved


def _require_interface(interface: str) -> str:
    normalized = _require_non_blank(interface, name="interface")
    interface_path = Path("/sys/class/net") / normalized
    if not interface_path.exists():
        raise FileNotFoundError(f"interface not found: {normalized}")
    return normalized


def validate_preflight(config: LiveSensorPreflightConfig) -> None:
    _require_interface(config.interface)
    _require_existing_file(config.dumpcap_binary, name="dumpcap_binary", executable=True)
    _require_existing_file(config.java_binary, name="java_binary", executable=True)
    _require_existing_file(config.extractor_binary, name="extractor_binary", executable=True)
    _require_existing_path(config.jnetpcap_path, name="jnetpcap_path")
    activation_path = _require_existing_file(config.activation_path, name="activation_path")
    resolve_active_model_bundle(activation_path)
    _require_writable_directory(config.spool_dir, name="spool_dir")
    _require_writable_parent(config.alerts_output_path, name="alerts_output_path")
    _require_writable_parent(config.quarantine_output_path, name="quarantine_output_path")
    _require_writable_parent(config.summary_output_path, name="summary_output_path")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the staged-live IDS sensor runtime contract before systemd starts the daemon."
    )
    parser.add_argument("--interface", required=True)
    parser.add_argument("--dumpcap-binary", type=Path, required=True)
    parser.add_argument("--java-binary", type=Path, required=True)
    parser.add_argument("--extractor-binary", type=Path, required=True)
    parser.add_argument("--jnetpcap-path", type=Path, required=True)
    parser.add_argument("--activation-path", type=Path, required=True)
    parser.add_argument("--spool-dir", type=Path, required=True)
    parser.add_argument("--alerts-output-path", type=Path, required=True)
    parser.add_argument("--quarantine-output-path", type=Path, required=True)
    parser.add_argument("--summary-output-path", type=Path, required=True)
    return parser.parse_args(argv)


def build_config_from_args(args: argparse.Namespace) -> LiveSensorPreflightConfig:
    return LiveSensorPreflightConfig(
        interface=args.interface,
        dumpcap_binary=Path(args.dumpcap_binary),
        java_binary=Path(args.java_binary),
        extractor_binary=Path(args.extractor_binary),
        jnetpcap_path=Path(args.jnetpcap_path),
        activation_path=Path(args.activation_path),
        spool_dir=Path(args.spool_dir),
        alerts_output_path=Path(args.alerts_output_path),
        quarantine_output_path=Path(args.quarantine_output_path),
        summary_output_path=Path(args.summary_output_path),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validate_preflight(build_config_from_args(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
