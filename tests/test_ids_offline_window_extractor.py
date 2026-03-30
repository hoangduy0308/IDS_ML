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
    PcapFormatError,
    extract_flows,
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


def _build_udp_frame(
    *,
    src_mac: str,
    dst_mac: str,
    src_ip: str,
    dst_ip: str,
    src_port: int,
    dst_port: int,
    payload: bytes,
    vlan_tag: int | None = None,
) -> bytes:
    udp_header_len = 8
    ip_header_len = 20
    total_length = ip_header_len + udp_header_len + len(payload)
    ethernet = _mac(dst_mac) + _mac(src_mac)
    if vlan_tag is None:
        ethernet += struct.pack("!H", 0x0800)
    else:
        ethernet += struct.pack("!H", 0x8100)
        ethernet += struct.pack("!H", vlan_tag)
        ethernet += struct.pack("!H", 0x0800)
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        (4 << 4) | 5,
        0,
        total_length,
        0,
        0,
        64,
        17,
        0,
        _ipv4(src_ip),
        _ipv4(dst_ip),
    )
    udp_length = udp_header_len + len(payload)
    udp_header = struct.pack("!HHHH", src_port, dst_port, udp_length, 0)
    return ethernet + ip_header + udp_header + payload


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
    assert adapted.features["Flow Bytes/s"] == pytest.approx(208.888889)
    assert adapted.features["Flow Packets/s"] == pytest.approx(3.333333)
    assert adapted.features["Fwd Packets/s"] == pytest.approx(2.222222)
    assert adapted.features["Bwd Packets/s"] == pytest.approx(1.111111)
    assert adapted.features["Bwd Bulk Rate Avg"] == pytest.approx(16.666667)
    assert len(adapted.features) == 72
    assert adapted.metadata["source_flow_id"].endswith("-00000")
    assert adapted.controlled_extras["capture_mode"] == "closed-window"


def test_extract_flows_exposes_canonical_core_without_adapter_aliasing(tmp_path: Path) -> None:
    pcap_path = _build_sample_pcap(tmp_path / "capture-00001.pcap")

    flows = extract_flows(pcap_path)

    assert len(flows) == 1
    flow = flows[0]
    canonical = flow.canonical_feature_values()

    assert canonical["Flow Duration"] == 900.0
    assert canonical["Flow Bytes/s"] == pytest.approx(208.888889)
    assert canonical["Flow Packets/s"] == pytest.approx(3.333333)
    assert canonical["Fwd Packets/s"] == pytest.approx(2.222222)
    assert canonical["Bwd Packets/s"] == pytest.approx(1.111111)
    assert canonical["Bwd Bulk Rate Avg"] == pytest.approx(16.666667)
    assert flow.metadata_values()["flow_id"].endswith("-00000")


def test_extract_flows_handles_vlan_udp_frames_and_ignores_non_ip_frames(tmp_path: Path) -> None:
    pcap_path = tmp_path / "capture-vlan-udp.pcap"
    client_mac = "02:00:00:00:00:01"
    server_mac = "02:00:00:00:00:02"
    client_ip = "10.0.1.10"
    server_ip = "10.0.1.20"
    vlan_udp_frame = _build_udp_frame(
        src_mac=client_mac,
        dst_mac=server_mac,
        src_ip=client_ip,
        dst_ip=server_ip,
        src_port=5353,
        dst_port=53,
        payload=b"dns-query",
        vlan_tag=7,
    )
    non_ip_frame = _mac(server_mac) + _mac(client_mac) + struct.pack("!H", 0x86DD) + (b"\x00" * 40)
    _write_pcap(
        pcap_path,
        [
            (1_700_000_002.0, vlan_udp_frame),
            (1_700_000_002.1, non_ip_frame),
        ],
    )

    flows = extract_flows(pcap_path)

    assert len(flows) == 1
    flow = flows[0]
    canonical = flow.canonical_feature_values()
    assert flow.protocol == 17
    assert flow.forward_src_port == 5353
    assert flow.forward_dst_port == 53
    assert canonical["Protocol"] == 17.0
    assert canonical["Total Fwd Packet"] == 1
    assert canonical["Total Bwd packets"] == 0


def test_extract_flows_merges_reverse_first_packets_into_one_flow(tmp_path: Path) -> None:
    pcap_path = tmp_path / "capture-reverse-first.pcap"
    client_mac = "02:00:00:00:00:01"
    server_mac = "02:00:00:00:00:02"
    client_ip = "10.0.2.10"
    server_ip = "10.0.2.20"
    frames = [
        (
            1_700_000_003.0,
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
                payload=b"reply",
            ),
        ),
        (
            1_700_000_003.4,
            _build_tcp_frame(
                src_mac=client_mac,
                dst_mac=server_mac,
                src_ip=client_ip,
                dst_ip=server_ip,
                src_port=12345,
                dst_port=80,
                seq=3,
                ack=7,
                flags=0x18,
                payload=b"client-data",
            ),
        ),
    ]
    _write_pcap(pcap_path, frames)

    flows = extract_flows(pcap_path)

    assert len(flows) == 1
    flow = flows[0]
    canonical = flow.canonical_feature_values()
    assert flow.forward_src_port == 80
    assert flow.forward_dst_port == 12345
    assert flow.source_flow_id.startswith("10.0.2.20:80-10.0.2.10:12345")
    assert canonical["Total Fwd Packet"] == 1
    assert canonical["Total Bwd packets"] == 1
    assert canonical["Down/Up Ratio"] == 1.0


@pytest.mark.parametrize(
    ("pcap_bytes", "message"),
    [
        (
            struct.pack("<IHHIIII", 0xDEADBEEF, 2, 4, 0, 0, 65535, 1),
            "unsupported pcap magic number",
        ),
        (
            struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 2),
            "unsupported data link type: 2",
        ),
        (
            struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1) + struct.pack("<II", 1, 2),
            "truncated pcap record header",
        ),
        (
            struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
            + struct.pack("<IIII", 1, 2, 8, 8)
            + b"1234",
            "truncated pcap record payload",
        ),
    ],
)
def test_extract_flows_rejects_malformed_and_unsupported_pcap_variants(
    tmp_path: Path,
    pcap_bytes: bytes,
    message: str,
) -> None:
    pcap_path = tmp_path / "invalid.pcap"
    pcap_path.write_bytes(pcap_bytes)

    with pytest.raises(PcapFormatError, match=message):
        extract_flows(pcap_path)


def test_extract_window_uses_zero_duration_guard_without_flooring_subsecond_flows(
    tmp_path: Path,
) -> None:
    pcap_path = tmp_path / "capture-00002.pcap"
    client_mac = "02:00:00:00:00:01"
    server_mac = "02:00:00:00:00:02"
    client_ip = "10.0.0.10"
    server_ip = "10.0.0.20"
    timestamp = 1_700_000_001.0
    frames = [
        (
            timestamp,
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
            timestamp,
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
    ]
    _write_pcap(pcap_path, frames)
    output_dir = tmp_path / "flows"

    output_path = extract_window(
        OfflineExtractorConfig(
            input_path=pcap_path,
            output_dir=output_dir,
            profile_id=PRIMARY_PROFILE_ID,
        )
    )

    rows = _read_csv_rows(output_path)
    adapted = adapt_record(rows[0], profile_id=PRIMARY_PROFILE_ID, record_index=0)

    assert adapted.features["Flow Duration"] == 0.0
    assert adapted.features["Flow Bytes/s"] == 0.0
    assert adapted.features["Flow Packets/s"] == 0.0
    assert adapted.features["Fwd Packets/s"] == 0.0
    assert adapted.features["Bwd Packets/s"] == 0.0
    assert adapted.features["Bwd Bulk Rate Avg"] == 0.0


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
    rows = _read_csv_rows(output_path)
    assert len(rows) == 1
    assert rows[0]["FlowDuration"] == "900"


def test_cli_rejects_invalid_flow_suffix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="flow_suffix must look like '_Flow.csv'"):
        OfflineExtractorConfig(
            input_path=tmp_path / "capture.pcap",
            output_dir=tmp_path / "flows",
            profile_id=PRIMARY_PROFILE_ID,
            flow_suffix="Flow.csv",
        )
