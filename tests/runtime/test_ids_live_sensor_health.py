from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.runtime.live_sensor_health import (  # noqa: E402
    LiveSensorHealthConfig,
    build_live_sensor_health_payload,
)
from ids.core.model_bundle import (  # noqa: E402
    build_composite_inference_contract_metadata,
    build_feature_schema_metadata,
    build_inference_contract_metadata,
)
from ids.ops.model_bundle_lifecycle import (  # noqa: E402
    build_activation_record_payload,
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


def write_composite_bundle_contract(bundle_root: Path, *, bundle_name: str) -> Path:
    bundle_root.mkdir(parents=True, exist_ok=True)
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
                "bundle_name": bundle_name,
                "created_at": "2026-03-29T00:00:00+00:00",
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


def append_raw_summary_line(summary_output_path: Path, raw_line: str) -> None:
    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_output_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(raw_line)
        handle.write("\n")


def test_build_live_sensor_health_payload_reports_healthy_matching_evidence(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="2026-03-29T03:01:00Z",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is True
    assert payload["status"] == "ok"
    assert payload["runtime_contract_kind"] == "binary"
    assert payload["active_bundle_contract_kind"] == "binary"
    assert payload["active_bundle_is_composite"] is False
    assert payload["components"]["activation_contract"]["ok"] is True
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is True
    assert runtime_evidence["state"] == "current"
    assert runtime_evidence["age_seconds"] == 60.0
    assert runtime_evidence["latest_summary"]["active_bundle"]["active_bundle_name"] == "bundle-under-test"


def test_build_live_sensor_health_payload_reports_healthy_composite_evidence(tmp_path: Path) -> None:
    bundle_root = write_composite_bundle_contract(tmp_path / "composite-bundle", bundle_name="composite-bundle")
    activation_path = tmp_path / "active_bundle.json"
    write_activation_record(
        activation_path,
        build_activation_record_payload(
            active_bundle_root=bundle_root,
            active_bundle_name="composite-bundle",
            activated_at="2026-03-29T03:00:00+00:00",
        ),
    )
    summary_output_path = tmp_path / "ids_live_sensor_summary.jsonl"
    append_summary_event(
        summary_output_path,
        activation_path=activation_path,
        bundle_root=bundle_root,
        bundle_name="composite-bundle",
        timestamp="2026-03-29T03:01:00Z",
    )
    config = LiveSensorHealthConfig(
        activation_path=activation_path,
        summary_output_path=summary_output_path,
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is True
    assert payload["status"] == "ok"
    assert payload["runtime_contract_kind"] == "composite"
    assert payload["active_bundle_contract_kind"] == "composite"
    assert payload["active_bundle_is_composite"] is True
    assert payload["components"]["activation_contract"]["payload"]["runtime_contract_kind"] == "composite"
    assert payload["components"]["activation_contract"]["payload"]["is_composite_contract"] is True
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is True
    assert runtime_evidence["state"] == "current"
    assert runtime_evidence["latest_summary"]["active_bundle"]["active_bundle_name"] == "composite-bundle"


def test_build_live_sensor_health_payload_rejects_empty_summary_file(tmp_path: Path) -> None:
    config, _ = make_config(tmp_path)
    config.summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.summary_output_path.write_text("\n\n", encoding="utf-8")

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is False
    assert runtime_evidence["state"] == "missing"
    assert runtime_evidence["detail"] == "summary output exists but contains no events"


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


def test_build_live_sensor_health_payload_rejects_unexpected_summary_event(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_raw_summary_line(
        config.summary_output_path,
        json.dumps(
            {
                "event_type": "something_else",
                "timestamp": "2026-03-29T03:01:00+00:00",
                "active_bundle": {
                    "activation_path": str(config.activation_path.resolve()),
                    "active_bundle_root": str(bundle_root.resolve()),
                    "active_bundle_name": "bundle-under-test",
                },
            }
        ),
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is False
    assert runtime_evidence["state"] == "unexpected_event"


def test_build_live_sensor_health_payload_rejects_malformed_summary_json(tmp_path: Path) -> None:
    config, _ = make_config(tmp_path)
    append_raw_summary_line(config.summary_output_path, "{not-json")

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is False
    assert runtime_evidence["state"] == "malformed"
    assert "Expecting property name enclosed in double quotes" in runtime_evidence["detail"]


def test_build_live_sensor_health_payload_rejects_invalid_summary_timestamp(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="not-a-timestamp",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is False
    assert runtime_evidence["state"] == "malformed"
    assert runtime_evidence["detail"] == "latest summary event timestamp is missing or invalid"


def test_build_live_sensor_health_payload_rejects_capture_failure_summary(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="2026-03-29T03:01:00+00:00",
        reason="capture-failure",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is False
    assert runtime_evidence["state"] == "capture_failure"
    assert runtime_evidence["detail"] == "latest summary event reports capture-failure"


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


def test_build_live_sensor_health_payload_handles_empty_summary_file(tmp_path: Path) -> None:
    config, _ = make_config(tmp_path)
    config.summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.summary_output_path.write_text("", encoding="utf-8")

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    runtime_evidence = payload["components"]["runtime_evidence"]
    assert payload["ready"] is False
    assert runtime_evidence["state"] == "missing"
    assert runtime_evidence["detail"] == "summary output exists but contains no events"


def test_build_live_sensor_health_payload_rejects_unexpected_event_type(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="2026-03-29T03:01:00+00:00",
    )
    payload = json.loads(config.summary_output_path.read_text(encoding="utf-8").strip())
    payload["event_type"] = "other_event"
    config.summary_output_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    runtime_evidence = result["components"]["runtime_evidence"]
    assert result["ready"] is False
    assert runtime_evidence["state"] == "unexpected_event"
    assert "not a live_sensor_summary" in runtime_evidence["detail"]


def test_build_live_sensor_health_payload_rejects_truncated_malformed_summary_json(tmp_path: Path) -> None:
    config, _ = make_config(tmp_path)
    config.summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.summary_output_path.write_text("{bad-json\n", encoding="utf-8")

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    runtime_evidence = payload["components"]["runtime_evidence"]
    assert payload["ready"] is False
    assert runtime_evidence["state"] == "malformed"
    assert "Expecting property name enclosed in double quotes" in runtime_evidence["detail"]


def test_build_live_sensor_health_payload_rejects_invalid_timestamp(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="not-a-timestamp",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    runtime_evidence = payload["components"]["runtime_evidence"]
    assert payload["ready"] is False
    assert runtime_evidence["state"] == "malformed"
    assert runtime_evidence["detail"] == "latest summary event timestamp is missing or invalid"


def test_build_live_sensor_health_payload_rejects_capture_failure_event(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="2026-03-29T03:01:00+00:00",
        reason="capture-failure",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    runtime_evidence = payload["components"]["runtime_evidence"]
    assert payload["ready"] is False
    assert runtime_evidence["state"] == "capture_failure"
    assert runtime_evidence["detail"] == "latest summary event reports capture-failure"


def test_build_live_sensor_health_payload_handles_invalid_activation_contract(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="2026-03-29T03:01:00+00:00",
    )
    config.activation_path.write_text("{bad-json\n", encoding="utf-8")

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert payload["ready"] is False
    assert payload["components"]["activation_contract"]["state"] == "invalid"
    assert payload["components"]["runtime_evidence"]["state"] == "current"


def test_build_live_sensor_health_payload_normalizes_z_suffix_timestamps(tmp_path: Path) -> None:
    config, bundle_root = make_config(tmp_path)
    append_summary_event(
        config.summary_output_path,
        activation_path=config.activation_path,
        bundle_root=bundle_root,
        bundle_name="bundle-under-test",
        timestamp="2026-03-29T03:01:00Z",
    )

    payload = build_live_sensor_health_payload(
        config,
        now=datetime(2026, 3, 29, 3, 2, 0, tzinfo=timezone.utc),
    )

    runtime_evidence = payload["components"]["runtime_evidence"]
    assert payload["ready"] is True
    assert runtime_evidence["state"] == "current"
    assert runtime_evidence["timestamp"] == "2026-03-29T03:01:00+00:00"


def test_build_live_sensor_health_payload_rejects_invalid_activation_contract_even_with_current_summary(
    tmp_path: Path,
) -> None:
    config, bundle_root = make_config(tmp_path)
    config.activation_path.write_text("{not-json", encoding="utf-8")
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

    assert payload["ready"] is False
    activation_contract = payload["components"]["activation_contract"]
    assert activation_contract["ok"] is False
    assert activation_contract["state"] == "invalid"
    runtime_evidence = payload["components"]["runtime_evidence"]
    assert runtime_evidence["ok"] is True
    assert runtime_evidence["state"] == "current"
