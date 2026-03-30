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
    activation_path: Path
    spool_dir: Path
    alerts_output_path: Path
    quarantine_output_path: Path
    summary_output_path: Path
    extractor_command_prefix: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "interface", _require_non_blank(self.interface, name="interface"))
        object.__setattr__(self, "dumpcap_binary", Path(self.dumpcap_binary))
        object.__setattr__(self, "activation_path", Path(self.activation_path))
        object.__setattr__(self, "spool_dir", Path(self.spool_dir))
        object.__setattr__(self, "alerts_output_path", Path(self.alerts_output_path))
        object.__setattr__(self, "quarantine_output_path", Path(self.quarantine_output_path))
        object.__setattr__(self, "summary_output_path", Path(self.summary_output_path))
        normalized_prefix = tuple(
            str(part).strip()
            for part in self.extractor_command_prefix
            if str(part).strip()
        )
        if not normalized_prefix:
            raise ValueError("extractor_command_prefix must not be blank")
        object.__setattr__(self, "extractor_command_prefix", normalized_prefix)


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


def _require_extractor_command_prefix(prefix: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(str(part).strip() for part in prefix if str(part).strip())
    if not normalized:
        raise ValueError("extractor_command_prefix must not be blank")
    _require_existing_file(
        Path(normalized[0]),
        name="extractor_command_prefix[0]",
        executable=True,
    )
    return normalized


def validate_preflight(config: LiveSensorPreflightConfig) -> None:
    _require_interface(config.interface)
    _require_existing_file(config.dumpcap_binary, name="dumpcap_binary", executable=True)
    _require_extractor_command_prefix(config.extractor_command_prefix)
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
    parser.add_argument("--extractor-command-prefix", nargs="+", required=True)
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
        activation_path=Path(args.activation_path),
        spool_dir=Path(args.spool_dir),
        alerts_output_path=Path(args.alerts_output_path),
        quarantine_output_path=Path(args.quarantine_output_path),
        summary_output_path=Path(args.summary_output_path),
        extractor_command_prefix=tuple(args.extractor_command_prefix),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validate_preflight(build_config_from_args(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
