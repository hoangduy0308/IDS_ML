from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_live_sensor_health import (  # noqa: E402
    LiveSensorHealthConfig,
    build_live_sensor_health_payload,
)
from scripts.ids_model_bundle import (  # noqa: E402
    build_activation_record_payload,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
    write_activation_record,
)


def write_bundle_contract(bundle_root: Path, *, bundle_name: str) -> Path:
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
                "created_at": "2026-03-29T00:00:00+00:00",
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
                    "inference_contract": build_inference_contract_metadata(
                        positive_label="Attack",
                        negative_label="Benign",
                        threshold=0.5,
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return bundle_root


def make_config(tmp_path: Path, *, freshness_window_seconds: float = 300.0) -> tuple[LiveSensorHealthConfig, Path]:
    bundle_root = write_bundle_contract(tmp_path / "bundle", bundle_name="bundle-under-test")
    activation_path = tmp_path / "active_bundle.json"
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=bundle_root,
            active_bundle_name="bundle-under-test",
            activated_at="2026-03-29T03:00:00+00:00",
        ),
    )
    summary_output_path = tmp_path / "ids_live_sensor_summary.jsonl"
    return (
        LiveSensorHealthConfig(
            activation_path=activation_path,
            summary_output_path=summary_output_path,
            freshness_window_seconds=freshness_window_seconds,
        ),
        bundle_root.resolve(),
    )


def append_summary_event(
    summary_output_path: Path,
    *,
    activation_path: Path,
    bundle_root: Path,
    bundle_name: str,
    timestamp: str,
    reason: str = "window-processed",
) -> None:
    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": "live_sensor_summary",
        "reason": reason,
        "timestamp": timestamp,
        "processed_windows": 1,
        "extractor_failures": 0,
        "latest_queue_depth": 0,
        "oldest_pending_window_age_seconds": 0.0,
        "latest_extractor_runtime_seconds": 0.25,
        "total_extractor_runtime_seconds": 0.25,
        "active_bundle": {
            "activation_path": str(activation_path.resolve()),
            "active_bundle_root": str(bundle_root.resolve()),
            "active_bundle_name": bundle_name,
            "compatibility_status": "compatible",
            "verification_status": "verified",
            "manifest_version": 2,
            "activated_at": "2026-03-29T03:00:00+00:00",
        },
    }
    with summary_output_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event))
        handle.write("\n")


def test_build_live_sensor_health_payload_reports_healthy_matching_evidence(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="2026-03-29T03:01:00+00:00",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is True
    assert payload["status"] == "ok"
    assert payload["components"]["activation_contract"]["ok"] is True
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is True
    assert runtime_evidence["state"] == "current"
    assert runtime_evidence["age_seconds"] == 60.0
    assert runtime_evidence["latest_summary"]["active_bundle"]["active_bundle_name"] == "bundle-under-test"


def test_build_live_sensor_health_payload_rejects_missing_summary_evidence(tmp_path: Path) -> None:
    config, _ = make_config(tmp_path)

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is False
    assert runtime_evidence["state"] == "missing"
    assert runtime_evidence["detail"] == "summary output not found"


def test_build_live_sensor_health_payload_rejects_stale_summary_evidence(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path, freshness_window_seconds=30.0)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="2026-03-29T03:00:00+00:00",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is False
    assert runtime_evidence["state"] == "stale"
    assert "stale" in runtime_evidence["detail"]


def test_build_live_sensor_health_payload_rejects_mismatched_bundle_evidence(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    other_bundle_root = write_bundle_contract(tmp_path / "other-bundle", bundle_name="other-bundle").resolve()
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=other_bundle_root,
        bundle_name="other-bundle",
        timestamp="2026-03-29T03:01:00+00:00",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is False
    assert runtime_evidence["state"] == "mismatch"
    assert str(bundle_root) in runtime_evidence["detail"]
