from __future__ import annotations

import argparse
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

from ids.core.feature_contract import FlowFeatureContract
from ids.runtime.inference import IDSInferencer, build_model_config
from ids.runtime.live_capture import (
    CaptureBacklogExceededError,
    CaptureFailure,
    ClosedCaptureWindow,
    DumpcapCaptureConfig,
    RollingDumpcapCaptureManager,
)
from ids.runtime.live_flow_bridge import (
    BridgeWindowResult,
    DEFAULT_ADAPTER_PROFILE_ID,
    DEFAULT_EXTRACTOR_COMMAND_PREFIX,
    LiveFlowBridge,
    LiveFlowBridgeConfig,
)
from ids.runtime.live_sensor_sinks import (
    DEFAULT_ALERTS_OUTPUT_PATH,
    DEFAULT_QUARANTINE_OUTPUT_PATH,
    DEFAULT_SUMMARY_OUTPUT_PATH,
    LiveSensorLocalSink,
    default_summary_output_stream,
)
from ids.runtime.realtime_pipeline import (
    DEFAULT_FLUSH_INTERVAL_SECONDS,
    DEFAULT_MAX_BATCH_SIZE,
    RealtimePipelineRunner,
)
from scripts.ids_model_bundle import DEFAULT_ACTIVATION_RECORD_NAME, build_bundle_status_payload


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
    dumpcap_binary: str = "dumpcap"
    extractor_command_prefix: tuple[str, ...] = DEFAULT_EXTRACTOR_COMMAND_PREFIX
    adapter_profile_id: str = DEFAULT_ADAPTER_PROFILE_ID
    alerts_output_path: Path = DEFAULT_ALERTS_OUTPUT_PATH
    quarantine_output_path: Path = DEFAULT_QUARANTINE_OUTPUT_PATH
    summary_output_path: Path = DEFAULT_SUMMARY_OUTPUT_PATH
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE
    flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS
    activation_path: Path = Path(DEFAULT_ACTIVATION_RECORD_NAME)

    def __post_init__(self) -> None:
        object.__setattr__(self, "interface", str(self.interface).strip())
        object.__setattr__(self, "spool_dir", Path(self.spool_dir).resolve())
        object.__setattr__(self, "alerts_output_path", Path(self.alerts_output_path))
        object.__setattr__(self, "quarantine_output_path", Path(self.quarantine_output_path))
        object.__setattr__(self, "summary_output_path", Path(self.summary_output_path))
        object.__setattr__(self, "activation_path", Path(self.activation_path).resolve())
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
        if not self.dumpcap_binary.strip():
            raise ValueError("dumpcap_binary must not be blank")


@dataclass
class LiveSensorDaemonSummary:
    processed_windows: int = 0
    queued_windows: int = 0
    restartable_failures: int = 0
    recoverable_window_errors: int = 0
    recoverable_quarantines: int = 0
    benign_predictions: int = 0


class CaptureSessionFatalError(RuntimeError):
    def __init__(self, failure: CaptureFailure) -> None:
        self.failure = failure
        super().__init__(
            "fatal dumpcap exit "
            f"(stage={failure.stage}, returncode={failure.returncode}, reason={failure.reason})"
        )


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
            dumpcap_binary=config.dumpcap_binary,
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
        if runtime_runner is None:
            runtime_model_config = build_model_config(activation_path=config.activation_path)
            runtime_runner = RealtimePipelineRunner(
                contract=FlowFeatureContract.from_feature_file(
                    runtime_model_config.feature_columns_path
                ),
                inferencer=IDSInferencer(runtime_model_config),
                max_batch_size=config.max_batch_size,
                flush_interval_seconds=config.flush_interval_seconds,
                time_source=self.time_source,
            )
        self.runtime_runner = runtime_runner
        self.sink = sink or LiveSensorLocalSink(
            alerts_output_path=config.alerts_output_path,
            quarantine_output_path=config.quarantine_output_path,
            summary_output_path=config.summary_output_path,
            summary_output_stream=default_summary_output_stream(),
        )
        if hasattr(self.sink, "set_active_bundle_state"):
            active_bundle = build_bundle_status_payload(config.activation_path)
            if active_bundle.get("runtime_ready"):
                self.sink.set_active_bundle_state(
                    activation_path=active_bundle["activation_path"],
                    active_bundle_root=active_bundle["active_bundle_root"],
                    active_bundle_name=active_bundle["active_bundle_name"],
                    compatibility_status="compatible",
                    verification_status=str(active_bundle.get("verification_status", "verified")),
                    manifest_version=active_bundle.get("manifest_version"),
                    activated_at=active_bundle.get("activated_at"),
                    previous_bundle_root=active_bundle.get("previous_bundle_root"),
                    previous_bundle_name=active_bundle.get("previous_bundle_name"),
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
        observed_lines: list[str] = []
        try:
            for line in reader(process):
                if self.capture_manager.parse_closed_window_notification(str(line)) is None:
                    observed_lines.append(line)
                self.enqueue_notification_line(line)
                self.process_pending_windows()
            self.process_pending_windows()
            failure = self._classify_capture_session_exit(process, observed_lines)
            if failure.is_fatal:
                self._summary.restartable_failures += 1
                self.close(reason="capture-failure")
                raise CaptureSessionFatalError(failure)
            return self.close()
        finally:
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

    def close(self, *, reason: str = "close") -> dict[str, Any]:
        self._finalize_runtime(reason="runtime-finalize")
        summary = self.sink.close(reason=reason)
        return summary

    def _classify_capture_session_exit(
        self,
        process: subprocess.Popen[str],
        observed_lines: Sequence[str],
    ) -> CaptureFailure:
        returncode = process.wait()
        stderr_lines = [line for line in observed_lines if str(line).strip()]
        if process.stderr is not None:
            remaining_stderr = process.stderr.read()
            if remaining_stderr:
                stderr_lines.append(remaining_stderr)
        return self.capture_manager.classify_capture_failure(
            stage="runtime",
            returncode=returncode,
            stderr="\n".join(stderr_lines),
        )

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
            self._record_runtime_results(
                runtime_alerts,
                runtime_quarantines,
                flushed=flushed,
                summary_reason="runtime-flush",
            )
        runtime_alerts, flushed = self.runtime_runner.flush_if_due(now=self.time_source())
        self._record_runtime_results(
            runtime_alerts,
            (),
            flushed=flushed,
            summary_reason="runtime-flush",
        )

    def _finalize_runtime(self, *, reason: str) -> None:
        runtime_alerts, flushed = self.runtime_runner.finalize()
        self._record_runtime_results(
            runtime_alerts,
            (),
            flushed=flushed,
            summary_reason=reason,
        )

    def _record_runtime_results(
        self,
        runtime_alerts: Iterable[dict[str, Any]],
        runtime_quarantines: Iterable[dict[str, Any]],
        *,
        flushed: bool,
        summary_reason: str,
    ) -> None:
        for quarantine in runtime_quarantines:
            self.sink.record_quarantine(quarantine)
        for alert in runtime_alerts:
            if alert["is_alert"]:
                self.sink.record_alert(alert)
            else:
                self.sink.record_benign_prediction()
                self._summary.benign_predictions += 1
        if flushed:
            self.sink.capture_summary(reason=summary_reason)

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
    parser.add_argument("--dumpcap-binary", default="dumpcap")
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
    parser.add_argument("--activation-path", type=Path, required=True)
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
        dumpcap_binary=args.dumpcap_binary,
        extractor_command_prefix=tuple(args.extractor_command_prefix),
        adapter_profile_id=args.adapter_profile_id,
        alerts_output_path=args.alerts_output_path,
        quarantine_output_path=args.quarantine_output_path,
        summary_output_path=args.summary_output_path,
        max_batch_size=args.max_batch_size,
        flush_interval_seconds=args.flush_interval_seconds,
        activation_path=args.activation_path,
    )
    return LiveSensorDaemon(config)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    daemon = build_daemon_from_args(args)
    daemon.serve_capture_session()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
