from __future__ import annotations

from pathlib import Path
import json

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.core.model_bundle import (  # noqa: E402
    ModelBundleContractError,
    build_composite_inference_contract_metadata,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
    load_feature_columns as load_bundle_feature_columns,
    load_model_bundle_manifest,
)
from ids.core.feature_contract import load_feature_columns as load_contract_feature_columns  # noqa: E402
from ids.core.model_bundle_activation import (  # noqa: E402
    DEFAULT_ACTIVATION_RECORD_NAME,
    build_bundle_status_payload,
    load_activation_record,
    resolve_active_model_bundle,
)
from ids.ops.model_bundle_lifecycle import (  # noqa: E402
    build_activation_record_payload,
    write_activation_record,
)


def write_feature_columns(path: Path) -> None:
    path.write_text(json.dumps({"feature_columns": ["f1", "f2"]}), encoding="utf-8")


def write_bundle_manifest(
    bundle_root: Path,
    *,
    inference_contract_version: str = "ids_binary_classifier.v1",
) -> None:
    feature_columns_path = bundle_root / "feature_columns.json"
    write_feature_columns(feature_columns_path)
    payload = {
        "manifest_version": 2,
        "bundle_name": "bundle-under-test",
        "created_at": "2026-03-29T00:00:00+07:00",
        "model_key": "catboost_full_data",
        "model_family": "CatBoostClassifier",
        "model_artifact": "model.cbm",
        "feature_columns_file": "feature_columns.json",
        "threshold": 0.5,
        "positive_label": "Attack",
        "negative_label": "Benign",
        "feature_count": 2,
        "train_rows": 123,
        "metrics_file": "metrics.json",
        "training_summary_file": "training_summary.json",
        "compatibility": {
            "feature_schema": build_feature_schema_metadata(feature_columns_path),
            "inference_contract": {
                **build_inference_contract_metadata(
                    positive_label="Attack",
                    negative_label="Benign",
                    threshold=0.5,
                ),
                "version": inference_contract_version,
            },
        },
    }
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(json.dumps(payload), encoding="utf-8")


def write_composite_bundle_manifest(bundle_root: Path) -> None:
    stage1_feature_columns_path = bundle_root / "stage1_feature_columns.json"
    stage2_feature_columns_path = bundle_root / "stage2_feature_columns.json"
    stage1_feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", "f2"]}),
        encoding="utf-8",
    )
    stage2_feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", "f2", "f3"]}),
        encoding="utf-8",
    )
    (bundle_root / "stage1_model.cbm").write_text("stage1", encoding="utf-8")
    (bundle_root / "stage2_model.cbm").write_text("stage2", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "bundle_name": "bundle-under-test",
                "created_at": "2026-03-29T00:00:00+07:00",
                "model_key": "catboost_full_data",
                "model_family": "CatBoostClassifier",
                "model_artifact": "stage1_model.cbm",
                "feature_columns_file": "stage1_feature_columns.json",
                "threshold": 0.5,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "feature_count": 2,
                "train_rows": 123,
                "metrics_file": "metrics.json",
                "training_summary_file": "training_summary.json",
                "compatibility": {
                    "feature_schema": build_feature_schema_metadata(stage1_feature_columns_path),
                    "inference_contract": build_composite_inference_contract_metadata(
                        positive_label="Attack",
                        negative_label="Benign",
                        threshold=0.5,
                        stage2_model_artifact="stage2_model.cbm",
                        stage2_feature_columns_path=stage2_feature_columns_path,
                        top1_confidence_threshold=0.5589,
                        runner_up_margin_threshold=0.3097,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )


def test_load_model_bundle_manifest_accepts_versioned_contract(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_bundle_manifest(bundle_root)

    manifest = load_model_bundle_manifest(bundle_root)

    assert manifest.bundle_name == "bundle-under-test"
    assert manifest.model_path == (bundle_root / "model.cbm").resolve()
    assert manifest.feature_columns_path == (bundle_root / "feature_columns.json").resolve()


def test_load_model_bundle_manifest_fails_without_compatibility_block(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_feature_columns(bundle_root / "feature_columns.json")
    (bundle_root / "model.cbm").write_text("placeholder", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "bundle_name": "bundle-under-test",
                "model_artifact": "model.cbm",
                "feature_columns_file": "feature_columns.json",
                "threshold": 0.5,
                "positive_label": "Attack",
                "negative_label": "Benign",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ModelBundleContractError, match="missing compatibility block"):
        load_model_bundle_manifest(bundle_root)


def test_load_model_bundle_manifest_fails_on_feature_schema_digest_mismatch(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_bundle_manifest(bundle_root)
    payload = json.loads((bundle_root / "model_bundle.json").read_text(encoding="utf-8"))
    payload["compatibility"]["feature_schema"]["sha256"] = "0" * 64
    (bundle_root / "model_bundle.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelBundleContractError, match="feature schema digest mismatch"):
        load_model_bundle_manifest(bundle_root)


def test_load_model_bundle_manifest_fails_on_unsupported_inference_contract(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_bundle_manifest(bundle_root, inference_contract_version="ids_binary_classifier.v0")

    with pytest.raises(ModelBundleContractError, match="Unsupported inference contract version"):
        load_model_bundle_manifest(bundle_root)


def test_load_model_bundle_manifest_accepts_composite_contract(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_composite_bundle_manifest(bundle_root)

    manifest = load_model_bundle_manifest(bundle_root)

    assert manifest.is_composite_contract is True
    assert manifest.stage2_model_path == (bundle_root / "stage2_model.cbm").resolve()
    assert manifest.stage2_feature_columns_path == (
        bundle_root / "stage2_feature_columns.json"
    ).resolve()
    assert manifest.stage2_abstention["top1_confidence"] == pytest.approx(0.5589)
    assert manifest.stage2_abstention["runner_up_margin"] == pytest.approx(0.3097)


@pytest.mark.parametrize(
    ("flag_name", "error_message"),
    [
        (
            "allows_external_stage1_model_path",
            "Composite stage1 contract cannot allow external model path overrides",
        ),
        (
            "allows_external_stage1_feature_columns_path",
            "Composite stage1 contract cannot allow external feature schema overrides",
        ),
        (
            "allows_external_stage1_threshold_override",
            "Composite stage1 contract cannot allow external threshold overrides",
        ),
        (
            "allows_external_stage2_model_path",
            "Composite stage2 contract cannot allow external model path overrides",
        ),
        (
            "allows_external_stage2_feature_columns_path",
            "Composite stage2 contract cannot allow external feature schema overrides",
        ),
        (
            "allows_external_abstention_override",
            "Composite inference contract cannot allow external abstention overrides",
        ),
    ],
)
def test_load_model_bundle_manifest_rejects_composite_external_override_flags(
    tmp_path: Path,
    flag_name: str,
    error_message: str,
) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_composite_bundle_manifest(bundle_root)
    manifest_path = bundle_root / "model_bundle.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["compatibility"]["inference_contract"][flag_name] = True
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelBundleContractError, match=error_message):
        load_model_bundle_manifest(bundle_root)


@pytest.mark.parametrize(
    ("flag_name", "error_message"),
    [
        (
            "allows_external_model_path",
            "Inference contract cannot allow external model path overrides",
        ),
        (
            "allows_external_feature_columns_path",
            "Inference contract cannot allow external feature schema overrides",
        ),
        (
            "allows_external_threshold_override",
            "Inference contract cannot allow external threshold overrides",
        ),
    ],
)
def test_load_model_bundle_manifest_rejects_legacy_binary_external_override_flags(
    tmp_path: Path,
    flag_name: str,
    error_message: str,
) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_bundle_manifest(bundle_root)
    manifest_path = bundle_root / "model_bundle.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["compatibility"]["inference_contract"][flag_name] = True
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelBundleContractError, match=error_message):
        load_model_bundle_manifest(bundle_root)


def test_load_model_bundle_manifest_fails_on_incomplete_composite_contract(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_composite_bundle_manifest(bundle_root)
    manifest_path = bundle_root / "model_bundle.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    del payload["compatibility"]["inference_contract"]["stage2"]
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelBundleContractError, match="missing stage2"):
        load_model_bundle_manifest(bundle_root)


@pytest.mark.parametrize(
    ("mutate_manifest", "error_message"),
    [
        (lambda payload: payload.__setitem__("manifest_version", "bogus"), "invalid manifest_version"),
        (lambda payload: payload.__setitem__("threshold", "bogus"), "invalid threshold"),
        (
            lambda payload: payload["compatibility"]["feature_schema"].__setitem__("feature_count", "bogus"),
            "invalid feature_count",
        ),
    ],
)
def test_load_model_bundle_manifest_normalizes_invalid_metadata_fields(
    tmp_path: Path,
    mutate_manifest,
    error_message: str,
) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_bundle_manifest(bundle_root)
    manifest_path = bundle_root / "model_bundle.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate_manifest(payload)
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelBundleContractError, match=error_message):
        load_model_bundle_manifest(bundle_root)


def test_load_activation_record_normalizes_invalid_record_version(tmp_path: Path) -> None:
    activation_path = tmp_path / DEFAULT_ACTIVATION_RECORD_NAME
    activation_path.write_text(
        json.dumps(
            {
                "record_version": "bogus",
                "active_bundle_root": str((tmp_path / "bundle").resolve()),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ModelBundleContractError, match="invalid record_version"):
        load_activation_record(activation_path)


def test_feature_column_loader_is_shared_and_bundle_wraps_errors(tmp_path: Path) -> None:
    feature_columns_path = tmp_path / "feature_columns.json"
    feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", " "]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Blank feature column name found"):
        load_contract_feature_columns(feature_columns_path)

    with pytest.raises(ModelBundleContractError, match="Blank feature column name found"):
        load_bundle_feature_columns(feature_columns_path)


def test_resolve_active_model_bundle_uses_activation_record(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_bundle_manifest(bundle_root)
    activation_path = tmp_path / DEFAULT_ACTIVATION_RECORD_NAME
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=bundle_root,
            active_bundle_name="bundle-under-test",
            activated_at="2026-03-29T00:00:00+07:00",
        ),
    )

    manifest = resolve_active_model_bundle(activation_path)

    assert manifest.bundle_root == bundle_root.resolve()


def test_build_bundle_status_payload_reads_activation_record(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    write_bundle_manifest(bundle_root)
    activation_path = tmp_path / DEFAULT_ACTIVATION_RECORD_NAME
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=bundle_root,
            active_bundle_name="bundle-under-test",
            activated_at="2026-03-29T00:00:00+07:00",
        ),
    )

    payload = build_bundle_status_payload(activation_path)

    assert payload["runtime_ready"] is True
    assert payload["active_bundle_root"] == str(bundle_root.resolve())
    assert payload["active_bundle_name"] == "bundle-under-test"
    assert payload["feature_columns_path"] == str((bundle_root / "feature_columns.json").resolve())


def test_load_activation_record_preserves_previous_known_good_bundle(tmp_path: Path) -> None:
    current_bundle_root = tmp_path / "bundle-current"
    previous_bundle_root = tmp_path / "bundle-previous"
    current_bundle_root.mkdir()
    previous_bundle_root.mkdir()
    activation_path = tmp_path / DEFAULT_ACTIVATION_RECORD_NAME
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=current_bundle_root,
            active_bundle_name="bundle-current",
            activated_at="2026-03-29T00:00:00+07:00",
            previous_bundle_root=previous_bundle_root,
            previous_bundle_name="bundle-previous",
        ),
    )

    record = load_activation_record(activation_path)

    assert record.active_bundle_root == current_bundle_root.resolve()
    assert record.previous_bundle_root == previous_bundle_root.resolve()
