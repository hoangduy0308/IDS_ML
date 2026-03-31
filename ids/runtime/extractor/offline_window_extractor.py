from __future__ import annotations

import argparse
import ipaddress
import struct
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean, pvariance, pstdev
from typing import Any, Iterable, Iterator, Mapping, Sequence

from ids.runtime.adapter.record_adapter import PRIMARY_PROFILE_ID
from ids.runtime.extractor.offline_window_serializer import write_flow_csv


DEFAULT_FLOW_SUFFIX = "_Flow.csv"
DEFAULT_COLLECTOR_ID = "offline-window-extractor"
DEFAULT_CAPTURE_MODE = "closed-window"
DEFAULT_FLOW_FAMILY = "bidirectional"
ACTIVE_GAP_THRESHOLD_SECONDS = 1.0
ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_VLAN = 0x8100
IP_PROTOCOL_TCP = 6
IP_PROTOCOL_UDP = 17


@dataclass(frozen=True)
class PacketEvent:
    timestamp: float
    packet_length: int
    payload_length: int
    header_length: int
    direction: str
    protocol: int
    flags: int = 0
    window_size: int = 0


@dataclass
class FlowSummary:
    flow_index: int
    forward_src_ip: str
    forward_src_port: int
    forward_dst_ip: str
    forward_dst_port: int
    protocol: int
    packet_events: list[PacketEvent] = field(default_factory=list)

    def add_packet(self, packet: PacketEvent) -> None:
        self.packet_events.append(packet)

    @property
    def first_timestamp(self) -> float:
        return min(packet.timestamp for packet in self.packet_events)

    @property
    def last_timestamp(self) -> float:
        return max(packet.timestamp for packet in self.packet_events)

    @property
    def source_flow_id(self) -> str:
        return f"{self.forward_src_ip}:{self.forward_src_port}-{self.forward_dst_ip}:{self.forward_dst_port}-{self.flow_index:05d}"

    def sort_key(self) -> tuple[float, int, str, int, str, int]:
        return (
            self.first_timestamp,
            self.protocol,
            self.forward_src_ip,
            self.forward_src_port,
            self.forward_dst_ip,
            self.forward_dst_port,
        )

    def canonical_feature_values(self) -> dict[str, Any]:
        return self._build_canonical_feature_values()

    def metadata_values(self) -> dict[str, Any]:
        protocol_name = "tcp" if self.protocol == IP_PROTOCOL_TCP else "udp" if self.protocol == IP_PROTOCOL_UDP else "ip"
        flow_family = DEFAULT_FLOW_FAMILY if self._has_backward_packets() else "unidirectional"
        captured_at = datetime.fromtimestamp(self.first_timestamp, tz=timezone.utc).isoformat()
        return {
            "flow_id": self.source_flow_id,
            "collector_id": DEFAULT_COLLECTOR_ID,
            "captured_at": captured_at,
            "flow_family": flow_family,
            "transport_family": protocol_name,
            "capture_mode": DEFAULT_CAPTURE_MODE,
        }

    def _build_canonical_feature_values(self) -> dict[str, Any]:
        packets = sorted(self.packet_events, key=lambda packet: (packet.timestamp, packet.direction))
        forward_packets = [packet for packet in packets if packet.direction == "forward"]
        backward_packets = [packet for packet in packets if packet.direction == "backward"]

        duration_seconds = max(self.last_timestamp - self.first_timestamp, 0.0)
        rate_duration_seconds = duration_seconds
        all_lengths = [packet.packet_length for packet in packets]
        forward_lengths = [packet.packet_length for packet in forward_packets]
        backward_lengths = [packet.packet_length for packet in backward_packets]
        forward_payload_lengths = [packet.payload_length for packet in forward_packets]
        backward_payload_lengths = [packet.payload_length for packet in backward_packets]
        forward_header_lengths = [packet.header_length for packet in forward_packets]
        backward_header_lengths = [packet.header_length for packet in backward_packets]
        forward_window_sizes = [packet.window_size for packet in forward_packets if packet.window_size > 0]
        backward_window_sizes = [packet.window_size for packet in backward_packets if packet.window_size > 0]
        flow_iats = _intervals(packet.timestamp for packet in packets)
        forward_iats = _intervals(packet.timestamp for packet in forward_packets)
        backward_iats = _intervals(packet.timestamp for packet in backward_packets)
        active_durations, idle_durations = _split_active_idle_periods(
            packet.timestamp for packet in packets
        )

        total_packet_bytes = sum(all_lengths)
        total_payload_bytes = sum(packet.payload_length for packet in packets)
        forward_payload_total = sum(forward_payload_lengths)
        backward_payload_total = sum(backward_payload_lengths)
        forward_count = len(forward_packets)
        backward_count = len(backward_packets)
        total_count = len(packets)
        flow_header_total = sum(packet.header_length for packet in packets)

        forward_psh_flags = sum(1 for packet in forward_packets if packet.flags & 0x08)
        flag_counts = {
            "FIN Flag Count": sum(1 for packet in packets if packet.flags & 0x01),
            "SYN Flag Count": sum(1 for packet in packets if packet.flags & 0x02),
            "RST Flag Count": sum(1 for packet in packets if packet.flags & 0x04),
            "PSH Flag Count": sum(1 for packet in packets if packet.flags & 0x08),
            "ACK Flag Count": sum(1 for packet in packets if packet.flags & 0x10),
            "CWR Flag Count": sum(1 for packet in packets if packet.flags & 0x80),
            "ECE Flag Count": sum(1 for packet in packets if packet.flags & 0x40),
        }

        source_port = self.forward_src_port
        dest_port = self.forward_dst_port
        canonical_values = {
            "Src Port": source_port,
            "Dst Port": dest_port,
            "Protocol": float(self.protocol),
            "Flow Duration": _round_metric(_seconds_to_millis(duration_seconds), 3),
            "Total Fwd Packet": forward_count,
            "Total Bwd packets": backward_count,
            "Total Length of Fwd Packet": forward_payload_total,
            "Total Length of Bwd Packet": backward_payload_total,
            "Fwd Packet Length Max": _max_or_zero(forward_lengths),
            "Fwd Packet Length Min": _min_or_zero(forward_lengths),
            "Fwd Packet Length Mean": _mean_or_zero(forward_lengths),
            "Fwd Packet Length Std": _std_or_zero(forward_lengths),
            "Bwd Packet Length Max": _max_or_zero(backward_lengths),
            "Bwd Packet Length Min": _min_or_zero(backward_lengths),
            "Bwd Packet Length Mean": _mean_or_zero(backward_lengths),
            "Bwd Packet Length Std": _std_or_zero(backward_lengths),
            "Packet Length Max": _max_or_zero(all_lengths),
            "Packet Length Min": _min_or_zero(all_lengths),
            "Packet Length Mean": _mean_or_zero(all_lengths),
            "Packet Length Std": _std_or_zero(all_lengths),
            "Packet Length Variance": _round_metric(_var_or_zero(all_lengths)),
            "Flow Bytes/s": _round_metric(_rate(total_packet_bytes, rate_duration_seconds)),
            "Flow Packets/s": _round_metric(_rate(total_count, rate_duration_seconds)),
            "Flow IAT Mean": _round_metric(_mean_or_zero(flow_iats)),
            "Flow IAT Std": _round_metric(_std_or_zero(flow_iats)),
            "Flow IAT Max": _round_metric(_max_or_zero(flow_iats)),
            "Flow IAT Min": _round_metric(_min_or_zero(flow_iats)),
            "Fwd IAT Total": _round_metric(sum(forward_iats)),
            "Fwd IAT Mean": _round_metric(_mean_or_zero(forward_iats)),
            "Fwd IAT Std": _round_metric(_std_or_zero(forward_iats)),
            "Fwd IAT Max": _round_metric(_max_or_zero(forward_iats)),
            "Fwd IAT Min": _round_metric(_min_or_zero(forward_iats)),
            "Bwd IAT Total": _round_metric(sum(backward_iats)),
            "Bwd IAT Mean": _round_metric(_mean_or_zero(backward_iats)),
            "Bwd IAT Std": _round_metric(_std_or_zero(backward_iats)),
            "Bwd IAT Max": _round_metric(_max_or_zero(backward_iats)),
            "Bwd IAT Min": _round_metric(_min_or_zero(backward_iats)),
            "Fwd PSH Flags": forward_psh_flags,
            "Fwd Header Length": sum(forward_header_lengths),
            "Bwd Header Length": sum(backward_header_lengths),
            "Fwd Packets/s": _round_metric(_rate(forward_count, rate_duration_seconds)),
            "Bwd Packets/s": _round_metric(_rate(backward_count, rate_duration_seconds)),
            **flag_counts,
            "Down/Up Ratio": _ratio(backward_count, forward_count),
            "Average Packet Size": _round_metric(_mean_or_zero(all_lengths)),
            "Fwd Segment Size Avg": _round_metric(_mean_or_zero(forward_payload_lengths)),
            "Bwd Segment Size Avg": _round_metric(_mean_or_zero(backward_payload_lengths)),
            "Bwd Bytes/Bulk Avg": _round_metric(_mean_or_zero(backward_payload_lengths)),
            "Bwd Packet/Bulk Avg": _round_metric(
                _mean_or_zero(float(value) for value in backward_payload_lengths)
            ),
            "Bwd Bulk Rate Avg": _round_metric(_rate(backward_payload_total, rate_duration_seconds)),
            "Subflow Fwd Packets": forward_count,
            "Subflow Fwd Bytes": forward_payload_total,
            "Subflow Bwd Packets": backward_count,
            "Subflow Bwd Bytes": backward_payload_total,
            "Fwd Act Data Pkts": sum(1 for packet in forward_packets if packet.payload_length > 0),
            "Fwd Seg Size Min": _round_metric(_min_or_zero(forward_payload_lengths)),
            "FWD Init Win Bytes": _round_metric(_max_or_zero(forward_window_sizes)),
            "Bwd Init Win Bytes": _round_metric(_max_or_zero(backward_window_sizes)),
            "Active Mean": _round_metric(_mean_or_zero(active_durations)),
            "Active Std": _round_metric(_std_or_zero(active_durations)),
            "Active Max": _round_metric(_max_or_zero(active_durations)),
            "Active Min": _round_metric(_min_or_zero(active_durations)),
            "Idle Mean": _round_metric(_mean_or_zero(idle_durations)),
            "Idle Std": _round_metric(_std_or_zero(idle_durations)),
            "Idle Max": _round_metric(_max_or_zero(idle_durations)),
            "Idle Min": _round_metric(_min_or_zero(idle_durations)),
        }

        return canonical_values

    def _has_backward_packets(self) -> bool:
        return any(packet.direction == "backward" for packet in self.packet_events)


@dataclass(frozen=True)
class OfflineExtractorConfig:
    input_path: Path
    output_dir: Path
    profile_id: str = PRIMARY_PROFILE_ID
    flow_suffix: str = DEFAULT_FLOW_SUFFIX

    def __post_init__(self) -> None:
        if not self.flow_suffix.startswith("_") or not self.flow_suffix.endswith(".csv"):
            raise ValueError("flow_suffix must look like '_Flow.csv'")
        if not str(self.profile_id).strip():
            raise ValueError("profile_id must not be blank")


class PcapFormatError(ValueError):
    pass


def extract_flows(path: Path) -> list[FlowSummary]:
    return _parse_pcap_and_build_flows(Path(path))


def extract_window(config: OfflineExtractorConfig) -> Path:
    input_path = Path(config.input_path)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}{config.flow_suffix}"

    flows = extract_flows(input_path)
    write_flow_csv(flows, output_path, profile_id=config.profile_id)

    return output_path


def _parse_pcap_and_build_flows(path: Path) -> list[FlowSummary]:
    flows: dict[tuple[str, int, str, int, int], FlowSummary] = {}
    reverse_index: dict[tuple[str, int, str, int, int], tuple[str, int, str, int, int]] = {}
    next_flow_index = 0

    for timestamp, frame in _read_pcap_packets(path):
        parsed = _decode_frame(timestamp, frame)
        if parsed is None:
            continue
        (
            src_ip,
            src_port,
            dst_ip,
            dst_port,
            protocol,
            header_length,
            payload_length,
            packet_length,
            flags,
            window_size,
        ) = parsed
        forward_key = (src_ip, src_port, dst_ip, dst_port, protocol)
        backward_key = (dst_ip, dst_port, src_ip, src_port, protocol)

        if forward_key in flows:
            flow = flows[forward_key]
            direction = "forward"
        elif backward_key in flows:
            flow = flows[backward_key]
            direction = "backward"
        else:
            flow = FlowSummary(
                flow_index=next_flow_index,
                forward_src_ip=src_ip,
                forward_src_port=src_port,
                forward_dst_ip=dst_ip,
                forward_dst_port=dst_port,
                protocol=protocol,
            )
            next_flow_index += 1
            flows[forward_key] = flow
            reverse_index[backward_key] = forward_key
            direction = "forward"

        flow.add_packet(
            PacketEvent(
                timestamp=timestamp,
                packet_length=packet_length,
                payload_length=payload_length,
                header_length=header_length,
                direction=direction,
                protocol=protocol,
                flags=flags,
                window_size=window_size,
            )
        )

        if forward_key not in flows and backward_key in reverse_index:
            flows[forward_key] = flows[reverse_index[backward_key]]

    return list({id(flow): flow for flow in flows.values()}.values())


def _read_pcap_packets(path: Path) -> Iterator[tuple[float, bytes]]:
    with Path(path).open("rb") as handle:
        global_header = handle.read(24)
        if len(global_header) != 24:
            raise PcapFormatError("pcap file is missing a global header")

        magic = global_header[:4]
        if magic == b"\xd4\xc3\xb2\xa1":
            endian = "<"
            resolution = 1_000_000.0
        elif magic == b"\xa1\xb2\xc3\xd4":
            endian = ">"
            resolution = 1_000_000.0
        elif magic == b"\x4d\x3c\xb2\xa1":
            endian = "<"
            resolution = 1_000_000_000.0
        elif magic == b"\xa1\xb2\x3c\x4d":
            endian = ">"
            resolution = 1_000_000_000.0
        else:
            raise PcapFormatError("unsupported pcap magic number")

        network = struct.unpack(f"{endian}I", global_header[20:24])[0]
        if network != 1:
            raise PcapFormatError(f"unsupported data link type: {network}")

        record_header_struct = struct.Struct(f"{endian}IIII")
        while True:
            record_header = handle.read(record_header_struct.size)
            if not record_header:
                break
            if len(record_header) != record_header_struct.size:
                raise PcapFormatError("truncated pcap record header")
            ts_sec, ts_frac, incl_len, _orig_len = record_header_struct.unpack(record_header)
            frame = handle.read(incl_len)
            if len(frame) != incl_len:
                raise PcapFormatError("truncated pcap record payload")
            timestamp = ts_sec + (ts_frac / resolution)
            yield timestamp, frame


def _decode_frame(
    timestamp: float,
    frame: bytes,
) -> tuple[str, int, str, int, int, int, int, int, int, int] | None:
    if len(frame) < 14:
        return None

    ethernet_offset = 14
    ethertype = struct.unpack("!H", frame[12:14])[0]
    if ethertype == ETHERTYPE_VLAN:
        if len(frame) < 18:
            return None
        ethertype = struct.unpack("!H", frame[16:18])[0]
        ethernet_offset = 18

    if ethertype != ETHERTYPE_IPV4 or len(frame) < ethernet_offset + 20:
        return None

    ip_header_offset = ethernet_offset
    version_ihl = frame[ip_header_offset]
    version = version_ihl >> 4
    ihl_words = version_ihl & 0x0F
    if version != 4 or ihl_words < 5:
        return None

    ip_header_length = ihl_words * 4
    if len(frame) < ip_header_offset + ip_header_length:
        return None

    total_length = struct.unpack("!H", frame[ip_header_offset + 2 : ip_header_offset + 4])[0]
    protocol = frame[ip_header_offset + 9]
    src_ip = str(ipaddress.IPv4Address(frame[ip_header_offset + 12 : ip_header_offset + 16]))
    dst_ip = str(ipaddress.IPv4Address(frame[ip_header_offset + 16 : ip_header_offset + 20]))
    l4_offset = ip_header_offset + ip_header_length
    header_length = ip_header_length
    flags = 0
    window_size = 0

    if protocol == IP_PROTOCOL_TCP:
        if len(frame) < l4_offset + 20:
            return None
        src_port, dst_port = struct.unpack("!HH", frame[l4_offset : l4_offset + 4])
        tcp_header_length = ((frame[l4_offset + 12] >> 4) & 0x0F) * 4
        if tcp_header_length < 20 or len(frame) < l4_offset + tcp_header_length:
            return None
        flags = frame[l4_offset + 13]
        window_size = struct.unpack("!H", frame[l4_offset + 14 : l4_offset + 16])[0]
        header_length += tcp_header_length
        payload_length = max(total_length - ip_header_length - tcp_header_length, 0)
    elif protocol == IP_PROTOCOL_UDP:
        if len(frame) < l4_offset + 8:
            return None
        src_port, dst_port = struct.unpack("!HH", frame[l4_offset : l4_offset + 4])
        header_length += 8
        payload_length = max(total_length - ip_header_length - 8, 0)
    else:
        return None

    return (
        src_ip,
        src_port,
        dst_ip,
        dst_port,
        protocol,
        header_length,
        payload_length,
        len(frame),
        flags,
        window_size,
    )


def _intervals(times: Iterable[float]) -> list[float]:
    ordered = sorted(float(value) for value in times)
    if len(ordered) < 2:
        return []
    return [max(0.0, later - earlier) for earlier, later in zip(ordered, ordered[1:])]


def _split_active_idle_periods(times: Iterable[float]) -> tuple[list[float], list[float]]:
    ordered = sorted(float(value) for value in times)
    if not ordered:
        return [], []

    active_periods: list[float] = []
    idle_periods: list[float] = []
    cluster_start = ordered[0]
    cluster_last = ordered[0]

    for ts in ordered[1:]:
        gap = ts - cluster_last
        if gap > ACTIVE_GAP_THRESHOLD_SECONDS:
            active_periods.append(max(0.0, cluster_last - cluster_start))
            idle_periods.append(max(0.0, gap))
            cluster_start = ts
        cluster_last = ts

    active_periods.append(max(0.0, cluster_last - cluster_start))
    return active_periods, idle_periods


def _mean_or_zero(values: Iterable[float]) -> float:
    values = [float(value) for value in values]
    if not values:
        return 0.0
    return float(fmean(values))


def _std_or_zero(values: Iterable[float]) -> float:
    values = [float(value) for value in values]
    if len(values) < 2:
        return 0.0
    return float(pstdev(values))


def _var_or_zero(values: Iterable[float]) -> float:
    values = [float(value) for value in values]
    if len(values) < 2:
        return 0.0
    return float(pvariance(values))


def _max_or_zero(values: Iterable[float]) -> float:
    values = [float(value) for value in values]
    return float(max(values)) if values else 0.0


def _min_or_zero(values: Iterable[float]) -> float:
    values = [float(value) for value in values]
    return float(min(values)) if values else 0.0


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _rate(numerator: float, duration_seconds: float) -> float:
    if duration_seconds <= 0:
        return 0.0
    return float(numerator) / float(duration_seconds)


def _seconds_to_millis(value: float) -> float:
    return float(max(value, 0.0) * 1000.0)


def _round_metric(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract deterministic closed-window flow CSVs from pcap inputs using the "
            "offline replacement extractor core."
        )
    )
    parser.add_argument("pcap_path", type=Path, help="Closed pcap window to extract.")
    parser.add_argument("output_dir", type=Path, help="Directory where the _Flow.csv file is written.")
    parser.add_argument(
        "--profile-id",
        default=PRIMARY_PROFILE_ID,
        help="Adapter profile compatibility surface to target.",
    )
    parser.add_argument(
        "--flow-suffix",
        default=DEFAULT_FLOW_SUFFIX,
        help="Suffix used for the generated CSV file name.",
    )
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    extract_window(
        OfflineExtractorConfig(
            input_path=Path(args.pcap_path),
            output_dir=Path(args.output_dir),
            profile_id=str(args.profile_id),
            flow_suffix=str(args.flow_suffix),
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
