from __future__ import annotations

from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console.db import OperatorStore  # noqa: E402
from scripts.ids_operator_console.notification_runtime import (  # noqa: E402
    NotificationRuntimeConfig,
    run_notification_maintenance_cycle,
    run_notification_worker,
)
from scripts.ids_operator_console.notifications import (  # noqa: E402
    NotificationDeliveryError,
    TelegramNotifierConfig,
)


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _build_runtime_config(tmp_path: Path, *, telegram: TelegramNotifierConfig | None) -> NotificationRuntimeConfig:
    return NotificationRuntimeConfig(
        database_path=tmp_path / "operator_console.db",
        alerts_input_path=tmp_path / "ids_live_alerts.jsonl",
        quarantine_input_path=tmp_path / "ids_live_quarantine.jsonl",
        summary_input_path=tmp_path / "ids_live_sensor_summary.jsonl",
        telegram=telegram,
        worker_poll_interval_seconds=0.01,
    )


def test_run_notification_maintenance_cycle_orders_ingest_queue_and_dispatch(tmp_path: Path) -> None:
    runtime_config = _build_runtime_config(
        tmp_path,
        telegram=TelegramNotifierConfig(
            bot_token="token",
            default_chat_id="-100runtime",
            max_attempts=3,
            base_backoff_seconds=1,
        ),
    )
    _append_jsonl(
        runtime_config.alerts_input_path,
        {
            "event_type": "model_prediction",
            "source_event_id": "runtime-alert-1",
            "timestamp": "2026-03-28T15:00:00+00:00",
            "severity": "high",
            "src_ip": "10.1.0.5",
            "dst_ip": "10.1.0.7",
            "src_port": 443,
            "dst_port": 50505,
            "protocol": "tcp",
            "is_alert": True,
            "attack_score": 0.98,
        },
    )

    result = run_notification_maintenance_cycle(
        runtime_config,
        sender=lambda _cfg, _chat_id, _text: "telegram-runtime-1",
    )

    assert result.ingest.alerts_ingested == 1
    assert result.queued == 1
    assert result.dispatch.scanned == 1
    assert result.dispatch.sent == 1
    assert result.dispatch.retried == 0
    assert result.dispatch.failed == 0
    assert result.status.enabled is True
    assert result.status.sent_count == 1
    assert result.status.pending_count == 0
    assert result.status.failed_count == 0


def test_run_notification_maintenance_cycle_disabled_mode_skips_queue_growth(tmp_path: Path) -> None:
    runtime_config = _build_runtime_config(tmp_path, telegram=None)
    _append_jsonl(
        runtime_config.alerts_input_path,
        {
            "event_type": "model_prediction",
            "source_event_id": "runtime-disabled-1",
            "timestamp": "2026-03-28T15:05:00+00:00",
            "severity": "medium",
            "src_ip": "10.2.0.5",
            "dst_ip": "10.2.0.7",
            "is_alert": True,
        },
    )

    result = run_notification_maintenance_cycle(runtime_config)
    store = OperatorStore.open(runtime_config.database_path)
    try:
        deliveries = store._connection.execute("SELECT COUNT(*) AS count FROM notification_deliveries").fetchone()  # noqa: SLF001
    finally:
        store.close()

    assert result.ingest.alerts_ingested == 1
    assert result.queued == 0
    assert result.dispatch.scanned == 0
    assert result.dispatch.sent == 0
    assert result.status.enabled is False
    assert result.status.configured is False
    assert deliveries is not None
    assert int(deliveries["count"]) == 0


def test_run_notification_worker_reuses_persisted_retry_state_across_iterations(tmp_path: Path) -> None:
    runtime_config = _build_runtime_config(
        tmp_path,
        telegram=TelegramNotifierConfig(
            bot_token="token",
            default_chat_id="-100retry",
            max_attempts=3,
            base_backoff_seconds=1,
        ),
    )
    _append_jsonl(
        runtime_config.alerts_input_path,
        {
            "event_type": "model_prediction",
            "source_event_id": "runtime-retry-1",
            "timestamp": "2026-03-28T15:10:00+00:00",
            "severity": "high",
            "src_ip": "10.3.0.5",
            "dst_ip": "10.3.0.7",
            "is_alert": True,
        },
    )

    attempts = {"count": 0}
    sleep_calls: list[float] = []

    def flaky_sender(_cfg: TelegramNotifierConfig, _chat_id: str, _text: str) -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise NotificationDeliveryError("temporary outage", retryable=True, retry_after_seconds=0)
        return "telegram-runtime-2"

    def release_retry_backoff(_seconds: float) -> None:
        sleep_calls.append(_seconds)
        store = OperatorStore.open(runtime_config.database_path)
        try:
            store._connection.execute(  # noqa: SLF001
                """
                UPDATE notification_deliveries
                SET next_attempt_at = '1970-01-01T00:00:00+00:00'
                WHERE dedupe_key = 'runtime-retry-1'
                """
            )
            store._connection.commit()  # noqa: SLF001
        finally:
            store.close()

    results = run_notification_worker(
        runtime_config,
        iterations=2,
        sender=flaky_sender,
        sleep_fn=release_retry_backoff,
    )
    store = OperatorStore.open(runtime_config.database_path)
    try:
        delivery = store._connection.execute(  # noqa: SLF001
            """
            SELECT status, attempt_count, provider_message_id
            FROM notification_deliveries
            WHERE dedupe_key = 'runtime-retry-1'
            """
        ).fetchone()
    finally:
        store.close()

    assert len(results) == 2
    assert results[0].dispatch.retried == 1
    assert results[1].dispatch.sent == 1
    assert delivery is not None
    assert delivery["status"] == "sent"
    assert int(delivery["attempt_count"]) == 2
    assert delivery["provider_message_id"] == "telegram-runtime-2"
    assert sleep_calls == [runtime_config.worker_poll_interval_seconds]


def test_run_notification_worker_honors_poll_interval_between_iterations(tmp_path: Path) -> None:
    runtime_config = _build_runtime_config(tmp_path, telegram=None)
    sleep_calls: list[float] = []

    results = run_notification_worker(
        runtime_config,
        iterations=3,
        sleep_fn=sleep_calls.append,
    )

    assert len(results) == 3
    assert sleep_calls == [
        runtime_config.worker_poll_interval_seconds,
        runtime_config.worker_poll_interval_seconds,
    ]
