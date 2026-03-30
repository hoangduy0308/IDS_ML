from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ids.runtime.live_sensor_sinks import (  # noqa: E402
    LiveSensorLocalSink,
    DEFAULT_ALERTS_OUTPUT_PATH,
    DEFAULT_QUARANTINE_OUTPUT_PATH,
    DEFAULT_SUMMARY_OUTPUT_PATH,
    render_journald_summary,
    resolve_output_paths,
)


def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_sink_persists_alerts_quarantines_and_summary(tmp_path: Path) -> None:
    summary_stream = io.StringIO()
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
        timestamp_source=lambda: "2026-03-28T03:00:00+00:00",
        summary_output_stream=summary_stream,
    )

    sink.record_alert({"event_type": "model_prediction", "record_index": 0, "is_alert": True})
    sink.record_quarantine(
        {"event_type": "schema_anomaly", "reason": "invalid_json", "record_index": 1}
    )
    sink.record_benign_prediction(3)
    sink.record_skipped_non_tcp_udp()
    sink.record_extractor_failure("dumpcap exited unexpectedly")
    sink.record_window_telemetry(
        queue_depth=4,
        oldest_pending_window_age_seconds=1.25,
        extractor_runtime_seconds=0.42,
        capture_window_seconds=2.0,
        pending_window_count=2,
    )
    sink.set_active_bundle_state(
        activation_path="/var/lib/ids-live-sensor/active_bundle.json",
        active_bundle_root="/opt/ids_ml_new/artifacts/final_model/catboost_full_data_v1",
        active_bundle_name="catboost_full_data_v1",
        compatibility_status="compatible",
        verification_status="verified",
        manifest_version=2,
        activated_at="2026-03-28T02:59:00+00:00",
        previous_bundle_name="catboost_full_data_v0",
    )

    assert load_jsonl(tmp_path / "alerts.jsonl") == [
        {"event_type": "model_prediction", "record_index": 0, "is_alert": True}
    ]
    assert load_jsonl(tmp_path / "quarantine.jsonl") == [
        {"event_type": "schema_anomaly", "reason": "invalid_json", "record_index": 1}
    ]

    snapshot = sink.capture_summary(reason="periodic")
    summary = sink.close()

    alerts = load_jsonl(tmp_path / "alerts.jsonl")
    quarantines = load_jsonl(tmp_path / "quarantine.jsonl")
    summaries = load_jsonl(tmp_path / "summary.jsonl")

    assert alerts == [
        {"event_type": "model_prediction", "record_index": 0, "is_alert": True}
    ]
    assert quarantines == [
        {"event_type": "schema_anomaly", "reason": "invalid_json", "record_index": 1}
    ]
    assert summary["alert_records"] == 1
    assert summary["quarantine_records"] == 1
    assert summary["benign_predictions"] == 3
    assert summary["skipped_non_tcp_udp_records"] == 1
    assert summary["extractor_failures"] == 1
    assert summary["latest_queue_depth"] == 4
    assert summary["oldest_pending_window_age_seconds"] == 1.25
    assert summary["latest_extractor_runtime_seconds"] == 0.42
    assert summary["total_extractor_runtime_seconds"] == 0.42
    assert summary["processed_windows"] == 1
    assert summary["active_bundle"]["active_bundle_name"] == "catboost_full_data_v1"
    assert summary["active_bundle"]["previous_bundle_name"] == "catboost_full_data_v0"
    assert summary["reason"] == "close"
    assert summary["journald_message"] == render_journald_summary(summary)
    assert summaries[0] == snapshot
    assert summaries[-1]["reason"] == "close"
    assert "queue_depth=4" in snapshot["journald_message"]
    assert "oldest_pending_window_age_seconds=1.250" in snapshot["journald_message"]
    assert "extractor_runtime_seconds=0.420" in snapshot["journald_message"]
    assert "active_bundle=catboost_full_data_v1" in snapshot["journald_message"]
    assert summary["latest_queue_depth"] == 4
    emitted_lines = [line for line in summary_stream.getvalue().splitlines() if line.strip()]
    assert emitted_lines == [snapshot["journald_message"], summary["journald_message"]]


def test_sink_rejects_directory_outputs_and_path_collisions(tmp_path: Path) -> None:
    alerts_dir = tmp_path / "alerts-dir"
    alerts_dir.mkdir()

    with pytest.raises(IsADirectoryError):
        LiveSensorLocalSink(
            alerts_output_path=alerts_dir,
            quarantine_output_path=tmp_path / "quarantine.jsonl",
            summary_output_path=tmp_path / "summary.jsonl",
        )

    with pytest.raises(ValueError, match="must be distinct"):
        resolve_output_paths(
            alerts_output_path=tmp_path / "shared.jsonl",
            quarantine_output_path=tmp_path / "shared.jsonl",
            summary_output_path=tmp_path / "summary.jsonl",
        )


def test_sink_preserves_history_across_restart_and_close(tmp_path: Path) -> None:
    alerts_path = tmp_path / "alerts.jsonl"
    quarantine_path = tmp_path / "quarantine.jsonl"
    summary_path = tmp_path / "summary.jsonl"

    first = LiveSensorLocalSink(
        alerts_output_path=alerts_path,
        quarantine_output_path=quarantine_path,
        summary_output_path=summary_path,
        timestamp_source=lambda: "2026-03-28T03:00:00+00:00",
    )
    first.record_alert({"event_type": "model_prediction", "record_index": 0, "is_alert": True})
    first.record_quarantine({"event_type": "schema_anomaly", "reason": "bad_record"})
    first.capture_summary(reason="periodic")
    first.close()

    second = LiveSensorLocalSink(
        alerts_output_path=alerts_path,
        quarantine_output_path=quarantine_path,
        summary_output_path=summary_path,
        timestamp_source=lambda: "2026-03-28T03:05:00+00:00",
    )
    second.record_alert({"event_type": "model_prediction", "record_index": 1, "is_alert": False})
    second.capture_summary(reason="periodic")
    second.close()

    alerts = load_jsonl(alerts_path)
    quarantines = load_jsonl(quarantine_path)
    summaries = load_jsonl(summary_path)

    assert [event["record_index"] for event in alerts] == [0, 1]
    assert len(quarantines) == 1
    assert [event["reason"] for event in summaries] == ["periodic", "close", "periodic", "close"]


def test_sink_snapshot_is_available_without_flushing(tmp_path: Path) -> None:
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
        timestamp_source=lambda: "2026-03-28T03:05:00+00:00",
    )
    sink.record_window_telemetry(
        queue_depth=2,
        oldest_pending_window_age_seconds=5.5,
        extractor_runtime_seconds=0.75,
    )

    snapshot = sink.snapshot_summary()

    assert snapshot["latest_queue_depth"] == 2
    assert snapshot["oldest_pending_window_age_seconds"] == 5.5
    assert snapshot["latest_extractor_runtime_seconds"] == 0.75
    assert snapshot["journald_message"].startswith("ids-live-sensor reason=snapshot")
    assert DEFAULT_ALERTS_OUTPUT_PATH.name == "ids_live_alerts.jsonl"
    assert DEFAULT_QUARANTINE_OUTPUT_PATH.name == "ids_live_quarantine.jsonl"
    assert DEFAULT_SUMMARY_OUTPUT_PATH.name == "ids_live_sensor_summary.jsonl"


def test_sink_can_disable_summary_line_emission(tmp_path: Path) -> None:
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
        summary_output_stream=None,
        timestamp_source=lambda: "2026-03-28T03:10:00+00:00",
    )

    sink.record_window_telemetry(
        queue_depth=1,
        oldest_pending_window_age_seconds=0.5,
        extractor_runtime_seconds=0.1,
    )
    summary = sink.close()

    assert summary["journald_message"] == render_journald_summary(summary)
    assert len(load_jsonl(tmp_path / "summary.jsonl")) == 1
