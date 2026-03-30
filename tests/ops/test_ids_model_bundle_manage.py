from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import ids.ops.model_bundle_manage as manage  # noqa: E402
from scripts.ids_model_bundle import (  # noqa: E402
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)


def write_bundle(bundle_root: Path, *, bundle_name: str, threshold: float) -> Path:
    bundle_root.mkdir(parents=True, exist_ok=True)
    feature_columns_path = bundle_root / "feature_columns.json"
    feature_columns_path.write_text(
        json.dumps({"feature_columns": ["f1", "f2"]}),
        encoding="utf-8",
    )
    (bundle_root / "model.cbm").write_text("model", encoding="utf-8")
    (bundle_root / "model_bundle.json").write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "bundle_name": bundle_name,
                "created_at": "2026-03-29T00:00:00+07:00",
                "model_key": "catboost_full_data",
                "model_family": "CatBoostClassifier",
                "model_artifact": "model.cbm",
                "feature_columns_file": "feature_columns.json",
                "threshold": threshold,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "feature_count": 2,
                "train_rows": 123,
                "metrics_file": "metrics.json",
                "training_summary_file": "training_summary.json",
                "compatibility": {
                    "feature_schema": build_feature_schema_metadata(feature_columns_path),
                    "inference_contract": build_inference_contract_metadata(
                        positive_label="Attack",
                        negative_label="Benign",
                        threshold=threshold,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return bundle_root


def test_manage_status_reports_not_ready_without_activation_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"

    rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["activation_record_exists"] is False
    assert payload["runtime_ready"] is False


def test_manage_verify_promote_status_and_rollback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    bundle_a = write_bundle(tmp_path / "bundle-a", bundle_name="bundle-a", threshold=0.5)
    bundle_b = write_bundle(tmp_path / "bundle-b", bundle_name="bundle-b", threshold=0.7)

    verify_rc = manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "verify",
            "--bundle-root",
            str(bundle_a),
        ]
    )
    verify_payload = json.loads(capsys.readouterr().out)
    assert verify_rc == 0
    assert verify_payload["compatible"] is True
    assert verify_payload["bundle_name"] == "bundle-a"

    promote_a_rc = manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "promote",
            "--bundle-root",
            str(bundle_a),
        ]
    )
    promote_a_payload = json.loads(capsys.readouterr().out)
    assert promote_a_rc == 0
    assert promote_a_payload["active_bundle_name"] == "bundle-a"
    assert "previous_bundle_root" not in promote_a_payload

    promote_b_rc = manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "activate",
            "--bundle-root",
            str(bundle_b),
        ]
    )
    promote_b_payload = json.loads(capsys.readouterr().out)
    assert promote_b_rc == 0
    assert promote_b_payload["active_bundle_name"] == "bundle-b"
    assert promote_b_payload["previous_bundle_name"] == "bundle-a"

    status_rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    status_payload = json.loads(capsys.readouterr().out)
    assert status_rc == 0
    assert status_payload["active_bundle_name"] == "bundle-b"
    assert status_payload["previous_bundle_name"] == "bundle-a"

    rollback_rc = manage.main(["--activation-path", str(activation_path), "--json", "rollback"])
    rollback_payload = json.loads(capsys.readouterr().out)
    assert rollback_rc == 0
    assert rollback_payload["active_bundle_name"] == "bundle-a"
    assert rollback_payload["previous_bundle_name"] == "bundle-b"


def test_manage_rollback_fails_without_previous_known_good(
    tmp_path: Path,
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    bundle_a = write_bundle(tmp_path / "bundle-a", bundle_name="bundle-a", threshold=0.5)
    manage.main(
        [
            "--activation-path",
            str(activation_path),
            "promote",
            "--bundle-root",
            str(bundle_a),
        ]
    )

    with pytest.raises(SystemExit, match="previous known-good bundle"):
        manage.main(["--activation-path", str(activation_path), "rollback"])


def test_manage_failed_promote_preserves_previous_active_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activation_path = tmp_path / "active_bundle.json"
    bundle_a = write_bundle(tmp_path / "bundle-a", bundle_name="bundle-a", threshold=0.5)
    bundle_b = write_bundle(tmp_path / "bundle-b", bundle_name="bundle-b", threshold=0.7)

    manage.main(
        [
            "--activation-path",
            str(activation_path),
            "--json",
            "promote",
            "--bundle-root",
            str(bundle_a),
        ]
    )
    capsys.readouterr()

    bundle_b_manifest_path = bundle_b / "model_bundle.json"
    bundle_b_payload = json.loads(bundle_b_manifest_path.read_text(encoding="utf-8"))
    bundle_b_payload["compatibility"]["inference_contract"]["version"] = "ids_binary_classifier.v999"
    bundle_b_manifest_path.write_text(
        json.dumps(bundle_b_payload),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Unsupported inference contract version"):
        manage.main(
            [
                "--activation-path",
                str(activation_path),
                "promote",
                "--bundle-root",
                str(bundle_b),
            ]
        )

    status_rc = manage.main(["--activation-path", str(activation_path), "--json", "status"])
    status_payload = json.loads(capsys.readouterr().out)

    assert status_rc == 0
    assert status_payload["active_bundle_name"] == "bundle-a"
    assert "previous_bundle_name" not in status_payload
