from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, TextIO

import pandas as pd

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_feature_contract import FlowFeatureContract, QuarantinedFlowRecord
from scripts.ids_inference import (
    DEFAULT_FEATURE_COLUMNS_PATH,
    DEFAULT_MODEL_PATH,
    DEFAULT_THRESHOLD,
    IDSInferencer,
    build_inferencer,
)


DEFAULT_ALERTS_OUTPUT_PATH = Path("ids_alerts.jsonl")
DEFAULT_QUARANTINE_OUTPUT_PATH = Path("ids_quarantine.jsonl")
DEFAULT_MAX_BATCH_SIZE = 32
DEFAULT_FLUSH_INTERVAL_SECONDS = 1.0
_STREAM_END = object()


@dataclass(frozen=True)
class BufferedRecord:
    record_index: int
    source_record: dict[str, Any]
    passthrough: dict[str, Any]
    aligned_features: dict[str, float]


@dataclass
class PipelineSummary:
    input_mode: str
    total_records: int = 0
    valid_records: int = 0
    quarantined_records: int = 0
    schema_anomaly_records: int = 0
    alert_records: int = 0
    batch_flushes: int = 0


class RealtimePipelineRunner:
    def __init__(
        self,
        *,
        contract: FlowFeatureContract,
        inferencer: IDSInferencer,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS,
        time_source: callable | None = None,
    ) -> None:
        if max_batch_size <= 0:
            raise ValueError("max_batch_size must be positive")
        if flush_interval_seconds <= 0:
            raise ValueError("flush_interval_seconds must be positive")
        self.contract = contract
        self.inferencer = inferencer
        self.max_batch_size = int(max_batch_size)
        self.flush_interval_seconds = float(flush_interval_seconds)
        self.time_source = time_source or time.monotonic
        self._buffer: list[BufferedRecord] = []
        self._buffer_started_at: float | None = None

    def ingest_record(
        self,
        record: Mapping[str, Any],
        *,
        record_index: int,
        now: float | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        current_time = self.time_source() if now is None else now
        alerts, quarantines, flushed = self._flush_if_due(current_time)

        result = self.contract.validate_record(record, record_index=record_index)
        if isinstance(result, QuarantinedFlowRecord):
            quarantines.append(self._build_quarantine_event(result))
            return alerts, quarantines, flushed

        buffered = BufferedRecord(
            record_index=record_index,
            source_record=result.source_record,
            passthrough=result.passthrough,
            aligned_features=result.aligned_features,
        )
        if not self._buffer:
            self._buffer_started_at = current_time
        self._buffer.append(buffered)
        if len(self._buffer) >= self.max_batch_size:
            size_alerts = self.flush_buffer()
            alerts.extend(size_alerts)
            flushed = True
        return alerts, quarantines, flushed

    def finalize(self) -> tuple[list[dict[str, Any]], bool]:
        if not self._buffer:
            return [], False
        return self.flush_buffer(), True

    def flush_if_due(self, *, now: float | None = None) -> tuple[list[dict[str, Any]], bool]:
        current_time = self.time_source() if now is None else now
        alerts, _, flushed = self._flush_if_due(current_time)
        return alerts, flushed

    def _flush_if_due(
        self, now: float
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        if not self._buffer or self._buffer_started_at is None:
            return [], [], False
        if now - self._buffer_started_at < self.flush_interval_seconds:
            return [], [], False
        return self.flush_buffer(), [], True

    def flush_buffer(self) -> list[dict[str, Any]]:
        if not self._buffer:
            return []
        frame = pd.DataFrame(
            [record.aligned_features for record in self._buffer],
            columns=self.contract.feature_columns,
        )
        predictions = self.inferencer.predict(frame, include_input=False)
        alert_events: list[dict[str, Any]] = []
        for buffered, prediction in zip(
            self._buffer,
            predictions.to_dict(orient="records"),
            strict=True,
        ):
            alert_events.append(
                {
                    "event_type": "model_prediction",
                    "record_index": buffered.record_index,
                    "passthrough": buffered.passthrough,
                    "attack_score": float(prediction["attack_score"]),
                    "predicted_label": str(prediction["predicted_label"]),
                    "is_alert": bool(prediction["is_alert"]),
                    "threshold": float(prediction["threshold"]),
                }
            )
        self._buffer = []
        self._buffer_started_at = None
        return alert_events

    @staticmethod
    def _build_quarantine_event(quarantine: QuarantinedFlowRecord) -> dict[str, Any]:
        event = quarantine.to_alert()
        event["event_type"] = "schema_anomaly"
        event["source_record"] = quarantine.source_record
        return event


def read_jsonl_stream(stream: TextIO):
    for index, line in enumerate(stream, start=1):
        line = line.rstrip("\n")
        if line.strip():
            yield index, line


def read_jsonl_stream_realtime(
    stream: TextIO,
    *,
    poll_interval_seconds: float,
):
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    line_queue: queue.Queue[tuple[int, str] | object] = queue.Queue()

    def _reader() -> None:
        try:
            for index, line in enumerate(stream, start=1):
                line_queue.put((index, line.rstrip("\n")))
        finally:
            line_queue.put(_STREAM_END)

    reader_thread = threading.Thread(
        target=_reader,
        name="ids-jsonl-stream-reader",
        daemon=True,
    )
    reader_thread.start()

    while True:
        try:
            item = line_queue.get(timeout=poll_interval_seconds)
        except queue.Empty:
            yield None, None
            continue
        if item is _STREAM_END:
            break
        index, line = item
        if line.strip():
            yield index, line


def append_jsonl_records(handle: TextIO, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    for record in records:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")
    handle.flush()


def resolve_output_paths(
    *,
    input_path: Path | None,
    alerts_output_path: Path | None,
    quarantine_output_path: Path | None,
) -> tuple[Path, Path]:
    if alerts_output_path is not None and quarantine_output_path is not None:
        return alerts_output_path.resolve(), quarantine_output_path.resolve()
    if input_path is not None:
        resolved_input = input_path.resolve()
        alerts_path = alerts_output_path or resolved_input.with_name(
            f"{resolved_input.stem}_alerts.jsonl"
        )
        quarantine_path = quarantine_output_path or resolved_input.with_name(
            f"{resolved_input.stem}_quarantine.jsonl"
        )
        return alerts_path.resolve(), quarantine_path.resolve()
    return (
        (alerts_output_path or DEFAULT_ALERTS_OUTPUT_PATH).resolve(),
        (quarantine_output_path or DEFAULT_QUARANTINE_OUTPUT_PATH).resolve(),
    )


def run_pipeline_stream(
    *,
    stream: TextIO,
    input_mode: str,
    alerts_output_path: Path,
    quarantine_output_path: Path,
    runner: RealtimePipelineRunner,
) -> PipelineSummary:
    summary = PipelineSummary(input_mode=input_mode)
    alerts_output_path.parent.mkdir(parents=True, exist_ok=True)
    quarantine_output_path.parent.mkdir(parents=True, exist_ok=True)

    def emit_alerts(
        handle: TextIO,
        events: list[dict[str, Any]],
        *,
        flushed: bool,
    ) -> None:
        append_jsonl_records(handle, events)
        summary.valid_records += len(events)
        summary.alert_records += sum(1 for event in events if event["is_alert"])
        if flushed and events:
            summary.batch_flushes += 1

    def emit_quarantines(handle: TextIO, events: list[dict[str, Any]]) -> None:
        append_jsonl_records(handle, events)
        summary.quarantined_records += len(events)
        summary.schema_anomaly_records += len(events)

    if input_mode == "stdin":
        stream_events = read_jsonl_stream_realtime(
            stream,
            poll_interval_seconds=max(
                0.05,
                min(runner.flush_interval_seconds / 4.0, 0.25),
            ),
        )
    else:
        stream_events = read_jsonl_stream(stream)

    with alerts_output_path.open("w", encoding="utf-8", newline="\n") as alerts_handle:
        with quarantine_output_path.open("w", encoding="utf-8", newline="\n") as quarantine_handle:
            for line_number, line in stream_events:
                if line_number is None:
                    due_alerts, flushed = runner.flush_if_due()
                    emit_alerts(alerts_handle, due_alerts, flushed=flushed)
                    continue

                summary.total_records += 1
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    emit_quarantines(
                        quarantine_handle,
                        [
                            {
                                "event_type": "schema_anomaly",
                                "anomaly_type": "invalid_json",
                                "reason": "invalid_json",
                                "record_index": line_number - 1,
                                "line_number": line_number,
                                "raw_line": line,
                                "error": str(exc),
                                "missing_features": [],
                                "non_numeric_features": [],
                                "alias_collisions": [],
                                "passthrough": {},
                            }
                        ],
                    )
                    continue
                if not isinstance(payload, dict):
                    emit_quarantines(
                        quarantine_handle,
                        [
                            {
                                "event_type": "schema_anomaly",
                                "anomaly_type": "invalid_record_type",
                                "reason": "invalid_record_type",
                                "record_index": line_number - 1,
                                "line_number": line_number,
                                "raw_record": payload,
                                "missing_features": [],
                                "non_numeric_features": [],
                                "alias_collisions": [],
                                "passthrough": {},
                            }
                        ],
                    )
                    continue

                batch_alerts, batch_quarantines, flushed = runner.ingest_record(
                    payload,
                    record_index=line_number - 1,
                )
                emit_alerts(alerts_handle, batch_alerts, flushed=flushed)
                emit_quarantines(quarantine_handle, batch_quarantines)

            final_alerts, flushed = runner.finalize()
            emit_alerts(alerts_handle, final_alerts, flushed=flushed)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the IDS realtime micro-batch pipeline on structured JSONL flow records."
    )
    parser.add_argument("--input-path", type=Path, default=None)
    parser.add_argument("--alerts-output-path", type=Path, default=None)
    parser.add_argument("--quarantine-output-path", type=Path, default=None)
    parser.add_argument("--bundle-root", type=Path, default=None)
    parser.add_argument("--config-path", type=Path, default=None)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument(
        "--feature-columns-path",
        type=Path,
        default=DEFAULT_FEATURE_COLUMNS_PATH,
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--max-batch-size", type=int, default=DEFAULT_MAX_BATCH_SIZE)
    parser.add_argument(
        "--flush-interval-seconds",
        type=float,
        default=DEFAULT_FLUSH_INTERVAL_SECONDS,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_mode = "file" if args.input_path is not None else "stdin"
    alerts_output_path, quarantine_output_path = resolve_output_paths(
        input_path=args.input_path,
        alerts_output_path=args.alerts_output_path,
        quarantine_output_path=args.quarantine_output_path,
    )
    contract = FlowFeatureContract.from_feature_file(args.feature_columns_path)
    inferencer = build_inferencer(
        bundle_root=args.bundle_root,
        config_path=args.config_path,
        model_path=args.model_path,
        feature_columns_path=args.feature_columns_path,
        threshold=args.threshold,
    )
    runner = RealtimePipelineRunner(
        contract=contract,
        inferencer=inferencer,
        max_batch_size=args.max_batch_size,
        flush_interval_seconds=args.flush_interval_seconds,
    )

    if args.input_path is not None:
        with args.input_path.open("r", encoding="utf-8") as handle:
            summary = run_pipeline_stream(
                stream=handle,
                input_mode=input_mode,
                alerts_output_path=alerts_output_path,
                quarantine_output_path=quarantine_output_path,
                runner=runner,
            )
    else:
        summary = run_pipeline_stream(
            stream=sys.stdin,
            input_mode=input_mode,
            alerts_output_path=alerts_output_path,
            quarantine_output_path=quarantine_output_path,
            runner=runner,
        )

    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
