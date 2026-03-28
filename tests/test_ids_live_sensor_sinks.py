from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_live_sensor_sinks import (  # noqa: E402
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
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
        timestamp_source=lambda: "2026-03-28T03:00:00+00:00",
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
    assert summary["reason"] == "snapshot"
    assert summary["journald_message"] == render_journald_summary(summary)
    assert summaries == [snapshot]
    assert "queue_depth=4" in snapshot["journald_message"]
    assert "oldest_pending_window_age_seconds=1.250" in snapshot["journald_message"]
    assert "extractor_runtime_seconds=0.420" in snapshot["journald_message"]
    assert summary["latest_queue_depth"] == 4


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


def test_sink_close_rolls_back_on_promotion_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alerts_path = tmp_path / "alerts.jsonl"
    quarantine_path = tmp_path / "quarantine.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    original_alerts = json.dumps({"existing": "alerts"}) + "\n"
    original_quarantine = json.dumps({"existing": "quarantine"}) + "\n"
    original_summary = json.dumps({"existing": "summary"}) + "\n"
    alerts_path.write_text(original_alerts, encoding="utf-8")
    quarantine_path.write_text(original_quarantine, encoding="utf-8")
    summary_path.write_text(original_summary, encoding="utf-8")

    sink = LiveSensorLocalSink(
        alerts_output_path=alerts_path,
        quarantine_output_path=quarantine_path,
        summary_output_path=summary_path,
    )
    sink.record_alert({"event_type": "model_prediction", "record_index": 0, "is_alert": False})
    sink.record_quarantine({"event_type": "schema_anomaly", "reason": "bad_record"})
    sink.capture_summary(reason="periodic")

    original_replace = Path.replace
    replace_calls = 0

    def fail_second_promotion(self: Path, target: Path) -> Path:
        nonlocal replace_calls
        if target in (alerts_path, quarantine_path, summary_path):
            replace_calls += 1
            if replace_calls == 2:
                raise OSError("promotion exploded")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_second_promotion)

    with pytest.raises(OSError, match="promotion exploded"):
        sink.close()

    assert alerts_path.read_text(encoding="utf-8") == original_alerts
    assert quarantine_path.read_text(encoding="utf-8") == original_quarantine
    assert summary_path.read_text(encoding="utf-8") == original_summary
    assert list(tmp_path.glob(".*.tmp")) == []
    assert list(tmp_path.glob(".*.bak")) == []


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
