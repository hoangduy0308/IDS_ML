from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_model_bundle import (  # noqa: E402
    DEFAULT_ACTIVATION_RECORD_NAME,
    ModelBundleContractError,
    build_activation_record_payload,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
    load_activation_record,
    load_model_bundle_manifest,
    resolve_active_model_bundle,
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
