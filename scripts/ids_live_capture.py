from __future__ import annotations

import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Deque, Sequence


DEFAULT_DUMPCAP_BINARY = "dumpcap"
DEFAULT_CAPTURE_FILTER = "tcp or udp"
DEFAULT_OUTPUT_FORMAT = "pcap"
DEFAULT_CAPTURE_BUFFER_MEGABYTES = 64
DEFAULT_UPDATE_INTERVAL_SECONDS = 1.0
_VALID_INTERFACE_NAME = re.compile(r"^[A-Za-z0-9_.:-]+$")
_WINDOW_PATH_RE = re.compile(r"(?P<path>[^\s'\"<>|]+?\.pcap(?:ng)?)", re.IGNORECASE)
_FATAL_FAILURE_MARKERS = (
    "no such device",
    "permission denied",
    "cannot open",
    "could not open",
    "unable to open",
    "interface not found",
    "failed to start",
    "unsupported output format",
    "not enough privileges",
)
_RECOVERABLE_FAILURE_MARKERS = (
    "stopped",
    "stop requested",
    "closed",
    "shutdown",
    "terminated",
    "interrupted",
    "rotation",
    "timeout",
    "eof",
)


def _format_number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return format(float(value), "g")


def _normalize_capture_filter(capture_filter: str) -> str:
    normalized = " ".join(str(capture_filter).split()).strip().lower()
    if normalized != DEFAULT_CAPTURE_FILTER:
        raise ValueError("capture_filter must be exactly 'tcp or udp'")
    return DEFAULT_CAPTURE_FILTER


def _validate_interface_name(interface: str) -> str:
    normalized = str(interface).strip()
    if not normalized:
        raise ValueError("interface must not be blank")
    if normalized != interface:
        raise ValueError("interface must not contain leading or trailing whitespace")
    if not _VALID_INTERFACE_NAME.fullmatch(normalized):
        raise ValueError("interface must contain only Linux-safe interface characters")
    return normalized


def _safe_interface_slug(interface: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", interface)


@dataclass(frozen=True)
class DumpcapCaptureConfig:
    interface: str
    spool_dir: Path
    window_duration_seconds: float
    window_file_count: int
    max_pending_windows: int
    capture_buffer_megabytes: int = DEFAULT_CAPTURE_BUFFER_MEGABYTES
    update_interval_seconds: float = DEFAULT_UPDATE_INTERVAL_SECONDS
    capture_filter: str = DEFAULT_CAPTURE_FILTER
    output_format: str = DEFAULT_OUTPUT_FORMAT
    dumpcap_binary: str = DEFAULT_DUMPCAP_BINARY

    def __post_init__(self) -> None:
        object.__setattr__(self, "interface", _validate_interface_name(self.interface))
        object.__setattr__(self, "spool_dir", Path(self.spool_dir))
        if not self.spool_dir.is_absolute():
            raise ValueError("spool_dir must be an absolute path")
        if self.window_duration_seconds <= 0:
            raise ValueError("window_duration_seconds must be positive")
        if self.window_file_count <= 0:
            raise ValueError("window_file_count must be positive")
        if self.max_pending_windows <= 0:
            raise ValueError("max_pending_windows must be positive")
        if self.capture_buffer_megabytes <= 0:
            raise ValueError("capture_buffer_megabytes must be positive")
        if self.update_interval_seconds <= 0:
            raise ValueError("update_interval_seconds must be positive")
        capture_filter = _normalize_capture_filter(self.capture_filter)
        object.__setattr__(self, "capture_filter", capture_filter)
        if self.output_format.lower() != DEFAULT_OUTPUT_FORMAT:
            raise ValueError("output_format must be pcap for the staged-live seam")
        object.__setattr__(self, "output_format", DEFAULT_OUTPUT_FORMAT)
        if not self.dumpcap_binary.strip():
            raise ValueError("dumpcap_binary must not be blank")


@dataclass(frozen=True)
class ClosedCaptureWindow:
    path: Path
    interface: str
    observed_at: float
    notification: str
    sequence_number: int | None = None
    slot_index: int | None = None
    rolled_over: bool = False


@dataclass(frozen=True)
class CaptureBacklogSnapshot:
    pending_windows: int
    pending_paths: tuple[Path, ...]
    oldest_pending_age_seconds: float | None


@dataclass(frozen=True)
class CaptureFailure:
    stage: str
    returncode: int
    stderr: str
    classification: str
    reason: str

    @property
    def is_fatal(self) -> bool:
        return self.classification == "fatal"


class CaptureBacklogExceededError(RuntimeError):
    pass


class RollingDumpcapCaptureManager:
    def __init__(
        self,
        config: DumpcapCaptureConfig,
        *,
        time_source: Callable[[], float] | None = None,
    ) -> None:
        self.config = config
        self.time_source = time_source or time.monotonic
        self._next_sequence_number = 0
        self._pending_windows: Deque[ClosedCaptureWindow] = deque()

    @property
    def capture_output_prefix(self) -> Path:
        return self.config.spool_dir / f"{_safe_interface_slug(self.config.interface)}-window"

    def window_slot_for_sequence(self, sequence_number: int) -> int:
        if sequence_number < 0:
            raise ValueError("sequence_number must be non-negative")
        return sequence_number % self.config.window_file_count

    def window_path_for_sequence(self, sequence_number: int) -> Path:
        slot_index = self.window_slot_for_sequence(sequence_number)
        return self.config.spool_dir / (
            f"{_safe_interface_slug(self.config.interface)}-window-{slot_index:05d}."
            f"{self.config.output_format}"
        )

    def build_dumpcap_command(self, output_prefix: Path | None = None) -> list[str]:
        prefix = Path(output_prefix) if output_prefix is not None else self.capture_output_prefix
        return [
            self.config.dumpcap_binary,
            "-i",
            self.config.interface,
            "-f",
            self.config.capture_filter,
            "-w",
            str(prefix),
            "-F",
            self.config.output_format,
            "-B",
            str(self.config.capture_buffer_megabytes),
            "--update-interval",
            _format_number(self.config.update_interval_seconds),
            "-b",
            f"duration:{_format_number(self.config.window_duration_seconds)}",
            "-b",
            f"files:{self.config.window_file_count}",
            "-b",
            f"printname:{prefix}",
        ]

    def launch_dumpcap(
        self,
        output_prefix: Path | None = None,
        *,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> subprocess.Popen[str]:
        command = self.build_dumpcap_command(output_prefix=output_prefix)
        return popen_factory(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def parse_closed_window_notification(
        self,
        line: str,
        *,
        observed_at: float | None = None,
    ) -> ClosedCaptureWindow | None:
        matches = list(_WINDOW_PATH_RE.finditer(line))
        if not matches:
            return None
        path = Path(matches[-1].group("path").rstrip(".,;"))
        observed = self.time_source() if observed_at is None else observed_at
        slot_index = self._extract_slot_index(path)
        return ClosedCaptureWindow(
            path=path,
            interface=self.config.interface,
            observed_at=observed,
            notification=line,
            slot_index=slot_index,
            rolled_over=False,
        )

    def record_closed_window_notification(
        self,
        line: str,
        *,
        observed_at: float | None = None,
    ) -> ClosedCaptureWindow | None:
        event = self.parse_closed_window_notification(line, observed_at=observed_at)
        if event is None:
            return None
        sequence_number = self._next_sequence_number
        self._next_sequence_number += 1
        event = replace(
            event,
            sequence_number=sequence_number,
            rolled_over=sequence_number >= self.config.window_file_count,
        )
        if len(self._pending_windows) >= self.config.max_pending_windows:
            raise CaptureBacklogExceededError(
                "pending closed windows exceeded the configured ceiling"
            )
        self._pending_windows.append(event)
        return event

    def acknowledge_window_consumed(self, window_path: Path) -> ClosedCaptureWindow:
        path = Path(window_path)
        for index, pending in enumerate(self._pending_windows):
            if pending.path == path:
                self._pending_windows.rotate(-index)
                consumed = self._pending_windows.popleft()
                self._pending_windows.rotate(index)
                return consumed
        raise KeyError(f"window path not tracked as pending: {path}")

    def backlog_snapshot(self, *, now: float | None = None) -> CaptureBacklogSnapshot:
        current_time = self.time_source() if now is None else now
        pending_paths = tuple(window.path for window in self._pending_windows)
        if not self._pending_windows:
            return CaptureBacklogSnapshot(
                pending_windows=0,
                pending_paths=(),
                oldest_pending_age_seconds=None,
            )
        oldest = min(window.observed_at for window in self._pending_windows)
        return CaptureBacklogSnapshot(
            pending_windows=len(self._pending_windows),
            pending_paths=pending_paths,
            oldest_pending_age_seconds=current_time - oldest,
        )

    def classify_capture_failure(
        self,
        *,
        stage: str,
        returncode: int,
        stderr: str,
    ) -> CaptureFailure:
        normalized = " ".join(stderr.split()).strip().lower()
        if any(marker in normalized for marker in _RECOVERABLE_FAILURE_MARKERS):
            classification = "recoverable"
            reason = "expected_stop_or_rotation"
        elif any(marker in normalized for marker in _FATAL_FAILURE_MARKERS):
            classification = "fatal"
            reason = "fatal_startup_or_runtime_error"
        elif returncode == 0:
            classification = "recoverable"
            reason = "clean_exit"
        elif stage in {"startup", "launch"}:
            classification = "fatal"
            reason = "startup_failure"
        else:
            classification = "fatal"
            reason = "runtime_failure"
        return CaptureFailure(
            stage=stage,
            returncode=returncode,
            stderr=stderr,
            classification=classification,
            reason=reason,
        )

    @staticmethod
    def _extract_slot_index(path: Path) -> int | None:
        stem = path.stem
        match = re.search(r"(?:-|_)(\d+)$", stem)
        if match is None:
            return None
        return int(match.group(1))
