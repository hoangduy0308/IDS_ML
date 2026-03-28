from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_live_capture import ClosedCaptureWindow  # noqa: E402
from scripts.ids_live_flow_bridge import (  # noqa: E402
    BridgeWindowResult,
    LiveFlowBridge,
    LiveFlowBridgeConfig,
)
from scripts.ids_live_sensor import LiveSensorDaemon, LiveSensorDaemonConfig  # noqa: E402
from scripts.ids_live_sensor_sinks import LiveSensorLocalSink  # noqa: E402


def load_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class ScriptedRuntimeRunner:
    def __init__(self) -> None:
        self.ingested: list[tuple[int | None, float]] = []
        self.finalize_calls = 0

    def ingest_record(
        self,
        record: dict[str, object],
        *,
        record_index: int | None,
        now: float | None = None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], bool]:
        flow_duration = float(record["Flow Duration"])
        self.ingested.append((record_index, flow_duration))
        is_alert = flow_duration >= 50.0
        return (
            [
                {
                    "event_type": "model_prediction",
                    "record_index": record_index,
                    "is_alert": is_alert,
                    "threshold": 50.0,
                }
            ],
            [],
            False,
        )

    def finalize(self) -> tuple[list[dict[str, object]], list[dict[str, object]], bool]:
        self.finalize_calls += 1
        return [], [], False


class FixtureBridge:
    def __init__(self, fixture_events: list[dict[str, object]], handoff_dir: Path) -> None:
        self.fixture_events = fixture_events
        self.handoff_dir = handoff_dir
        self.window_sequences: list[int | None] = []
        self.handoff_writer = LiveFlowBridge(LiveFlowBridgeConfig())

    def bridge_window(
        self,
        window: ClosedCaptureWindow,
        *,
        output_dir: Path | None = None,
    ) -> BridgeWindowResult:
        sequence_number = window.sequence_number or 0
        self.window_sequences.append(sequence_number)
        fixture = self.fixture_events[sequence_number]
        extractor_output_path = Path(output_dir or window.path.parent) / (
            f"{window.path.stem}_Flow.csv"
        )
        extractor_output_path.parent.mkdir(parents=True, exist_ok=True)
        window.path.parent.mkdir(parents=True, exist_ok=True)
        window.path.write_text("closed capture window\n", encoding="utf-8")
        extractor_output_path.write_text("flow export\n", encoding="utf-8")

        if fixture["event_type"] == "bridge_record":
            result = BridgeWindowResult(
                window=window,
                extractor_output_path=extractor_output_path,
                command=("Cmd",),
                adapted_records=(
                    {
                        "event_type": "bridge_record",
                        "window_path": str(window.path),
                        "extractor_output_path": str(extractor_output_path),
                        "record_index": fixture["record_index"],
                        "profile": fixture["profile"],
                        "record": dict(fixture["record"]),
                    },
                ),
                adapter_quarantines=(),
                window_errors=(),
            )
        else:
            result = BridgeWindowResult(
                window=window,
                extractor_output_path=extractor_output_path,
                command=("Cmd",),
                adapted_records=(),
                adapter_quarantines=(
                    {
                        "event_type": "adapter_quarantine",
                        "profile": fixture["profile"],
                        "reason": fixture["reason"],
                        "record_index": fixture["record_index"],
                        "window_path": str(window.path),
                        "extractor_output_path": str(extractor_output_path),
                    },
                ),
                window_errors=(),
            )

        self.handoff_dir.mkdir(parents=True, exist_ok=True)
        self.handoff_writer.write_result_jsonl(
            result,
            self.handoff_dir / f"{window.path.stem}.jsonl",
        )
        return result


def make_config(tmp_path: Path, **overrides: object) -> LiveSensorDaemonConfig:
    kwargs: dict[str, object] = {
        "spool_dir": tmp_path / "spool",
        "alerts_output_path": tmp_path / "alerts.jsonl",
        "quarantine_output_path": tmp_path / "quarantine.jsonl",
        "summary_output_path": tmp_path / "summary.jsonl",
    }
    kwargs.update(overrides)
    return LiveSensorDaemonConfig(**kwargs)


def test_ids_live_sensor_e2e_drives_alert_benign_quarantine_and_handoff(tmp_path: Path) -> None:
    fixture_path = REPO_ROOT / "artifacts" / "demo" / "ids_live_sensor_e2e_sample.jsonl"
    fixture_events = load_jsonl(fixture_path)

    bridge = FixtureBridge(fixture_events, handoff_dir=tmp_path / "handoff")
    runtime = ScriptedRuntimeRunner()
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
        timestamp_source=lambda: "2026-03-28T03:00:00+00:00",
    )
    daemon = LiveSensorDaemon(
        make_config(tmp_path, max_pending_windows=3),
        bridge=bridge,
        runtime_runner=runtime,
        sink=sink,
    )

    window0 = daemon.enqueue_notification_line(
        f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(0)}",
        observed_at=10.0,
    )
    window1 = daemon.enqueue_notification_line(
        f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(1)}",
        observed_at=11.0,
    )
    window2 = daemon.enqueue_notification_line(
        f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(2)}",
        observed_at=12.0,
    )

    processed = daemon.process_pending_windows()
    summary = daemon.close()

    assert window0 is not None
    assert window1 is not None
    assert window2 is not None
    assert bridge.window_sequences == [0, 1, 2]
    assert [entry[0] for entry in runtime.ingested] == [0, 1]
    assert len(processed) == 3
    assert summary["processed_windows"] == 3
    assert summary["alert_records"] == 1
    assert summary["quarantine_records"] == 1
    assert summary["benign_predictions"] == 1
    assert summary["reason"] == "snapshot"
    assert summary["latest_queue_depth"] == 0

    alerts = load_jsonl(tmp_path / "alerts.jsonl")
    quarantines = load_jsonl(tmp_path / "quarantine.jsonl")
    summaries = load_jsonl(tmp_path / "summary.jsonl")

    assert len(alerts) == 1
    assert len(quarantines) == 1
    assert any(event["reason"] == "window-enqueued" for event in summaries)
    assert any(event["reason"] == "window-processed" for event in summaries)
    assert (tmp_path / "handoff" / f"{window0.path.stem}.jsonl").exists()
    assert (tmp_path / "handoff" / f"{window1.path.stem}.jsonl").exists()
    assert (tmp_path / "handoff" / f"{window2.path.stem}.jsonl").exists()
    assert not window0.path.exists()
    assert not window1.path.exists()
    assert not window2.path.exists()
    assert not (tmp_path / "spool" / "flows" / f"{window0.path.stem}_Flow.csv").exists()
    assert not (tmp_path / "spool" / "flows" / f"{window1.path.stem}_Flow.csv").exists()
    assert not (tmp_path / "spool" / "flows" / f"{window2.path.stem}_Flow.csv").exists()


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
