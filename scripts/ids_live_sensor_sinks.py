from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterable, Mapping


DEFAULT_ALERTS_OUTPUT_PATH = Path("ids_live_alerts.jsonl")
DEFAULT_QUARANTINE_OUTPUT_PATH = Path("ids_live_quarantine.jsonl")
DEFAULT_SUMMARY_OUTPUT_PATH = Path("ids_live_sensor_summary.jsonl")


@dataclass(frozen=True)
class LiveSensorWindowTelemetry:
    queue_depth: int
    oldest_pending_window_age_seconds: float
    extractor_runtime_seconds: float
    capture_window_seconds: float | None = None
    pending_window_count: int = 0
    processed_window_count: int = 0


@dataclass
class LiveSensorSinkSummary:
    alert_records: int = 0
    quarantine_records: int = 0
    benign_predictions: int = 0
    skipped_non_tcp_udp_records: int = 0
    processed_windows: int = 0
    extractor_failures: int = 0
    latest_queue_depth: int = 0
    oldest_pending_window_age_seconds: float = 0.0
    latest_extractor_runtime_seconds: float = 0.0
    total_extractor_runtime_seconds: float = 0.0
    window_telemetry: LiveSensorWindowTelemetry | None = None
    extractor_failure_reasons: list[str] = field(default_factory=list)


def _validate_output_path(path: Path) -> None:
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"Output path must be a file, got directory: {path}")


def _validate_output_collisions(*paths: Path | None) -> None:
    resolved_paths = [path.resolve() for path in paths if path is not None]
    collisions: list[str] = []
    for index, left in enumerate(resolved_paths):
        for right in resolved_paths[index + 1 :]:
            if left == right:
                collisions.append(str(left))
    if collisions:
        raise ValueError(
            "Live sensor output paths must be distinct. Collisions: "
            + ", ".join(collisions)
        )


def resolve_output_paths(
    *,
    alerts_output_path: Path | None = None,
    quarantine_output_path: Path | None = None,
    summary_output_path: Path | None = None,
) -> tuple[Path, Path, Path | None]:
    resolved_alerts = (alerts_output_path or DEFAULT_ALERTS_OUTPUT_PATH).resolve()
    resolved_quarantine = (quarantine_output_path or DEFAULT_QUARANTINE_OUTPUT_PATH).resolve()
    resolved_summary = (
        summary_output_path.resolve()
        if summary_output_path is not None
        else DEFAULT_SUMMARY_OUTPUT_PATH.resolve()
    )
    _validate_output_collisions(resolved_alerts, resolved_quarantine, resolved_summary)
    _validate_output_path(resolved_alerts)
    _validate_output_path(resolved_quarantine)
    if resolved_summary is not None:
        _validate_output_path(resolved_summary)
    return resolved_alerts, resolved_quarantine, resolved_summary


def _write_jsonl_records(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(dict(record), ensure_ascii=False))
            handle.write("\n")


def _reserve_staged_path(final_path: Path, *, suffix: str) -> Path:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=final_path.parent,
        prefix=f".{final_path.stem}.",
        suffix=suffix,
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def _cleanup_staged_paths(paths: Iterable[Path]) -> None:
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            continue


def _restore_backup_path(backup_path: Path, final_path: Path) -> None:
    backup_path.replace(final_path)


def _promote_staged_output_paths_transactionally(
    staged_paths: list[tuple[Path, Path]],
) -> None:
    backup_paths: list[tuple[Path, Path]] = []
    promoted_final_paths: list[Path] = []
    try:
        for _, final_path in staged_paths:
            if not final_path.exists():
                continue
            backup_path = _reserve_staged_path(
                final_path,
                suffix=f"{final_path.suffix}.bak" if final_path.suffix else ".bak",
            )
            final_path.replace(backup_path)
            backup_paths.append((backup_path, final_path))

        for temp_path, final_path in staged_paths:
            temp_path.replace(final_path)
            promoted_final_paths.append(final_path)
    except BaseException as exc:
        restore_error: BaseException | None = None
        for backup_path, final_path in reversed(backup_paths):
            if backup_path.exists():
                try:
                    _restore_backup_path(backup_path, final_path)
                except BaseException as restore_exc:
                    if restore_error is None:
                        restore_error = restore_exc
        backed_up_final_paths = {final_path for _, final_path in backup_paths}
        _cleanup_staged_paths(
            final_path
            for final_path in promoted_final_paths
            if final_path not in backed_up_final_paths
        )
        _cleanup_staged_paths(temp_path for temp_path, _ in staged_paths)
        if restore_error is not None:
            raise exc from restore_error
        raise
    else:
        _cleanup_staged_paths(backup_path for backup_path, _ in backup_paths)


def _summary_event_from_snapshot(
    summary: LiveSensorSinkSummary,
    *,
    reason: str,
    timestamp_source: Callable[[], str] | None = None,
) -> dict[str, Any]:
    telemetry = summary.window_telemetry
    timestamp = (
        timestamp_source()
        if timestamp_source is not None
        else datetime.now(timezone.utc).isoformat()
    )
    event: dict[str, Any] = {
        "event_type": "live_sensor_summary",
        "reason": reason,
        "timestamp": timestamp,
        "alert_records": summary.alert_records,
        "quarantine_records": summary.quarantine_records,
        "benign_predictions": summary.benign_predictions,
        "skipped_non_tcp_udp_records": summary.skipped_non_tcp_udp_records,
        "processed_windows": summary.processed_windows,
        "extractor_failures": summary.extractor_failures,
        "latest_queue_depth": summary.latest_queue_depth,
        "oldest_pending_window_age_seconds": summary.oldest_pending_window_age_seconds,
        "latest_extractor_runtime_seconds": summary.latest_extractor_runtime_seconds,
        "total_extractor_runtime_seconds": summary.total_extractor_runtime_seconds,
    }
    if telemetry is not None:
        event["window_telemetry"] = asdict(telemetry)
    if summary.extractor_failure_reasons:
        event["extractor_failure_reasons"] = list(summary.extractor_failure_reasons)
    return event


def render_journald_summary(event: Mapping[str, Any]) -> str:
    parts = [
        "ids-live-sensor",
        f"reason={event.get('reason', 'periodic')}",
        f"queue_depth={event.get('latest_queue_depth', 0)}",
        "oldest_pending_window_age_seconds="
        f"{event.get('oldest_pending_window_age_seconds', 0.0):.3f}",
        "extractor_runtime_seconds="
        f"{event.get('latest_extractor_runtime_seconds', 0.0):.3f}",
        f"alerts={event.get('alert_records', 0)}",
        f"quarantines={event.get('quarantine_records', 0)}",
        f"benign={event.get('benign_predictions', 0)}",
        f"skipped_non_tcp_udp={event.get('skipped_non_tcp_udp_records', 0)}",
        f"processed_windows={event.get('processed_windows', 0)}",
        f"extractor_failures={event.get('extractor_failures', 0)}",
    ]
    return " ".join(parts)


class LiveSensorLocalSink:
    def __init__(
        self,
        *,
        alerts_output_path: Path | None = None,
        quarantine_output_path: Path | None = None,
        summary_output_path: Path | None = None,
        timestamp_source: Callable[[], str] | None = None,
    ) -> None:
        (
            self.alerts_output_path,
            self.quarantine_output_path,
            self.summary_output_path,
        ) = resolve_output_paths(
            alerts_output_path=alerts_output_path,
            quarantine_output_path=quarantine_output_path,
            summary_output_path=summary_output_path,
        )
        self._timestamp_source = timestamp_source
        self._alert_records: list[dict[str, Any]] = []
        self._quarantine_records: list[dict[str, Any]] = []
        self._summary_events: list[dict[str, Any]] = []
        self._summary = LiveSensorSinkSummary()
        self._closed = False

    def record_alert(self, event: Mapping[str, Any]) -> None:
        self._ensure_open()
        self._alert_records.append(dict(event))
        self._summary.alert_records += 1

    def record_quarantine(self, event: Mapping[str, Any]) -> None:
        self._ensure_open()
        self._quarantine_records.append(dict(event))
        self._summary.quarantine_records += 1

    def record_benign_prediction(self, count: int = 1) -> None:
        self._ensure_open()
        if count < 0:
            raise ValueError("count must be non-negative")
        self._summary.benign_predictions += int(count)

    def record_skipped_non_tcp_udp(self, count: int = 1) -> None:
        self._ensure_open()
        if count < 0:
            raise ValueError("count must be non-negative")
        self._summary.skipped_non_tcp_udp_records += int(count)

    def record_extractor_failure(self, reason: str) -> None:
        self._ensure_open()
        cleaned_reason = str(reason).strip()
        if not cleaned_reason:
            raise ValueError("reason must not be blank")
        self._summary.extractor_failures += 1
        self._summary.extractor_failure_reasons.append(cleaned_reason)

    def record_window_telemetry(
        self,
        *,
        queue_depth: int,
        oldest_pending_window_age_seconds: float,
        extractor_runtime_seconds: float,
        capture_window_seconds: float | None = None,
        pending_window_count: int = 0,
        processed_window_increment: int = 1,
    ) -> LiveSensorWindowTelemetry:
        self._ensure_open()
        telemetry = LiveSensorWindowTelemetry(
            queue_depth=int(queue_depth),
            oldest_pending_window_age_seconds=float(oldest_pending_window_age_seconds),
            extractor_runtime_seconds=float(extractor_runtime_seconds),
            capture_window_seconds=(
                None if capture_window_seconds is None else float(capture_window_seconds)
            ),
            pending_window_count=int(pending_window_count),
            processed_window_count=int(processed_window_increment),
        )
        self._summary.window_telemetry = telemetry
        self._summary.latest_queue_depth = telemetry.queue_depth
        self._summary.oldest_pending_window_age_seconds = (
            telemetry.oldest_pending_window_age_seconds
        )
        self._summary.latest_extractor_runtime_seconds = telemetry.extractor_runtime_seconds
        self._summary.total_extractor_runtime_seconds += telemetry.extractor_runtime_seconds
        self._summary.processed_windows += telemetry.processed_window_count
        return telemetry

    def capture_summary(self, *, reason: str = "periodic") -> dict[str, Any]:
        self._ensure_open()
        event = _summary_event_from_snapshot(
            self._summary,
            reason=reason,
            timestamp_source=self._timestamp_source,
        )
        event["journald_message"] = render_journald_summary(event)
        self._summary_events.append(event)
        return event

    def snapshot_summary(self) -> dict[str, Any]:
        event = _summary_event_from_snapshot(
            self._summary,
            reason="snapshot",
            timestamp_source=self._timestamp_source,
        )
        event["journald_message"] = render_journald_summary(event)
        return event

    def flush(self) -> dict[str, Any]:
        self._ensure_open()
        if not self._summary_events:
            self.capture_summary(reason="flush")

        staged_paths: list[tuple[Path, Path]] = []
        try:
            alerts_temp_path = _reserve_staged_path(
                self.alerts_output_path,
                suffix=f"{self.alerts_output_path.suffix}.tmp"
                if self.alerts_output_path.suffix
                else ".tmp",
            )
            _write_jsonl_records(alerts_temp_path, self._alert_records)
            staged_paths.append((alerts_temp_path, self.alerts_output_path))

            quarantine_temp_path = _reserve_staged_path(
                self.quarantine_output_path,
                suffix=f"{self.quarantine_output_path.suffix}.tmp"
                if self.quarantine_output_path.suffix
                else ".tmp",
            )
            _write_jsonl_records(quarantine_temp_path, self._quarantine_records)
            staged_paths.append((quarantine_temp_path, self.quarantine_output_path))

            if self.summary_output_path is not None:
                summary_temp_path = _reserve_staged_path(
                    self.summary_output_path,
                    suffix=f"{self.summary_output_path.suffix}.tmp"
                    if self.summary_output_path.suffix
                    else ".tmp",
                )
                _write_jsonl_records(summary_temp_path, self._summary_events)
                staged_paths.append((summary_temp_path, self.summary_output_path))

            _promote_staged_output_paths_transactionally(staged_paths)
        except BaseException:
            _cleanup_staged_paths(temp_path for temp_path, _ in staged_paths)
            raise
        return self.snapshot_summary()

    def close(self) -> dict[str, Any]:
        if self._closed:
            return self.snapshot_summary()
        summary = self.flush()
        self._closed = True
        return summary

    def __enter__(self) -> "LiveSensorLocalSink":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.close()
        return False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("LiveSensorLocalSink is closed")


def write_summary_snapshot(
    sink: LiveSensorLocalSink,
    *,
    reason: str = "periodic",
) -> dict[str, Any]:
    return sink.capture_summary(reason=reason)
