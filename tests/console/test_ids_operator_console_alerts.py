from __future__ import annotations

from pathlib import Path
import json

import pytest

from ids.console.alerts import (  # noqa: E402
    add_investigation_note,
    build_alert_family_view,
    get_alert_timeline,
    list_alert_incidents_for_triage,
    list_alerts_for_notification,
    list_alerts_for_triage,
    load_console_snapshot,
    transition_alert_status,
)
from ids.console.db import OperatorStore  # noqa: E402


def _new_store(tmp_path: Path) -> OperatorStore:
    return OperatorStore.open(tmp_path / "operator_console.db")


def _seed_alert(
    store: OperatorStore,
    *,
    source_event_id: str,
    src_ip: str,
    severity: str = "high",
    payload: dict[str, object] | None = None,
) -> int:
    alert_payload: dict[str, object] = {"event_type": "model_prediction", "src_ip": src_ip, "score": 0.99}
    if payload is not None:
        alert_payload.update(payload)
    return store.upsert_alert(
        source_event_id=source_event_id,
        event_ts="2026-03-28T15:00:00+00:00",
        severity=severity,
        src_ip=src_ip,
        dst_ip="192.168.1.20",
        src_port=443,
        dst_port=51432,
        protocol="tcp",
        fingerprint=f"fp-{source_event_id}",
        payload=alert_payload,
    )


def test_transition_alert_status_persists_history_and_validates_states(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        alert_id = _seed_alert(store, source_event_id="alert-001", src_ip="10.0.0.11")

        first = transition_alert_status(store, alert_id=alert_id, to_status="acknowledged", changed_by="operator-a")
        second = transition_alert_status(store, alert_id=alert_id, to_status="investigating", changed_by="operator-a")

        assert first["triage_status"] == "acknowledged"
        assert second["triage_status"] == "investigating"

        timeline = get_alert_timeline(store, alert_id=alert_id)
        history = timeline["status_history"]
        assert len(history) == 2
        assert history[0]["to_status"] == "investigating"
        assert history[1]["to_status"] == "acknowledged"

        with pytest.raises(ValueError, match="invalid triage status"):
            transition_alert_status(store, alert_id=alert_id, to_status="triaged")
    finally:
        store.close()


def test_investigation_notes_are_durable_and_queryable(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        alert_id = _seed_alert(store, source_event_id="alert-002", src_ip="10.0.0.12")

        note = add_investigation_note(
            store,
            alert_id=alert_id,
            note_text="Correlated with scanner host inventory",
            author="operator-b",
        )
        assert note["author"] == "operator-b"

        timeline = get_alert_timeline(store, alert_id=alert_id)
        notes = timeline["notes"]
        assert len(notes) == 1
        assert notes[0]["note_text"] == "Correlated with scanner host inventory"
    finally:
        store.close()


def test_suppression_only_filters_attack_alert_presentation_notification(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        suppressed_alert_id = _seed_alert(store, source_event_id="alert-003", src_ip="10.1.1.10")
        visible_alert_id = _seed_alert(store, source_event_id="alert-004", src_ip="10.1.1.11")
        assert suppressed_alert_id != visible_alert_id

        before = store.list_alerts(limit=10)
        suppressed_before_payload = next(
            row["payload_json"] for row in before if row["source_event_id"] == "alert-003"
        )

        store.create_suppression_rule(
            rule_name="Suppress trusted scanner",
            match_field="src_ip",
            match_value="10.1.1.10",
            applies_to="model_alert",
        )

        visible_alerts = list_alerts_for_triage(store, include_suppressed=False)
        all_alerts = list_alerts_for_triage(store, include_suppressed=True)
        notify_alerts = list_alerts_for_notification(store)

        assert {row["source_event_id"] for row in visible_alerts} == {"alert-004"}
        assert {row["source_event_id"] for row in all_alerts} == {"alert-003", "alert-004"}
        assert {row["source_event_id"] for row in notify_alerts} == {"alert-004"}

        suppressed_row = next(row for row in all_alerts if row["source_event_id"] == "alert-003")
        assert suppressed_row["suppressed"] is True

        after = store.list_alerts(limit=10)
        suppressed_after_payload = next(
            row["payload_json"] for row in after if row["source_event_id"] == "alert-003"
        )
        assert json.loads(suppressed_before_payload) == json.loads(suppressed_after_payload)
    finally:
        store.close()


def test_console_snapshot_keeps_alerts_anomalies_and_summaries_separate(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        _seed_alert(store, source_event_id="alert-005", src_ip="10.9.0.1")
        store.store_anomaly(
            source_event_id="anom-001",
            event_ts="2026-03-28T15:01:00+00:00",
            anomaly_type="schema_anomaly",
            reason="missing feature",
            redacted_summary="payload redacted",
            payload={"anomaly_type": "schema_anomaly", "reason": "missing field"},
        )
        store.store_summary(
            summary_ts="2026-03-28T15:02:00+00:00",
            payload={"window_seconds": 60, "alert_count": 1, "anomaly_count": 1},
        )
        store.create_suppression_rule(
            rule_name="Suppress src",
            match_field="src_ip",
            match_value="10.9.0.1",
            applies_to="model_alert",
        )

        snapshot = load_console_snapshot(store, include_suppressed_alerts=False)
        assert snapshot.keys() == {"alerts", "anomalies", "summaries"}
        assert snapshot["alerts"] == []
        assert len(snapshot["anomalies"]) == 1
        assert snapshot["anomalies"][0]["anomaly_type"] == "schema_anomaly"
        assert len(snapshot["summaries"]) == 1
    finally:
        store.close()


def test_alert_family_view_model_distinguishes_known_unknown_benign_and_legacy(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        _seed_alert(
            store,
            source_event_id="family-known",
            src_ip="10.0.0.21",
            payload={
                "family_status": "known",
                "attack_family": "DDoS",
                "attack_family_confidence": 0.93,
                "attack_family_margin": 0.44,
            },
        )
        _seed_alert(
            store,
            source_event_id="family-unknown",
            src_ip="10.0.0.22",
            payload={
                "family_status": "unknown",
                "attack_family_confidence": 0.61,
                "attack_family_margin": 0.11,
            },
        )
        _seed_alert(
            store,
            source_event_id="family-benign",
            src_ip="10.0.0.24",
            payload={
                "family_status": "benign",
                "attack_family": "stale-family",
                "attack_family_confidence": 0.72,
                "attack_family_margin": 0.31,
            },
        )
        _seed_alert(store, source_event_id="family-legacy", src_ip="10.0.0.23")

        triage_rows = list_alerts_for_triage(store, include_suppressed=True)
        by_event = {row["source_event_id"]: row for row in triage_rows}

        known = by_event["family-known"]["family"]
        assert known["family_status"] == "known"
        assert known["family_state"] == "known"
        assert known["legacy_unavailable"] is False
        assert known["attack_family"] == "DDoS"
        assert known["attack_family_confidence"] == pytest.approx(0.93)
        assert known["attack_family_margin"] == pytest.approx(0.44)

        unknown = by_event["family-unknown"]["family"]
        assert unknown["family_status"] == "unknown"
        assert unknown["family_state"] == "unknown"
        assert unknown["legacy_unavailable"] is False
        assert unknown["attack_family"] is None
        assert unknown["attack_family_confidence"] == pytest.approx(0.61)
        assert unknown["attack_family_margin"] == pytest.approx(0.11)

        benign = by_event["family-benign"]["family"]
        assert benign["family_status"] == "benign"
        assert benign["family_state"] == "benign"
        assert benign["legacy_unavailable"] is False
        assert benign["attack_family"] is None
        assert benign["attack_family_confidence"] is None
        assert benign["attack_family_margin"] is None

        legacy = by_event["family-legacy"]["family"]
        assert legacy["family_status"] is None
        assert legacy["family_state"] == "legacy_unavailable"
        assert legacy["legacy_unavailable"] is True
        assert legacy["attack_family"] is None
        assert legacy["attack_family_confidence"] is None
        assert legacy["attack_family_margin"] is None
    finally:
        store.close()


def test_build_alert_family_view_handles_payload_json_fallback() -> None:
    alert = {
        "payload_json": json.dumps(
            {
                "family_status": "known",
                "attack_family": "Recon",
                "attack_family_confidence": "0.75",
                "attack_family_margin": "0.25",
            }
        )
    }

    family = build_alert_family_view(alert)

    assert family["family_status"] == "known"
    assert family["family_state"] == "known"
    assert family["legacy_unavailable"] is False
    assert family["attack_family"] == "Recon"
    assert family["attack_family_confidence"] == pytest.approx(0.75)
    assert family["attack_family_margin"] == pytest.approx(0.25)


def test_list_alerts_for_triage_enriches_flow_fields_from_passthrough_payload(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        store.upsert_alert(
            source_event_id="live-alert-001",
            event_ts="2026-04-05T23:00:17+00:00",
            severity=None,
            src_ip=None,
            dst_ip=None,
            src_port=None,
            dst_port=None,
            protocol=None,
            fingerprint=None,
            payload={
                "event_type": "model_prediction",
                "attack_score": 0.9999,
                "predicted_label": "Attack",
                "is_alert": True,
                "passthrough": {
                    "transport_family": "tcp",
                    "source_flow_id": "192.168.117.132:56619-192.168.117.128:830-00103",
                },
            },
        )

        alerts = list_alerts_for_triage(store, include_suppressed=True)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["src_ip"] == "192.168.117.132"
        assert alert["dst_ip"] == "192.168.117.128"
        assert alert["src_port"] == 56619
        assert alert["dst_port"] == 830
        assert alert["protocol"] == "tcp"
        assert alert["severity"] == "critical"
        assert alert["source_flow_id"] == "192.168.117.132:56619-192.168.117.128:830-00103"
        assert "192.168.117.132:56619 -> 192.168.117.128:830" in alert["flow_summary"]
    finally:
        store.close()


def test_list_alert_incidents_for_triage_groups_same_burst_into_single_incident(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        for idx, dst_port in enumerate((80, 443, 830), start=1):
            store.upsert_alert(
                source_event_id=f"scan-alert-{idx}",
                event_ts=f"2026-04-05T23:00:{10 + idx:02d}+00:00",
                severity=None,
                src_ip=None,
                dst_ip=None,
                src_port=None,
                dst_port=None,
                protocol=None,
                fingerprint=None,
                payload={
                    "event_type": "model_prediction",
                    "attack_score": 0.9999,
                    "predicted_label": "Attack",
                    "is_alert": True,
                    "passthrough": {
                        "transport_family": "tcp",
                        "source_flow_id": f"192.168.117.132:56619-192.168.117.128:{dst_port}-00{idx:03d}",
                    },
                },
            )

        incidents = list_alert_incidents_for_triage(store, include_suppressed=True)

        assert len(incidents) == 1
        incident = incidents[0]
        assert incident["incident_alert_count"] == 3
        assert incident["src_ip"] == "192.168.117.132"
        assert incident["dst_ip"] == "192.168.117.128"
        assert incident["incident_dst_ports"] == [80, 443, 830]
        assert incident["severity"] == "critical"
        assert incident["source_event_id"] == "192.168.117.132 -> 192.168.117.128 (3 alerts)"
        assert "tcp" in str(incident["incident_summary"]).lower()
    finally:
        store.close()
