from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


# Explicit one-to-one field-name normalization only. Missing canonical features
# still remain invalid after aliasing and are quarantined instead of inferred.
DEFAULT_ALIAS_MAP: dict[str, str] = {
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_feature_columns(path: Path) -> list[str]:
    payload = read_json(path)
    columns = payload.get("feature_columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError(f"Invalid feature_columns payload in {path}")
    normalized = [str(column) for column in columns]
    if any(not column.strip() for column in normalized):
        raise ValueError(f"Blank feature column name found in {path}")
    return normalized


def coerce_numeric_feature(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid numeric features")
    if value is None:
        raise ValueError("missing values are not valid numeric features")
    if isinstance(value, str) and not value.strip():
        raise ValueError("blank strings are not valid numeric features")
    try:
        coerced = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unable to coerce value {value!r} to float") from exc
    if not math.isfinite(coerced):
        raise ValueError(f"non-finite value {value!r} is not valid")
    return coerced


@dataclass(frozen=True)
class ValidatedFlowRecord:
    aligned_features: dict[str, float]
    passthrough: dict[str, Any]
    source_record: dict[str, Any]


@dataclass(frozen=True)
class QuarantinedFlowRecord:
    source_record: dict[str, Any]
    passthrough: dict[str, Any]
    reason: str
    missing_features: tuple[str, ...] = ()
    non_numeric_features: tuple[str, ...] = ()
    alias_collisions: tuple[str, ...] = ()
    anomaly_type: str = "schema_validation_failed"
    record_index: int | None = None

    def to_alert(self) -> dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type,
            "reason": self.reason,
            "record_index": self.record_index,
            "missing_features": list(self.missing_features),
            "non_numeric_features": list(self.non_numeric_features),
            "alias_collisions": list(self.alias_collisions),
            "passthrough": self.passthrough,
        }


@dataclass(frozen=True)
class BatchValidationResult:
    valid_records: list[ValidatedFlowRecord]
    quarantined_records: list[QuarantinedFlowRecord]


class FlowFeatureContract:
    def __init__(
        self,
        feature_columns: Iterable[str],
        alias_map: Mapping[str, str] | None = None,
    ) -> None:
        columns = [str(column) for column in feature_columns]
        if not columns:
            raise ValueError("feature_columns must not be empty")
        self.feature_columns = columns
        self.feature_column_set = set(columns)
        self.alias_map = dict(alias_map or DEFAULT_ALIAS_MAP)
        self._validate_alias_map()

    @classmethod
    def from_feature_file(
        cls,
        path: Path,
        alias_map: Mapping[str, str] | None = None,
    ) -> "FlowFeatureContract":
        return cls(load_feature_columns(path), alias_map=alias_map)

    def _validate_alias_map(self) -> None:
        for alias, canonical in self.alias_map.items():
            if alias == canonical:
                raise ValueError(f"Alias {alias!r} must not point to itself")
            if canonical not in self.feature_column_set:
                raise ValueError(
                    f"Alias {alias!r} points to unknown canonical feature {canonical!r}"
                )

    def _extract_passthrough(self, record: Mapping[str, Any]) -> dict[str, Any]:
        passthrough: dict[str, Any] = {}
        for key, value in record.items():
            canonical_name = self.alias_map.get(key, key)
            if canonical_name not in self.feature_column_set:
                passthrough[str(key)] = value
        return passthrough

    def _normalize_record(
        self, record: Mapping[str, Any]
    ) -> tuple[dict[str, Any], tuple[str, ...]]:
        normalized: dict[str, Any] = {}
        collisions: list[str] = []
        for raw_key, value in record.items():
            key = str(raw_key)
            canonical_key = self.alias_map.get(key, key)
            if canonical_key in normalized:
                collisions.append(canonical_key)
                continue
            normalized[canonical_key] = value
        return normalized, tuple(sorted(set(collisions)))

    def validate_record(
        self,
        record: Mapping[str, Any],
        record_index: int | None = None,
    ) -> ValidatedFlowRecord | QuarantinedFlowRecord:
        source_record = {str(key): value for key, value in record.items()}
        passthrough = self._extract_passthrough(source_record)
        normalized_record, alias_collisions = self._normalize_record(source_record)
        if alias_collisions:
            return QuarantinedFlowRecord(
                source_record=source_record,
                passthrough=passthrough,
                reason="alias_collision",
                alias_collisions=alias_collisions,
                record_index=record_index,
            )

        missing_features = tuple(
            column for column in self.feature_columns if column not in normalized_record
        )
        if missing_features:
            return QuarantinedFlowRecord(
                source_record=source_record,
                passthrough=passthrough,
                reason="missing_required_features",
                missing_features=missing_features,
                record_index=record_index,
            )

        aligned_features: dict[str, float] = {}
        non_numeric_features: list[str] = []
        for column in self.feature_columns:
            try:
                aligned_features[column] = coerce_numeric_feature(normalized_record[column])
            except ValueError:
                non_numeric_features.append(column)
        if non_numeric_features:
            return QuarantinedFlowRecord(
                source_record=source_record,
                passthrough=passthrough,
                reason="non_numeric_required_features",
                non_numeric_features=tuple(non_numeric_features),
                record_index=record_index,
            )

        return ValidatedFlowRecord(
            aligned_features=aligned_features,
            passthrough=passthrough,
            source_record=source_record,
        )

    def split_records(self, records: Iterable[Mapping[str, Any]]) -> BatchValidationResult:
        valid_records: list[ValidatedFlowRecord] = []
        quarantined_records: list[QuarantinedFlowRecord] = []
        for record_index, record in enumerate(records):
            result = self.validate_record(record, record_index=record_index)
            if isinstance(result, ValidatedFlowRecord):
                valid_records.append(result)
            else:
                quarantined_records.append(result)
        return BatchValidationResult(
            valid_records=valid_records,
            quarantined_records=quarantined_records,
        )
