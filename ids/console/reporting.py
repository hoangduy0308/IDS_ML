from __future__ import annotations

from collections import Counter
from typing import Any
import json

from .alerts import list_alerts_for_triage
from .db import OperatorStore


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


def export_alert_rows(
    store: OperatorStore,
    *,
    limit: int = 500,
    triage_status: str | None = None,
    include_suppressed: bool = False,
) -> list[dict[str, Any]]:
    alerts = list_alerts_for_triage(
        store,
        limit=limit,
        triage_status=triage_status,
        include_suppressed=include_suppressed,
    )

    exported: list[dict[str, Any]] = []
    for alert in alerts:
        exported.append(
            {
                "id": alert["id"],
                "sensor_id": alert["sensor_id"],
                "source_event_id": alert.get("source_event_id"),
                "event_ts": alert["event_ts"],
                "severity": alert.get("severity"),
                "triage_status": alert["triage_status"],
                "suppressed": bool(alert.get("suppressed", False)),
                "src_ip": alert.get("src_ip"),
                "dst_ip": alert.get("dst_ip"),
                "protocol": alert.get("protocol"),
                "payload": alert.get("payload", _decode_payload(alert.get("payload_json"))),
            }
        )
    return exported


def export_anomaly_rows(
    store: OperatorStore,
    *,
    limit: int = 500,
    include_payload: bool = False,
) -> list[dict[str, Any]]:
    anomalies = store.list_anomalies(limit=limit)
    exported: list[dict[str, Any]] = []
    for row in anomalies:
        base = {
            "id": row["id"],
            "sensor_id": row["sensor_id"],
            "source_event_id": row.get("source_event_id"),
            "event_ts": row["event_ts"],
            "anomaly_type": row["anomaly_type"],
            "reason": row.get("reason"),
            "redacted_summary": row.get("redacted_summary"),
        }
        if include_payload:
            base["payload"] = _decode_payload(row.get("payload_json"))
        exported.append(base)
    return exported


def export_summary_rows(
    store: OperatorStore,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    summaries = store.list_recent_summaries(limit=limit)
    exported: list[dict[str, Any]] = []
    for row in summaries:
        exported.append(
            {
                "id": row["id"],
                "sensor_id": row["sensor_id"],
                "summary_ts": row["summary_ts"],
                "payload": _decode_payload(row.get("payload_json")),
            }
        )
    return exported


def build_report_bundle(
    store: OperatorStore,
    *,
    alert_limit: int = 500,
    anomaly_limit: int = 500,
    summary_limit: int = 200,
    triage_status: str | None = None,
    include_suppressed_alerts: bool = False,
    include_anomaly_payload: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "alerts": export_alert_rows(
            store,
            limit=alert_limit,
            triage_status=triage_status,
            include_suppressed=include_suppressed_alerts,
        ),
        "anomalies": export_anomaly_rows(
            store,
            limit=anomaly_limit,
            include_payload=include_anomaly_payload,
        ),
        "summaries": export_summary_rows(store, limit=summary_limit),
    }


def build_report_rollup(report_bundle: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    alerts = report_bundle.get("alerts", [])
    anomalies = report_bundle.get("anomalies", [])
    summaries = report_bundle.get("summaries", [])

    status_counter = Counter(str(row.get("triage_status", "unknown")) for row in alerts)
    severity_counter = Counter(str(row.get("severity", "unknown")) for row in alerts)

    return {
        "alerts_total": len(alerts),
        "alerts_by_status": dict(status_counter),
        "alerts_by_severity": dict(severity_counter),
        "anomalies_total": len(anomalies),
        "summaries_total": len(summaries),
        "latest_summary_ts": summaries[0]["summary_ts"] if summaries else None,
    }

