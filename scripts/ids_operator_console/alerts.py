from __future__ import annotations

from typing import Any
import json

from .db import OperatorStore


ALERT_TRIAGE_STATES = (
    "new",
    "acknowledged",
    "investigating",
    "resolved",
    "false_positive",
)


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ALERT_TRIAGE_STATES:
        raise ValueError(
            "invalid triage status "
            f"{value!r}; expected one of: {', '.join(ALERT_TRIAGE_STATES)}"
        )
    return normalized


def _decode_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return dict(raw_payload)
    if isinstance(raw_payload, str):
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def transition_alert_status(
    store: OperatorStore,
    *,
    alert_id: int,
    to_status: str,
    changed_by: str = "admin",
) -> dict[str, Any]:
    normalized = _normalize_status(to_status)
    return store.update_alert_status(alert_id=alert_id, to_status=normalized, changed_by=changed_by)


def add_investigation_note(
    store: OperatorStore,
    *,
    alert_id: int,
    note_text: str,
    author: str = "admin",
) -> dict[str, Any]:
    note_id = store.add_alert_note(alert_id=alert_id, note_text=note_text, author=author)
    notes = store.list_alert_notes(alert_id=alert_id)
    for note in notes:
        if int(note["id"]) == note_id:
            return note
    raise RuntimeError("note insert succeeded but inserted note could not be read back")


def get_alert_timeline(store: OperatorStore, *, alert_id: int) -> dict[str, list[dict[str, Any]]]:
    return {
        "notes": store.list_alert_notes(alert_id=alert_id),
        "status_history": store.list_alert_status_history(alert_id=alert_id),
    }


def _matches_suppression_rule(alert: dict[str, Any], rule: dict[str, Any]) -> bool:
    match_field = str(rule.get("match_field", "")).strip()
    match_value = str(rule.get("match_value", "")).strip()
    if not match_field or not match_value:
        return False

    payload = _decode_payload(alert.get("payload_json"))
    if match_field in alert and alert.get(match_field) is not None:
        candidate = alert.get(match_field)
    else:
        candidate = payload.get(match_field)
    if candidate is None:
        return False
    return str(candidate) == match_value


def is_alert_suppressed(store: OperatorStore, *, alert: dict[str, Any]) -> bool:
    rules = store.list_active_suppression_rules(applies_to="model_alert")
    for rule in rules:
        if _matches_suppression_rule(alert, rule):
            return True
    return False


def list_alerts_for_triage(
    store: OperatorStore,
    *,
    limit: int = 100,
    triage_status: str | None = None,
    include_suppressed: bool = False,
) -> list[dict[str, Any]]:
    status_filter = _normalize_status(triage_status) if triage_status is not None else None
    rows = store.list_alerts(limit=limit, triage_status=status_filter)

    hydrated: list[dict[str, Any]] = []
    for row in rows:
        alert = dict(row)
        suppressed = is_alert_suppressed(store, alert=alert)
        alert["suppressed"] = suppressed
        alert["payload"] = _decode_payload(alert.get("payload_json"))
        if include_suppressed or not suppressed:
            hydrated.append(alert)
    return hydrated


def list_alerts_for_notification(
    store: OperatorStore,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    candidates = list_alerts_for_triage(store, limit=limit, include_suppressed=False)
    return [alert for alert in candidates if alert.get("triage_status") not in {"resolved", "false_positive"}]


def load_console_snapshot(
    store: OperatorStore,
    *,
    alert_limit: int = 100,
    anomaly_limit: int = 100,
    summary_limit: int = 20,
    include_suppressed_alerts: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "alerts": list_alerts_for_triage(
            store,
            limit=alert_limit,
            include_suppressed=include_suppressed_alerts,
        ),
        "anomalies": store.list_anomalies(limit=anomaly_limit),
        "summaries": store.list_recent_summaries(limit=summary_limit),
    }

