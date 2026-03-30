from __future__ import annotations

import csv
import struct
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_offline_window_extractor import (  # noqa: E402
    OfflineExtractorConfig,
    extract_window,
    main,
)
from scripts.ids_record_adapter import PRIMARY_PROFILE_ID, adapt_record, get_adapter_profile  # noqa: E402


EXPECTED_FIXTURE_PATH = REPO_ROOT / "artifacts" / "demo" / "ids_offline_window_extractor_expected.csv"


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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_extract_window_writes_bridge_consumable_csv(tmp_path: Path) -> None:
    pcap_path = _build_sample_pcap(tmp_path / "capture-00001.pcap")
    output_dir = tmp_path / "flows"

    output_path = extract_window(
        OfflineExtractorConfig(
            input_path=pcap_path,
            output_dir=output_dir,
            profile_id=PRIMARY_PROFILE_ID,
        )
    )

    profile = get_adapter_profile(PRIMARY_PROFILE_ID)
    rows = _read_csv_rows(output_path)

    assert output_path.name == "capture-00001_Flow.csv"
    assert output_path.exists()
    assert len(rows) == 1
    assert set(rows[0]) == set(profile.accepted_source_keys())
    assert rows[0]["SrcPort"] == "12345"
    assert rows[0]["DstPort"] == "80"
    assert rows[0]["FlowDuration"] == "900"
    assert rows[0]["Protocol"] == "6"
    assert rows[0]["flow_family"] == "bidirectional"
    assert rows[0]["transport_family"] == "tcp"
    assert rows[0]["capture_mode"] == "closed-window"

    adapted = adapt_record(rows[0], profile_id=PRIMARY_PROFILE_ID, record_index=0)
    assert adapted.features["Src Port"] == 12345.0
    assert adapted.features["Dst Port"] == 80.0
    assert adapted.features["Flow Duration"] == 900.0
    assert len(adapted.features) == 72
    assert adapted.metadata["source_flow_id"].endswith("-00000")
    assert adapted.controlled_extras["capture_mode"] == "closed-window"


def test_extract_window_matches_golden_csv_fixture(tmp_path: Path) -> None:
    pcap_path = _build_sample_pcap(tmp_path / "capture-00001.pcap")
    output_dir = tmp_path / "flows"

    output_path = extract_window(
        OfflineExtractorConfig(
            input_path=pcap_path,
            output_dir=output_dir,
            profile_id=PRIMARY_PROFILE_ID,
        )
    )

    assert output_path.read_text(encoding="utf-8") == EXPECTED_FIXTURE_PATH.read_text(
        encoding="utf-8"
    )


def test_cli_supports_positional_command_contract_and_help() -> None:
    help_run = subprocess.run(
        [sys.executable, "-m", "scripts.ids_offline_window_extractor", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert help_run.returncode == 0
    assert "offline replacement extractor core" in help_run.stdout


def test_cli_accepts_closed_pcap_and_writes_expected_output(tmp_path: Path) -> None:
    pcap_path = _build_sample_pcap(tmp_path / "capture-00001.pcap")
    output_dir = tmp_path / "flows"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.ids_offline_window_extractor",
            str(pcap_path),
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    output_path = output_dir / "capture-00001_Flow.csv"
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == EXPECTED_FIXTURE_PATH.read_text(
        encoding="utf-8"
    )


def test_cli_rejects_invalid_flow_suffix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="flow_suffix must look like '_Flow.csv'"):
        OfflineExtractorConfig(
            input_path=tmp_path / "capture.pcap",
            output_dir=tmp_path / "flows",
            profile_id=PRIMARY_PROFILE_ID,
            flow_suffix="Flow.csv",
        )
