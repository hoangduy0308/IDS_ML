from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import sys

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_feature_contract import FlowFeatureContract  # noqa: E402
from scripts.ids_inference import DEFAULT_FEATURE_COLUMNS_PATH  # noqa: E402
from scripts.ids_live_capture import ClosedCaptureWindow  # noqa: E402
from scripts.ids_live_flow_bridge import (  # noqa: E402
    BridgeWindowResult,
    ExtractorRunResult,
    LiveFlowBridge,
    LiveFlowBridgeConfig,
)
from scripts.ids_live_sensor import LiveSensorDaemon, LiveSensorDaemonConfig  # noqa: E402
from scripts.ids_live_sensor_sinks import LiveSensorLocalSink  # noqa: E402
from scripts.ids_realtime_pipeline import RealtimePipelineRunner  # noqa: E402


def load_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_primary_sample_row() -> dict[str, object]:
    sample_path = REPO_ROOT / "artifacts" / "demo" / "ids_record_adapter_primary_sample.jsonl"
    first_line = sample_path.read_text(encoding="utf-8").splitlines()[0]
    return json.loads(first_line)


def write_csv_output(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class DeterministicInferencer:
    def predict(self, frame: pd.DataFrame, *, include_input: bool = False) -> pd.DataFrame:
        records: list[dict[str, object]] = []
        for _, row in frame.iterrows():
            flow_duration = float(row["Flow Duration"])
            is_alert = flow_duration >= 50.0
            records.append(
                {
                    "attack_score": flow_duration / 100.0,
                    "predicted_label": "attack" if is_alert else "benign",
                    "is_alert": is_alert,
                    "threshold": 0.5,
                }
            )
        return pd.DataFrame.from_records(records)


class RecordingBridge(LiveFlowBridge):
    def __init__(self, fixtures_by_sequence: dict[int, list[dict[str, object]]]) -> None:
        self.window_sequences: list[int] = []
        self.result_handoff_paths: list[Path] = []

        def fake_runner(
            command: list[str] | tuple[str, ...],
            window: ClosedCaptureWindow,
            output_path: Path,
        ) -> ExtractorRunResult:
            sequence_number = window.sequence_number or 0
            self.window_sequences.append(sequence_number)
            rows = fixtures_by_sequence[sequence_number]
            window.path.parent.mkdir(parents=True, exist_ok=True)
            window.path.write_text("closed capture window\n", encoding="utf-8")
            write_csv_output(output_path, rows)
            return ExtractorRunResult(returncode=0, stdout="ok", stderr="")

        super().__init__(
            LiveFlowBridgeConfig(extractor_command_prefix=("Cmd",)),
            extractor_runner=fake_runner,
        )

    def bridge_window(
        self,
        window: ClosedCaptureWindow,
        *,
        output_dir: Path | None = None,
    ) -> BridgeWindowResult:
        result = super().bridge_window(window, output_dir=output_dir)
        handoff_path = (output_dir or window.path.parent) / f"{window.path.stem}.jsonl"
        self.write_result_jsonl(result, handoff_path)
        self.result_handoff_paths.append(handoff_path)
        return result


def make_config(tmp_path: Path, **overrides: object) -> LiveSensorDaemonConfig:
    kwargs: dict[str, object] = {
        "spool_dir": tmp_path / "spool",
        "alerts_output_path": tmp_path / "alerts.jsonl",
        "quarantine_output_path": tmp_path / "quarantine.jsonl",
        "summary_output_path": tmp_path / "summary.jsonl",
        "max_batch_size": 2,
        "flush_interval_seconds": 60.0,
    }
    kwargs.update(overrides)
    return LiveSensorDaemonConfig(**kwargs)


def test_ids_live_sensor_e2e_uses_real_bridge_and_runtime_handoff(tmp_path: Path) -> None:
    base_row = load_primary_sample_row()
    alert_row = dict(base_row)
    alert_row["FlowDuration"] = 80.0
    benign_row = dict(base_row)
    benign_row["FlowDuration"] = 10.0
    second_alert_row = dict(base_row)
    second_alert_row["FlowDuration"] = 90.0
    quarantine_row = dict(base_row)
    quarantine_row["FlowDuration"] = "bad"

    bridge = RecordingBridge(
        {
            0: [alert_row],
            1: [benign_row],
            2: [second_alert_row],
            3: [quarantine_row],
        }
    )
    runtime = RealtimePipelineRunner(
        contract=FlowFeatureContract.from_feature_file(DEFAULT_FEATURE_COLUMNS_PATH),
        inferencer=DeterministicInferencer(),
        max_batch_size=2,
        flush_interval_seconds=60.0,
    )
    summary_stream = io.StringIO()
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
        timestamp_source=lambda: "2026-03-28T03:00:00+00:00",
        summary_output_stream=summary_stream,
    )
    daemon = LiveSensorDaemon(
        make_config(tmp_path, max_pending_windows=4),
        bridge=bridge,
        runtime_runner=runtime,
        sink=sink,
    )

    windows = [
        daemon.enqueue_notification_line(
            f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(index)}",
            observed_at=10.0 + index,
        )
        for index in range(4)
    ]

    processed = daemon.process_pending_windows()
    summary = daemon.close()

    assert all(window is not None for window in windows)
    assert bridge.window_sequences == [0, 1, 2, 3]
    assert len(processed) == 4
    assert summary["processed_windows"] == 4
    assert summary["alert_records"] == 2
    assert summary["quarantine_records"] == 1
    assert summary["benign_predictions"] == 1
    assert summary["reason"] == "close"

    alerts = load_jsonl(tmp_path / "alerts.jsonl")
    quarantines = load_jsonl(tmp_path / "quarantine.jsonl")
    summaries = load_jsonl(tmp_path / "summary.jsonl")
    handoffs = [load_jsonl(path) for path in bridge.result_handoff_paths]
    emitted_lines = [line for line in summary_stream.getvalue().splitlines() if line.strip()]

    assert len(alerts) == 2
    assert sum(1 for event in alerts if event["is_alert"] is True) == 2
    assert len(quarantines) == 1
    assert quarantines[0]["reason"] == "non_numeric_required_features"
    assert any(event["reason"] == "runtime-flush" for event in summaries)
    assert any(event["reason"] == "runtime-finalize" for event in summaries)
    assert summaries[-1]["reason"] == "close"
    assert emitted_lines[-1] == summary["journald_message"]
    assert handoffs[0][0]["event_type"] == "bridge_record"
    assert handoffs[-1][0]["event_type"] == "adapter_quarantine"

    for window in windows:
        assert window is not None
        assert not window.path.exists()
        assert not (tmp_path / "spool" / "flows" / f"{window.path.stem}_Flow.csv").exists()


def test_demo_fixture_has_bridge_alert_benign_and_quarantine_variants() -> None:
    fixture_path = REPO_ROOT / "artifacts" / "demo" / "ids_live_sensor_e2e_sample.jsonl"
    fixture_events = load_jsonl(fixture_path)

    assert [event["event_type"] for event in fixture_events] == [
        "bridge_record",
        "bridge_record",
        "adapter_quarantine",
    ]
    assert fixture_events[0]["record"]["Flow Duration"] == 80.0
    assert fixture_events[1]["record"]["Flow Duration"] == 10.0
    assert fixture_events[2]["reason"] == "non_numeric_required_features"
