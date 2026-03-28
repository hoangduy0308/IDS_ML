from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console.alerts import transition_alert_status  # noqa: E402
from scripts.ids_operator_console.db import OperatorStore  # noqa: E402
from scripts.ids_operator_console.reporting import (  # noqa: E402
    build_report_bundle,
    build_report_rollup,
    export_alert_rows,
    export_anomaly_rows,
    export_summary_rows,
)


def _new_store(tmp_path: Path) -> OperatorStore:
    return OperatorStore.open(tmp_path / "operator_console.db")


def _seed_alert(store: OperatorStore, *, source_event_id: str, src_ip: str, severity: str = "high") -> int:
    return store.upsert_alert(
        source_event_id=source_event_id,
        event_ts="2026-03-28T16:00:00+00:00",
        severity=severity,
        src_ip=src_ip,
        dst_ip="192.168.10.2",
        src_port=443,
        dst_port=52222,
        protocol="tcp",
        fingerprint=f"fp-{source_event_id}",
        payload={"event_type": "model_prediction", "src_ip": src_ip, "score": 0.95},
    )


def test_export_alert_rows_supports_filters_and_suppression(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        alert_1 = _seed_alert(store, source_event_id="alert-001", src_ip="10.2.0.1", severity="high")
        alert_2 = _seed_alert(store, source_event_id="alert-002", src_ip="10.2.0.2", severity="medium")
        transition_alert_status(store, alert_id=alert_1, to_status="investigating")
        transition_alert_status(store, alert_id=alert_2, to_status="resolved")
        store.create_suppression_rule(
            rule_name="Suppress scanner",
            match_field="src_ip",
            match_value="10.2.0.1",
            applies_to="model_alert",
        )

        investigating = export_alert_rows(store, triage_status="investigating", include_suppressed=False)
        assert investigating == []

        all_investigating = export_alert_rows(store, triage_status="investigating", include_suppressed=True)
        assert len(all_investigating) == 1
        assert all_investigating[0]["source_event_id"] == "alert-001"
        assert all_investigating[0]["suppressed"] is True

        resolved = export_alert_rows(store, triage_status="resolved", include_suppressed=False)
        assert len(resolved) == 1
        assert resolved[0]["source_event_id"] == "alert-002"
    finally:
        store.close()


def test_export_anomaly_rows_default_to_redaction_safe_output(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        store.store_anomaly(
            source_event_id="anom-001",
            event_ts="2026-03-28T16:01:00+00:00",
            anomaly_type="schema_anomaly",
            reason="missing feature",
            redacted_summary="payload redacted",
            payload={"raw_payload": {"secret": "do-not-export"}, "reason": "missing feature"},
        )

        redacted = export_anomaly_rows(store, include_payload=False)
        assert len(redacted) == 1
        assert "payload" not in redacted[0]
        assert redacted[0]["redacted_summary"] == "payload redacted"

        with_payload = export_anomaly_rows(store, include_payload=True)
        assert len(with_payload) == 1
        assert with_payload[0]["payload"]["reason"] == "missing feature"
    finally:
        store.close()


def test_report_bundle_and_rollup_cover_alerts_anomalies_and_summaries(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        alert_id = _seed_alert(store, source_event_id="alert-003", src_ip="10.2.0.3", severity="critical")
        transition_alert_status(store, alert_id=alert_id, to_status="acknowledged")

        store.store_anomaly(
            source_event_id="anom-002",
            event_ts="2026-03-28T16:02:00+00:00",
            anomaly_type="schema_anomaly",
            reason="bad type",
            redacted_summary="schema mismatch",
            payload={"reason": "bad type"},
        )
        store.store_summary(
            summary_ts="2026-03-28T16:03:00+00:00",
            payload={"window_seconds": 60, "alert_count": 1, "anomaly_count": 1},
        )

        bundle = build_report_bundle(store)
        assert len(bundle["alerts"]) == 1
        assert len(bundle["anomalies"]) == 1
        assert len(bundle["summaries"]) == 1

        summaries = export_summary_rows(store)
        assert summaries[0]["payload"]["alert_count"] == 1

        rollup = build_report_rollup(bundle)
        assert rollup["alerts_total"] == 1
        assert rollup["alerts_by_status"]["acknowledged"] == 1
        assert rollup["alerts_by_severity"]["critical"] == 1
        assert rollup["anomalies_total"] == 1
        assert rollup["summaries_total"] == 1
        assert rollup["latest_summary_ts"] == "2026-03-28T16:03:00+00:00"
    finally:
        store.close()

