from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Protocol, Sequence

from ids.runtime.adapter.record_adapter import get_adapter_profile


class SerializableFlow(Protocol):
    def canonical_feature_values(self) -> dict[str, Any]: ...
    def metadata_values(self) -> dict[str, Any]: ...
    def sort_key(self) -> tuple[float, int, str, int, str, int]: ...


def flow_to_source_record(flow: SerializableFlow, profile_id: str) -> dict[str, Any]:
    profile = get_adapter_profile(profile_id)
    canonical_feature_values = flow.canonical_feature_values()
    canonical_to_source = {
        canonical_key: source_key
        for source_key, canonical_key in profile.feature_alias_map.items()
    }
    source_record: dict[str, Any] = {
        canonical_to_source[canonical_key]: value
        for canonical_key, value in canonical_feature_values.items()
    }
    source_record.update(
        {
            source_key: value
            for source_key, value in flow.metadata_values().items()
        }
    )
    return source_record


def write_flow_csv(flows: Sequence[SerializableFlow], output_path: Path, profile_id: str) -> Path:
    profile = get_adapter_profile(profile_id)
    fieldnames = list(profile.accepted_source_keys())
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for flow in sorted(flows, key=lambda item: item.sort_key()):
            row = flow_to_source_record(flow, profile_id)
            writer.writerow({key: _format_csv_value(row.get(key, "")) for key in fieldnames})

    return output_path


def _format_csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return value
