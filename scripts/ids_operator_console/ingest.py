from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
import json
import os

from .db import DEFAULT_SENSOR_ID, OperatorStore


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _extract_event_ts(payload: Mapping[str, Any]) -> str:
    for key in ("timestamp", "event_ts", "time", "ts"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return _utc_now_iso()


def _extract_source_event_id(payload: Mapping[str, Any]) -> str | None:
    for key in ("source_event_id", "event_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int):
            return str(value)
    return None


def _extract_field(payload: Mapping[str, Any], *candidate_keys: str) -> Any:
    for key in candidate_keys:
        value = payload.get(key)
        if value is not None:
            return value
    passthrough = payload.get("passthrough")
    if isinstance(passthrough, Mapping):
        for key in candidate_keys:
            value = passthrough.get(key)
            if value is not None:
                return value
    return None


def _extract_optional_int(payload: Mapping[str, Any], *candidate_keys: str) -> int | None:
    value = _extract_field(payload, *candidate_keys)
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _extract_optional_text(payload: Mapping[str, Any], *candidate_keys: str) -> str | None:
    value = _extract_field(payload, *candidate_keys)
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


@dataclass(frozen=True)
class StreamIngestResult:
    stream_name: str
    records_read: int
    records_committed: int
    parse_errors: int
    committed_offset: int
    file_reset: bool


@dataclass(frozen=True)
class IngestRunSummary:
    alerts_ingested: int = 0
    anomalies_ingested: int = 0
    summaries_ingested: int = 0
    parse_errors: int = 0
    streams_scanned: int = 0


class SensorOutputIngestor:
    def __init__(
        self,
        *,
        store: OperatorStore,
        alerts_input_path: Path,
        quarantine_input_path: Path,
        summary_input_path: Path,
        sensor_id: str = DEFAULT_SENSOR_ID,
        json_loader: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self._store = store
        self._sensor_id = sensor_id
        self._streams: tuple[tuple[str, Path, str], ...] = (
            ("alerts", Path(alerts_input_path).resolve(), "alert"),
            ("quarantine", Path(quarantine_input_path).resolve(), "anomaly"),
            ("summary", Path(summary_input_path).resolve(), "summary"),
        )
        self._json_loader = json_loader or self._default_json_loader

    @staticmethod
    def _default_json_loader(raw: str) -> Mapping[str, Any]:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("JSONL record must be an object")
        return parsed

    def run_once(self) -> IngestRunSummary:
        alerts_ingested = 0
        anomalies_ingested = 0
        summaries_ingested = 0
        parse_errors = 0

        for stream_name, stream_path, stream_kind in self._streams:
            result = self._ingest_stream(
                stream_name=stream_name,
                stream_path=stream_path,
                stream_kind=stream_kind,
            )
            parse_errors += result.parse_errors
            if stream_kind == "alert":
                alerts_ingested += result.records_committed
            elif stream_kind == "anomaly":
                anomalies_ingested += result.records_committed
            elif stream_kind == "summary":
                summaries_ingested += result.records_committed

        return IngestRunSummary(
            alerts_ingested=alerts_ingested,
            anomalies_ingested=anomalies_ingested,
            summaries_ingested=summaries_ingested,
            parse_errors=parse_errors,
            streams_scanned=len(self._streams),
        )

    def _ingest_stream(self, *, stream_name: str, stream_path: Path, stream_kind: str) -> StreamIngestResult:
        stat = stream_path.stat() if stream_path.exists() else None
        existing = self._store.get_ingest_offset(stream_name)

        file_inode: int | None = None
        file_device: int | None = None
        file_size = 0
        file_reset = False
        offset = 0

        if stat is not None:
            file_inode = int(stat.st_ino)
            file_device = int(stat.st_dev)
            file_size = int(stat.st_size)

        if existing is not None:
            previous_offset = int(existing["offset_bytes"])
            previous_inode = existing["file_inode"]
            previous_device = existing["file_device"]
            if stat is None:
                offset = 0
            elif previous_offset > file_size:
                file_reset = True
                offset = 0
            elif previous_inode != file_inode or previous_device != file_device:
                file_reset = True
                offset = 0
            else:
                offset = previous_offset

        if stat is None:
            persisted = self._store.record_ingest_offset(
                stream_name=stream_name,
                source_path=stream_path,
                file_inode=None,
                file_device=None,
                file_size=0,
                offset_bytes=0,
                last_record_ts=(existing or {}).get("last_record_ts") if existing is not None else None,
                sensor_id=self._sensor_id,
            )
            return StreamIngestResult(
                stream_name=stream_name,
                records_read=0,
                records_committed=0,
                parse_errors=0,
                committed_offset=int(persisted["offset_bytes"]) if persisted is not None else 0,
                file_reset=file_reset,
            )

        with stream_path.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read()

        if not chunk:
            persisted = self._store.record_ingest_offset(
                stream_name=stream_name,
                source_path=stream_path,
                file_inode=file_inode,
                file_device=file_device,
                file_size=file_size,
                offset_bytes=offset,
                last_record_ts=(existing or {}).get("last_record_ts") if existing is not None else None,
                sensor_id=self._sensor_id,
            )
            return StreamIngestResult(
                stream_name=stream_name,
                records_read=0,
                records_committed=0,
                parse_errors=0,
                committed_offset=int(persisted["offset_bytes"]) if persisted is not None else offset,
                file_reset=file_reset,
            )

        lines = chunk.split(b"\n")
        trailing_fragment = b""
        if chunk[-1:] != b"\n":
            trailing_fragment = lines.pop()
        complete_lines = [line for line in lines if line.strip()]

        parsed_records = 0
        committed_records = 0
        parse_errors = 0
        last_record_ts: str | None = None

        for raw_line in complete_lines:
            raw_text = raw_line.decode("utf-8").strip()
            if not raw_text:
                continue
            try:
                payload = self._json_loader(raw_text)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                parse_errors += 1
                self._store.store_anomaly(
                    event_ts=_utc_now_iso(),
                    anomaly_type="ingest_parse_error",
                    reason=f"{stream_name}: {exc}",
                    redacted_summary=f"ingest parse failure in {stream_name}",
                    payload={"stream_name": stream_name, "raw_line": raw_text[:512]},
                    sensor_id=self._sensor_id,
                )
                continue

            parsed_records += 1
            event_ts = _extract_event_ts(payload)
            if stream_kind == "alert":
                self._store.upsert_alert(
                    event_ts=event_ts,
                    payload=payload,
                    sensor_id=self._sensor_id,
                    source_event_id=_extract_source_event_id(payload),
                    severity=_extract_optional_text(payload, "severity"),
                    src_ip=_extract_optional_text(payload, "src_ip", "source_ip", "Src IP"),
                    dst_ip=_extract_optional_text(payload, "dst_ip", "destination_ip", "Dst IP"),
                    src_port=_extract_optional_int(payload, "src_port", "source_port", "Src Port"),
                    dst_port=_extract_optional_int(payload, "dst_port", "destination_port", "Dst Port"),
                    protocol=_extract_optional_text(payload, "protocol", "Protocol"),
                    fingerprint=_extract_optional_text(payload, "fingerprint"),
                )
            elif stream_kind == "anomaly":
                self._store.store_anomaly(
                    event_ts=event_ts,
                    anomaly_type=_extract_optional_text(payload, "anomaly_type", "event_type") or "schema_anomaly",
                    reason=_extract_optional_text(payload, "reason"),
                    redacted_summary=_extract_optional_text(payload, "redacted_summary", "reason"),
                    payload=payload,
                    sensor_id=self._sensor_id,
                    source_event_id=_extract_source_event_id(payload),
                )
            elif stream_kind == "summary":
                self._store.store_summary(
                    summary_ts=event_ts,
                    payload=payload,
                    sensor_id=self._sensor_id,
                )
            committed_records += 1
            last_record_ts = event_ts

        committed_offset = offset + len(chunk) - len(trailing_fragment)
        persisted = self._store.record_ingest_offset(
            stream_name=stream_name,
            source_path=stream_path,
            file_inode=file_inode,
            file_device=file_device,
            file_size=file_size,
            offset_bytes=committed_offset,
            last_record_ts=last_record_ts,
            sensor_id=self._sensor_id,
        )

        return StreamIngestResult(
            stream_name=stream_name,
            records_read=parsed_records,
            records_committed=committed_records,
            parse_errors=parse_errors,
            committed_offset=int(persisted["offset_bytes"]) if persisted is not None else committed_offset,
            file_reset=file_reset,
        )


def ingest_sensor_outputs_once(
    *,
    store: OperatorStore,
    alerts_input_path: Path,
    quarantine_input_path: Path,
    summary_input_path: Path,
    sensor_id: str = DEFAULT_SENSOR_ID,
) -> IngestRunSummary:
    ingestor = SensorOutputIngestor(
        store=store,
        alerts_input_path=alerts_input_path,
        quarantine_input_path=quarantine_input_path,
        summary_input_path=summary_input_path,
        sensor_id=sensor_id,
    )
    return ingestor.run_once()


__all__ = [
    "IngestRunSummary",
    "SensorOutputIngestor",
    "StreamIngestResult",
    "ingest_sensor_outputs_once",
]
