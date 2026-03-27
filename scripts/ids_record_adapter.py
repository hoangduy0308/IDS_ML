from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass, field
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TextIO

PRIMARY_PROFILE_ID = "cicflowmeter_primary_v1"
SECONDARY_PROFILE_ID = "cicflowmeter_secondary_v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_JSONL_LINE_LENGTH = 1_048_576

ADAPTER_FIXED_METADATA_KEYS = (
    "adapter_profile",
    "source_flow_id",
    "source_collector_id",
    "source_timestamp",
)
ADAPTER_UPSTREAM_METADATA_KEYS = ADAPTER_FIXED_METADATA_KEYS[1:]

_DEFAULT_ADAPTER_FEATURE_COLUMNS: tuple[str, ...] | None = None
_DEFAULT_ADAPTER_CONTRACT: Any | None = None
_DEFAULT_ADAPTER_PROFILE_REGISTRY: "AdapterProfileRegistry" | None = None


PRIMARY_PROFILE_FEATURE_ALIAS_OVERRIDES = {
    "SrcPort": "Src Port",
    "DstPort": "Dst Port",
    "FlowDuration": "Flow Duration",
    "Tot Fwd Pkts": "Total Fwd Packet",
    "Tot Bwd Pkts": "Total Bwd packets",
    "TotLen Fwd Pkts": "Total Length of Fwd Packet",
    "TotLen Bwd Pkts": "Total Length of Bwd Packet",
    "Pkt Len Min": "Packet Length Min",
    "Pkt Len Max": "Packet Length Max",
    "Pkt Len Mean": "Packet Length Mean",
    "Pkt Len Std": "Packet Length Std",
    "Pkt Len Var": "Packet Length Variance",
    "Init Fwd Win Byts": "FWD Init Win Bytes",
    "Init Bwd Win Byts": "Bwd Init Win Bytes",
}

PRIMARY_PROFILE_METADATA_ALIASES = {
    "flow_id": "source_flow_id",
    "collector_id": "source_collector_id",
    "captured_at": "source_timestamp",
}

PRIMARY_PROFILE_CONTROLLED_EXTRA_KEYS = (
    "flow_family",
    "transport_family",
    "capture_mode",
)


SECONDARY_PROFILE_FEATURE_ALIAS_OVERRIDES = {
    "SourcePort": "Src Port",
    "DestinationPort": "Dst Port",
    "Duration": "Flow Duration",
    "TotalFwdPackets": "Total Fwd Packet",
    "TotalBwdPackets": "Total Bwd packets",
    "FwdPktsLenTotal": "Total Length of Fwd Packet",
    "BwdPktsLenTotal": "Total Length of Bwd Packet",
    "PacketLenMin": "Packet Length Min",
    "PacketLenMax": "Packet Length Max",
    "PacketLenMean": "Packet Length Mean",
    "PacketLenStd": "Packet Length Std",
    "PacketLenVar": "Packet Length Variance",
    "InitFwdWinBytes": "FWD Init Win Bytes",
    "InitBwdWinBytes": "Bwd Init Win Bytes",
}

SECONDARY_PROFILE_METADATA_ALIASES = {
    "trace_id": "source_flow_id",
    "sensor_id": "source_collector_id",
    "event_ts": "source_timestamp",
}

SECONDARY_PROFILE_CONTROLLED_EXTRA_KEYS = (
    "flow_family",
    "transport_family",
    "capture_mode",
)


def _build_closed_feature_alias_map(
    feature_alias_overrides: Mapping[str, str],
    *,
    feature_columns: Sequence[str] | None = None,
) -> dict[str, str]:
    resolved_feature_columns = (
        tuple(str(column) for column in feature_columns)
        if feature_columns is not None
        else _get_default_adapter_feature_columns()
    )
    normalized_overrides = {
        str(source_key).strip(): str(target_key).strip()
        for source_key, target_key in feature_alias_overrides.items()
    }
    override_targets = set(normalized_overrides.values())
    explicit_map = {
        str(column): str(column)
        for column in resolved_feature_columns
        if str(column) not in override_targets
    }
    explicit_map.update(normalized_overrides)
    return explicit_map


def _ensure_cli_repo_bootstrap() -> None:
    if __package__ not in (None, ""):
        return
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def _load_feature_contract_module() -> Any:
    try:
        return importlib.import_module("scripts.ids_feature_contract")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Unable to import scripts.ids_feature_contract. Import the adapter as a "
            "module from the repository root, or execute it via the CLI entrypoint."
        ) from exc


def build_default_adapter_contract(
    feature_columns: Sequence[str] | None = None,
) -> Any:
    feature_contract_module = _load_feature_contract_module()
    resolved_feature_columns = (
        tuple(str(column) for column in feature_columns)
        if feature_columns is not None
        else _get_default_adapter_feature_columns()
    )
    return feature_contract_module.FlowFeatureContract(resolved_feature_columns, alias_map={})


def _get_default_adapter_feature_columns() -> tuple[str, ...]:
    global _DEFAULT_ADAPTER_FEATURE_COLUMNS
    if _DEFAULT_ADAPTER_FEATURE_COLUMNS is None:
        feature_contract_module = _load_feature_contract_module()
        _DEFAULT_ADAPTER_FEATURE_COLUMNS = tuple(feature_contract_module.load_default_feature_columns())
    return _DEFAULT_ADAPTER_FEATURE_COLUMNS


def _get_default_adapter_contract() -> Any:
    global _DEFAULT_ADAPTER_CONTRACT
    if _DEFAULT_ADAPTER_CONTRACT is None:
        _DEFAULT_ADAPTER_CONTRACT = build_default_adapter_contract()
    return _DEFAULT_ADAPTER_CONTRACT


def _get_default_adapter_profile_registry() -> "AdapterProfileRegistry":
    global _DEFAULT_ADAPTER_PROFILE_REGISTRY
    if _DEFAULT_ADAPTER_PROFILE_REGISTRY is None:
        _DEFAULT_ADAPTER_PROFILE_REGISTRY = build_default_adapter_registry()
    return _DEFAULT_ADAPTER_PROFILE_REGISTRY


class _DefaultAdapterProfileRegistryProxy:
    def available_profile_ids(self) -> tuple[str, ...]:
        return _get_default_adapter_profile_registry().available_profile_ids()

    def get(self, profile_id: str) -> "AdapterProfileDefinition":
        return _get_default_adapter_profile_registry().get(profile_id)

    def require(self, profile_id: str) -> "AdapterProfileDefinition":
        return _get_default_adapter_profile_registry().require(profile_id)


def _is_quarantined_flow_record(value: Any) -> bool:
    feature_contract_module = _load_feature_contract_module()
    return isinstance(value, feature_contract_module.QuarantinedFlowRecord)


def _normalize_mapping(
    mapping: Mapping[str, str],
    *,
    label: str,
    profile_id: str,
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}
    for raw_key, raw_value in mapping.items():
        key = str(raw_key).strip()
        value = str(raw_value).strip()
        if not key:
            raise ValueError(f"{profile_id}: {label} contains a blank source key")
        if not value:
            raise ValueError(f"{profile_id}: {label} contains a blank target key")
        if key in normalized:
            raise ValueError(f"{profile_id}: {label} contains duplicate source key {key!r}")
        normalized[key] = value
        collisions.setdefault(value, []).append(key)

    duplicate_targets = sorted(
        target for target, source_keys in collisions.items() if len(source_keys) > 1
    )
    if duplicate_targets:
        raise ValueError(
            f"{profile_id}: {label} must be one-to-one; duplicate targets: "
            + ", ".join(repr(target) for target in duplicate_targets)
        )
    return normalized


def _validate_controlled_extra_keys(
    extra_keys: Sequence[str],
    *,
    profile_id: str,
) -> tuple[str, ...]:
    normalized = tuple(str(key).strip() for key in extra_keys)
    if any(not key for key in normalized):
        raise ValueError(f"{profile_id}: controlled_extra_keys contains a blank key")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{profile_id}: controlled_extra_keys must not contain duplicates")
    return normalized


def _stringify_source_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in record.items()}


def _normalize_source_record(
    record: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]:
    normalized: dict[str, Any] = {}
    normalized_origins: dict[str, str] = {}
    blank_source_keys: list[str] = []
    normalized_key_collisions: list[str] = []

    for raw_key, value in record.items():
        normalized_key = raw_key.strip()
        if not normalized_key:
            blank_source_keys.append(raw_key)
            continue
        if normalized_key in normalized and raw_key != normalized_origins[normalized_key]:
            normalized_key_collisions.append(normalized_key)
            continue
        normalized[normalized_key] = value
        normalized_origins[normalized_key] = raw_key

    return (
        normalized,
        tuple(sorted(set(blank_source_keys))),
        tuple(sorted(set(normalized_key_collisions))),
    )


@dataclass(frozen=True)
class AdapterProfileDefinition:
    profile_id: str
    feature_alias_map: dict[str, str]
    metadata_alias_map: dict[str, str]
    controlled_extra_keys: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        profile_id = str(self.profile_id).strip()
        if not profile_id:
            raise ValueError("profile_id must not be blank")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(
            self,
            "feature_alias_map",
            _normalize_mapping(
                self.feature_alias_map,
                label="feature_alias_map",
                profile_id=profile_id,
            ),
        )
        object.__setattr__(
            self,
            "metadata_alias_map",
            _normalize_mapping(
                self.metadata_alias_map,
                label="metadata_alias_map",
                profile_id=profile_id,
            ),
        )
        extras = _validate_controlled_extra_keys(
            self.controlled_extra_keys,
            profile_id=profile_id,
        )
        object.__setattr__(self, "controlled_extra_keys", extras)

        source_feature_keys = set(self.feature_alias_map)
        source_metadata_keys = set(self.metadata_alias_map)
        if source_feature_keys & source_metadata_keys:
            overlap = ", ".join(repr(key) for key in sorted(source_feature_keys & source_metadata_keys))
            raise ValueError(f"{profile_id}: feature and metadata source keys overlap on {overlap}")

        feature_targets = set(self.feature_alias_map.values())
        metadata_targets = set(self.metadata_alias_map.values())
        overlapping_targets = sorted(feature_targets & metadata_targets)
        if overlapping_targets:
            raise ValueError(
                f"{profile_id}: feature and metadata maps overlap on "
                + ", ".join(repr(target) for target in overlapping_targets)
            )

        normalized_metadata_targets = set(ADAPTER_UPSTREAM_METADATA_KEYS)
        invalid_metadata_targets = sorted(metadata_targets - normalized_metadata_targets)
        if invalid_metadata_targets:
            raise ValueError(
                f"{profile_id}: metadata_alias_map targets must stay within the"
                f" upstream-controlled adapter metadata keys: "
                f"{', '.join(repr(key) for key in invalid_metadata_targets)}"
            )

        controlled_extra_keys = set(self.controlled_extra_keys)
        if controlled_extra_keys & source_feature_keys:
            overlap = ", ".join(repr(key) for key in sorted(controlled_extra_keys & source_feature_keys))
            raise ValueError(f"{profile_id}: controlled extras overlap feature source keys on {overlap}")
        if controlled_extra_keys & source_metadata_keys:
            overlap = ", ".join(repr(key) for key in sorted(controlled_extra_keys & source_metadata_keys))
            raise ValueError(f"{profile_id}: controlled extras overlap metadata source keys on {overlap}")
        if controlled_extra_keys & normalized_metadata_targets:
            overlap = ", ".join(repr(key) for key in sorted(controlled_extra_keys & normalized_metadata_targets))
            raise ValueError(f"{profile_id}: controlled extras overlap fixed adapter metadata keys on {overlap}")

    def accepted_source_keys(self) -> tuple[str, ...]:
        return (
            tuple(self.feature_alias_map)
            + tuple(self.metadata_alias_map)
            + self.controlled_extra_keys
        )

    def known_source_keys(self) -> tuple[str, ...]:
        return self.accepted_source_keys()

    def normalized_metadata_keys(self) -> tuple[str, ...]:
        return tuple(self.metadata_alias_map.values())

    def partition_source_record(
        self,
        record: Mapping[str, Any],
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        tuple[str, ...],
        tuple[str, ...],
    ]:
        feature_values: dict[str, Any] = {}
        metadata: dict[str, Any] = {}
        controlled_extras: dict[str, Any] = {}
        alias_collisions: list[str] = []
        unmapped_fields: list[str] = []

        for raw_key, raw_value in record.items():
            if raw_key in self.feature_alias_map:
                target_key = self.feature_alias_map[raw_key]
                destination = feature_values
            elif raw_key in self.metadata_alias_map:
                target_key = self.metadata_alias_map[raw_key]
                destination = metadata
            elif raw_key in self.controlled_extra_keys:
                target_key = raw_key
                destination = controlled_extras
            else:
                unmapped_fields.append(raw_key)
                continue

            if (
                target_key in feature_values
                or target_key in metadata
                or target_key in controlled_extras
            ):
                alias_collisions.append(target_key)
                continue
            destination[target_key] = raw_value

        return (
            feature_values,
            metadata,
            controlled_extras,
            tuple(sorted(set(alias_collisions))),
            tuple(sorted(set(unmapped_fields))),
        )


@dataclass(frozen=True)
class AdaptedFlowRecord:
    profile: str
    record_index: int | None
    features: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)
    controlled_extras: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        record = dict(self.features)
        record["adapter_profile"] = self.profile
        record.update(self.metadata)
        record.update(self.controlled_extras)
        return record

    def to_runtime_record(self) -> dict[str, Any]:
        return self.to_record()


@dataclass(frozen=True)
class AdapterQuarantineRecord:
    profile: str
    reason: str
    source_record: dict[str, Any]
    record_index: int | None = None
    missing_fields: tuple[str, ...] = ()
    non_numeric_fields: tuple[str, ...] = ()
    alias_collisions: tuple[str, ...] = ()
    unmapped_fields: tuple[str, ...] = ()
    blank_source_keys: tuple[str, ...] = ()
    normalized_key_collisions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    controlled_extras: dict[str, Any] = field(default_factory=dict)
    anomaly_type: str = "adapter_schema_validation_failed"

    def to_event(self, *, include_source_record: bool = False) -> dict[str, Any]:
        if include_source_record:
            metadata = {str(key): value for key, value in self.metadata.items()}
            controlled_extras = {
                str(key): value for key, value in self.controlled_extras.items()
            }
            metadata_redacted = False
            controlled_extras_redacted = False
        else:
            metadata, metadata_redacted = _redact_passthrough_mapping(self.metadata)
            controlled_extras, controlled_extras_redacted = _redact_passthrough_mapping(
                self.controlled_extras
            )
        event = {
            "event_type": "adapter_quarantine",
            "anomaly_type": self.anomaly_type,
            "profile": self.profile,
            "reason": self.reason,
            "record_index": self.record_index,
            "missing_fields": list(self.missing_fields),
            "non_numeric_fields": list(self.non_numeric_fields),
            "alias_collisions": list(self.alias_collisions),
            "unmapped_fields": list(self.unmapped_fields),
            "blank_source_keys": list(self.blank_source_keys),
            "normalized_key_collisions": list(self.normalized_key_collisions),
            "source_record": (
                {str(key): value for key, value in self.source_record.items()}
                if include_source_record
                else _redact_source_record(self.source_record)
            ),
            "metadata": metadata,
            "controlled_extras": controlled_extras,
        }
        if not include_source_record:
            event["source_record_redacted"] = True
            event["metadata_redacted"] = metadata_redacted
            event["controlled_extras_redacted"] = controlled_extras_redacted
        return event


class UnknownAdapterProfileError(ValueError):
    def __init__(self, profile_id: str, available_profiles: Sequence[str]) -> None:
        self.profile_id = str(profile_id)
        self.available_profiles = tuple(str(profile) for profile in available_profiles)
        available = ", ".join(self.available_profiles) if self.available_profiles else "<none>"
        super().__init__(
            f"Unknown adapter profile {self.profile_id!r}. Available profiles: {available}"
        )


class FileModePathCollisionError(ValueError):
    """Raised when file-mode CLI paths resolve to the same destination."""


class AdapterProfileRegistry:
    def __init__(
        self,
        profiles: Sequence[AdapterProfileDefinition],
    ) -> None:
        if not profiles:
            raise ValueError("profiles must not be empty")
        profile_map: dict[str, AdapterProfileDefinition] = {}
        for profile in profiles:
            if profile.profile_id in profile_map:
                raise ValueError(f"Duplicate adapter profile {profile.profile_id!r}")
            profile_map[profile.profile_id] = profile
        self._profiles = profile_map

    def available_profile_ids(self) -> tuple[str, ...]:
        return tuple(self._profiles)

    def get(self, profile_id: str) -> AdapterProfileDefinition:
        normalized = str(profile_id).strip()
        try:
            return self._profiles[normalized]
        except KeyError as exc:
            raise UnknownAdapterProfileError(normalized, self.available_profile_ids()) from exc

    def require(self, profile_id: str) -> AdapterProfileDefinition:
        if not str(profile_id).strip():
            raise ValueError("profile_id must be provided explicitly")
        return self.get(str(profile_id).strip())


def _validate_profile_contract_compatibility(
    profile: AdapterProfileDefinition,
    feature_columns: Sequence[str],
) -> None:
    normalized_feature_columns = tuple(str(column) for column in feature_columns)
    contract_feature_set = set(normalized_feature_columns)
    profile_feature_targets = set(profile.feature_alias_map.values())
    missing_targets = tuple(sorted(contract_feature_set - profile_feature_targets))
    unexpected_targets = tuple(sorted(profile_feature_targets - contract_feature_set))
    if missing_targets or unexpected_targets:
        details: list[str] = []
        if missing_targets:
            details.append(
                "missing canonical targets: " + ", ".join(repr(name) for name in missing_targets)
            )
        if unexpected_targets:
            details.append(
                "unknown canonical targets: "
                + ", ".join(repr(name) for name in unexpected_targets)
            )
        raise ValueError(
            f"{profile.profile_id}: profile acceptance does not match the configured "
            f"contract ({'; '.join(details)})"
        )


def _validate_registry_contract_compatibility(
    registry: AdapterProfileRegistry,
    contract: Any,
) -> None:
    for profile_id in registry.available_profile_ids():
        _validate_profile_contract_compatibility(
            registry.get(profile_id),
            contract.feature_columns,
        )


@dataclass(frozen=True)
class BatchAdaptationResult:
    adapted_records: list[AdaptedFlowRecord]
    quarantined_records: list[AdapterQuarantineRecord]


@dataclass(frozen=True)
class JsonlReadResult:
    line_number: int
    raw_line: str
    payload: dict[str, Any] | None
    error_reason: str | None = None
    raw_char_count: int | None = None


@dataclass
class AdapterCliSummary:
    profile: str
    input_mode: str
    total_records: int = 0
    adapted_records: int = 0
    quarantined_records: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "input_mode": self.input_mode,
            "total_records": self.total_records,
            "adapted_records": self.adapted_records,
            "quarantined_records": self.quarantined_records,
        }


class StructuredRecordAdapter:
    def __init__(
        self,
        *,
        contract: Any | None = None,
        profile_registry: AdapterProfileRegistry | None = None,
    ) -> None:
        self._contract = contract
        self._profile_registry = profile_registry
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        if self._contract is None or self._profile_registry is None:
            return
        _validate_registry_contract_compatibility(self._profile_registry, self._contract)

    @property
    def contract(self) -> Any:
        if self._contract is None:
            self._contract = _get_default_adapter_contract()
            self._validate_configuration()
        return self._contract

    @property
    def profile_registry(self) -> AdapterProfileRegistry:
        if self._profile_registry is None:
            if tuple(self.contract.feature_columns) != _get_default_adapter_feature_columns():
                raise ValueError(
                    "Custom contracts require an explicit profile_registry; shipped adapter "
                    "profile IDs stay fixed to the default contract surface."
                )
            self._profile_registry = _get_default_adapter_profile_registry()
            self._validate_configuration()
        return self._profile_registry

    def adapt_record(
        self,
        record: Mapping[str, Any],
        *,
        profile_id: str,
        record_index: int | None = None,
    ) -> AdaptedFlowRecord | AdapterQuarantineRecord:
        profile = self.profile_registry.require(profile_id)
        raw_source_record = _stringify_source_record(record)
        source_record, blank_source_keys, normalized_key_collisions = _normalize_source_record(
            raw_source_record
        )
        if blank_source_keys:
            return AdapterQuarantineRecord(
                profile=profile.profile_id,
                reason="blank_source_keys",
                source_record=raw_source_record,
                record_index=record_index,
                blank_source_keys=blank_source_keys,
            )
        if normalized_key_collisions:
            return AdapterQuarantineRecord(
                profile=profile.profile_id,
                reason="normalized_key_collision",
                source_record=raw_source_record,
                record_index=record_index,
                normalized_key_collisions=normalized_key_collisions,
            )
        (
            feature_values,
            metadata,
            controlled_extras,
            alias_collisions,
            unmapped_fields,
        ) = profile.partition_source_record(
            source_record,
        )

        if alias_collisions:
            return AdapterQuarantineRecord(
                profile=profile.profile_id,
                reason="alias_collision",
                source_record=source_record,
                record_index=record_index,
                alias_collisions=alias_collisions,
                metadata=metadata,
                controlled_extras=controlled_extras,
            )

        if unmapped_fields:
            return AdapterQuarantineRecord(
                profile=profile.profile_id,
                reason="unmapped_source_fields",
                source_record=source_record,
                record_index=record_index,
                unmapped_fields=unmapped_fields,
                metadata=metadata,
                controlled_extras=controlled_extras,
            )

        adapter_input = dict(feature_values)
        adapter_input["adapter_profile"] = profile.profile_id
        adapter_input.update(metadata)
        adapter_input.update(controlled_extras)
        validation = self.contract.validate_record(adapter_input, record_index=record_index)
        if _is_quarantined_flow_record(validation):
            return AdapterQuarantineRecord(
                profile=profile.profile_id,
                reason=validation.reason,
                source_record=source_record,
                record_index=record_index,
                missing_fields=validation.missing_features,
                non_numeric_fields=validation.non_numeric_features,
                alias_collisions=validation.alias_collisions,
                metadata=metadata,
                controlled_extras=controlled_extras,
            )

        return AdaptedFlowRecord(
            profile=profile.profile_id,
            record_index=record_index,
            features=validation.aligned_features,
            metadata=metadata,
            controlled_extras=controlled_extras,
        )

    def adapt_records(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        profile_id: str,
    ) -> BatchAdaptationResult:
        adapted_records: list[AdaptedFlowRecord] = []
        quarantined_records: list[AdapterQuarantineRecord] = []
        for record_index, record in enumerate(records):
            result = self.adapt_record(
                record,
                profile_id=profile_id,
                record_index=record_index,
            )
            if isinstance(result, AdaptedFlowRecord):
                adapted_records.append(result)
            else:
                quarantined_records.append(result)
        return BatchAdaptationResult(
            adapted_records=adapted_records,
            quarantined_records=quarantined_records,
        )


def _read_jsonl_payloads(stream: TextIO) -> Iterable[JsonlReadResult]:
    line_number = 0
    max_read_size = MAX_JSONL_LINE_LENGTH + 1

    while True:
        raw_line = stream.readline(max_read_size)
        if raw_line == "":
            break
        line_number += 1
        if len(raw_line) > MAX_JSONL_LINE_LENGTH and not raw_line.endswith("\n"):
            raw_char_count = len(raw_line)
            while raw_line and not raw_line.endswith("\n"):
                raw_line = stream.readline(max_read_size)
                raw_char_count += len(raw_line)
            yield JsonlReadResult(
                line_number=line_number,
                raw_line="",
                payload=None,
                error_reason="jsonl_line_too_large",
                raw_char_count=raw_char_count,
            )
            continue

        line = raw_line.rstrip("\n")
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            yield JsonlReadResult(
                line_number=line_number,
                raw_line=line,
                payload=None,
                error_reason="invalid_json",
            )
            continue
        if not isinstance(payload, dict):
            yield JsonlReadResult(
                line_number=line_number,
                raw_line=line,
                payload=None,
                error_reason="invalid_record_type",
            )
            continue
        yield JsonlReadResult(
            line_number=line_number,
            raw_line=line,
            payload=payload,
        )


def _write_jsonl_record(handle: TextIO, record: Mapping[str, Any]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False))
    handle.write("\n")


def _redact_source_record(source_record: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {
        "redacted": True,
        "field_count": len(source_record),
    }
    if "raw_line" in source_record:
        redacted["raw_char_count"] = len(str(source_record["raw_line"]))
    if "raw_char_count" in source_record:
        redacted["raw_char_count"] = int(source_record["raw_char_count"])
    if "raw_record" in source_record:
        redacted["raw_char_count"] = len(str(source_record["raw_record"]))
    return redacted


def _redact_passthrough_mapping(values: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    if not values:
        return {}, False
    return (
        {
            "redacted": True,
            "field_count": len(values),
        },
        True,
    )


def _validate_output_path_collisions(
    *,
    input_path: Path | None,
    output_path: Path | None,
    quarantine_output_path: Path | None,
) -> None:
    collisions: list[str] = []
    if input_path is not None and output_path == input_path:
        collisions.append(
            f"--output-path resolves to the same file as --input-path ({output_path})"
        )
    if input_path is not None and quarantine_output_path == input_path:
        collisions.append(
            "--quarantine-output-path resolves to the same file as "
            f"--input-path ({quarantine_output_path})"
        )
    if (
        output_path is not None
        and quarantine_output_path is not None
        and output_path == quarantine_output_path
    ):
        collisions.append(
            "--output-path resolves to the same file as "
            f"--quarantine-output-path ({output_path})"
        )
    if collisions:
        raise FileModePathCollisionError(
            "File-mode paths must be distinct. " + "; ".join(collisions)
        )


def _resolve_adapter_output_paths(
    *,
    input_path: Path | None,
    output_path: Path | None,
    quarantine_output_path: Path | None,
) -> tuple[Path | None, Path | None]:
    resolved_input = input_path.resolve() if input_path is not None else None
    resolved_output = output_path.resolve() if output_path is not None else None
    resolved_quarantine = (
        quarantine_output_path.resolve() if quarantine_output_path is not None else None
    )
    if resolved_input is not None:
        resolved_output = resolved_output or resolved_input.with_name(
            f"{resolved_input.stem}_adapted.jsonl"
        )
        resolved_quarantine = resolved_quarantine or resolved_input.with_name(
            f"{resolved_input.stem}_adapter_quarantine.jsonl"
        )
    _validate_output_path_collisions(
        input_path=resolved_input,
        output_path=resolved_output,
        quarantine_output_path=resolved_quarantine,
    )
    return resolved_output, resolved_quarantine


def _open_redirected_stdin_sink_handles(
    *,
    output_path: Path | None,
    quarantine_output_path: Path | None,
) -> tuple[TextIO, TextIO, ExitStack]:
    adapted_output: TextIO = sys.stdout
    quarantine_output: TextIO = sys.stderr
    created_paths: list[Path] = []
    stack = ExitStack()
    try:
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_existed = output_path.exists()
            adapted_output = stack.enter_context(
                output_path.open("a+", encoding="utf-8", newline="\n")
            )
            if not output_existed:
                created_paths.append(output_path)
        if quarantine_output_path is not None:
            quarantine_output_path.parent.mkdir(parents=True, exist_ok=True)
            quarantine_existed = quarantine_output_path.exists()
            quarantine_output = stack.enter_context(
                quarantine_output_path.open("a+", encoding="utf-8", newline="\n")
            )
            if not quarantine_existed:
                created_paths.append(quarantine_output_path)

        for handle in (adapted_output, quarantine_output):
            if handle in (sys.stdout, sys.stderr):
                continue
            handle.seek(0)
            handle.truncate(0)

        return adapted_output, quarantine_output, stack
    except Exception:
        stack.close()
        for path in created_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
        raise


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize CICFlowMeter-like structured records into runtime-ready JSONL."
        )
    )
    parser.add_argument(
        "--profile",
        required=True,
        choices=list_adapter_profile_ids(),
        help="Explicit adapter profile to use.",
    )
    parser.add_argument("--input-path", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--quarantine-output-path", type=Path, default=None)
    parser.add_argument(
        "--include-raw-quarantine-source",
        action="store_true",
        help="Emit full source_record payloads in CLI quarantine output.",
    )
    return parser


def run_adapter_cli(
    *,
    profile_id: str,
    input_stream: TextIO,
    adapted_output: TextIO,
    quarantine_output: TextIO,
    adapter: StructuredRecordAdapter | None = None,
    include_raw_quarantine_source: bool = False,
) -> AdapterCliSummary:
    selected_adapter = adapter or DEFAULT_STRUCTURED_RECORD_ADAPTER
    summary = AdapterCliSummary(profile=profile_id, input_mode="stdin")
    for read_result in _read_jsonl_payloads(input_stream):
        summary.total_records += 1
        if read_result.error_reason is not None:
            source_record: dict[str, Any] = {"raw_line": read_result.raw_line}
            if read_result.raw_char_count is not None:
                source_record["raw_char_count"] = read_result.raw_char_count
            quarantine = AdapterQuarantineRecord(
                profile=profile_id,
                reason=read_result.error_reason,
                source_record=source_record,
                record_index=read_result.line_number - 1,
            )
            _write_jsonl_record(
                quarantine_output,
                quarantine.to_event(
                    include_source_record=include_raw_quarantine_source,
                ),
            )
            summary.quarantined_records += 1
            continue
        assert read_result.payload is not None

        result = selected_adapter.adapt_record(
            read_result.payload,
            profile_id=profile_id,
            record_index=read_result.line_number - 1,
        )
        if isinstance(result, AdaptedFlowRecord):
            _write_jsonl_record(adapted_output, result.to_record())
            summary.adapted_records += 1
        else:
            _write_jsonl_record(
                quarantine_output,
                result.to_event(include_source_record=include_raw_quarantine_source),
            )
            summary.quarantined_records += 1
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    _ensure_cli_repo_bootstrap()
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    input_mode = "file" if args.input_path is not None else "stdin"
    summary: AdapterCliSummary

    if args.input_path is not None:
        try:
            output_path, quarantine_output_path = _resolve_adapter_output_paths(
                input_path=args.input_path,
                output_path=args.output_path,
                quarantine_output_path=args.quarantine_output_path,
            )
        except FileModePathCollisionError as exc:
            parser.error(str(exc))
        assert output_path is not None
        assert quarantine_output_path is not None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        quarantine_output_path.parent.mkdir(parents=True, exist_ok=True)
        with ExitStack() as stack:
            input_handle = stack.enter_context(args.input_path.open("r", encoding="utf-8"))
            adapted_handle = stack.enter_context(
                output_path.open("w", encoding="utf-8", newline="\n")
            )
            quarantine_handle = stack.enter_context(
                quarantine_output_path.open("w", encoding="utf-8", newline="\n")
            )
            summary = run_adapter_cli(
                profile_id=args.profile,
                input_stream=input_handle,
                adapted_output=adapted_handle,
                quarantine_output=quarantine_handle,
                include_raw_quarantine_source=args.include_raw_quarantine_source,
            )
            summary.input_mode = input_mode
    else:
        try:
            resolved_output_path, resolved_quarantine_output_path = _resolve_adapter_output_paths(
                input_path=None,
                output_path=args.output_path,
                quarantine_output_path=args.quarantine_output_path,
            )
        except FileModePathCollisionError as exc:
            parser.error(str(exc))
        with ExitStack() as stack:
            adapted_output, quarantine_output, redirected_stack = _open_redirected_stdin_sink_handles(
                output_path=resolved_output_path,
                quarantine_output_path=resolved_quarantine_output_path,
            )
            stack.enter_context(redirected_stack)
            summary = run_adapter_cli(
                profile_id=args.profile,
                input_stream=sys.stdin,
                adapted_output=adapted_output,
                quarantine_output=quarantine_output,
                include_raw_quarantine_source=args.include_raw_quarantine_source,
            )
            summary.input_mode = input_mode

    _ = summary
    return 0


def build_default_adapter_registry() -> AdapterProfileRegistry:
    primary_profile = AdapterProfileDefinition(
        profile_id=PRIMARY_PROFILE_ID,
        feature_alias_map=_build_closed_feature_alias_map(
            PRIMARY_PROFILE_FEATURE_ALIAS_OVERRIDES,
        ),
        metadata_alias_map=PRIMARY_PROFILE_METADATA_ALIASES,
        controlled_extra_keys=PRIMARY_PROFILE_CONTROLLED_EXTRA_KEYS,
        description="Primary CICFlowMeter-like profile with flow_id/collector_id metadata.",
    )
    secondary_profile = AdapterProfileDefinition(
        profile_id=SECONDARY_PROFILE_ID,
        feature_alias_map=_build_closed_feature_alias_map(
            SECONDARY_PROFILE_FEATURE_ALIAS_OVERRIDES,
        ),
        metadata_alias_map=SECONDARY_PROFILE_METADATA_ALIASES,
        controlled_extra_keys=SECONDARY_PROFILE_CONTROLLED_EXTRA_KEYS,
        description="Secondary CICFlowMeter-like profile with trace_id/sensor_id metadata.",
    )
    return AdapterProfileRegistry([primary_profile, secondary_profile])


DEFAULT_ADAPTER_PROFILE_REGISTRY = _DefaultAdapterProfileRegistryProxy()
DEFAULT_STRUCTURED_RECORD_ADAPTER = StructuredRecordAdapter()


def get_adapter_profile(profile_id: str) -> AdapterProfileDefinition:
    return DEFAULT_ADAPTER_PROFILE_REGISTRY.require(profile_id)


def list_adapter_profile_ids() -> tuple[str, ...]:
    return DEFAULT_ADAPTER_PROFILE_REGISTRY.available_profile_ids()


def adapt_record(
    record: Mapping[str, Any],
    *,
    profile_id: str,
    record_index: int | None = None,
    adapter: StructuredRecordAdapter | None = None,
) -> AdaptedFlowRecord | AdapterQuarantineRecord:
    selected_adapter = adapter or DEFAULT_STRUCTURED_RECORD_ADAPTER
    return selected_adapter.adapt_record(
        record,
        profile_id=profile_id,
        record_index=record_index,
    )


def adapt_records(
    records: Iterable[Mapping[str, Any]],
    *,
    profile_id: str,
    adapter: StructuredRecordAdapter | None = None,
) -> BatchAdaptationResult:
    selected_adapter = adapter or DEFAULT_STRUCTURED_RECORD_ADAPTER
    return selected_adapter.adapt_records(records, profile_id=profile_id)


if __name__ == "__main__":
    raise SystemExit(main())
