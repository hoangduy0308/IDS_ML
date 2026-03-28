from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console.alerts import (  # noqa: E402
    add_investigation_note,
    get_alert_timeline,
    list_alerts_for_notification,
    list_alerts_for_triage,
    load_console_snapshot,
    transition_alert_status,
)
from scripts.ids_operator_console.db import OperatorStore  # noqa: E402


def _new_store(tmp_path: Path) -> OperatorStore:
    return OperatorStore.open(tmp_path / "operator_console.db")


def _seed_alert(
    store: OperatorStore,
    *,
    source_event_id: str,
    src_ip: str,
    severity: str = "high",
) -> int:
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
        payload={"event_type": "model_prediction", "src_ip": src_ip, "score": 0.99},
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

