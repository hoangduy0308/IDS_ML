from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request
import json

from .alerts import list_alert_incidents_for_notification
from .db import OperatorStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _decode_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return dict(raw_payload)
    if isinstance(raw_payload, str):
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


@dataclass(frozen=True)
class TelegramNotifierConfig:
    bot_token: str
    default_chat_id: str
    api_base_url: str = "https://api.telegram.org"
    request_timeout_seconds: float = 10.0
    max_attempts: int = 5
    base_backoff_seconds: int = 30

    def __post_init__(self) -> None:
        if not self.bot_token.strip():
            raise ValueError("bot_token must not be blank")
        if not self.default_chat_id.strip():
            raise ValueError("default_chat_id must not be blank")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be > 0")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_backoff_seconds < 1:
            raise ValueError("base_backoff_seconds must be >= 1")


@dataclass(frozen=True)
class NotificationDispatchSummary:
    queued: int
    sent: int
    retried: int
    failed: int
    scanned: int


class NotificationDeliveryError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


TelegramSender = Callable[[TelegramNotifierConfig, str, str], str]


def _format_score_fragment(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return "n/a"


def build_alert_notification_text(alert: Mapping[str, Any]) -> str:
    payload = _decode_payload(alert.get("payload"))
    if not payload:
        payload = _decode_payload(alert.get("payload_json"))

    source_event_id = str(
        alert.get("latest_source_event_id")
        or alert.get("source_event_id")
        or f"alert-{alert.get('id')}"
    )
    severity = str(alert.get("severity") or "unknown").upper()
    event_ts = str(alert.get("event_ts") or payload.get("timestamp") or "unknown")
    src_ip = str(alert.get("src_ip") or payload.get("src_ip") or "n/a")
    dst_ip = str(alert.get("dst_ip") or payload.get("dst_ip") or "n/a")
    src_port = alert.get("src_port")
    dst_port = alert.get("dst_port")
    protocol = str(alert.get("protocol") or payload.get("protocol") or "n/a").upper()
    incident_count = int(alert.get("incident_alert_count") or 1)
    incident_summary = str(alert.get("incident_summary") or f"{src_ip} -> {dst_ip}")
    predicted_label = str(alert.get("predicted_label") or payload.get("predicted_label") or "unknown")
    attack_family = str(alert.get("attack_family") or payload.get("attack_family") or "unknown")
    dst_ports = alert.get("incident_dst_ports")
    score = payload.get("attack_score", payload.get("score"))
    score_fragment = _format_score_fragment(alert.get("attack_score") or score)

    if incident_count > 1:
        port_preview = ""
        if isinstance(dst_ports, list) and dst_ports:
            shown = ", ".join(str(port) for port in dst_ports[:6])
            remainder = len(dst_ports) - min(len(dst_ports), 6)
            port_preview = f"\ndst_ports={shown}" + (f" +{remainder} more" if remainder > 0 else "")
        return (
            "[IDS ALERT BURST]\n"
            f"incident={source_event_id}\n"
            f"severity={severity}\n"
            f"alerts={incident_count}\n"
            f"flow={incident_summary}\n"
            f"protocol={protocol}\n"
            f"score_max={score_fragment}"
            f"{port_preview}\n"
            f"timestamp={event_ts}"
        )

    src_fragment = f"{src_ip}:{src_port}" if src_port is not None else src_ip
    dst_fragment = f"{dst_ip}:{dst_port}" if dst_port is not None else dst_ip
    return (
        "[IDS ALERT]\n"
        f"event={source_event_id}\n"
        f"severity={severity}\n"
        f"flow={src_fragment} -> {dst_fragment}\n"
        f"protocol={protocol}\n"
        f"label={predicted_label}\n"
        f"family={attack_family}\n"
        f"score={score_fragment}\n"
        f"timestamp={event_ts}"
    )


def _alert_dedupe_key(alert: Mapping[str, Any]) -> str:
    if int(alert.get("incident_alert_count") or 1) > 1:
        src_ip = str(alert.get("src_ip") or "unknown-src")
        dst_ip = str(alert.get("dst_ip") or "unknown-dst")
        protocol = str(alert.get("protocol") or "unknown-proto").lower()
        bucket = str(alert.get("event_ts") or "unknown-ts")[:16]
        return f"incident:{src_ip}:{dst_ip}:{protocol}:{bucket}"
    fingerprint = alert.get("fingerprint")
    if fingerprint:
        bucket = str(alert.get("event_ts") or "unknown-ts")[:16]
        return f"flow:{fingerprint}:{bucket}"
    source_event_id = alert.get("source_event_id")
    if source_event_id:
        return str(source_event_id)
    return f"alert-id:{alert.get('id')}"


def queue_alert_notifications(
    store: OperatorStore,
    *,
    chat_id: str,
    limit: int = 100,
) -> int:
    if not chat_id.strip():
        raise ValueError("chat_id must not be blank")

    alerts = list_alert_incidents_for_notification(store, limit=limit)
    queued = 0
    for alert in alerts:
        payload = {
            "text": build_alert_notification_text(alert),
            "source_event_id": alert.get("source_event_id"),
            "triage_status": alert.get("triage_status"),
            "event_ts": alert.get("event_ts"),
        }
        store.save_notification_delivery(
            alert_id=int(alert["id"]),
            channel="telegram",
            target=chat_id,
            dedupe_key=_alert_dedupe_key(alert),
            payload=payload,
            status="pending",
        )
        queued += 1
    return queued


def _extract_retry_after_seconds(error_payload: dict[str, Any]) -> int | None:
    parameters = error_payload.get("parameters")
    if not isinstance(parameters, dict):
        return None
    retry_after = parameters.get("retry_after")
    if isinstance(retry_after, int) and retry_after > 0:
        return retry_after
    if isinstance(retry_after, str) and retry_after.strip().isdigit():
        return int(retry_after)
    return None


def send_telegram_message(
    config: TelegramNotifierConfig,
    *,
    chat_id: str,
    text: str,
) -> str:
    if not chat_id.strip():
        raise NotificationDeliveryError("chat_id must not be blank", retryable=False)
    if not text.strip():
        raise NotificationDeliveryError("text must not be blank", retryable=False)

    url = f"{config.api_base_url.rstrip('/')}/bot{config.bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    raw_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib_request.Request(
        url=url,
        data=raw_data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib_request.urlopen(request, timeout=config.request_timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed_error = json.loads(raw_body)
            retry_after_seconds = _extract_retry_after_seconds(parsed_error)
        except json.JSONDecodeError:
            parsed_error = {}
            retry_after_seconds = None

        if exc.code in {429, 500, 502, 503, 504}:
            raise NotificationDeliveryError(
                f"telegram send failed with HTTP {exc.code}",
                retryable=True,
                retry_after_seconds=retry_after_seconds,
            ) from exc
        raise NotificationDeliveryError(
            f"telegram send rejected with HTTP {exc.code}",
            retryable=False,
            retry_after_seconds=retry_after_seconds,
        ) from exc
    except urllib_error.URLError as exc:
        raise NotificationDeliveryError(
            f"telegram send failed: {exc.reason}",
            retryable=True,
        ) from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise NotificationDeliveryError(
            "telegram response is not valid JSON",
            retryable=True,
        ) from exc

    if not isinstance(parsed, dict):
        raise NotificationDeliveryError("telegram response payload is invalid", retryable=True)
    if bool(parsed.get("ok")) is not True:
        retry_after_seconds = _extract_retry_after_seconds(parsed)
        raise NotificationDeliveryError(
            str(parsed.get("description") or "telegram rejected request"),
            retryable=bool(retry_after_seconds),
            retry_after_seconds=retry_after_seconds,
        )

    result = parsed.get("result")
    if not isinstance(result, dict):
        raise NotificationDeliveryError("telegram response missing result payload", retryable=True)
    message_id = result.get("message_id")
    if isinstance(message_id, int):
        return str(message_id)
    if isinstance(message_id, str) and message_id.strip():
        return message_id
    raise NotificationDeliveryError("telegram response missing message_id", retryable=True)


def _next_attempt_ts(
    *,
    base_backoff_seconds: int,
    current_attempt_count: int,
    retry_after_seconds: int | None,
) -> str:
    if retry_after_seconds is not None and retry_after_seconds > 0:
        delay_seconds = retry_after_seconds
    else:
        exponent = max(current_attempt_count - 1, 0)
        delay_seconds = min(base_backoff_seconds * (2**exponent), 3600)
    return (_utc_now() + timedelta(seconds=delay_seconds)).replace(microsecond=0).isoformat()


def dispatch_pending_telegram_notifications(
    store: OperatorStore,
    *,
    config: TelegramNotifierConfig,
    limit: int = 100,
    sender: TelegramSender | None = None,
) -> NotificationDispatchSummary:
    pending = store.list_pending_notification_deliveries(
        channel="telegram",
        as_of_ts=_utc_now_iso(),
        limit=limit,
    )
    sent = 0
    retried = 0
    failed = 0
    sender_fn = sender or (lambda cfg, chat_id, text: send_telegram_message(cfg, chat_id=chat_id, text=text))

    for delivery in pending:
        delivery_id = int(delivery["id"])
        payload = _decode_payload(delivery.get("payload_json"))
        chat_id = str(delivery.get("target") or config.default_chat_id)
        text = str(payload.get("text", "")).strip()
        attempt_count = int(delivery.get("attempt_count", 0))

        try:
            message_id = sender_fn(config, chat_id, text)
        except NotificationDeliveryError as exc:
            next_attempt_count = attempt_count + 1
            if exc.retryable and next_attempt_count < config.max_attempts:
                next_attempt_at = _next_attempt_ts(
                    base_backoff_seconds=config.base_backoff_seconds,
                    current_attempt_count=next_attempt_count,
                    retry_after_seconds=exc.retry_after_seconds,
                )
                store.mark_notification_attempt(
                    delivery_id=delivery_id,
                    status="retry",
                    last_error=str(exc),
                    next_attempt_at=next_attempt_at,
                )
                retried += 1
            else:
                store.mark_notification_attempt(
                    delivery_id=delivery_id,
                    status="failed",
                    last_error=str(exc),
                    next_attempt_at=None,
                )
                failed += 1
            continue
        except Exception as exc:
            next_attempt_count = attempt_count + 1
            if next_attempt_count < config.max_attempts:
                next_attempt_at = _next_attempt_ts(
                    base_backoff_seconds=config.base_backoff_seconds,
                    current_attempt_count=next_attempt_count,
                    retry_after_seconds=None,
                )
                store.mark_notification_attempt(
                    delivery_id=delivery_id,
                    status="retry",
                    last_error=f"unexpected sender error: {exc}",
                    next_attempt_at=next_attempt_at,
                )
                retried += 1
            else:
                store.mark_notification_attempt(
                    delivery_id=delivery_id,
                    status="failed",
                    last_error=f"unexpected sender error: {exc}",
                    next_attempt_at=None,
                )
                failed += 1
            continue

        store.mark_notification_attempt(
            delivery_id=delivery_id,
            status="sent",
            last_error=None,
            next_attempt_at=None,
            provider_message_id=message_id,
        )
        sent += 1

    return NotificationDispatchSummary(
        queued=0,
        sent=sent,
        retried=retried,
        failed=failed,
        scanned=len(pending),
    )


def queue_and_dispatch_notifications(
    store: OperatorStore,
    *,
    config: TelegramNotifierConfig,
    limit: int = 100,
    sender: TelegramSender | None = None,
) -> NotificationDispatchSummary:
    queued = queue_alert_notifications(store, chat_id=config.default_chat_id, limit=limit)
    dispatched = dispatch_pending_telegram_notifications(store, config=config, limit=limit, sender=sender)
    return NotificationDispatchSummary(
        queued=queued,
        sent=dispatched.sent,
        retried=dispatched.retried,
        failed=dispatched.failed,
        scanned=dispatched.scanned,
    )


def redrive_failed_telegram_notifications(
    store: OperatorStore,
    *,
    limit: int = 100,
) -> int:
    return store.redrive_failed_notification_deliveries(channel="telegram", limit=limit)


__all__ = [
    "NotificationDeliveryError",
    "NotificationDispatchSummary",
    "TelegramNotifierConfig",
    "build_alert_notification_text",
    "dispatch_pending_telegram_notifications",
    "queue_alert_notifications",
    "queue_and_dispatch_notifications",
    "redrive_failed_telegram_notifications",
    "send_telegram_message",
]
