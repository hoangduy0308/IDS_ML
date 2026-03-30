from __future__ import annotations

import io
import json
from pathlib import Path
import shlex
import re

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.runtime.live_capture import CaptureBacklogExceededError, ClosedCaptureWindow  # noqa: E402
from ids.runtime.live_flow_bridge import BridgeWindowResult  # noqa: E402
from ids.runtime.live_sensor import (  # noqa: E402
    CaptureSessionFatalError,
    DEFAULT_CAPTURE_WINDOW_DURATION_SECONDS,
    LiveSensorDaemon,
    LiveSensorDaemonConfig,
)
from ids.runtime.live_sensor_sinks import LiveSensorLocalSink  # noqa: E402
from ids.core.model_bundle import (  # noqa: E402
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)
from ids.ops.model_bundle_lifecycle import (  # noqa: E402
    ActiveBundleResolutionError,
    build_activation_record_payload,
    write_activation_record,
)


def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_activation_contract(tmp_path: Path) -> Path:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir(parents=True, exist_ok=True)
    feature_columns_path = bundle_root / "feature_columns.json"
    feature_columns_path.write_text(
        json.dumps({"feature_columns": ["Flow Duration", "Src Port", "Dst Port"]}),
        encoding="utf-8",
    )
    (bundle_root / "model.cbm").write_text("model", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "bundle_name": "bundle-under-test",
                "created_at": "2026-03-29T00:00:00+07:00",
                "model_key": "catboost_full_data",
                "model_family": "CatBoostClassifier",
                "model_artifact": "model.cbm",
                "feature_columns_file": "feature_columns.json",
                "threshold": 0.5,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "feature_count": 3,
                "train_rows": 123,
                "metrics_file": "metrics.json",
                "training_summary_file": "training_summary.json",
                "compatibility": {
                    "feature_schema": build_feature_schema_metadata(feature_columns_path),
                    "inference_contract": build_inference_contract_metadata(
                        positive_label="Attack",
                        negative_label="Benign",
                        threshold=0.5,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    activation_path = tmp_path / "active_bundle.json"
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=bundle_root,
            active_bundle_name="bundle-under-test",
            activated_at="2026-03-29T00:00:00+07:00",
        ),
    )
    return activation_path


class RecordingRuntimeRunner:
    def __init__(self) -> None:
        self.ingested: list[tuple[int | None, dict[str, object]]] = []
        self.finalize_calls = 0
        self.flush_if_due_calls = 0

    def ingest_record(
        self,
        record: dict[str, object],
        *,
        record_index: int | None,
        now: float | None = None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], bool]:
        self.ingested.append((record_index, dict(record)))
        is_alert = float(record["Flow Duration"]) >= 50.0
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

    def finalize(self) -> tuple[list[dict[str, object]], bool]:
        self.finalize_calls += 1
        return [], False

    def flush_if_due(self, *, now: float | None = None) -> tuple[list[dict[str, object]], bool]:
        self.flush_if_due_calls += 1
        return [], False


class RecordingBridge:
    def __init__(self) -> None:
        self.window_sequences: list[int | None] = []

    def bridge_window(
        self,
        window: ClosedCaptureWindow,
        *,
        output_dir: Path | None = None,
    ) -> BridgeWindowResult:
        self.window_sequences.append(window.sequence_number)
        extractor_output_path = Path(output_dir or window.path.parent) / (
            f"{window.path.stem}_Flow.csv"
        )
        window.path.parent.mkdir(parents=True, exist_ok=True)
        extractor_output_path.parent.mkdir(parents=True, exist_ok=True)
        window.path.write_text("closed window", encoding="utf-8")
        extractor_output_path.write_text("flow output", encoding="utf-8")

        if window.sequence_number == 0:
            return BridgeWindowResult(
                window=window,
                extractor_output_path=extractor_output_path,
                command=("Cmd",),
                adapted_records=(
                    {
                        "event_type": "bridge_record",
                        "record_index": 0,
                        "profile": "cicflowmeter_primary_v1",
                        "record": {
                            "Flow Duration": 10.0,
                            "Src Port": 1.0,
                            "Dst Port": 2.0,
                        },
                    },
                ),
                adapter_quarantines=(),
                window_errors=(),
            )

        if window.sequence_number == 1:
            return BridgeWindowResult(
                window=window,
                extractor_output_path=extractor_output_path,
                command=("Cmd",),
                adapted_records=(
                    {
                        "event_type": "bridge_record",
                        "record_index": 1,
                        "profile": "cicflowmeter_primary_v1",
                        "record": {
                            "Flow Duration": 80.0,
                            "Src Port": 3.0,
                            "Dst Port": 4.0,
                        },
                    },
                ),
                adapter_quarantines=(
                    {
                        "event_type": "adapter_quarantine",
                        "profile": "cicflowmeter_primary_v1",
                        "reason": "non_numeric_required_features",
                        "window_path": str(window.path),
                        "extractor_output_path": str(extractor_output_path),
                    },
                ),
                window_errors=(),
            )

        return BridgeWindowResult(
            window=window,
            extractor_output_path=extractor_output_path,
            command=("Cmd",),
            adapted_records=(),
            adapter_quarantines=(),
            window_errors=(
                {
                    "event_type": "window_stage_error",
                    "stage": "extractor",
                    "reason": "extractor_process_failed",
                    "window_path": str(window.path),
                    "extractor_output_path": str(extractor_output_path),
                },
            ),
        )


class RecordingSink:
    def __init__(self) -> None:
        self.alerts: list[dict[str, object]] = []
        self.quarantines: list[dict[str, object]] = []
        self.benign_predictions = 0
        self.extractor_failures: list[str] = []
        self.summary_events: list[dict[str, object]] = []
        self.telemetry: list[dict[str, object]] = []

    def record_alert(self, event: dict[str, object]) -> None:
        self.alerts.append(dict(event))

    def record_quarantine(self, event: dict[str, object]) -> None:
        self.quarantines.append(dict(event))

    def record_benign_prediction(self, count: int = 1) -> None:
        self.benign_predictions += int(count)

    def record_extractor_failure(self, reason: str) -> None:
        self.extractor_failures.append(reason)

    def record_window_telemetry(self, **kwargs: object) -> dict[str, object]:
        telemetry = dict(kwargs)
        self.telemetry.append(telemetry)
        return telemetry

    def capture_summary(self, *, reason: str = "periodic") -> dict[str, object]:
        event = {
            "event_type": "live_sensor_summary",
            "reason": reason,
            "alert_records": len(self.alerts),
            "quarantine_records": len(self.quarantines),
            "benign_predictions": self.benign_predictions,
            "extractor_failures": len(self.extractor_failures),
            "latest_queue_depth": self.telemetry[-1]["queue_depth"] if self.telemetry else 0,
        }
        self.summary_events.append(event)
        return event

    def close(self) -> dict[str, object]:
        return self.capture_summary(reason="close")


class FakeStderr:
    def __init__(self, trailing_text: str = "") -> None:
        self._trailing_text = trailing_text

    def read(self) -> str:
        value = self._trailing_text
        self._trailing_text = ""
        return value


class FakeProcess:
    def __init__(self, *, returncode: int, trailing_stderr: str = "") -> None:
        self._returncode = returncode
        self._waited = False
        self._terminated = False
        self.stderr = FakeStderr(trailing_stderr)

    def wait(self) -> int:
        self._waited = True
        return self._returncode

    def poll(self) -> int | None:
        if self._waited:
            return self._returncode
        if self._terminated:
            return 0
        return None

    def terminate(self) -> None:
        self._terminated = True


def make_config(tmp_path: Path, **overrides: object) -> LiveSensorDaemonConfig:
    kwargs = {
        "spool_dir": tmp_path / "spool",
        "alerts_output_path": tmp_path / "alerts.jsonl",
        "quarantine_output_path": tmp_path / "quarantine.jsonl",
        "summary_output_path": tmp_path / "summary.jsonl",
        "activation_path": write_activation_contract(tmp_path),
    }
    kwargs.update(overrides)
    return LiveSensorDaemonConfig(**kwargs)


def test_daemon_config_wires_capture_window_duration_and_support_modules(tmp_path: Path) -> None:
    daemon = LiveSensorDaemon(
        make_config(tmp_path),
        bridge=object(),  # type: ignore[arg-type]
        runtime_runner=RecordingRuntimeRunner(),
        sink=RecordingSink(),
    )

    assert daemon.config.capture_window_duration_seconds == DEFAULT_CAPTURE_WINDOW_DURATION_SECONDS
    assert daemon.capture_manager.config.window_duration_seconds == DEFAULT_CAPTURE_WINDOW_DURATION_SECONDS
    assert daemon.capture_manager.config.window_file_count == 2
    assert daemon.capture_manager.config.max_pending_windows == 2


def test_daemon_processes_windows_in_order_and_cleans_spool_artifacts(tmp_path: Path) -> None:
    bridge = RecordingBridge()
    runtime = RecordingRuntimeRunner()
    summary_stream = io.StringIO()
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
        summary_output_stream=summary_stream,
    )
    daemon = LiveSensorDaemon(
        make_config(tmp_path),
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

    assert window0 is not None
    assert window1 is not None
    assert daemon.pending_window_count == 2

    processed = daemon.process_pending_windows()
    summary = daemon.close()

    assert bridge.window_sequences == [0, 1]
    assert len(processed) == 2
    assert runtime.finalize_calls == 1
    assert runtime.flush_if_due_calls == 2
    assert summary["alert_records"] == 1
    assert summary["quarantine_records"] == 1
    assert summary["benign_predictions"] == 1
    assert summary["processed_windows"] == 2
    assert summary["active_bundle"]["active_bundle_name"] == "bundle-under-test"
    assert summary["active_bundle"]["compatibility_status"] == "compatible"
    assert not window0.path.exists()
    assert not window1.path.exists()
    assert not (tmp_path / "spool" / "flows" / "eth0-window-00000_Flow.csv").exists()
    assert not (tmp_path / "spool" / "flows" / "eth0-window-00001_Flow.csv").exists()

    summary_events = load_jsonl(tmp_path / "summary.jsonl")
    queue_depths = [event["latest_queue_depth"] for event in summary_events]
    assert queue_depths[:2] == [1, 2]
    assert queue_depths[-1] == 0
    emitted_lines = [line for line in summary_stream.getvalue().splitlines() if line.strip()]
    assert emitted_lines[-1] == summary["journald_message"]
    assert "active_bundle=bundle-under-test" in summary["journald_message"]


def test_daemon_raises_when_pending_windows_exceed_ceiling(tmp_path: Path) -> None:
    daemon = LiveSensorDaemon(
        make_config(tmp_path, max_pending_windows=1),
        bridge=RecordingBridge(),
        runtime_runner=RecordingRuntimeRunner(),
        sink=RecordingSink(),
    )

    daemon.enqueue_notification_line(
        f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(0)}",
        observed_at=10.0,
    )

    with pytest.raises(CaptureBacklogExceededError, match="pending closed windows"):
        daemon.enqueue_notification_line(
            f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(1)}",
            observed_at=11.0,
        )

    assert daemon._summary.restartable_failures == 1
    assert daemon.pending_window_count == 1


def test_daemon_serve_notification_lines_handles_window_errors_and_quarantines(
    tmp_path: Path,
) -> None:
    bridge = RecordingBridge()
    runtime = RecordingRuntimeRunner()
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
    )
    daemon = LiveSensorDaemon(
        make_config(tmp_path),
        bridge=bridge,
        runtime_runner=runtime,
        sink=sink,
    )

    summary = daemon.serve_notification_lines(
        [
            f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(0)}",
            f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(1)}",
            f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(2)}",
        ]
    )

    assert summary.recoverable_window_errors == 1
    assert summary.recoverable_quarantines == 1
    assert summary.processed_windows == 3
    assert summary.benign_predictions == 1
    assert bridge.window_sequences == [0, 1, 2]
    assert runtime.finalize_calls == 1

    persisted_summaries = load_jsonl(tmp_path / "summary.jsonl")
    assert any(event["reason"] == "window-processed" for event in persisted_summaries)
    assert any(
        event.get("extractor_failure_reasons") == ["extractor_process_failed"]
        for event in persisted_summaries
    )
    assert len(load_jsonl(tmp_path / "quarantine.jsonl")) == 1
    assert len(load_jsonl(tmp_path / "alerts.jsonl")) == 1


def test_serve_capture_session_raises_on_fatal_dumpcap_exit(tmp_path: Path) -> None:
    bridge = RecordingBridge()
    runtime = RecordingRuntimeRunner()
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
    )
    daemon = LiveSensorDaemon(
        make_config(tmp_path),
        bridge=bridge,
        runtime_runner=runtime,
        sink=sink,
    )

    lines = [
        f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(0)}",
    ]

    def popen_factory(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess(returncode=1)

    with pytest.raises(CaptureSessionFatalError, match="fatal dumpcap exit") as exc_info:
        daemon.serve_capture_session(
            popen_factory=popen_factory,  # type: ignore[arg-type]
            notification_reader=lambda process: iter(lines),
        )

    assert exc_info.value.failure.is_fatal is True
    assert runtime.finalize_calls == 1
    assert len(load_jsonl(tmp_path / "alerts.jsonl")) == 0
    summaries = load_jsonl(tmp_path / "summary.jsonl")
    assert summaries[-1]["reason"] == "capture-failure"


def test_serve_capture_session_returns_cleanly_on_recoverable_dumpcap_exit(tmp_path: Path) -> None:
    bridge = RecordingBridge()
    runtime = RecordingRuntimeRunner()
    sink = LiveSensorLocalSink(
        alerts_output_path=tmp_path / "alerts.jsonl",
        quarantine_output_path=tmp_path / "quarantine.jsonl",
        summary_output_path=tmp_path / "summary.jsonl",
    )
    daemon = LiveSensorDaemon(
        make_config(tmp_path),
        bridge=bridge,
        runtime_runner=runtime,
        sink=sink,
    )

    lines = [
        f"dumpcap: file closed {daemon.capture_manager.window_path_for_sequence(0)}",
        "dumpcap: capture stopped by request",
    ]

    def popen_factory(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess(returncode=0)

    summary = daemon.serve_capture_session(
        popen_factory=popen_factory,  # type: ignore[arg-type]
        notification_reader=lambda process: iter(lines),
    )

    assert summary["reason"] == "close"
    assert runtime.finalize_calls == 1
    assert len(load_jsonl(tmp_path / "summary.jsonl")) >= 2


def test_service_unit_keeps_preflight_and_stdout_journal_contract() -> None:
    service_path = REPO_ROOT / "deploy" / "systemd" / "ids-live-sensor.service"
    content = service_path.read_text(encoding="utf-8")

    assert "IDS_LIVE_SENSOR_DUMPCAP_BINARY=" in content
    assert "IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX=" in content
    assert "IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH=" in content
    assert "ids_live_sensor_preflight.py" in content
    assert '--dumpcap-binary ${IDS_LIVE_SENSOR_DUMPCAP_BINARY}' in content
    assert '--extractor-command-prefix ${IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX}' in content
    assert '--activation-path ${IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH}' in content
    assert '--interface "$IDS_LIVE_SENSOR_INTERFACE"' in content
    assert '--dumpcap-binary "$IDS_LIVE_SENSOR_DUMPCAP_BINARY"' in content
    assert '--extractor-command-prefix "$IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX"' not in content
    execstart_line = next(
        line for line in content.splitlines() if line.startswith("ExecStart=")
    )
    command_match = re.search(r"bash -lc '(.*)'$", execstart_line)
    assert command_match is not None
    shell_command = command_match.group(1).replace(
        "${IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX}",
        "/opt/extractor-prefix /opt/extractor-bridge",
    )
    tokens = shlex.split(shell_command)
    prefix_index = tokens.index("--extractor-command-prefix")
    assert tokens[prefix_index + 1 : prefix_index + 3] == [
        "/opt/extractor-prefix",
        "/opt/extractor-bridge",
    ]
    assert '--activation-path "$IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH"' in content
    assert "StandardOutput=journal" in content
    assert "StandardError=journal" in content


def test_daemon_uses_activation_contract_for_runtime_wiring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded_models: list[Path] = []
    observed_feature_paths: list[Path] = []

    class DummyModel:
        def load_model(self, path: Path) -> None:
            loaded_models.append(Path(path))

        def predict_proba(self, frame: object) -> object:
            raise AssertionError("predict_proba should not run in this wiring test")

    def fake_contract_loader(path: Path) -> object:
        observed_feature_paths.append(Path(path))
        return object()

    monkeypatch.setattr("ids.runtime.inference.CatBoostClassifier", DummyModel)
    monkeypatch.setattr(
        "ids.runtime.live_sensor.FlowFeatureContract.from_feature_file",
        fake_contract_loader,
    )

    daemon = LiveSensorDaemon(make_config(tmp_path))

    assert loaded_models == [(tmp_path / "bundle" / "model.cbm").resolve()]
    assert observed_feature_paths == [(tmp_path / "bundle" / "feature_columns.json").resolve()]
    assert daemon.config.activation_path == (tmp_path / "active_bundle.json").resolve()
    assert daemon.sink.snapshot_summary()["active_bundle"]["active_bundle_name"] == "bundle-under-test"


def test_daemon_fails_closed_when_activation_contract_missing(tmp_path: Path) -> None:
    with pytest.raises(ActiveBundleResolutionError, match="Activation record not found"):
        LiveSensorDaemon(make_config(tmp_path, activation_path=tmp_path / "missing.json"))
