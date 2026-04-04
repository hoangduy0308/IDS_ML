from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Callable

from .config import OperatorConsoleConfig
from .db import DEFAULT_SENSOR_ID, OperatorStore, open_operator_store
from .ingest import IngestRunSummary, ingest_sensor_outputs_once
from .notifications import (
    NotificationDispatchSummary,
    TelegramNotifierConfig,
    TelegramSender,
    dispatch_pending_telegram_notifications,
    queue_alert_notifications,
)


def _zero_dispatch_summary() -> NotificationDispatchSummary:
    return NotificationDispatchSummary(queued=0, sent=0, retried=0, failed=0, scanned=0)


@dataclass(frozen=True)
class NotificationRuntimeConfig:
    database_path: Path
    alerts_input_path: Path
    quarantine_input_path: Path
    summary_input_path: Path
    telegram: TelegramNotifierConfig | None
    sensor_id: str = DEFAULT_SENSOR_ID
    queue_limit: int = 100
    dispatch_limit: int = 100
    worker_poll_interval_seconds: float = 30.0

    @property
    def notifications_enabled(self) -> bool:
        return self.telegram is not None

    @classmethod
    def from_operator_console_config(
        cls,
        config: OperatorConsoleConfig,
        *,
        queue_limit: int = 100,
        dispatch_limit: int = 100,
        worker_poll_interval_seconds: float = 30.0,
    ) -> "NotificationRuntimeConfig":
        telegram_config: TelegramNotifierConfig | None = None
        if config.telegram_bot_token is not None and config.telegram_chat_id is not None:
            telegram_config = TelegramNotifierConfig(
                bot_token=config.telegram_bot_token,
                default_chat_id=config.telegram_chat_id,
            )
        return cls(
            database_path=config.database_path,
            alerts_input_path=config.alerts_input_path,
            quarantine_input_path=config.quarantine_input_path,
            summary_input_path=config.summary_input_path,
            telegram=telegram_config,
            queue_limit=queue_limit,
            dispatch_limit=dispatch_limit,
            worker_poll_interval_seconds=worker_poll_interval_seconds,
        )


@dataclass(frozen=True)
class NotificationRuntimeStatus:
    enabled: bool
    configured: bool
    channel: str
    target: str | None
    pending_count: int
    retry_count: int
    failed_count: int
    sent_count: int
    due_count: int
    oldest_due_at: str | None
    last_error: dict[str, str] | None


@dataclass(frozen=True)
class NotificationMaintenanceCycleResult:
    ingest: IngestRunSummary
    queued: int
    dispatch: NotificationDispatchSummary
    status: NotificationRuntimeStatus


def build_notification_runtime_status(
    store: OperatorStore,
    *,
    runtime_config: NotificationRuntimeConfig,
    resolved_telegram: TelegramNotifierConfig | None = None,
    channel: str = "telegram",
) -> NotificationRuntimeStatus:
    effective_telegram = resolved_telegram if resolved_telegram is not None else runtime_config.telegram
    summary = store.get_notification_delivery_summary(channel=channel)
    last_error = summary.get("last_error")
    normalized_last_error = None
    if isinstance(last_error, dict):
        normalized_last_error = {
            "status": str(last_error.get("status") or ""),
            "message": str(last_error.get("last_error") or ""),
            "updated_at": str(last_error.get("updated_at") or ""),
        }
    return NotificationRuntimeStatus(
        enabled=effective_telegram is not None,
        configured=effective_telegram is not None,
        channel=channel,
        target=effective_telegram.default_chat_id if effective_telegram is not None else None,
        pending_count=int(summary["pending_count"]),
        retry_count=int(summary["retry_count"]),
        failed_count=int(summary["failed_count"]),
        sent_count=int(summary["sent_count"]),
        due_count=int(summary["due_count"]),
        oldest_due_at=summary.get("oldest_due_at"),
        last_error=normalized_last_error,
    )


def resolve_telegram_config(
    store: OperatorStore,
    fallback: TelegramNotifierConfig | None,
) -> TelegramNotifierConfig | None:
    """Resolve effective Telegram config: DB wins over env fallback.

    Returns the resolved config or None.  For source information, use
    :func:`resolve_telegram_config_with_source`.
    """
    config, _source = resolve_telegram_config_with_source(store, fallback)
    return config


def resolve_telegram_config_with_source(
    store: OperatorStore,
    fallback: TelegramNotifierConfig | None,
) -> tuple[TelegramNotifierConfig | None, str]:
    """Resolve effective Telegram config and report its source.

    Returns ``(config_or_none, source)`` where *source* is one of
    ``"database"``, ``"environment"``, or ``"none"``.
    """
    db_token = store.get_setting("telegram_bot_token")
    db_chat_id = store.get_setting("telegram_chat_id")
    if db_token and db_token.strip() and db_chat_id and db_chat_id.strip():
        try:
            return (
                TelegramNotifierConfig(
                    bot_token=db_token,
                    default_chat_id=db_chat_id,
                ),
                "database",
            )
        except ValueError:
            pass  # fall through to fallback
    if fallback is not None:
        return fallback, "environment"
    return None, "none"


def run_notification_maintenance_cycle(
    runtime_config: NotificationRuntimeConfig,
    *,
    store: OperatorStore | None = None,
    sender: TelegramSender | None = None,
    ingest_once: Callable[..., IngestRunSummary] = ingest_sensor_outputs_once,
    queue_fn: Callable[..., int] = queue_alert_notifications,
    dispatch_fn: Callable[..., NotificationDispatchSummary] = dispatch_pending_telegram_notifications,
) -> NotificationMaintenanceCycleResult:
    owns_store = store is None
    active_store = store or open_operator_store(runtime_config.database_path)
    try:
        ingest_summary = ingest_once(
            store=active_store,
            alerts_input_path=runtime_config.alerts_input_path,
            quarantine_input_path=runtime_config.quarantine_input_path,
            summary_input_path=runtime_config.summary_input_path,
            sensor_id=runtime_config.sensor_id,
        )

        resolved_telegram = resolve_telegram_config(active_store, runtime_config.telegram)

        queued = 0
        dispatch_summary = _zero_dispatch_summary()
        if resolved_telegram is not None:
            queued = queue_fn(
                active_store,
                chat_id=resolved_telegram.default_chat_id,
                limit=runtime_config.queue_limit,
            )
            dispatch_summary = dispatch_fn(
                active_store,
                config=resolved_telegram,
                limit=runtime_config.dispatch_limit,
                sender=sender,
            )
        status = build_notification_runtime_status(
            active_store, runtime_config=runtime_config, resolved_telegram=resolved_telegram,
        )
        return NotificationMaintenanceCycleResult(
            ingest=ingest_summary,
            queued=queued,
            dispatch=dispatch_summary,
            status=status,
        )
    finally:
        if owns_store:
            active_store.close()


def run_notification_worker(
    runtime_config: NotificationRuntimeConfig,
    *,
    iterations: int | None = None,
    sender: TelegramSender | None = None,
    sleep_fn: Callable[[float], None] = sleep,
) -> list[NotificationMaintenanceCycleResult]:
    collect_results = iterations is not None
    results: list[NotificationMaintenanceCycleResult] = []
    completed = 0
    while iterations is None or completed < iterations:
        result = run_notification_maintenance_cycle(runtime_config, sender=sender)
        if collect_results:
            results.append(result)
        completed += 1
        if iterations is not None and completed >= iterations:
            break
        sleep_fn(runtime_config.worker_poll_interval_seconds)
    return results


__all__ = [
    "NotificationMaintenanceCycleResult",
    "NotificationRuntimeConfig",
    "NotificationRuntimeStatus",
    "build_notification_runtime_status",
    "resolve_telegram_config",
    "resolve_telegram_config_with_source",
    "run_notification_maintenance_cycle",
    "run_notification_worker",
]
