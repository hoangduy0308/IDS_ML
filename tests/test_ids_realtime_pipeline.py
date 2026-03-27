from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_feature_contract import FlowFeatureContract  # noqa: E402
from scripts.ids_realtime_pipeline import (  # noqa: E402
    RealtimePipelineRunner,
    resolve_output_paths,
    run_pipeline_stream,
)


class DummyInferencer:
    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def predict(self, frame: pd.DataFrame, include_input: bool = True) -> pd.DataFrame:
        scores = frame["Flow Duration"].astype(float) / 100.0
        alerts = scores >= self.threshold
        labels = ["Attack" if is_alert else "Benign" for is_alert in alerts]
        return pd.DataFrame(
            {
                "attack_score": scores,
                "predicted_label": labels,
                "is_alert": alerts,
                "threshold": self.threshold,
            }
        )


def make_contract() -> FlowFeatureContract:
    return FlowFeatureContract(
        feature_columns=["Src Port", "Dst Port", "Protocol", "Flow Duration"],
        alias_map={
            "SrcPort": "Src Port",
            "DstPort": "Dst Port",
            "FlowDuration": "Flow Duration",
        },
    )


def load_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_run_pipeline_stream_file_mode_mixes_valid_invalid_and_final_drain(tmp_path: Path) -> None:
    input_path = tmp_path / "flows.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps({"SrcPort": 10, "DstPort": 20, "Protocol": 6, "FlowDuration": 20, "trace_id": "a"}),
                json.dumps({"SrcPort": 11, "DstPort": 21, "Protocol": "bad", "FlowDuration": 70, "trace_id": "b"}),
                json.dumps({"SrcPort": 12, "DstPort": 22, "Protocol": 6, "FlowDuration": 80, "trace_id": "c"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    alerts_path, quarantine_path = resolve_output_paths(
        input_path=input_path,
        alerts_output_path=None,
        quarantine_output_path=None,
    )
    runner = RealtimePipelineRunner(
        contract=make_contract(),
        inferencer=DummyInferencer(),
        max_batch_size=2,
        flush_interval_seconds=60.0,
    )

    with input_path.open("r", encoding="utf-8") as handle:
        summary = run_pipeline_stream(
            stream=handle,
            input_mode="file",
            alerts_output_path=alerts_path,
            quarantine_output_path=quarantine_path,
            runner=runner,
        )

    alerts = load_jsonl(alerts_path)
    quarantines = load_jsonl(quarantine_path)

    assert summary.input_mode == "file"
    assert summary.total_records == 3
    assert summary.valid_records == 2
    assert summary.quarantined_records == 1
    assert summary.schema_anomaly_records == 1
    assert summary.alert_records == 1
    assert summary.batch_flushes == 1
    assert [event["record_index"] for event in alerts] == [0, 2]
    assert alerts[0]["passthrough"] == {"trace_id": "a"}
    assert alerts[1]["is_alert"] is True
    assert quarantines[0]["reason"] == "non_numeric_required_features"
    assert quarantines[0]["passthrough"] == {"trace_id": "b"}


def test_runner_flushes_on_time_trigger_without_losing_valid_records() -> None:
    runner = RealtimePipelineRunner(
        contract=make_contract(),
        inferencer=DummyInferencer(),
        max_batch_size=10,
        flush_interval_seconds=1.0,
    )

    alerts, quarantines, flushed = runner.ingest_record(
        {"SrcPort": 10, "DstPort": 20, "Protocol": 6, "FlowDuration": 20, "trace_id": "a"},
        record_index=0,
        now=0.0,
    )
    assert alerts == []
    assert quarantines == []
    assert flushed is False

    alerts, quarantines, flushed = runner.ingest_record(
        {"SrcPort": 11, "DstPort": 21, "Protocol": 6, "FlowDuration": 90, "trace_id": "b"},
        record_index=1,
        now=1.5,
    )

    assert flushed is True
    assert quarantines == []
    assert len(alerts) == 1
    assert alerts[0]["record_index"] == 0

    final_alerts, final_flushed = runner.finalize()
    assert final_flushed is True
    assert len(final_alerts) == 1
    assert final_alerts[0]["record_index"] == 1
    assert final_alerts[0]["is_alert"] is True


def test_run_pipeline_stream_supports_stdin_mode_and_invalid_json(tmp_path: Path) -> None:
    alerts_path = tmp_path / "alerts.jsonl"
    quarantine_path = tmp_path / "quarantine.jsonl"
    runner = RealtimePipelineRunner(
        contract=make_contract(),
        inferencer=DummyInferencer(),
        max_batch_size=5,
        flush_interval_seconds=60.0,
    )
    stream = io.StringIO(
        "\n".join(
            [
                json.dumps({"SrcPort": 10, "DstPort": 20, "Protocol": 6, "FlowDuration": 55, "sensor": "x"}),
                '{"not": "json"',
            ]
        )
        + "\n"
    )

    summary = run_pipeline_stream(
        stream=stream,
        input_mode="stdin",
        alerts_output_path=alerts_path,
        quarantine_output_path=quarantine_path,
        runner=runner,
    )

    alerts = load_jsonl(alerts_path)
    quarantines = load_jsonl(quarantine_path)

    assert summary.input_mode == "stdin"
    assert summary.total_records == 2
    assert summary.valid_records == 1
    assert summary.quarantined_records == 1
    assert alerts[0]["passthrough"] == {"sensor": "x"}
    assert quarantines[0]["reason"] == "invalid_json"
    assert quarantines[0]["anomaly_type"] == "invalid_json"
