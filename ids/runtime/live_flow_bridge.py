from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from ids.runtime.adapter.record_adapter import (
    AdaptedFlowRecord,
    AdapterQuarantineRecord,
    PRIMARY_PROFILE_ID,
    UnknownAdapterProfileError,
    adapt_record,
)


DEFAULT_EXTRACTOR_COMMAND_PREFIX: tuple[str, ...] = ("Cmd",)
DEFAULT_ADAPTER_PROFILE_ID = PRIMARY_PROFILE_ID
DEFAULT_FLOW_SUFFIX = "_Flow.csv"


class _CaptureWindowLike(Protocol):
    path: Path


@dataclass(frozen=True)
class LiveFlowBridgeConfig:
    extractor_command_prefix: tuple[str, ...] = DEFAULT_EXTRACTOR_COMMAND_PREFIX
    adapter_profile_id: str = DEFAULT_ADAPTER_PROFILE_ID
    flow_suffix: str = DEFAULT_FLOW_SUFFIX

    def __post_init__(self) -> None:
        prefix = tuple(str(part).strip() for part in self.extractor_command_prefix if str(part).strip())
        if not prefix:
            raise ValueError("extractor_command_prefix must not be blank")
        object.__setattr__(self, "extractor_command_prefix", prefix)
        if not self.adapter_profile_id.strip():
            raise ValueError("adapter_profile_id must not be blank")
        object.__setattr__(self, "adapter_profile_id", self.adapter_profile_id.strip())
        if not self.flow_suffix.endswith(".csv") or not self.flow_suffix.startswith("_"):
            raise ValueError("flow_suffix must look like '_Flow.csv'")
        object.__setattr__(self, "flow_suffix", self.flow_suffix)


@dataclass(frozen=True)
class ExtractorRunResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class BridgeWindowResult:
    window: _CaptureWindowLike
    extractor_output_path: Path
    command: tuple[str, ...]
    adapted_records: tuple[dict[str, Any], ...]
    adapter_quarantines: tuple[dict[str, Any], ...]
    window_errors: tuple[dict[str, Any], ...]


ExtractorRunner = Callable[[Sequence[str], _CaptureWindowLike, Path], ExtractorRunResult]


class LiveFlowBridge:
    def __init__(
        self,
        config: LiveFlowBridgeConfig,
        *,
        extractor_runner: ExtractorRunner | None = None,
    ) -> None:
        self.config = config
        self.extractor_runner = extractor_runner or self._default_extractor_runner

    def extractor_output_path_for(
        self,
        window: _CaptureWindowLike,
        *,
        output_dir: Path | None = None,
    ) -> Path:
        base_dir = Path(output_dir) if output_dir is not None else window.path.parent
        return base_dir / f"{window.path.stem}{self.config.flow_suffix}"

    def build_extractor_command(
        self,
        window: _CaptureWindowLike,
        *,
        output_dir: Path | None = None,
    ) -> list[str]:
        base_dir = Path(output_dir) if output_dir is not None else window.path.parent
        return [
            *self.config.extractor_command_prefix,
            str(window.path),
            str(base_dir),
        ]

    def bridge_window(
        self,
        window: _CaptureWindowLike,
        *,
        output_dir: Path | None = None,
    ) -> BridgeWindowResult:
        command = tuple(self.build_extractor_command(window, output_dir=output_dir))
        extractor_output_path = self.extractor_output_path_for(window, output_dir=output_dir)
        extractor_output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            run_result = self.extractor_runner(command, window, extractor_output_path)
        except Exception as exc:  # pragma: no cover - defensive guard
            return BridgeWindowResult(
                window=window,
                extractor_output_path=extractor_output_path,
                command=command,
                adapted_records=(),
                adapter_quarantines=(),
                window_errors=(
                    self._build_window_error(
                        stage="extractor",
                        reason="extractor_runner_failed",
                        window=window,
                        extractor_output_path=extractor_output_path,
                        command=command,
                        stderr=str(exc),
                    ),
                ),
            )

        if run_result.returncode != 0:
            return BridgeWindowResult(
                window=window,
                extractor_output_path=extractor_output_path,
                command=command,
                adapted_records=(),
                adapter_quarantines=(),
                window_errors=(
                    self._build_window_error(
                        stage="extractor",
                        reason="extractor_process_failed",
                        window=window,
                        extractor_output_path=extractor_output_path,
                        command=command,
                        returncode=run_result.returncode,
                        stdout=run_result.stdout,
                        stderr=run_result.stderr,
                    ),
                ),
            )

        if not extractor_output_path.exists():
            return BridgeWindowResult(
                window=window,
                extractor_output_path=extractor_output_path,
                command=command,
                adapted_records=(),
                adapter_quarantines=(),
                window_errors=(
                    self._build_window_error(
                        stage="output",
                        reason="missing_extractor_output",
                        window=window,
                        extractor_output_path=extractor_output_path,
                        command=command,
                        stdout=run_result.stdout,
                        stderr=run_result.stderr,
                    ),
                ),
            )

        try:
            rows = self._load_csv_rows(extractor_output_path)
        except Exception as exc:  # pragma: no cover - defensive guard
            return BridgeWindowResult(
                window=window,
                extractor_output_path=extractor_output_path,
                command=command,
                adapted_records=(),
                adapter_quarantines=(),
                window_errors=(
                    self._build_window_error(
                        stage="output",
                        reason="invalid_extractor_output",
                        window=window,
                        extractor_output_path=extractor_output_path,
                        command=command,
                        stderr=str(exc),
                    ),
                ),
            )

        adapted_records: list[dict[str, Any]] = []
        adapter_quarantines: list[dict[str, Any]] = []
        window_errors: list[dict[str, Any]] = []

        for row_index, row in enumerate(rows):
            try:
                adapted = adapt_record(
                    row,
                    profile_id=self.config.adapter_profile_id,
                    record_index=row_index,
                )
            except UnknownAdapterProfileError as exc:
                window_errors.append(
                    self._build_window_error(
                        stage="adapter",
                        reason="unknown_adapter_profile",
                        window=window,
                        extractor_output_path=extractor_output_path,
                        command=command,
                        stderr=str(exc),
                    )
                )
                break

            if isinstance(adapted, AdaptedFlowRecord):
                adapted_records.append(
                    {
                        "event_type": "bridge_record",
                        "window_path": str(window.path),
                        "extractor_output_path": str(extractor_output_path),
                        "record_index": adapted.record_index,
                        "profile": adapted.profile,
                        "record": adapted.to_runtime_record(),
                    }
                )
                continue

            if isinstance(adapted, AdapterQuarantineRecord):
                adapter_quarantines.append(
                    {
                        **adapted.to_event(include_source_record=False),
                        "window_path": str(window.path),
                        "extractor_output_path": str(extractor_output_path),
                    }
                )
                continue

            window_errors.append(
                self._build_window_error(
                    stage="adapter",
                    reason="unexpected_adapter_result",
                    window=window,
                    extractor_output_path=extractor_output_path,
                    command=command,
                )
            )
            break

        return BridgeWindowResult(
            window=window,
            extractor_output_path=extractor_output_path,
            command=command,
            adapted_records=tuple(adapted_records),
            adapter_quarantines=tuple(adapter_quarantines),
            window_errors=tuple(window_errors),
        )

    def write_result_jsonl(self, result: BridgeWindowResult, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for event in result.window_errors + result.adapter_quarantines + result.adapted_records:
                handle.write(json.dumps(event, ensure_ascii=False))
                handle.write("\n")

    @staticmethod
    def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("extractor output is missing a header row")
            return [dict(row) for row in reader]

    @staticmethod
    def _build_window_error(
        *,
        stage: str,
        reason: str,
        window: _CaptureWindowLike,
        extractor_output_path: Path,
        command: Sequence[str],
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> dict[str, Any]:
        return {
            "event_type": "window_stage_error",
            "stage": stage,
            "reason": reason,
            "window_path": str(window.path),
            "extractor_output_path": str(extractor_output_path),
            "command": list(command),
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    @staticmethod
    def _default_extractor_runner(
        command: Sequence[str],
        window: _CaptureWindowLike,
        output_path: Path,
    ) -> ExtractorRunResult:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            check=False,
            text=True,
        )
        return ExtractorRunResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
