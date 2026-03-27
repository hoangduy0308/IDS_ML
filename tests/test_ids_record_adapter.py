from __future__ import annotations

import inspect
import io
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_feature_contract import DEFAULT_FEATURE_COLUMNS_PATH, FlowFeatureContract, load_feature_columns  # noqa: E402
from scripts.ids_record_adapter import (  # noqa: E402
    ADAPTER_FIXED_METADATA_KEYS,
    MAX_JSONL_LINE_LENGTH,
    PRIMARY_PROFILE_ID,
    PRIMARY_PROFILE_METADATA_ALIASES,
    SECONDARY_PROFILE_ID,
    SECONDARY_PROFILE_METADATA_ALIASES,
    AdaptedFlowRecord,
    AdapterProfileDefinition,
    BatchAdaptationResult,
    AdapterQuarantineRecord,
    DEFAULT_ADAPTER_PROFILE_REGISTRY,
    DEFAULT_STRUCTURED_RECORD_ADAPTER,
    StructuredRecordAdapter,
    UnknownAdapterProfileError,
    _read_jsonl_payloads,
    adapt_record as module_adapt_record,
    adapt_records as module_adapt_records,
    build_default_adapter_registry,
    get_adapter_profile,
    list_adapter_profile_ids,
)
from scripts.ids_realtime_pipeline import RealtimePipelineRunner, run_pipeline_stream  # noqa: E402


FEATURE_COLUMNS = load_feature_columns(DEFAULT_FEATURE_COLUMNS_PATH)


class DummyInferencer:
    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def predict(self, frame: pd.DataFrame, include_input: bool = True) -> pd.DataFrame:
        scores = frame["Flow Duration"].astype(float) / 100.0
        alerts = scores >= self.threshold
        labels = ["Attack" if is_alert else "Benign" for is_alert in alerts]
        return pd.DataFrame(
            {
                "attack_score": scores,
                "predicted_label": labels,
                "is_alert": alerts,
                "threshold": self.threshold,
            }
        )


def make_profile_record(
    profile_id: str,
    *,
    flow_duration: float = 80.0,
    extra_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    profile = get_adapter_profile(profile_id)
    record = {column: float(index + 1) for index, column in enumerate(FEATURE_COLUMNS)}
    record["Flow Duration"] = float(flow_duration)
    for source_key, canonical_key in profile.feature_alias_map.items():
        record[source_key] = record.pop(canonical_key)
    for source_key, target_key in profile.metadata_alias_map.items():
        record[source_key] = f"{target_key}-value"
    for key in profile.controlled_extra_keys:
        record[key] = f"{key}-value"
    if extra_fields:
        record.update(extra_fields)
    return record


def load_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def adapter_script_path() -> Path:
    return REPO_ROOT / "scripts" / "ids_record_adapter.py"


PRIMARY_FIXTURE_PATH = REPO_ROOT / "artifacts" / "demo" / "ids_record_adapter_primary_sample.jsonl"
SECONDARY_FIXTURE_PATH = REPO_ROOT / "artifacts" / "demo" / "ids_record_adapter_secondary_sample.jsonl"

PRIMARY_PROFILE_MAPPING_ORACLE = {
    "SrcPort": ("Src Port", 1.0),
    "DstPort": ("Dst Port", 2.0),
    "FlowDuration": ("Flow Duration", 80.0),
    "Tot Fwd Pkts": ("Total Fwd Packet", 5.0),
    "Tot Bwd Pkts": ("Total Bwd packets", 6.0),
    "TotLen Fwd Pkts": ("Total Length of Fwd Packet", 7.0),
    "TotLen Bwd Pkts": ("Total Length of Bwd Packet", 8.0),
    "Pkt Len Min": ("Packet Length Min", 38.0),
    "Pkt Len Max": ("Packet Length Max", 39.0),
    "Pkt Len Mean": ("Packet Length Mean", 40.0),
    "Pkt Len Std": ("Packet Length Std", 41.0),
    "Pkt Len Var": ("Packet Length Variance", 42.0),
    "Init Fwd Win Byts": ("FWD Init Win Bytes", 61.0),
    "Init Bwd Win Byts": ("Bwd Init Win Bytes", 62.0),
}
SECONDARY_PROFILE_MAPPING_ORACLE = {
    "SourcePort": ("Src Port", 1.0),
    "DestinationPort": ("Dst Port", 2.0),
    "Duration": ("Flow Duration", 91.0),
    "TotalFwdPackets": ("Total Fwd Packet", 5.0),
    "TotalBwdPackets": ("Total Bwd packets", 6.0),
    "FwdPktsLenTotal": ("Total Length of Fwd Packet", 7.0),
    "BwdPktsLenTotal": ("Total Length of Bwd Packet", 8.0),
    "PacketLenMin": ("Packet Length Min", 38.0),
    "PacketLenMax": ("Packet Length Max", 39.0),
    "PacketLenMean": ("Packet Length Mean", 40.0),
    "PacketLenStd": ("Packet Length Std", 41.0),
    "PacketLenVar": ("Packet Length Variance", 42.0),
    "InitFwdWinBytes": ("FWD Init Win Bytes", 61.0),
    "InitBwdWinBytes": ("Bwd Init Win Bytes", 62.0),
}
PRIMARY_PROFILE_FIXTURE_RECORD = load_jsonl(PRIMARY_FIXTURE_PATH)[0]
SECONDARY_PROFILE_FIXTURE_RECORD = load_jsonl(SECONDARY_FIXTURE_PATH)[0]


def test_default_registry_exposes_two_explicit_profiles() -> None:
    registry = build_default_adapter_registry()

    assert registry.available_profile_ids() == (
        PRIMARY_PROFILE_ID,
        SECONDARY_PROFILE_ID,
    )
    assert list_adapter_profile_ids() == (
        PRIMARY_PROFILE_ID,
        SECONDARY_PROFILE_ID,
    )
    assert DEFAULT_ADAPTER_PROFILE_REGISTRY.available_profile_ids() == (
        PRIMARY_PROFILE_ID,
        SECONDARY_PROFILE_ID,
    )
    primary_profile = registry.get(PRIMARY_PROFILE_ID)
    secondary_profile = registry.get(SECONDARY_PROFILE_ID)
    assert set(primary_profile.accepted_source_keys()) == (
        set(primary_profile.feature_alias_map)
        | set(primary_profile.metadata_alias_map)
        | set(primary_profile.controlled_extra_keys)
    )
    assert set(secondary_profile.accepted_source_keys()) == (
        set(secondary_profile.feature_alias_map)
        | set(secondary_profile.metadata_alias_map)
        | set(secondary_profile.controlled_extra_keys)
    )


def test_adapter_rejects_registry_contract_mismatches_eagerly() -> None:
    mismatched_registry = build_default_adapter_registry(
        feature_columns=("Src Port", "Dst Port")
    )

    with pytest.raises(
        ValueError,
        match="profile acceptance does not match the configured contract",
    ):
        StructuredRecordAdapter(
            contract=FlowFeatureContract(FEATURE_COLUMNS, alias_map={}),
            profile_registry=mismatched_registry,
        )


@pytest.mark.parametrize(
    "profile_id, fixture_record, mapping_oracle, expected_metadata_alias_map",
    [
        (
            PRIMARY_PROFILE_ID,
            PRIMARY_PROFILE_FIXTURE_RECORD,
            PRIMARY_PROFILE_MAPPING_ORACLE,
            PRIMARY_PROFILE_METADATA_ALIASES,
        ),
        (
            SECONDARY_PROFILE_ID,
            SECONDARY_PROFILE_FIXTURE_RECORD,
            SECONDARY_PROFILE_MAPPING_ORACLE,
            SECONDARY_PROFILE_METADATA_ALIASES,
        ),
    ],
)
def test_shipped_profiles_follow_fixture_backed_mapping_oracles(
    profile_id: str,
    fixture_record: dict[str, object],
    mapping_oracle: dict[str, tuple[str, float]],
    expected_metadata_alias_map: dict[str, str],
) -> None:
    adapted = DEFAULT_STRUCTURED_RECORD_ADAPTER.adapt_record(
        fixture_record,
        profile_id=profile_id,
        record_index=0,
    )

    assert isinstance(adapted, AdaptedFlowRecord)
    assert adapted.profile == profile_id
    assert len(adapted.features) == 72
    for source_key, (canonical_key, expected_value) in mapping_oracle.items():
        assert fixture_record[source_key] == expected_value
        assert adapted.features[canonical_key] == expected_value
    for source_key, target_key in expected_metadata_alias_map.items():
        assert adapted.metadata[target_key] == fixture_record[source_key]
    assert set(adapted.metadata) == set(ADAPTER_FIXED_METADATA_KEYS[1:])


def test_profile_selection_requires_explicit_profile_and_rejects_unknown_names() -> None:
    assert inspect.signature(get_adapter_profile).parameters["profile_id"].default is inspect.Signature.empty
    assert (
        inspect.signature(StructuredRecordAdapter.adapt_record)
        .parameters["profile_id"]
        .default
        is inspect.Signature.empty
    )
    assert (
        inspect.signature(StructuredRecordAdapter.adapt_records)
        .parameters["profile_id"]
        .default
        is inspect.Signature.empty
    )
    assert inspect.signature(module_adapt_record).parameters["profile_id"].default is inspect.Signature.empty
    assert inspect.signature(module_adapt_records).parameters["profile_id"].default is inspect.Signature.empty

    with pytest.raises(ValueError, match="provided explicitly"):
        get_adapter_profile("  ")

    with pytest.raises(UnknownAdapterProfileError) as excinfo:
        get_adapter_profile("does-not-exist")

    message = str(excinfo.value)
    assert "does-not-exist" in message
    assert PRIMARY_PROFILE_ID in message
    assert SECONDARY_PROFILE_ID in message


def test_public_adaptation_entry_points_require_explicit_profile_id() -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(PRIMARY_PROFILE_ID)

    with pytest.raises(TypeError):
        adapter.adapt_record(source_record)  # type: ignore[call-arg]

    with pytest.raises(ValueError, match="provided explicitly"):
        adapter.adapt_record(source_record, profile_id="  ")

    with pytest.raises(TypeError):
        module_adapt_record(source_record)  # type: ignore[call-arg]

    with pytest.raises(ValueError, match="provided explicitly"):
        module_adapt_records([source_record], profile_id="  ")


def test_adapter_quarantine_records_include_the_required_shared_fields() -> None:
    record = AdapterQuarantineRecord(
        profile=PRIMARY_PROFILE_ID,
        reason="missing_required_features",
        record_index=7,
        source_record={"SrcPort": "1234", "DstPort": "80"},
        missing_fields=("Flow Duration",),
        metadata={"source_flow_id": "flow-17"},
        controlled_extras={"capture_mode": "batch"},
    )

    event = record.to_event()

    assert event["event_type"] == "adapter_quarantine"
    assert event["anomaly_type"] == "adapter_schema_validation_failed"
    assert event["profile"] == PRIMARY_PROFILE_ID
    assert event["reason"] == "missing_required_features"
    assert event["record_index"] == 7
    assert event["source_record"] == {"redacted": True, "field_count": 2}
    assert event["source_record_redacted"] is True
    assert event["missing_fields"] == ["Flow Duration"]
    assert event["metadata"] == {"redacted": True, "field_count": 1}
    assert event["metadata_redacted"] is True
    assert event["controlled_extras"] == {"redacted": True, "field_count": 1}
    assert event["controlled_extras_redacted"] is True


def test_adapter_quarantine_records_can_opt_in_to_raw_library_output() -> None:
    record = AdapterQuarantineRecord(
        profile=PRIMARY_PROFILE_ID,
        reason="missing_required_features",
        record_index=7,
        source_record={"SrcPort": "1234", "DstPort": "80"},
        metadata={"source_flow_id": "flow-17"},
        controlled_extras={"capture_mode": "batch"},
    )

    event = record.to_event(include_source_record=True)

    assert event["source_record"] == {"SrcPort": "1234", "DstPort": "80"}
    assert event["metadata"] == {"source_flow_id": "flow-17"}
    assert event["controlled_extras"] == {"capture_mode": "batch"}
    assert "source_record_redacted" not in event


def test_adapter_quarantine_empty_passthrough_mappings_do_not_claim_redaction() -> None:
    record = AdapterQuarantineRecord(
        profile=PRIMARY_PROFILE_ID,
        reason="missing_required_features",
        record_index=7,
        source_record={"SrcPort": "1234"},
    )

    event = record.to_event()

    assert event["metadata"] == {}
    assert event["metadata_redacted"] is False
    assert event["controlled_extras"] == {}
    assert event["controlled_extras_redacted"] is False


def test_adapter_profile_definition_rejects_overlapping_output_targets() -> None:
    with pytest.raises(ValueError, match="overlap"):
        AdapterProfileDefinition(
            profile_id="bad-profile",
            feature_alias_map={"SrcPort": "Src Port"},
            metadata_alias_map={"flow_id": "Src Port"},
        )


def test_adapter_profile_definition_rejects_adapter_profile_as_upstream_metadata_target() -> None:
    with pytest.raises(ValueError, match="adapter_profile"):
        AdapterProfileDefinition(
            profile_id="bad-profile",
            feature_alias_map={"SrcPort": "Src Port"},
            metadata_alias_map={"flow_id": "adapter_profile"},
        )


def test_adapted_flow_record_carries_model_fields_and_controlled_metadata() -> None:
    adapted = AdaptedFlowRecord(
        profile=PRIMARY_PROFILE_ID,
        record_index=3,
        features={"Src Port": 1234.0, "Dst Port": 80.0},
        metadata={"source_flow_id": "flow-9"},
        controlled_extras={"capture_mode": "stream"},
    )

    assert adapted.profile == PRIMARY_PROFILE_ID
    assert adapted.record_index == 3
    assert adapted.features == {"Src Port": 1234.0, "Dst Port": 80.0}
    assert adapted.metadata == {"source_flow_id": "flow-9"}
    assert adapted.controlled_extras == {"capture_mode": "stream"}
    assert adapted.to_record() == {
        "Src Port": 1234.0,
        "Dst Port": 80.0,
        "adapter_profile": PRIMARY_PROFILE_ID,
        "source_flow_id": "flow-9",
        "capture_mode": "stream",
    }


def test_primary_profile_adapts_to_runtime_ready_flat_record() -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(
        PRIMARY_PROFILE_ID,
        flow_duration=80.0,
        extra_fields={"notes": "should-quarantine-if-unmapped"},
    )
    source_record.pop("notes")

    adapted = adapter.adapt_record(
        source_record,
        profile_id=PRIMARY_PROFILE_ID,
        record_index=0,
    )

    assert isinstance(adapted, AdaptedFlowRecord)
    assert len(adapted.features) == 72
    assert adapted.metadata == {
        "source_flow_id": "source_flow_id-value",
        "source_collector_id": "source_collector_id-value",
        "source_timestamp": "source_timestamp-value",
    }
    assert adapted.controlled_extras == {
        "flow_family": "flow_family-value",
        "transport_family": "transport_family-value",
        "capture_mode": "capture_mode-value",
    }

    runtime_record = adapted.to_record()
    assert runtime_record["adapter_profile"] == PRIMARY_PROFILE_ID
    assert runtime_record["Flow Duration"] == 80.0
    assert runtime_record["Src Port"] == 1.0
    assert runtime_record["Dst Port"] == 2.0

    runtime = RealtimePipelineRunner(
        contract=FlowFeatureContract.from_feature_file(
            DEFAULT_FEATURE_COLUMNS_PATH,
            alias_map={},
        ),
        inferencer=DummyInferencer(),
        max_batch_size=4,
        flush_interval_seconds=60.0,
    )
    alerts, quarantines, flushed = runtime.ingest_record(runtime_record, record_index=0)
    assert alerts == []
    assert quarantines == []
    assert flushed is False

    final_alerts, final_flushed = runtime.finalize()
    assert final_flushed is True
    assert len(final_alerts) == 1
    assert final_alerts[0]["passthrough"]["adapter_profile"] == PRIMARY_PROFILE_ID
    assert final_alerts[0]["passthrough"]["source_flow_id"] == "source_flow_id-value"


def test_structured_record_adapter_batch_api_buckets_successes_and_quarantines() -> None:
    adapter = StructuredRecordAdapter()
    records = [
        make_profile_record(PRIMARY_PROFILE_ID, flow_duration=80.0),
        make_profile_record(PRIMARY_PROFILE_ID, extra_fields={"unexpected_field": "bad"}),
        make_profile_record(PRIMARY_PROFILE_ID, flow_duration=95.0),
    ]

    result = adapter.adapt_records(records, profile_id=PRIMARY_PROFILE_ID)

    assert isinstance(result, BatchAdaptationResult)
    assert [record.record_index for record in result.adapted_records] == [0, 2]
    assert [record.features["Flow Duration"] for record in result.adapted_records] == [80.0, 95.0]
    assert len(result.quarantined_records) == 1
    assert result.quarantined_records[0].record_index == 1
    assert result.quarantined_records[0].reason == "unmapped_source_fields"
    assert "unexpected_field" in result.quarantined_records[0].unmapped_fields


def test_module_batch_api_buckets_successes_and_quarantines() -> None:
    records = [
        make_profile_record(PRIMARY_PROFILE_ID, flow_duration=70.0),
        make_profile_record(PRIMARY_PROFILE_ID, extra_fields={"unexpected_field": "bad"}),
        make_profile_record(PRIMARY_PROFILE_ID, flow_duration=88.0),
    ]

    result = module_adapt_records(records, profile_id=PRIMARY_PROFILE_ID)

    assert isinstance(result, BatchAdaptationResult)
    assert [record.record_index for record in result.adapted_records] == [0, 2]
    assert [record.features["Flow Duration"] for record in result.adapted_records] == [70.0, 88.0]
    assert len(result.quarantined_records) == 1
    assert result.quarantined_records[0].record_index == 1
    assert result.quarantined_records[0].reason == "unmapped_source_fields"


def test_secondary_profile_adapts_with_lightly_changed_metadata_names() -> None:
    adapter = DEFAULT_STRUCTURED_RECORD_ADAPTER
    adapted = adapter.adapt_record(
        make_profile_record(SECONDARY_PROFILE_ID, flow_duration=90.0),
        profile_id=SECONDARY_PROFILE_ID,
        record_index=12,
    )

    assert isinstance(adapted, AdaptedFlowRecord)
    assert adapted.profile == SECONDARY_PROFILE_ID
    assert adapted.metadata == {
        "source_flow_id": "source_flow_id-value",
        "source_collector_id": "source_collector_id-value",
        "source_timestamp": "source_timestamp-value",
    }
    assert adapted.to_record()["adapter_profile"] == SECONDARY_PROFILE_ID
    assert adapted.features["Flow Duration"] == 90.0


@pytest.mark.parametrize("profile_id", [PRIMARY_PROFILE_ID, SECONDARY_PROFILE_ID])
def test_closed_profiles_reject_canonical_duplicates_of_aliased_fields(profile_id: str) -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(profile_id)
    mapping_oracle = (
        PRIMARY_PROFILE_MAPPING_ORACLE
        if profile_id == PRIMARY_PROFILE_ID
        else SECONDARY_PROFILE_MAPPING_ORACLE
    )
    source_alias, (canonical_key, _) = next(iter(mapping_oracle.items()))
    source_record[canonical_key] = 999.0

    result = adapter.adapt_record(
        source_record,
        profile_id=profile_id,
        record_index=4,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "unmapped_source_fields"
    assert result.unmapped_fields == (canonical_key,)
    assert result.record_index == 4
    assert result.profile == profile_id
    assert result.source_record[source_alias] != result.source_record[canonical_key]


@pytest.mark.parametrize(
    "profile_id, reserved_key",
    [
        (PRIMARY_PROFILE_ID, "adapter_profile"),
        (PRIMARY_PROFILE_ID, "source_flow_id"),
        (SECONDARY_PROFILE_ID, "source_timestamp"),
    ],
)
def test_reserved_adapter_metadata_cannot_be_spoofed_from_source_payload(
    profile_id: str,
    reserved_key: str,
) -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(
        profile_id,
        extra_fields={reserved_key: "spoofed"},
    )

    result = adapter.adapt_record(
        source_record,
        profile_id=profile_id,
        record_index=6,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "unmapped_source_fields"
    assert reserved_key in result.unmapped_fields
    assert result.profile == profile_id
    assert result.metadata["source_flow_id"] == "source_flow_id-value"


def test_custom_profile_can_reject_undeclared_canonical_feature_names() -> None:
    restricted_profile = AdapterProfileDefinition(
        profile_id="restricted",
        feature_alias_map={"FlowDuration": "Flow Duration"},
        metadata_alias_map={},
    )
    registry = build_default_adapter_registry()
    adapter = StructuredRecordAdapter(
        contract=FlowFeatureContract(
            ["Flow Duration"],
            alias_map={"FlowDuration": "Flow Duration"},
        ),
        profile_registry=type(registry)([restricted_profile]),
    )

    result = adapter.adapt_record(
        {"Flow Duration": 80.0},
        profile_id=restricted_profile.profile_id,
        record_index=0,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "unmapped_source_fields"
    assert result.unmapped_fields == ("Flow Duration",)


def test_canonical_only_quarantine_preserves_metadata_and_controlled_extras() -> None:
    adapter = StructuredRecordAdapter()
    source_record = {column: float(index + 1) for index, column in enumerate(FEATURE_COLUMNS)}
    for source_key, target_key in PRIMARY_PROFILE_METADATA_ALIASES.items():
        source_record[source_key] = f"{target_key}-value"
    source_record["capture_mode"] = "capture_mode-value"

    result = adapter.adapt_record(
        source_record,
        profile_id=PRIMARY_PROFILE_ID,
        record_index=17,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "unmapped_source_fields"
    assert "Flow Duration" in result.unmapped_fields
    assert result.metadata == {
        "source_flow_id": "source_flow_id-value",
        "source_collector_id": "source_collector_id-value",
        "source_timestamp": "source_timestamp-value",
    }
    assert result.controlled_extras == {
        "capture_mode": "capture_mode-value",
    }
    event = result.to_event()
    assert event["metadata"] == {"redacted": True, "field_count": 3}
    assert event["metadata_redacted"] is True
    assert event["controlled_extras"] == {"redacted": True, "field_count": 1}
    assert event["controlled_extras_redacted"] is True


@pytest.mark.parametrize("profile_id", [PRIMARY_PROFILE_ID, SECONDARY_PROFILE_ID])
def test_shipped_profiles_reject_canonical_payloads_without_upstream_aliases(
    profile_id: str,
) -> None:
    adapter = StructuredRecordAdapter()
    canonical_record = {column: float(index + 1) for index, column in enumerate(FEATURE_COLUMNS)}

    result = adapter.adapt_record(
        canonical_record,
        profile_id=profile_id,
        record_index=8,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "unmapped_source_fields"
    assert "Flow Duration" in result.unmapped_fields
    assert result.profile == profile_id


@pytest.mark.parametrize(
    "profile_id, metadata_alias_map",
    [
        (PRIMARY_PROFILE_ID, PRIMARY_PROFILE_METADATA_ALIASES),
        (SECONDARY_PROFILE_ID, SECONDARY_PROFILE_METADATA_ALIASES),
    ],
)
def test_shipped_profiles_reject_canonical_features_even_with_profile_metadata(
    profile_id: str,
    metadata_alias_map: dict[str, str],
) -> None:
    adapter = StructuredRecordAdapter()
    source_record = {column: float(index + 1) for index, column in enumerate(FEATURE_COLUMNS)}
    for source_key, target_key in metadata_alias_map.items():
        source_record[source_key] = f"{target_key}-value"

    result = adapter.adapt_record(
        source_record,
        profile_id=profile_id,
        record_index=15,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "unmapped_source_fields"
    assert "Flow Duration" in result.unmapped_fields


@pytest.mark.parametrize(
    "profile_id, mapping_oracle",
    [
        (PRIMARY_PROFILE_ID, PRIMARY_PROFILE_MAPPING_ORACLE),
        (SECONDARY_PROFILE_ID, SECONDARY_PROFILE_MAPPING_ORACLE),
    ],
)
def test_shipped_profiles_reject_mixed_alias_and_canonical_feature_payloads(
    profile_id: str,
    mapping_oracle: dict[str, tuple[str, float]],
) -> None:
    adapter = StructuredRecordAdapter()
    source_record = {column: float(index + 1) for index, column in enumerate(FEATURE_COLUMNS)}
    source_record["Flow Duration"] = 80.0 if profile_id == PRIMARY_PROFILE_ID else 91.0
    source_alias, (canonical_key, expected_value) = next(iter(mapping_oracle.items()))
    source_record.pop(canonical_key)
    source_record[source_alias] = expected_value

    result = adapter.adapt_record(
        source_record,
        profile_id=profile_id,
        record_index=16,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "unmapped_source_fields"
    assert canonical_key not in result.unmapped_fields
    assert "Flow Duration" in result.unmapped_fields


def test_missing_required_feature_becomes_adapter_quarantine() -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(PRIMARY_PROFILE_ID)
    source_record.pop("FlowDuration")

    result = adapter.adapt_record(
        source_record,
        profile_id=PRIMARY_PROFILE_ID,
        record_index=5,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "missing_required_features"
    assert "Flow Duration" in result.missing_fields
    assert result.profile == PRIMARY_PROFILE_ID


def test_non_numeric_required_feature_becomes_adapter_quarantine() -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(PRIMARY_PROFILE_ID)
    source_record["FlowDuration"] = "bad"

    result = adapter.adapt_record(
        source_record,
        profile_id=PRIMARY_PROFILE_ID,
        record_index=9,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "non_numeric_required_features"
    assert "Flow Duration" in result.non_numeric_fields
    assert result.profile == PRIMARY_PROFILE_ID


def test_unmapped_source_fields_become_adapter_quarantine() -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(PRIMARY_PROFILE_ID)
    source_record["unexpected_field"] = "value"

    result = adapter.adapt_record(
        source_record,
        profile_id=PRIMARY_PROFILE_ID,
        record_index=11,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "unmapped_source_fields"
    assert "unexpected_field" in result.unmapped_fields


def test_blank_source_keys_quarantine_explicitly_with_raw_evidence() -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(PRIMARY_PROFILE_ID)
    source_record["   "] = "bad-key"

    result = adapter.adapt_record(
        source_record,
        profile_id=PRIMARY_PROFILE_ID,
        record_index=13,
    )

    assert isinstance(result, AdapterQuarantineRecord)
    assert result.reason == "blank_source_keys"
    assert result.blank_source_keys == ("   ",)
    assert result.source_record["   "] == "bad-key"


def test_normalized_source_key_collisions_quarantine_explicitly() -> None:
    adapter = StructuredRecordAdapter()
    source_record = make_profile_record(PRIMARY_PROFILE_ID)
    collision_cases = [
        ("spaced_second", {**source_record, " SrcPort ": 9999.0}),
        (
            "canonical_second",
            {
                " SrcPort ": 9999.0,
                **{key: value for key, value in source_record.items() if key != "SrcPort"},
                "SrcPort": source_record["SrcPort"],
            },
        ),
    ]

    for case_index, (_, collision_record) in enumerate(collision_cases, start=14):
        result = adapter.adapt_record(
            collision_record,
            profile_id=PRIMARY_PROFILE_ID,
            record_index=case_index,
        )

        assert isinstance(result, AdapterQuarantineRecord)
        assert result.reason == "normalized_key_collision"
        assert result.normalized_key_collisions == ("SrcPort",)
        assert result.source_record[" SrcPort "] == 9999.0
        assert result.source_record["SrcPort"] != result.source_record[" SrcPort "]


def test_cli_file_mode_emits_runtime_ready_records_and_quarantine_sidecar(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "adapter_input.jsonl"
    adapted_output_path = tmp_path / "adapter_output.jsonl"
    quarantine_output_path = tmp_path / "adapter_quarantine.jsonl"
    runtime_alerts_path = tmp_path / "runtime_alerts.jsonl"
    runtime_quarantine_path = tmp_path / "runtime_quarantine.jsonl"

    input_path.write_text(PRIMARY_FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
            "--input-path",
            str(input_path),
            "--output-path",
            str(adapted_output_path),
            "--quarantine-output-path",
            str(quarantine_output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == ""
    assert result.stderr == ""

    adapted_records = load_jsonl(adapted_output_path)
    quarantine_records = load_jsonl(quarantine_output_path)

    assert len(adapted_records) == 1
    assert adapted_records[0]["adapter_profile"] == PRIMARY_PROFILE_ID
    assert adapted_records[0]["Flow Duration"] == 80.0
    assert len(quarantine_records) == 1
    assert quarantine_records[0]["reason"] == "missing_required_features"
    assert quarantine_records[0]["profile"] == PRIMARY_PROFILE_ID
    assert quarantine_records[0]["source_record_redacted"] is True
    assert quarantine_records[0]["metadata_redacted"] is True
    assert quarantine_records[0]["controlled_extras_redacted"] is True
    serialized_quarantine = json.dumps(quarantine_records[0], sort_keys=True)
    assert "FlowDuration" not in serialized_quarantine
    assert "source_flow_id-value" not in serialized_quarantine
    assert "capture_mode-value" not in serialized_quarantine

    runtime = RealtimePipelineRunner(
        contract=FlowFeatureContract.from_feature_file(
            DEFAULT_FEATURE_COLUMNS_PATH,
            alias_map={},
        ),
        inferencer=DummyInferencer(),
        max_batch_size=4,
        flush_interval_seconds=60.0,
    )
    with adapted_output_path.open("r", encoding="utf-8") as handle:
        summary = run_pipeline_stream(
            stream=handle,
            input_mode="file",
            alerts_output_path=runtime_alerts_path,
            quarantine_output_path=runtime_quarantine_path,
            runner=runtime,
        )

    runtime_alerts = load_jsonl(runtime_alerts_path)
    runtime_quarantines = load_jsonl(runtime_quarantine_path)

    assert summary.valid_records == 1
    assert summary.quarantined_records == 0
    assert runtime_alerts[0]["passthrough"]["adapter_profile"] == PRIMARY_PROFILE_ID
    assert runtime_quarantines == []


def test_cli_file_mode_secondary_profile_hands_off_cleanly_to_runtime(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "secondary_adapter_input.jsonl"
    adapted_output_path = tmp_path / "secondary_adapter_output.jsonl"
    quarantine_output_path = tmp_path / "secondary_adapter_quarantine.jsonl"
    runtime_alerts_path = tmp_path / "secondary_runtime_alerts.jsonl"
    runtime_quarantine_path = tmp_path / "secondary_runtime_quarantine.jsonl"

    input_path.write_text(SECONDARY_FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            SECONDARY_PROFILE_ID,
            "--input-path",
            str(input_path),
            "--output-path",
            str(adapted_output_path),
            "--quarantine-output-path",
            str(quarantine_output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == ""
    assert result.stderr == ""

    adapted_records = load_jsonl(adapted_output_path)
    quarantine_records = load_jsonl(quarantine_output_path)

    assert len(adapted_records) == 1
    assert adapted_records[0]["adapter_profile"] == SECONDARY_PROFILE_ID
    assert adapted_records[0]["Flow Duration"] == 91.0
    assert len(quarantine_records) == 1
    assert quarantine_records[0]["profile"] == SECONDARY_PROFILE_ID
    assert quarantine_records[0]["reason"] == "non_numeric_required_features"

    runtime = RealtimePipelineRunner(
        contract=FlowFeatureContract.from_feature_file(
            DEFAULT_FEATURE_COLUMNS_PATH,
            alias_map={},
        ),
        inferencer=DummyInferencer(),
        max_batch_size=4,
        flush_interval_seconds=60.0,
    )
    with adapted_output_path.open("r", encoding="utf-8") as handle:
        summary = run_pipeline_stream(
            stream=handle,
            input_mode="file",
            alerts_output_path=runtime_alerts_path,
            quarantine_output_path=runtime_quarantine_path,
            runner=runtime,
        )

    runtime_alerts = load_jsonl(runtime_alerts_path)
    runtime_quarantines = load_jsonl(runtime_quarantine_path)

    assert summary.valid_records == 1
    assert summary.quarantined_records == 0
    assert runtime_alerts[0]["passthrough"]["adapter_profile"] == SECONDARY_PROFILE_ID
    assert runtime_alerts[0]["passthrough"]["source_flow_id"] == "source_flow_id-value"
    assert runtime_quarantines == []


def test_cli_file_mode_uses_default_sidecar_names_when_paths_are_omitted(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "primary_records.jsonl"
    input_path.write_text(PRIMARY_FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
            "--input-path",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    adapted_output_path = tmp_path / "primary_records_adapted.jsonl"
    quarantine_output_path = tmp_path / "primary_records_adapter_quarantine.jsonl"

    assert result.stdout == ""
    assert result.stderr == ""
    assert adapted_output_path.exists()
    assert quarantine_output_path.exists()
    assert load_jsonl(adapted_output_path)[0]["adapter_profile"] == PRIMARY_PROFILE_ID
    quarantine_record = load_jsonl(quarantine_output_path)[0]
    assert quarantine_record["reason"] == "missing_required_features"
    assert quarantine_record["source_record_redacted"] is True
    assert quarantine_record["metadata_redacted"] is True
    assert quarantine_record["controlled_extras_redacted"] is True


def test_cli_file_mode_can_opt_in_to_raw_quarantine_source(tmp_path: Path) -> None:
    input_path = tmp_path / "raw_quarantine_input.jsonl"
    quarantine_output_path = tmp_path / "raw_quarantine_output.jsonl"
    input_path.write_text(
        json.dumps(
            make_profile_record(
                PRIMARY_PROFILE_ID,
                extra_fields={"unexpected_field": "boom"},
            )
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
            "--input-path",
            str(input_path),
            "--quarantine-output-path",
            str(quarantine_output_path),
            "--include-raw-quarantine-source",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    quarantine_records = load_jsonl(quarantine_output_path)

    assert result.stdout == ""
    assert result.stderr == ""
    assert len(quarantine_records) == 1
    assert "source_record_redacted" not in quarantine_records[0]
    assert quarantine_records[0]["source_record"]["unexpected_field"] == "boom"
    assert quarantine_records[0]["metadata"]["source_flow_id"] == "source_flow_id-value"
    assert quarantine_records[0]["controlled_extras"]["capture_mode"] == "capture_mode-value"


def test_cli_file_mode_rejects_input_output_path_collisions_before_opening_files(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "colliding_input.jsonl"
    original_payload = PRIMARY_FIXTURE_PATH.read_text(encoding="utf-8")
    input_path.write_text(original_payload, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
            "--input-path",
            str(input_path),
            "--output-path",
            str(input_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "File-mode paths must be distinct" in result.stderr
    assert "--output-path resolves to the same file as --input-path" in result.stderr
    assert input_path.read_text(encoding="utf-8") == original_payload


def test_cli_file_mode_rejects_output_quarantine_path_collisions_before_opening_files(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "source.jsonl"
    shared_sink_path = tmp_path / "shared_sink.jsonl"
    input_path.write_text(PRIMARY_FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
            "--input-path",
            str(input_path),
            "--output-path",
            str(shared_sink_path),
            "--quarantine-output-path",
            str(shared_sink_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "File-mode paths must be distinct" in result.stderr
    assert (
        "--output-path resolves to the same file as --quarantine-output-path"
        in result.stderr
    )
    assert not shared_sink_path.exists()


def test_cli_file_mode_rejects_input_quarantine_path_collisions_before_opening_files(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "source.jsonl"
    input_path.write_text(PRIMARY_FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
            "--input-path",
            str(input_path),
            "--quarantine-output-path",
            str(input_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "File-mode paths must be distinct" in result.stderr
    assert "--quarantine-output-path resolves to the same file as --input-path" in result.stderr
    assert load_jsonl(input_path) == load_jsonl(PRIMARY_FIXTURE_PATH)


def test_cli_stdin_redirected_sinks_cover_malformed_transport_paths(
    tmp_path: Path,
) -> None:
    adapted_output_path = tmp_path / "adapted.jsonl"
    quarantine_output_path = tmp_path / "adapter_quarantine.jsonl"
    valid_record = make_profile_record(PRIMARY_PROFILE_ID)
    payload = "\n".join(
        [
            json.dumps(valid_record),
            "{bad json",
            json.dumps(["not", "an", "object"]),
        ]
    )

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
            "--output-path",
            str(adapted_output_path),
            "--quarantine-output-path",
            str(quarantine_output_path),
        ],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )

    adapted_records = load_jsonl(adapted_output_path)
    quarantine_records = load_jsonl(quarantine_output_path)

    assert result.stdout == ""
    assert result.stderr == ""
    assert len(adapted_records) == 1
    assert adapted_records[0]["adapter_profile"] == PRIMARY_PROFILE_ID
    assert [record["reason"] for record in quarantine_records] == [
        "invalid_json",
        "invalid_record_type",
    ]
    assert [record["record_index"] for record in quarantine_records] == [1, 2]
    assert all(record["source_record_redacted"] is True for record in quarantine_records)
    serialized_quarantine = json.dumps(quarantine_records, sort_keys=True)
    assert "{bad json" not in serialized_quarantine
    assert "not" not in serialized_quarantine


def test_cli_stdin_rejects_output_quarantine_path_collisions_before_opening_files(
    tmp_path: Path,
) -> None:
    shared_sink_path = tmp_path / "shared_sink.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
            "--output-path",
            str(shared_sink_path),
            "--quarantine-output-path",
            str(shared_sink_path),
        ],
        input=json.dumps(make_profile_record(PRIMARY_PROFILE_ID)),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "File-mode paths must be distinct" in result.stderr
    assert (
        "--output-path resolves to the same file as --quarantine-output-path"
        in result.stderr
    )
    assert not shared_sink_path.exists()


def test_cli_stdin_stdout_mode_streams_success_and_quarantine_outputs() -> None:
    payload = SECONDARY_FIXTURE_PATH.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            SECONDARY_PROFILE_ID,
        ],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )

    adapted_lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    quarantine_lines = [json.loads(line) for line in result.stderr.splitlines() if line.strip()]

    assert len(adapted_lines) == 1
    assert adapted_lines[0]["adapter_profile"] == SECONDARY_PROFILE_ID
    assert adapted_lines[0]["Flow Duration"] == 91.0
    assert len(quarantine_lines) == 1
    assert quarantine_lines[0]["profile"] == SECONDARY_PROFILE_ID
    assert quarantine_lines[0]["reason"] == "non_numeric_required_features"
    assert quarantine_lines[0]["source_record_redacted"] is True
    serialized_quarantine = json.dumps(quarantine_lines[0], sort_keys=True)
    assert '"Duration":' not in serialized_quarantine
    assert '"bad"' not in serialized_quarantine


def test_cli_streaming_can_opt_in_to_raw_quarantine_source() -> None:
    payload = SECONDARY_FIXTURE_PATH.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            SECONDARY_PROFILE_ID,
            "--include-raw-quarantine-source",
        ],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )

    quarantine_lines = [json.loads(line) for line in result.stderr.splitlines() if line.strip()]

    assert len(quarantine_lines) == 1
    assert "source_record_redacted" not in quarantine_lines[0]
    assert quarantine_lines[0]["source_record"]["Duration"] == "bad"


def test_cli_quarantines_oversized_jsonl_lines_before_decoding() -> None:
    oversized_payload = json.dumps(
        {"payload": "x" * (MAX_JSONL_LINE_LENGTH + 32)}
    )

    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            PRIMARY_PROFILE_ID,
        ],
        input=oversized_payload,
        capture_output=True,
        text=True,
        check=True,
    )

    quarantine_lines = [json.loads(line) for line in result.stderr.splitlines() if line.strip()]

    assert result.stdout == ""
    assert len(quarantine_lines) == 1
    assert quarantine_lines[0]["reason"] == "jsonl_line_too_large"
    assert quarantine_lines[0]["source_record_redacted"] is True
    assert quarantine_lines[0]["source_record"]["raw_char_count"] > MAX_JSONL_LINE_LENGTH
    serialized_quarantine = json.dumps(quarantine_lines[0], sort_keys=True)
    assert "payload" not in serialized_quarantine


def test_jsonl_reader_bounds_newline_free_oversized_reads() -> None:
    class TrackingStream(io.StringIO):
        def __init__(self, value: str) -> None:
            super().__init__(value)
            self.readline_sizes: list[int] = []

        def readline(self, size: int = -1) -> str:
            self.readline_sizes.append(size)
            return super().readline(size)

    stream = TrackingStream("x" * (MAX_JSONL_LINE_LENGTH + 64))

    read_results = list(_read_jsonl_payloads(stream))

    assert len(read_results) == 1
    assert read_results[0].error_reason == "jsonl_line_too_large"
    assert read_results[0].raw_char_count == MAX_JSONL_LINE_LENGTH + 64
    assert max(stream.readline_sizes) == MAX_JSONL_LINE_LENGTH + 1


def test_importing_adapter_module_does_not_mutate_sys_path_or_read_repo_artifacts() -> None:
    script = f"""
import importlib.util
import json
import pathlib
import sys

module_path = pathlib.Path(r"{adapter_script_path()}")
before = list(sys.path)
read_calls = []
original_read_text = pathlib.Path.read_text

def tracked_read_text(self, *args, **kwargs):
    read_calls.append(str(self))
    return original_read_text(self, *args, **kwargs)

pathlib.Path.read_text = tracked_read_text
spec = importlib.util.spec_from_file_location("isolated_ids_record_adapter", module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
try:
    spec.loader.exec_module(module)
finally:
    pathlib.Path.read_text = original_read_text
print(json.dumps({{"before": before, "after": sys.path, "has_default": hasattr(module, "DEFAULT_STRUCTURED_RECORD_ADAPTER"), "read_calls": read_calls}}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)

    assert payload["has_default"] is True
    assert payload["after"] == payload["before"]
    assert payload["read_calls"] == []


def test_cli_rejects_unknown_profile_values() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(adapter_script_path()),
            "--profile",
            "does-not-exist",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr
    assert "does-not-exist" in result.stderr
