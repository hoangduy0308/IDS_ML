from __future__ import annotations

import csv
import json
import struct
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.runtime.live_capture import ClosedCaptureWindow  # noqa: E402
from ids.runtime.live_flow_bridge import (  # noqa: E402
    BridgeWindowResult,
    ExtractorRunResult,
    LiveFlowBridge,
    LiveFlowBridgeConfig,
)
from ids.runtime.adapter.record_adapter import PRIMARY_PROFILE_ID  # noqa: E402


def _mac(address: str) -> bytes:
    return bytes.fromhex(address.replace(":", ""))


def _ipv4(address: str) -> bytes:
    return bytes(int(part) for part in address.split("."))


def _build_tcp_frame(
    *,
    src_mac: str,
    dst_mac: str,
    src_ip: str,
    dst_ip: str,
    src_port: int,
    dst_port: int,
    seq: int,
    ack: int,
    flags: int,
    payload: bytes,
) -> bytes:
    tcp_header_len = 20
    ip_header_len = 20
    total_length = ip_header_len + tcp_header_len + len(payload)
    ethernet = _mac(dst_mac) + _mac(src_mac) + struct.pack("!H", 0x0800)
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        (4 << 4) | 5,
        0,
        total_length,
        0,
        0,
        64,
        6,
        0,
        _ipv4(src_ip),
        _ipv4(dst_ip),
    )
    tcp_header = struct.pack(
        "!HHLLBBHHH",
        src_port,
        dst_port,
        seq,
        ack,
        (5 << 4),
        flags,
        8192,
        0,
        0,
    )
    return ethernet + ip_header + tcp_header + payload


def _write_pcap(path: Path, frames: list[tuple[float, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for timestamp, frame in frames:
            ts_sec = int(timestamp)
            ts_usec = int(round((timestamp - ts_sec) * 1_000_000))
            handle.write(struct.pack("<IIII", ts_sec, ts_usec, len(frame), len(frame)))
            handle.write(frame)


def _build_sample_pcap(path: Path) -> Path:
    client_mac = "02:00:00:00:00:01"
    server_mac = "02:00:00:00:00:02"
    client_ip = "10.0.0.10"
    server_ip = "10.0.0.20"

    frames = [
        (
            1_700_000_000.0,
            _build_tcp_frame(
                src_mac=client_mac,
                dst_mac=server_mac,
                src_ip=client_ip,
                dst_ip=server_ip,
                src_port=12345,
                dst_port=80,
                seq=1,
                ack=0,
                flags=0x02,
                payload=b"",
            ),
        ),
        (
            1_700_000_000.4,
            _build_tcp_frame(
                src_mac=server_mac,
                dst_mac=client_mac,
                src_ip=server_ip,
                dst_ip=client_ip,
                src_port=80,
                dst_port=12345,
                seq=2,
                ack=2,
                flags=0x12,
                payload=b"reply-payload-1",
            ),
        ),
        (
            1_700_000_000.9,
            _build_tcp_frame(
                src_mac=client_mac,
                dst_mac=server_mac,
                src_ip=client_ip,
                dst_ip=server_ip,
                src_port=12345,
                dst_port=80,
                seq=3,
                ack=17,
                flags=0x18,
                payload=b"client-data",
            ),
        ),
    ]
    _write_pcap(path, frames)
    return path


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


def test_bridge_can_drive_the_offline_replacement_extractor_cli(tmp_path: Path) -> None:
    window = make_window(tmp_path)
    _build_sample_pcap(window.path)

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
        LiveFlowBridgeConfig(
            extractor_command_prefix=("ids-offline-window-extractor",),
            adapter_profile_id=PRIMARY_PROFILE_ID,
        ),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert result.command[:1] == ("ids-offline-window-extractor",)
    assert observed["command"] == result.command
    assert observed["window_path"] == window.path
    assert observed["output_path"] == result.extractor_output_path
    assert result.command[-2] == str(window.path)
    assert result.command[-1] == str(tmp_path / "flows")
    assert result.extractor_output_path.name == "capture-00001_Flow.csv"
    assert result.window_errors == ()
    assert result.adapter_quarantines == ()
    assert len(result.adapted_records) == 1

    emitted = result.adapted_records[0]
    assert emitted["event_type"] == "bridge_record"
    assert emitted["profile"] == PRIMARY_PROFILE_ID
    assert emitted["record"]["adapter_profile"] == PRIMARY_PROFILE_ID
    assert emitted["record"]["Flow Duration"] == 80.0
    assert emitted["record"]["flow_family"] == "flow_family-value"
    assert emitted["record"]["transport_family"] == "transport_family-value"
    assert emitted["record"]["capture_mode"] == "capture_mode-value"


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


def test_bridge_surfaces_window_stage_error_when_extractor_runner_raises(tmp_path: Path) -> None:
    window = make_window(tmp_path)

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        raise RuntimeError("boom")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd")),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert result.adapted_records == ()
    assert result.adapter_quarantines == ()
    assert len(result.window_errors) == 1
    error = result.window_errors[0]
    assert error["stage"] == "extractor"
    assert error["reason"] == "extractor_runner_failed"
    assert error["stderr"] == "boom"
    assert error["extractor_output_path"].endswith("_Flow.csv")


def test_bridge_surfaces_window_stage_error_when_extractor_output_is_missing(tmp_path: Path) -> None:
    window = make_window(tmp_path)

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        return ExtractorRunResult(returncode=0, stdout="ok", stderr="")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd")),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert len(result.window_errors) == 1
    error = result.window_errors[0]
    assert error["stage"] == "output"
    assert error["reason"] == "missing_extractor_output"
    assert error["window_path"] == str(window.path)
    assert error["extractor_output_path"].endswith("_Flow.csv")


def test_bridge_surfaces_window_stage_error_when_extractor_output_is_invalid(tmp_path: Path) -> None:
    window = make_window(tmp_path)

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        return ExtractorRunResult(returncode=0, stdout="ok", stderr="")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd")),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert len(result.window_errors) == 1
    error = result.window_errors[0]
    assert error["stage"] == "output"
    assert error["reason"] == "invalid_extractor_output"
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


def test_bridge_preserves_row_order_for_mixed_adapted_and_quarantine_rows(tmp_path: Path) -> None:
    window = make_window(tmp_path)
    good_row = load_primary_sample_row()
    bad_row = dict(good_row)
    bad_row["FlowDuration"] = "bad"

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        write_csv_output(output_path, [good_row, bad_row])
        return ExtractorRunResult(returncode=0, stdout="ok", stderr="")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd")),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert result.window_errors == ()
    assert len(result.adapted_records) == 1
    assert len(result.adapter_quarantines) == 1
    assert result.adapted_records[0]["record_index"] == 0
    assert result.adapter_quarantines[0]["record_index"] == 1


def test_bridge_surfaces_unknown_adapter_profile_with_window_stage_error(tmp_path: Path) -> None:
    window = make_window(tmp_path)

    def fake_runner(
        command: list[str] | tuple[str, ...],
        window_arg: ClosedCaptureWindow,
        output_path: Path,
    ) -> ExtractorRunResult:
        write_csv_output(output_path, [load_primary_sample_row()])
        return ExtractorRunResult(returncode=0, stdout="ok", stderr="")

    bridge = LiveFlowBridge(
        LiveFlowBridgeConfig(
            extractor_command_prefix=("cfm", "Cmd"),
            adapter_profile_id="unknown_profile",
        ),
        extractor_runner=fake_runner,
    )

    result = bridge.bridge_window(window, output_dir=tmp_path / "flows")

    assert result.adapted_records == ()
    assert result.adapter_quarantines == ()
    assert len(result.window_errors) == 1
    error = result.window_errors[0]
    assert error["stage"] == "adapter"
    assert error["reason"] == "unknown_adapter_profile"
    assert error["window_path"] == str(window.path)
    assert error["extractor_output_path"].endswith("_Flow.csv")


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
