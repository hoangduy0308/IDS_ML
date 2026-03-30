from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.core.feature_contract import (  # noqa: E402
    FlowFeatureContract,
    QuarantinedFlowRecord,
    ValidatedFlowRecord,
    coerce_numeric_feature,
    load_feature_columns,
)
from scripts.ids_feature_contract import (  # noqa: E402
    DEFAULT_FEATURE_COLUMNS_PATH,
    DEFAULT_TRAINING_FEATURE_COLUMNS_PATH,
)


def make_contract() -> FlowFeatureContract:
    return FlowFeatureContract(
        feature_columns=["Src Port", "Dst Port", "Protocol", "Flow Duration"],
        alias_map={
            "SrcPort": "Src Port",
            "DstPort": "Dst Port",
            "FlowDuration": "Flow Duration",
        },
    )


def test_validate_record_applies_explicit_aliases_and_preserves_passthrough() -> None:
    contract = make_contract()

    result = contract.validate_record(
        {
            "SrcPort": "1234",
            "DstPort": 80,
            "Protocol": "6",
            "FlowDuration": "42.5",
            "collector_id": "sensor-a",
        }
    )

    assert isinstance(result, ValidatedFlowRecord)
    assert list(result.aligned_features) == [
        "Src Port",
        "Dst Port",
        "Protocol",
        "Flow Duration",
    ]
    assert result.aligned_features["Src Port"] == 1234.0
    assert result.aligned_features["Flow Duration"] == 42.5
    assert result.passthrough == {"collector_id": "sensor-a"}


def test_validate_record_quarantines_missing_required_feature_without_defaults() -> None:
    contract = make_contract()

    result = contract.validate_record(
        {
            "SrcPort": "1234",
            "DstPort": 80,
            "Protocol": 6,
        }
    )

    assert isinstance(result, QuarantinedFlowRecord)
    assert result.reason == "missing_required_features"
    assert result.missing_features == ("Flow Duration",)


def test_validate_record_quarantines_non_numeric_required_feature() -> None:
    contract = make_contract()

    result = contract.validate_record(
        {
            "Src Port": "1234",
            "Dst Port": "80",
            "Protocol": "tcp",
            "Flow Duration": 1,
        }
    )

    assert isinstance(result, QuarantinedFlowRecord)
    assert result.reason == "non_numeric_required_features"
    assert result.non_numeric_features == ("Protocol",)


def test_validate_record_quarantines_alias_collision() -> None:
    contract = make_contract()

    result = contract.validate_record(
        {
            "Src Port": 443,
            "SrcPort": 8080,
            "Dst Port": 80,
            "Protocol": 6,
            "Flow Duration": 1,
        }
    )

    assert isinstance(result, QuarantinedFlowRecord)
    assert result.reason == "alias_collision"
    assert result.alias_collisions == ("Src Port",)


def test_split_records_keeps_valid_rows_when_invalid_rows_are_quarantined() -> None:
    contract = make_contract()

    result = contract.split_records(
        [
            {
                "SrcPort": "1234",
                "DstPort": 80,
                "Protocol": 6,
                "FlowDuration": 5,
                "trace_id": "ok-1",
            },
            {
                "SrcPort": "1234",
                "DstPort": 80,
                "Protocol": "bad",
                "FlowDuration": 5,
                "trace_id": "bad-1",
            },
        ]
    )

    assert len(result.valid_records) == 1
    assert len(result.quarantined_records) == 1
    assert result.valid_records[0].passthrough == {"trace_id": "ok-1"}
    assert result.quarantined_records[0].reason == "non_numeric_required_features"
    assert result.quarantined_records[0].record_index == 1


def test_canonical_feature_contract_matches_training_manifest() -> None:
    bundled_columns = load_feature_columns(DEFAULT_FEATURE_COLUMNS_PATH)
    training_columns = load_feature_columns(DEFAULT_TRAINING_FEATURE_COLUMNS_PATH)

    assert bundled_columns == training_columns
    assert len(bundled_columns) == 72


@pytest.mark.parametrize("value", [None, "", " ", True, float("inf"), "nan"])
def test_coerce_numeric_feature_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError):
        coerce_numeric_feature(value)
