from __future__ import annotations

from pathlib import Path

import pytest

from ids.console.db import OperatorStore  # noqa: E402
from ids.console.notifications import (  # noqa: E402
    NotificationDeliveryError,
    TelegramNotifierConfig,
    dispatch_pending_telegram_notifications,
    queue_alert_notifications,
    redrive_failed_telegram_notifications,
)
from ids.console.notification_runtime import (  # noqa: E402
    resolve_telegram_config,
    resolve_telegram_config_with_source,
)


def _new_store(tmp_path: Path) -> OperatorStore:
    return OperatorStore.open(tmp_path / "operator_console.db")


def _seed_alert(store: OperatorStore, *, source_event_id: str, src_ip: str) -> int:
    return store.upsert_alert(
        source_event_id=source_event_id,
        event_ts="2026-03-28T16:00:00+00:00",
        severity="high",
        src_ip=src_ip,
        dst_ip="192.168.10.5",
        src_port=443,
        dst_port=51234,
        protocol="tcp",
        payload={"event_type": "model_prediction", "src_ip": src_ip, "attack_score": 0.91, "is_alert": True},
    )


def test_queue_alert_notifications_respects_suppression_and_dedupes(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        _seed_alert(store, source_event_id="alert-1", src_ip="10.0.0.1")
        _seed_alert(store, source_event_id="alert-2", src_ip="10.0.0.2")
        store.create_suppression_rule(
            rule_name="suppress trusted src",
            match_field="src_ip",
            match_value="10.0.0.2",
            applies_to="model_alert",
        )

        queued_first = queue_alert_notifications(store, chat_id="-100123", limit=10)
        queued_second = queue_alert_notifications(store, chat_id="-100123", limit=10)

        deliveries = store._connection.execute(  # noqa: SLF001
            "SELECT id, dedupe_key, status FROM notification_deliveries ORDER BY id ASC"
        ).fetchall()

        assert queued_first == 1
        assert queued_second == 1
        assert len(deliveries) == 1
        assert deliveries[0]["dedupe_key"] == "alert-1"
        assert deliveries[0]["status"] == "pending"
    finally:
        store.close()


def test_dispatch_pending_notifications_success_marks_sent(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        _seed_alert(store, source_event_id="alert-success", src_ip="10.0.1.1")
        queue_alert_notifications(store, chat_id="-100success", limit=10)
        config = TelegramNotifierConfig(
            bot_token="token",
            default_chat_id="-100success",
            max_attempts=3,
            base_backoff_seconds=1,
        )

        summary = dispatch_pending_telegram_notifications(
            store,
            config=config,
            sender=lambda _cfg, _chat_id, _text: "telegram-msg-1",
        )

        delivery = store._connection.execute(  # noqa: SLF001
            "SELECT status, attempt_count, provider_message_id FROM notification_deliveries"
        ).fetchone()
        assert summary.scanned == 1
        assert summary.sent == 1
        assert summary.retried == 0
        assert summary.failed == 0
        assert delivery is not None
        assert delivery["status"] == "sent"
        assert int(delivery["attempt_count"]) == 1
        assert delivery["provider_message_id"] == "telegram-msg-1"
    finally:
        store.close()


def test_dispatch_retryable_failure_keeps_local_state_and_sets_retry(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        alert_id = _seed_alert(store, source_event_id="alert-retry", src_ip="10.0.2.1")
        queue_alert_notifications(store, chat_id="-100retry", limit=10)
        config = TelegramNotifierConfig(
            bot_token="token",
            default_chat_id="-100retry",
            max_attempts=3,
            base_backoff_seconds=1,
        )

        def failing_sender(_cfg: TelegramNotifierConfig, _chat_id: str, _text: str) -> str:
            raise NotificationDeliveryError(
                "temporary outage",
                retryable=True,
                retry_after_seconds=5,
            )

        summary = dispatch_pending_telegram_notifications(store, config=config, sender=failing_sender)
        delivery = store._connection.execute(  # noqa: SLF001
            "SELECT status, attempt_count, next_attempt_at, last_error FROM notification_deliveries"
        ).fetchone()
        alert = store._connection.execute("SELECT id FROM alerts WHERE id = ?", (alert_id,)).fetchone()  # noqa: SLF001

        assert summary.sent == 0
        assert summary.retried == 1
        assert summary.failed == 0
        assert delivery is not None
        assert delivery["status"] == "retry"
        assert int(delivery["attempt_count"]) == 1
        assert delivery["next_attempt_at"] is not None
        assert "temporary outage" in str(delivery["last_error"])
        assert alert is not None
    finally:
        store.close()


def test_queue_alert_notifications_does_not_reopen_terminal_delivery_state(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        _seed_alert(store, source_event_id="alert-terminal", src_ip="10.0.3.1")
        queue_alert_notifications(store, chat_id="-100terminal", limit=10)
        delivery = store._connection.execute(  # noqa: SLF001
            "SELECT id FROM notification_deliveries WHERE dedupe_key = 'alert-terminal'"
        ).fetchone()
        assert delivery is not None
        store.mark_notification_attempt(
            delivery_id=int(delivery["id"]),
            status="sent",
            provider_message_id="telegram-msg-terminal",
        )

        queued_again = queue_alert_notifications(store, chat_id="-100terminal", limit=10)
        persisted = store._connection.execute(  # noqa: SLF001
            "SELECT status, attempt_count, provider_message_id FROM notification_deliveries WHERE id = ?",
            (int(delivery["id"]),),
        ).fetchone()

        assert queued_again == 1
        assert persisted is not None
        assert persisted["status"] == "sent"
        assert int(persisted["attempt_count"]) == 1
        assert persisted["provider_message_id"] == "telegram-msg-terminal"
    finally:
        store.close()


def test_redrive_failed_notifications_requires_explicit_operator_action(tmp_path: Path) -> None:
    store = _new_store(tmp_path)
    try:
        _seed_alert(store, source_event_id="alert-redrive", src_ip="10.0.4.1")
        queue_alert_notifications(store, chat_id="-100redrive", limit=10)
        config = TelegramNotifierConfig(
            bot_token="token",
            default_chat_id="-100redrive",
            max_attempts=1,
            base_backoff_seconds=1,
        )

        def failing_sender(_cfg: TelegramNotifierConfig, _chat_id: str, _text: str) -> str:
            raise NotificationDeliveryError("permanent rejection", retryable=False)

        dispatch_pending_telegram_notifications(store, config=config, sender=failing_sender)
        queue_alert_notifications(store, chat_id="-100redrive", limit=10)
        failed_delivery = store._connection.execute(  # noqa: SLF001
            "SELECT status, attempt_count FROM notification_deliveries WHERE dedupe_key = 'alert-redrive'"
        ).fetchone()
        assert failed_delivery is not None
        assert failed_delivery["status"] == "failed"
        assert int(failed_delivery["attempt_count"]) == 1

        redriven = redrive_failed_telegram_notifications(store, limit=10)
        pending_delivery = store._connection.execute(  # noqa: SLF001
            "SELECT status, attempt_count, last_error FROM notification_deliveries WHERE dedupe_key = 'alert-redrive'"
        ).fetchone()

        assert redriven == 1
        assert pending_delivery is not None
        assert pending_delivery["status"] == "pending"
        assert int(pending_delivery["attempt_count"]) == 0
        assert pending_delivery["last_error"] is None
    finally:
        store.close()


def testresolve_telegram_config_db_overrides_none(tmp_path: Path) -> None:
    """When startup config has telegram=None but DB has both values, DB wins."""
    store = _new_store(tmp_path)
    try:
        store.set_setting("telegram_bot_token", "123:DB_TOKEN")
        store.set_setting("telegram_chat_id", "-100999")
        result = resolve_telegram_config(store, fallback=None)
        assert result is not None
        assert result.bot_token == "123:DB_TOKEN"
        assert result.default_chat_id == "-100999"
    finally:
        store.close()


def testresolve_telegram_config_db_overrides_env(tmp_path: Path) -> None:
    """When DB has values and env also has values, DB wins."""
    store = _new_store(tmp_path)
    try:
        env_config = TelegramNotifierConfig(bot_token="env_token", default_chat_id="-100env")
        store.set_setting("telegram_bot_token", "123:DB_TOKEN")
        store.set_setting("telegram_chat_id", "-100db")
        result = resolve_telegram_config(store, fallback=env_config)
        assert result is not None
        assert result.bot_token == "123:DB_TOKEN"
        assert result.default_chat_id == "-100db"
    finally:
        store.close()


def testresolve_telegram_config_empty_db_falls_back(tmp_path: Path) -> None:
    """When DB has no settings, fall back to env config."""
    store = _new_store(tmp_path)
    try:
        env_config = TelegramNotifierConfig(bot_token="env_token", default_chat_id="-100env")
        result = resolve_telegram_config(store, fallback=env_config)
        assert result is not None
        assert result.bot_token == "env_token"
        assert result.default_chat_id == "-100env"
    finally:
        store.close()


def testresolve_telegram_config_partial_db_falls_back(tmp_path: Path) -> None:
    """When DB has only token but no chat_id, fall back to env config."""
    store = _new_store(tmp_path)
    try:
        env_config = TelegramNotifierConfig(bot_token="env_token", default_chat_id="-100env")
        store.set_setting("telegram_bot_token", "123:DB_TOKEN")
        # chat_id is not set in DB
        result = resolve_telegram_config(store, fallback=env_config)
        assert result is not None
        assert result.bot_token == "env_token"
    finally:
        store.close()


def testresolve_telegram_config_empty_string_db_falls_back(tmp_path: Path) -> None:
    """When DB has empty strings, treat as not set and fall back."""
    store = _new_store(tmp_path)
    try:
        env_config = TelegramNotifierConfig(bot_token="env_token", default_chat_id="-100env")
        store.set_setting("telegram_bot_token", "")
        store.set_setting("telegram_chat_id", "")
        result = resolve_telegram_config(store, fallback=env_config)
        assert result is not None
        assert result.bot_token == "env_token"
    finally:
        store.close()


def testresolve_telegram_config_none_fallback_and_no_db(tmp_path: Path) -> None:
    """When DB has nothing and fallback is None, result is None (no notifications)."""
    store = _new_store(tmp_path)
    try:
        result = resolve_telegram_config(store, fallback=None)
        assert result is None
    finally:
        store.close()


# ── resolve_telegram_config_with_source tests ──────────────────────────────


def test_resolve_with_source_returns_database_when_db_has_values(tmp_path: Path) -> None:
    """resolve_telegram_config_with_source reports 'database' source."""
    store = _new_store(tmp_path)
    try:
        store.set_setting("telegram_bot_token", "123:DB_TOKEN")
        store.set_setting("telegram_chat_id", "-100999")
        config, source = resolve_telegram_config_with_source(store, fallback=None)
        assert config is not None
        assert config.bot_token == "123:DB_TOKEN"
        assert source == "database"
    finally:
        store.close()


def test_resolve_with_source_returns_environment_when_db_empty(tmp_path: Path) -> None:
    """resolve_telegram_config_with_source reports 'environment' source for env fallback."""
    store = _new_store(tmp_path)
    try:
        env_config = TelegramNotifierConfig(bot_token="env_token", default_chat_id="-100env")
        config, source = resolve_telegram_config_with_source(store, fallback=env_config)
        assert config is not None
        assert config.bot_token == "env_token"
        assert source == "environment"
    finally:
        store.close()


def test_resolve_with_source_returns_none_when_nothing_configured(tmp_path: Path) -> None:
    """resolve_telegram_config_with_source reports 'none' source when unconfigured."""
    store = _new_store(tmp_path)
    try:
        config, source = resolve_telegram_config_with_source(store, fallback=None)
        assert config is None
        assert source == "none"
    finally:
        store.close()
