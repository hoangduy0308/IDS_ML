from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_live_capture import ClosedCaptureWindow  # noqa: E402
from scripts.ids_live_flow_bridge import (  # noqa: E402
    BridgeWindowResult,
    ExtractorRunResult,
    LiveFlowBridge,
    LiveFlowBridgeConfig,
)


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


def make_window(tmp_path: Path) -> ClosedCaptureWindow:
    return ClosedCaptureWindow(
        path=tmp_path / "windows" / "capture-00001.pcap",
        interface="eth0",
        observed_at=12.5,
        notification="dumpcap: file closed capture-00001.pcap",
        sequence_number=1,
    )


def test_bridge_invokes_extractor_for_closed_window_and_normalizes_primary_records(
    tmp_path: Path,
) -> None:
    window = make_window(tmp_path)
    observed: dict[str, object] = {}

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        observed["command"] = tuple(command)
        observed["window_path"] = window_arg.path
        observed["output_path"] = output_path
        write_csv_output(output_path, [load_primary_sample_row()])
        return ExtractorRunResult(returncode=0, stdout="ok", stderr="")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd")),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert isinstance(result, BridgeWindowResult)
    assert observed["window_path"] == window.path
    assert observed["output_path"] == result.extractor_output_path
    assert result.command[:2] == ("cfm", "Cmd")
    assert str(window.path) in result.command
    assert str(tmp_path / "flows") in result.command
    assert result.extractor_output_path.name == "capture-00001_Flow.csv"
    assert result.window_errors == ()
    assert result.adapter_quarantines == ()
    assert len(result.adapted_records) == 1
    emitted = result.adapted_records[0]
    assert emitted["event_type"] == "bridge_record"
    assert emitted["profile"] == "cicflowmeter_primary_v1"
    assert emitted["record"]["adapter_profile"] == "cicflowmeter_primary_v1"
    assert emitted["record"]["Flow Duration"] == 80.0


def test_bridge_surfaces_window_stage_error_when_extractor_fails(tmp_path: Path) -> None:
    window = make_window(tmp_path)

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        return ExtractorRunResult(returncode=2, stdout="", stderr="Cmd failed")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd")),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert result.adapted_records == ()
    assert result.adapter_quarantines == ()
    assert len(result.window_errors) == 1
    error = result.window_errors[0]
    assert error["event_type"] == "window_stage_error"
    assert error["stage"] == "extractor"
    assert error["reason"] == "extractor_process_failed"
    assert error["window_path"] == str(window.path)
    assert error["extractor_output_path"].endswith("_Flow.csv")


def test_bridge_emits_adapter_quarantine_for_bad_extractor_rows(tmp_path: Path) -> None:
    window = make_window(tmp_path)
    bad_row = load_primary_sample_row()
    bad_row["FlowDuration"] = "bad"

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        write_csv_output(output_path, [bad_row])
        return ExtractorRunResult(returncode=0, stdout="ok", stderr="")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd")),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert result.window_errors == ()
    assert result.adapted_records == ()
    assert len(result.adapter_quarantines) == 1
    quarantine = result.adapter_quarantines[0]
    assert quarantine["event_type"] == "adapter_quarantine"
    assert quarantine["profile"] == "cicflowmeter_primary_v1"
    assert quarantine["window_path"] == str(window.path)
    assert quarantine["extractor_output_path"].endswith("_Flow.csv")


def test_bridge_write_result_jsonl_matches_demo_artifact_shape(tmp_path: Path) -> None:
    window = make_window(tmp_path)

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        write_csv_output(output_path, [load_primary_sample_row()])
        return ExtractorRunResult(returncode=0, stdout="ok", stderr="")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd")),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")
    demo_path = tmp_path / "demo" / "ids_live_sensor_primary_sample.jsonl"
    bridge.write_result_jsonl(result, demo_path)

    demo_lines = [json.loads(line) for line in demo_path.read_text(encoding="utf-8").splitlines()]
    assert demo_lines[0]["event_type"] == "bridge_record"
    assert demo_lines[0]["record"]["adapter_profile"] == "cicflowmeter_primary_v1"

