from __future__ import annotations

import io
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.core.feature_contract import FlowFeatureContract  # noqa: E402
from ids.runtime.realtime_pipeline import (  # noqa: E402
    RealtimePipelineRunner,
    main,
    resolve_output_paths,
    run_pipeline_stream,
)


class DummyInferencer:
    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self.config = type(
            "Config",
            (),
            {"feature_columns_path": Path("dummy_features.json")},
        )()

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


class ConfiglessInferencer(DummyInferencer):
    def __init__(self, threshold: float = 0.5) -> None:
        super().__init__(threshold=threshold)
        self.config = type("Config", (), {})()


class BlockingLineStream:
    def __init__(self) -> None:
        self._queue: queue.Queue[str | None] = queue.Queue()

    def push_line(self, line: str) -> None:
        payload = line if line.endswith("\n") else f"{line}\n"
        self._queue.put(payload)

    def close(self) -> None:
        self._queue.put(None)

    def __iter__(self) -> "BlockingLineStream":
        return self

    def __next__(self) -> str:
        item = self._queue.get(timeout=5.0)
        if item is None:
            raise StopIteration
        return item


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


def demo_fixture_path() -> Path:
    return REPO_ROOT / "artifacts" / "demo" / "ids_realtime_pipeline_sample.jsonl"


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


def test_run_pipeline_stream_flushes_stdin_records_before_eof(tmp_path: Path) -> None:
    alerts_path = tmp_path / "alerts.jsonl"
    quarantine_path = tmp_path / "quarantine.jsonl"
    runner = RealtimePipelineRunner(
        contract=make_contract(),
        inferencer=DummyInferencer(),
        max_batch_size=10,
        flush_interval_seconds=0.2,
    )
    stream = BlockingLineStream()
    result: dict[str, object] = {}
    errors: list[BaseException] = []

    def target() -> None:
        try:
            result["summary"] = run_pipeline_stream(
                stream=stream,
                input_mode="stdin",
                alerts_output_path=alerts_path,
                quarantine_output_path=quarantine_path,
                runner=runner,
            )
        except BaseException as exc:  # pragma: no cover - surfaced in assertions
            errors.append(exc)

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    stream.push_line(
        json.dumps(
            {
                "SrcPort": 10,
                "DstPort": 20,
                "Protocol": 6,
                "FlowDuration": 90,
                "trace_id": "stream-1",
            }
        )
    )

    deadline = time.monotonic() + 2.0
    flushed_alerts: list[dict[str, object]] | None = None
    while time.monotonic() < deadline:
        if alerts_path.exists():
            payload = alerts_path.read_text(encoding="utf-8").strip()
            if payload:
                flushed_alerts = [json.loads(line) for line in payload.splitlines() if line.strip()]
                break
        time.sleep(0.05)

    stream.close()
    worker.join(timeout=2.0)

    assert not errors, str(errors[0]) if errors else ""
    assert worker.is_alive() is False
    assert flushed_alerts is not None, "expected alert output before EOF"
    assert flushed_alerts[0]["passthrough"] == {"trace_id": "stream-1"}
    summary = result["summary"]
    assert summary.valid_records == 1
    assert summary.alert_records == 1
    assert summary.batch_flushes == 1
    assert quarantine_path.read_text(encoding="utf-8") == ""


def test_demo_fixture_drives_end_to_end_alert_and_quarantine_outputs(tmp_path: Path) -> None:
    alerts_path = tmp_path / "demo_alerts.jsonl"
    quarantine_path = tmp_path / "demo_quarantine.jsonl"
    runner = RealtimePipelineRunner(
        contract=make_contract(),
        inferencer=DummyInferencer(),
        max_batch_size=2,
        flush_interval_seconds=60.0,
    )

    with demo_fixture_path().open("r", encoding="utf-8") as handle:
        summary = run_pipeline_stream(
            stream=handle,
            input_mode="file",
            alerts_output_path=alerts_path,
            quarantine_output_path=quarantine_path,
            runner=runner,
        )

    alerts = load_jsonl(alerts_path)
    quarantines = load_jsonl(quarantine_path)

    assert summary.total_records == 4
    assert summary.valid_records == 2
    assert summary.quarantined_records == 2
    assert [event["passthrough"] for event in alerts] == [
        {"trace_id": "demo-ok-1", "sensor": "edge-a"},
        {"trace_id": "demo-ok-2", "sensor": "edge-b"},
    ]
    assert quarantines[0]["reason"] == "non_numeric_required_features"
    assert quarantines[1]["reason"] == "invalid_json"


def test_script_entrypoint_help_runs_from_repo_root() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/ids_realtime_pipeline.py", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Run the IDS realtime micro-batch pipeline" in completed.stdout


def test_main_supports_file_input_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    alerts_path = tmp_path / "alerts.jsonl"
    quarantine_path = tmp_path / "quarantine.jsonl"
    config_feature_columns_path = tmp_path / "config_feature_columns.json"
    config_feature_columns_path.write_text("[]\n", encoding="utf-8")
    captured_paths: dict[str, Path] = {}

    def _from_feature_file(cls, path: Path, alias_map: dict[str, str] | None = None):
        _ = cls, alias_map
        captured_paths["feature_columns_path"] = Path(path)
        return make_contract()

    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.build_model_config",
        lambda **_: type("Config", (), {"feature_columns_path": config_feature_columns_path})(),
    )
    monkeypatch.setattr("ids.runtime.realtime_pipeline.IDSInferencer", lambda config: DummyInferencer())
    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.FlowFeatureContract.from_feature_file",
        classmethod(_from_feature_file),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ids_realtime_pipeline.py",
            "--input-path",
            str(demo_fixture_path()),
            "--alerts-output-path",
            str(alerts_path),
            "--quarantine-output-path",
            str(quarantine_path),
            "--max-batch-size",
            "2",
            "--flush-interval-seconds",
            "60",
        ],
    )

    main()

    summary = json.loads(capsys.readouterr().out)
    alerts = load_jsonl(alerts_path)
    quarantines = load_jsonl(quarantine_path)

    assert summary["input_mode"] == "file"
    assert summary["valid_records"] == 2
    assert len(alerts) == 2
    assert len(quarantines) == 2
    assert captured_paths["feature_columns_path"] == config_feature_columns_path


def test_main_supports_configless_inferencer_without_hidden_schema_seam(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "flows.jsonl"
    input_path.write_text(
        json.dumps({"SrcPort": 10, "DstPort": 20, "Protocol": 6, "FlowDuration": 20}) + "\n",
        encoding="utf-8",
    )
    alerts_path = tmp_path / "alerts.jsonl"
    quarantine_path = tmp_path / "quarantine.jsonl"
    config_feature_columns_path = tmp_path / "config_feature_columns.json"
    config_feature_columns_path.write_text("[]\n", encoding="utf-8")
    captured_paths: dict[str, Path] = {}

    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.build_model_config",
        lambda **_: type("Config", (), {"feature_columns_path": config_feature_columns_path})(),
    )
    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.IDSInferencer",
        lambda config: ConfiglessInferencer(),
    )
    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.FlowFeatureContract.from_feature_file",
        classmethod(
            lambda cls, path, alias_map=None: (
                captured_paths.setdefault("feature_columns_path", Path(path)),
                make_contract(),
            )[1]
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ids_realtime_pipeline.py",
            "--input-path",
            str(input_path),
            "--alerts-output-path",
            str(alerts_path),
            "--quarantine-output-path",
            str(quarantine_path),
        ],
    )

    main()

    summary = json.loads(capsys.readouterr().out)
    assert summary["input_mode"] == "file"
    assert summary["valid_records"] == 1
    assert captured_paths["feature_columns_path"] == config_feature_columns_path


def test_main_uses_explicit_feature_columns_path_when_inferencer_config_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "flows.jsonl"
    input_path.write_text(
        json.dumps({"SrcPort": 10, "DstPort": 20, "Protocol": 6, "FlowDuration": 20}) + "\n",
        encoding="utf-8",
    )
    explicit_feature_columns_path = tmp_path / "explicit_feature_columns.json"
    explicit_feature_columns_path.write_text("[]\n", encoding="utf-8")
    alerts_path = tmp_path / "alerts.jsonl"
    quarantine_path = tmp_path / "quarantine.jsonl"
    config_feature_columns_path = tmp_path / "config_feature_columns.json"
    config_feature_columns_path.write_text("[]\n", encoding="utf-8")
    captured_paths: dict[str, Path] = {}

    def _from_feature_file(cls, path: Path, alias_map: dict[str, str] | None = None):
        _ = cls, alias_map
        captured_paths["feature_columns_path"] = Path(path)
        return make_contract()

    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.build_model_config",
        lambda **_: type("Config", (), {"feature_columns_path": config_feature_columns_path})(),
    )
    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.IDSInferencer",
        lambda config: ConfiglessInferencer(),
    )
    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.FlowFeatureContract.from_feature_file",
        classmethod(_from_feature_file),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ids_realtime_pipeline.py",
            "--input-path",
            str(input_path),
            "--alerts-output-path",
            str(alerts_path),
            "--quarantine-output-path",
            str(quarantine_path),
            "--feature-columns-path",
            str(explicit_feature_columns_path),
        ],
    )

    main()

    summary = json.loads(capsys.readouterr().out)
    assert summary["input_mode"] == "file"
    assert summary["valid_records"] == 1
    assert captured_paths["feature_columns_path"] == explicit_feature_columns_path


def test_main_forwards_activation_path_to_inferencer_when_provided(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    alerts_path = tmp_path / "alerts.jsonl"
    quarantine_path = tmp_path / "quarantine.jsonl"
    activation_path = tmp_path / "active_bundle.json"
    activation_path.write_text("{}", encoding="utf-8")
    captured_kwargs: dict[str, object] = {}

    class DummyInferencerWithConfig(DummyInferencer):
        def __init__(self) -> None:
            super().__init__()
            self.config = type("Config", (), {"feature_columns_path": demo_fixture_path()})()

    def _build_model_config(**kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return type("Config", (), {"feature_columns_path": demo_fixture_path()})()

    monkeypatch.setattr("ids.runtime.realtime_pipeline.build_model_config", _build_model_config)
    monkeypatch.setattr("ids.runtime.realtime_pipeline.IDSInferencer", lambda config: DummyInferencerWithConfig())
    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.FlowFeatureContract.from_feature_file",
        classmethod(lambda cls, path, alias_map=None: make_contract()),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "SrcPort": 1000,
                    "DstPort": 2000,
                    "Protocol": 6,
                    "FlowDuration": 95,
                    "trace_id": "stdin-1",
                }
            )
            + "\n"
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ids_realtime_pipeline.py",
            "--activation-path",
            str(activation_path),
            "--alerts-output-path",
            str(alerts_path),
            "--quarantine-output-path",
            str(quarantine_path),
        ],
    )

    main()

    summary = json.loads(capsys.readouterr().out)
    assert summary["input_mode"] == "stdin"
    assert captured_kwargs["activation_path"] == activation_path


def test_main_supports_stdin_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    alerts_path = tmp_path / "stdin_alerts.jsonl"
    quarantine_path = tmp_path / "stdin_quarantine.jsonl"
    stdin_stream = io.StringIO(
        json.dumps(
            {
                "SrcPort": 1000,
                "DstPort": 2000,
                "Protocol": 6,
                "FlowDuration": 95,
                "trace_id": "stdin-1",
            }
        )
        + "\n"
    )

    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.build_model_config",
        lambda **_: type("Config", (), {"feature_columns_path": demo_fixture_path()})(),
    )
    monkeypatch.setattr("ids.runtime.realtime_pipeline.IDSInferencer", lambda config: DummyInferencer())
    monkeypatch.setattr(
        "ids.runtime.realtime_pipeline.FlowFeatureContract.from_feature_file",
        classmethod(lambda cls, path, alias_map=None: make_contract()),
    )
    monkeypatch.setattr(sys, "stdin", stdin_stream)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ids_realtime_pipeline.py",
            "--alerts-output-path",
            str(alerts_path),
            "--quarantine-output-path",
            str(quarantine_path),
            "--max-batch-size",
            "2",
            "--flush-interval-seconds",
            "60",
        ],
    )

    main()

    summary = json.loads(capsys.readouterr().out)
    alerts = load_jsonl(alerts_path)
    quarantines = load_jsonl(quarantine_path)

    assert summary["input_mode"] == "stdin"
    assert summary["valid_records"] == 1
    assert alerts[0]["passthrough"] == {"trace_id": "stdin-1"}
    assert quarantines == []
