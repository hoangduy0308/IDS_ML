from __future__ import annotations

from typing import Any
import json
from collections import defaultdict

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


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return str(value).strip() or None


def _normalize_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _severity_rank(value: str | None) -> int:
    normalized = (value or "unknown").strip().lower()
    order = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
        "unknown": 0,
    }
    return order.get(normalized, 0)


def _severity_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.995:
        return "critical"
    if score >= 0.9:
        return "high"
    if score >= 0.75:
        return "medium"
    if score >= 0.5:
        return "low"
    return None


def _parse_source_flow_id(source_flow_id: str | None) -> dict[str, Any]:
    if source_flow_id is None:
        return {}
    raw = str(source_flow_id).strip()
    if not raw:
        return {}
    try:
        flow_pair, sequence = raw.rsplit("-", 1)
        src_endpoint, dst_endpoint = flow_pair.split("-", 1)
        src_ip, src_port = src_endpoint.rsplit(":", 1)
        dst_ip, dst_port = dst_endpoint.rsplit(":", 1)
    except ValueError:
        return {}
    return {
        "source_flow_id": raw,
        "src_ip": src_ip.strip() or None,
        "src_port": _normalize_optional_int(src_port),
        "dst_ip": dst_ip.strip() or None,
        "dst_port": _normalize_optional_int(dst_port),
        "flow_sequence": sequence.strip() or None,
    }


def _port_summary(ip: str | None, ports: set[int]) -> str | None:
    normalized_ip = _normalize_optional_text(ip)
    if normalized_ip is None:
        return None
    if not ports:
        return normalized_ip
    ordered = sorted(ports)
    if len(ordered) == 1:
        return f"{normalized_ip}:{ordered[0]}"
    preview = ", ".join(str(port) for port in ordered[:4])
    remainder = len(ordered) - min(len(ordered), 4)
    if remainder > 0:
        return f"{normalized_ip} ({preview} +{remainder} more)"
    return f"{normalized_ip} ({preview})"


def _hydrate_alert_payload_fields(alert: dict[str, Any]) -> dict[str, Any]:
    payload = alert.get("payload")
    if not isinstance(payload, dict):
        payload = _decode_payload(alert.get("payload_json"))
    passthrough = payload.get("passthrough")
    passthrough = passthrough if isinstance(passthrough, dict) else {}

    flow_fields = _parse_source_flow_id(
        _normalize_optional_text(
            passthrough.get("source_flow_id")
            or payload.get("source_flow_id")
            or payload.get("flow_id")
        )
    )

    src_ip = (
        _normalize_optional_text(alert.get("src_ip"))
        or _normalize_optional_text(payload.get("src_ip"))
        or _normalize_optional_text(payload.get("source_ip"))
        or _normalize_optional_text(payload.get("Src IP"))
        or _normalize_optional_text(flow_fields.get("src_ip"))
    )
    dst_ip = (
        _normalize_optional_text(alert.get("dst_ip"))
        or _normalize_optional_text(payload.get("dst_ip"))
        or _normalize_optional_text(payload.get("destination_ip"))
        or _normalize_optional_text(payload.get("Dst IP"))
        or _normalize_optional_text(flow_fields.get("dst_ip"))
    )
    src_port = (
        _normalize_optional_int(alert.get("src_port"))
        or _normalize_optional_int(payload.get("src_port"))
        or _normalize_optional_int(payload.get("source_port"))
        or _normalize_optional_int(payload.get("Src Port"))
        or _normalize_optional_int(flow_fields.get("src_port"))
    )
    dst_port = (
        _normalize_optional_int(alert.get("dst_port"))
        or _normalize_optional_int(payload.get("dst_port"))
        or _normalize_optional_int(payload.get("destination_port"))
        or _normalize_optional_int(payload.get("Dst Port"))
        or _normalize_optional_int(flow_fields.get("dst_port"))
    )
    protocol = (
        _normalize_optional_text(alert.get("protocol"))
        or _normalize_optional_text(payload.get("protocol"))
        or _normalize_optional_text(payload.get("Protocol"))
        or _normalize_optional_text(passthrough.get("transport_family"))
    )
    attack_score = _normalize_optional_float(payload.get("attack_score") or payload.get("score"))
    severity = _normalize_optional_text(alert.get("severity")) or _severity_from_score(attack_score) or "unknown"
    predicted_label = _normalize_optional_text(payload.get("predicted_label"))
    attack_family = _normalize_optional_text(payload.get("attack_family"))
    family_status = _normalize_optional_text(payload.get("family_status"))
    fingerprint = (
        _normalize_optional_text(alert.get("fingerprint"))
        or _normalize_optional_text(payload.get("fingerprint"))
        or _normalize_optional_text(flow_fields.get("source_flow_id"))
    )

    hydrated = dict(alert)
    hydrated["payload"] = payload
    hydrated["src_ip"] = src_ip
    hydrated["dst_ip"] = dst_ip
    hydrated["src_port"] = src_port
    hydrated["dst_port"] = dst_port
    hydrated["protocol"] = protocol
    hydrated["severity"] = severity
    hydrated["attack_score"] = attack_score
    hydrated["predicted_label"] = predicted_label
    hydrated["fingerprint"] = fingerprint
    hydrated["source_flow_id"] = flow_fields.get("source_flow_id")
    hydrated["flow_sequence"] = flow_fields.get("flow_sequence")
    hydrated["family_status"] = family_status
    hydrated["attack_family"] = attack_family
    hydrated["flow_summary"] = (
        f"{src_ip or '?'}"
        f"{':' + str(src_port) if src_port is not None else ''}"
        f" -> {dst_ip or '?'}"
        f"{':' + str(dst_port) if dst_port is not None else ''}"
        f"{f' ({protocol.upper()})' if protocol else ''}"
    )
    return hydrated


def _incident_key(alert: dict[str, Any]) -> tuple[str, str, str, str]:
    src_ip = _normalize_optional_text(alert.get("src_ip"))
    dst_ip = _normalize_optional_text(alert.get("dst_ip"))
    protocol = _normalize_optional_text(alert.get("protocol"))
    event_ts = _normalize_optional_text(alert.get("event_ts")) or "unknown"
    bucket = event_ts[:16] if len(event_ts) >= 16 else event_ts
    if src_ip is None or dst_ip is None or protocol is None:
        return ("singleton", str(alert.get("id")), protocol or "unknown", bucket)
    return (src_ip, dst_ip, protocol.lower(), bucket)


def group_alerts_into_incidents(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for alert in alerts:
        grouped[_incident_key(alert)].append(alert)

    incidents: list[dict[str, Any]] = []
    for group_alerts in grouped.values():
        ordered = sorted(
            group_alerts,
            key=lambda alert: (
                str(alert.get("event_ts") or ""),
                int(alert.get("id") or 0),
            ),
            reverse=True,
        )
        latest = dict(ordered[0])
        if len(ordered) == 1:
            latest["incident_alert_count"] = 1
            latest["incident_dst_ports"] = [port for port in [latest.get("dst_port")] if port is not None]
            latest["incident_src_ports"] = [port for port in [latest.get("src_port")] if port is not None]
            latest["incident_label"] = latest.get("source_event_id") or f"alert-{latest.get('id')}"
            latest["incident_summary"] = latest.get("flow_summary")
            latest["latest_source_event_id"] = latest.get("source_event_id")
            incidents.append(latest)
            continue

        src_ports = {int(port) for port in (alert.get("src_port") for alert in ordered) if port is not None}
        dst_ports = {int(port) for port in (alert.get("dst_port") for alert in ordered) if port is not None}
        highest_severity = max(
            (_normalize_optional_text(alert.get("severity")) or "unknown" for alert in ordered),
            key=_severity_rank,
        )
        highest_score = max(
            (
                _normalize_optional_float(alert.get("attack_score"))
                for alert in ordered
                if _normalize_optional_float(alert.get("attack_score")) is not None
            ),
            default=None,
        )
        latest["incident_alert_count"] = len(ordered)
        latest["incident_src_ports"] = sorted(src_ports)
        latest["incident_dst_ports"] = sorted(dst_ports)
        latest["severity"] = highest_severity
        latest["attack_score"] = highest_score
        latest["incident_label"] = (
            f"{latest.get('src_ip') or '?'} -> {latest.get('dst_ip') or '?'} "
            f"({len(ordered)} alerts)"
        )
        protocol_fragment = ""
        if latest.get("protocol"):
            protocol_fragment = f" ({str(latest.get('protocol') or '').upper()})"
        latest["incident_summary"] = (
            f"{_port_summary(_normalize_optional_text(latest.get('src_ip')), src_ports) or '?'} "
            f"-> {_port_summary(_normalize_optional_text(latest.get('dst_ip')), dst_ports) or '?'}"
            f"{protocol_fragment}"
        )
        latest["source_event_ids"] = [
            str(alert.get("source_event_id") or f"alert-{alert.get('id')}")
            for alert in ordered
        ]
        latest["latest_source_event_id"] = str(
            latest.get("source_event_id") or f"alert-{latest.get('id')}"
        )
        latest["source_event_id"] = latest["incident_label"]
        incidents.append(latest)

    incidents.sort(
        key=lambda alert: (
            str(alert.get("event_ts") or ""),
            int(alert.get("id") or 0),
        ),
        reverse=True,
    )
    return incidents


def build_alert_family_view(alert: dict[str, Any]) -> dict[str, Any]:
    payload = alert.get("payload")
    if not isinstance(payload, dict):
        payload = _decode_payload(alert.get("payload_json"))

    family_status = _normalize_optional_text(payload.get("family_status"))
    if family_status is not None:
        family_status = family_status.lower()
    if family_status not in {"known", "unknown", "benign"}:
        family_status = None

    attack_family = _normalize_optional_text(payload.get("attack_family"))
    attack_family_confidence = _normalize_optional_float(payload.get("attack_family_confidence"))
    attack_family_margin = _normalize_optional_float(payload.get("attack_family_margin"))

    if family_status in {"known", "unknown", "benign"}:
        family_state = family_status
        legacy_unavailable = False
        if family_state == "benign":
            attack_family = None
            attack_family_confidence = None
            attack_family_margin = None
    else:
        family_state = "legacy_unavailable"
        legacy_unavailable = True
        attack_family = None
        attack_family_confidence = None
        attack_family_margin = None

    return {
        "family_status": family_status,
        "attack_family": attack_family,
        "attack_family_confidence": attack_family_confidence,
        "attack_family_margin": attack_family_margin,
        "family_state": family_state,
        "legacy_unavailable": legacy_unavailable,
    }


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
        alert = _hydrate_alert_payload_fields(dict(row))
        suppressed = is_alert_suppressed(store, alert=alert)
        alert["suppressed"] = suppressed
        family_view = build_alert_family_view(alert)
        alert["family"] = family_view
        alert["family_status"] = family_view["family_status"]
        alert["attack_family"] = family_view["attack_family"]
        alert["attack_family_confidence"] = family_view["attack_family_confidence"]
        alert["attack_family_margin"] = family_view["attack_family_margin"]
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


def list_alert_incidents_for_triage(
    store: OperatorStore,
    *,
    limit: int = 100,
    triage_status: str | None = None,
    include_suppressed: bool = False,
) -> list[dict[str, Any]]:
    alerts = list_alerts_for_triage(
        store,
        limit=max(limit * 10, limit),
        triage_status=triage_status,
        include_suppressed=include_suppressed,
    )
    return group_alerts_into_incidents(alerts)[:limit]


def list_alert_incidents_for_notification(
    store: OperatorStore,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    alerts = list_alerts_for_notification(store, limit=max(limit * 10, limit))
    return group_alerts_into_incidents(alerts)[:limit]


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
