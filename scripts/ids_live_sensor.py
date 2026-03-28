from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_feature_contract import FlowFeatureContract
from scripts.ids_inference import DEFAULT_FEATURE_COLUMNS_PATH, DEFAULT_MODEL_PATH, DEFAULT_THRESHOLD, build_inferencer
from scripts.ids_live_capture import (
    CaptureBacklogExceededError,
    ClosedCaptureWindow,
    DumpcapCaptureConfig,
    RollingDumpcapCaptureManager,
)
from scripts.ids_live_flow_bridge import (
    BridgeWindowResult,
    DEFAULT_ADAPTER_PROFILE_ID,
    DEFAULT_EXTRACTOR_COMMAND_PREFIX,
    LiveFlowBridge,
    LiveFlowBridgeConfig,
)
from scripts.ids_live_sensor_sinks import (
    DEFAULT_ALERTS_OUTPUT_PATH,
    DEFAULT_QUARANTINE_OUTPUT_PATH,
    DEFAULT_SUMMARY_OUTPUT_PATH,
    LiveSensorLocalSink,
)
from scripts.ids_realtime_pipeline import (
    DEFAULT_FLUSH_INTERVAL_SECONDS,
    DEFAULT_MAX_BATCH_SIZE,
    RealtimePipelineRunner,
)


DEFAULT_INTERFACE = "eth0"
DEFAULT_SPOOL_DIRNAME = "live_sensor_spool"
DEFAULT_CAPTURE_WINDOW_DURATION_SECONDS = 2.5
DEFAULT_CAPTURE_WINDOW_FILE_COUNT = 2
DEFAULT_MAX_PENDING_WINDOWS = 2
DEFAULT_CAPTURE_BUFFER_MEGABYTES = 64
DEFAULT_UPDATE_INTERVAL_SECONDS = 0.5
DEFAULT_FLOW_OUTPUT_DIRNAME = "flows"


@dataclass(frozen=True)
class LiveSensorDaemonConfig:
    interface: str = DEFAULT_INTERFACE
    spool_dir: Path = Path(DEFAULT_SPOOL_DIRNAME)
    capture_window_duration_seconds: float = DEFAULT_CAPTURE_WINDOW_DURATION_SECONDS
    capture_window_file_count: int = DEFAULT_CAPTURE_WINDOW_FILE_COUNT
    max_pending_windows: int = DEFAULT_MAX_PENDING_WINDOWS
    capture_buffer_megabytes: int = DEFAULT_CAPTURE_BUFFER_MEGABYTES
    update_interval_seconds: float = DEFAULT_UPDATE_INTERVAL_SECONDS
    extractor_command_prefix: tuple[str, ...] = DEFAULT_EXTRACTOR_COMMAND_PREFIX
    adapter_profile_id: str = DEFAULT_ADAPTER_PROFILE_ID
    alerts_output_path: Path = DEFAULT_ALERTS_OUTPUT_PATH
    quarantine_output_path: Path = DEFAULT_QUARANTINE_OUTPUT_PATH
    summary_output_path: Path = DEFAULT_SUMMARY_OUTPUT_PATH
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE
    flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS
    feature_columns_path: Path = DEFAULT_FEATURE_COLUMNS_PATH
    model_path: Path = DEFAULT_MODEL_PATH
    threshold: float = DEFAULT_THRESHOLD
    bundle_root: Path | None = None
    config_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "interface", str(self.interface).strip())
        object.__setattr__(self, "spool_dir", Path(self.spool_dir).resolve())
        object.__setattr__(self, "alerts_output_path", Path(self.alerts_output_path))
        object.__setattr__(self, "quarantine_output_path", Path(self.quarantine_output_path))
        object.__setattr__(self, "summary_output_path", Path(self.summary_output_path))
        object.__setattr__(self, "feature_columns_path", Path(self.feature_columns_path))
        object.__setattr__(self, "model_path", Path(self.model_path))
        if self.bundle_root is not None:
            object.__setattr__(self, "bundle_root", Path(self.bundle_root))
        if self.config_path is not None:
            object.__setattr__(self, "config_path", Path(self.config_path))
        if self.capture_window_duration_seconds <= 0:
            raise ValueError("capture_window_duration_seconds must be positive")
        if self.capture_window_file_count <= 0:
            raise ValueError("capture_window_file_count must be positive")
        if self.max_pending_windows <= 0:
            raise ValueError("max_pending_windows must be positive")
        if self.capture_buffer_megabytes <= 0:
            raise ValueError("capture_buffer_megabytes must be positive")
        if self.update_interval_seconds <= 0:
            raise ValueError("update_interval_seconds must be positive")
        if self.max_batch_size <= 0:
            raise ValueError("max_batch_size must be positive")
        if self.flush_interval_seconds <= 0:
            raise ValueError("flush_interval_seconds must be positive")
        if not self.interface:
            raise ValueError("interface must not be blank")
        if not self.adapter_profile_id.strip():
            raise ValueError("adapter_profile_id must not be blank")
        if not self.extractor_command_prefix:
            raise ValueError("extractor_command_prefix must not be blank")


@dataclass
class LiveSensorDaemonSummary:
    processed_windows: int = 0
    queued_windows: int = 0
    restartable_failures: int = 0
    recoverable_window_errors: int = 0
    recoverable_quarantines: int = 0
    benign_predictions: int = 0


class LiveSensorDaemon:
    def __init__(
        self,
        config: LiveSensorDaemonConfig,
        *,
        capture_manager: RollingDumpcapCaptureManager | None = None,
        bridge: LiveFlowBridge | None = None,
        runtime_runner: RealtimePipelineRunner | None = None,
        sink: LiveSensorLocalSink | None = None,
        time_source: Callable[[], float] | None = None,
    ) -> None:
        self.config = config
        self.time_source = time_source or time.monotonic
        capture_config = DumpcapCaptureConfig(
            interface=config.interface,
            spool_dir=config.spool_dir,
            window_duration_seconds=config.capture_window_duration_seconds,
            window_file_count=config.capture_window_file_count,
            max_pending_windows=config.max_pending_windows,
            capture_buffer_megabytes=config.capture_buffer_megabytes,
            update_interval_seconds=config.update_interval_seconds,
        )
        self.capture_manager = capture_manager or RollingDumpcapCaptureManager(
            capture_config,
            time_source=self.time_source,
        )
        self.bridge = bridge or LiveFlowBridge(
            LiveFlowBridgeConfig(
                extractor_command_prefix=config.extractor_command_prefix,
                adapter_profile_id=config.adapter_profile_id,
            )
        )
        self.runtime_runner = runtime_runner or RealtimePipelineRunner(
            contract=FlowFeatureContract.from_feature_file(config.feature_columns_path),
            inferencer=build_inferencer(
                bundle_root=config.bundle_root,
                config_path=config.config_path,
                model_path=config.model_path,
                feature_columns_path=config.feature_columns_path,
                threshold=config.threshold,
            ),
            max_batch_size=config.max_batch_size,
            flush_interval_seconds=config.flush_interval_seconds,
            time_source=self.time_source,
        )
        self.sink = sink or LiveSensorLocalSink(
            alerts_output_path=config.alerts_output_path,
            quarantine_output_path=config.quarantine_output_path,
            summary_output_path=config.summary_output_path,
        )
        self._pending_windows: deque[ClosedCaptureWindow] = deque()
        self._summary = LiveSensorDaemonSummary()
        self._flow_output_dir = self.config.spool_dir / DEFAULT_FLOW_OUTPUT_DIRNAME

    @property
    def pending_window_count(self) -> int:
        return len(self._pending_windows)

    def enqueue_notification_line(
        self,
        line: str,
        *,
        observed_at: float | None = None,
    ) -> ClosedCaptureWindow | None:
        try:
            window = self.capture_manager.record_closed_window_notification(
                line,
                observed_at=observed_at,
            )
        except CaptureBacklogExceededError:
            self._summary.restartable_failures += 1
            self.sink.capture_summary(reason="capture-backlog-exceeded")
            raise
        if window is None:
            return None
        self._pending_windows.append(window)
        self._summary.queued_windows += 1
        self._update_queue_telemetry(processed_window_increment=0)
        self.sink.capture_summary(reason="window-enqueued")
        return window

    def process_pending_windows(self) -> list[BridgeWindowResult]:
        processed: list[BridgeWindowResult] = []
        while self._pending_windows:
            window = self._pending_windows.popleft()
            start = self.time_source()
            result: BridgeWindowResult | None = None
            success = False
            try:
                result = self.bridge.bridge_window(window, output_dir=self._flow_output_dir)
                self._apply_bridge_result(result)
                processed.append(result)
                success = True
            finally:
                self._cleanup_window_artifacts(window, result)
                try:
                    self.capture_manager.acknowledge_window_consumed(window.path)
                except KeyError:
                    pass
                elapsed = max(0.0, self.time_source() - start)
                self._update_queue_telemetry(
                    extractor_runtime_seconds=elapsed,
                    processed_window_increment=1 if success else 0,
                )
                if success:
                    self._summary.processed_windows += 1
                    self.sink.capture_summary(reason="window-processed")
        return processed

    def serve_notification_lines(self, notification_lines: Iterable[str]) -> LiveSensorDaemonSummary:
        for line in notification_lines:
            self.enqueue_notification_line(line)
            self.process_pending_windows()
        self.process_pending_windows()
        self.close()
        return self._summary

    def serve_capture_session(
        self,
        *,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        notification_reader: Callable[[subprocess.Popen[str]], Iterable[str]] | None = None,
    ) -> dict[str, Any]:
        process = self.capture_manager.launch_dumpcap(
            output_prefix=self.capture_manager.capture_output_prefix,
            popen_factory=popen_factory,
        )
        reader = notification_reader or self._default_notification_reader
        try:
            for line in reader(process):
                self.enqueue_notification_line(line)
                self.process_pending_windows()
            self.process_pending_windows()
            return self.close()
        finally:
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

    def close(self) -> dict[str, Any]:
        summary = self.sink.close()
        return summary

    def _apply_bridge_result(self, result: BridgeWindowResult) -> None:
        for error in result.window_errors:
            self.sink.record_extractor_failure(str(error.get("reason", "window_error")))
            self._summary.recoverable_window_errors += 1
        for quarantine in result.adapter_quarantines:
            self.sink.record_quarantine(quarantine)
            self._summary.recoverable_quarantines += 1
        for adapted in result.adapted_records:
            runtime_alerts, runtime_quarantines, flushed = self.runtime_runner.ingest_record(
                adapted["record"],
                record_index=adapted.get("record_index"),
                now=self.time_source(),
            )
            for quarantine in runtime_quarantines:
                self.sink.record_quarantine(quarantine)
            for alert in runtime_alerts:
                if alert["is_alert"]:
                    self.sink.record_alert(alert)
                else:
                    self.sink.record_benign_prediction()
                    self._summary.benign_predictions += 1
            if flushed:
                self.sink.capture_summary(reason="runtime-flush")
        runtime_alerts, runtime_quarantines, flushed = self.runtime_runner.finalize()
        for quarantine in runtime_quarantines:
            self.sink.record_quarantine(quarantine)
        for alert in runtime_alerts:
            if alert["is_alert"]:
                self.sink.record_alert(alert)
            else:
                self.sink.record_benign_prediction()
                self._summary.benign_predictions += 1
        if flushed:
            self.sink.capture_summary(reason="runtime-finalize")

    def _cleanup_window_artifacts(
        self,
        window: ClosedCaptureWindow,
        result: BridgeWindowResult | None,
    ) -> None:
        for path in (window.path, result.extractor_output_path if result is not None else None):
            if path is None:
                continue
            try:
                Path(path).unlink()
            except FileNotFoundError:
                continue

    def _update_queue_telemetry(
        self,
        *,
        extractor_runtime_seconds: float = 0.0,
        processed_window_increment: int = 0,
    ) -> None:
        snapshot = self.capture_manager.backlog_snapshot(now=self.time_source())
        self.sink.record_window_telemetry(
            queue_depth=snapshot.pending_windows,
            oldest_pending_window_age_seconds=snapshot.oldest_pending_age_seconds or 0.0,
            extractor_runtime_seconds=extractor_runtime_seconds,
            capture_window_seconds=self.config.capture_window_duration_seconds,
            pending_window_count=snapshot.pending_windows,
            processed_window_increment=processed_window_increment,
        )

    @staticmethod
    def _default_notification_reader(
        process: subprocess.Popen[str],
    ) -> Iterator[str]:
        if process.stderr is None:
            return
        for line in process.stderr:
            stripped = line.rstrip("\n")
            if stripped:
                yield stripped


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compose the staged-live IDS daemon from capture, bridge, runtime, and sink modules."
    )
    parser.add_argument("--interface", default=DEFAULT_INTERFACE)
    parser.add_argument("--spool-dir", type=Path, default=Path(DEFAULT_SPOOL_DIRNAME))
    parser.add_argument(
        "--capture-window-duration-seconds",
        type=float,
        default=DEFAULT_CAPTURE_WINDOW_DURATION_SECONDS,
    )
    parser.add_argument(
        "--capture-window-file-count",
        type=int,
        default=DEFAULT_CAPTURE_WINDOW_FILE_COUNT,
    )
    parser.add_argument("--max-pending-windows", type=int, default=DEFAULT_MAX_PENDING_WINDOWS)
    parser.add_argument(
        "--capture-buffer-megabytes",
        type=int,
        default=DEFAULT_CAPTURE_BUFFER_MEGABYTES,
    )
    parser.add_argument(
        "--update-interval-seconds",
        type=float,
        default=DEFAULT_UPDATE_INTERVAL_SECONDS,
    )
    parser.add_argument(
        "--extractor-command-prefix",
        nargs="+",
        default=list(DEFAULT_EXTRACTOR_COMMAND_PREFIX),
    )
    parser.add_argument("--adapter-profile-id", default=DEFAULT_ADAPTER_PROFILE_ID)
    parser.add_argument("--alerts-output-path", type=Path, default=DEFAULT_ALERTS_OUTPUT_PATH)
    parser.add_argument(
        "--quarantine-output-path",
        type=Path,
        default=DEFAULT_QUARANTINE_OUTPUT_PATH,
    )
    parser.add_argument("--summary-output-path", type=Path, default=DEFAULT_SUMMARY_OUTPUT_PATH)
    parser.add_argument("--max-batch-size", type=int, default=DEFAULT_MAX_BATCH_SIZE)
    parser.add_argument(
        "--flush-interval-seconds",
        type=float,
        default=DEFAULT_FLUSH_INTERVAL_SECONDS,
    )
    parser.add_argument(
        "--feature-columns-path",
        type=Path,
        default=DEFAULT_FEATURE_COLUMNS_PATH,
    )
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    return parser.parse_args(argv)


def build_daemon_from_args(args: argparse.Namespace) -> LiveSensorDaemon:
    config = LiveSensorDaemonConfig(
        interface=args.interface,
        spool_dir=args.spool_dir,
        capture_window_duration_seconds=args.capture_window_duration_seconds,
        capture_window_file_count=args.capture_window_file_count,
        max_pending_windows=args.max_pending_windows,
        capture_buffer_megabytes=args.capture_buffer_megabytes,
        update_interval_seconds=args.update_interval_seconds,
        extractor_command_prefix=tuple(args.extractor_command_prefix),
        adapter_profile_id=args.adapter_profile_id,
        alerts_output_path=args.alerts_output_path,
        quarantine_output_path=args.quarantine_output_path,
        summary_output_path=args.summary_output_path,
        max_batch_size=args.max_batch_size,
        flush_interval_seconds=args.flush_interval_seconds,
        feature_columns_path=args.feature_columns_path,
        model_path=args.model_path,
        threshold=args.threshold,
    )
    return LiveSensorDaemon(config)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    daemon = build_daemon_from_args(args)
    daemon.serve_capture_session()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
