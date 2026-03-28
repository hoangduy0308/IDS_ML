from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.ids_operator_console_preflight as preflight  # noqa: E402
from scripts.ids_operator_console.db import OperatorStore  # noqa: E402
from scripts.ids_operator_console.notifications import (  # noqa: E402
    NotificationDeliveryError,
    TelegramNotifierConfig,
    dispatch_pending_telegram_notifications,
    queue_alert_notifications,
)
from scripts.ids_operator_console_preflight import (  # noqa: E402
    OperatorConsolePreflightConfig,
    validate_preflight,
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


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _make_preflight_config(tmp_path: Path, **overrides: object) -> OperatorConsolePreflightConfig:
    runtime_dir = tmp_path / "runtime"
    logs_dir = tmp_path / "logs"
    templates_dir = tmp_path / "templates"
    static_dir = tmp_path / "static"
    runtime_dir.mkdir()
    logs_dir.mkdir()
    templates_dir.mkdir()
    static_dir.mkdir()

    kwargs: dict[str, object] = {
        "python_binary": _make_executable(tmp_path / "bin" / "python3"),
        "app_entrypoint": tmp_path / "scripts" / "ids_operator_console_server.py",
        "database_path": runtime_dir / "operator_console.db",
        "alerts_input_path": logs_dir / "ids_live_alerts.jsonl",
        "quarantine_input_path": logs_dir / "ids_live_quarantine.jsonl",
        "summary_input_path": logs_dir / "ids_live_sensor_summary.jsonl",
        "templates_dir": templates_dir,
        "static_dir": static_dir,
        "secret_key": "production-secret",
        "telegram_bot_token": None,
        "telegram_chat_id": None,
    }
    Path(kwargs["app_entrypoint"]).parent.mkdir(parents=True, exist_ok=True)
    Path(kwargs["app_entrypoint"]).write_text("print('ok')\n", encoding="utf-8")
    kwargs.update(overrides)
    return OperatorConsolePreflightConfig(**kwargs)


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


def test_preflight_accepts_valid_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)
    validate_preflight(config)


def test_preflight_rejects_placeholder_secret_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path, secret_key="change-me")
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="must not use default placeholder"):
        validate_preflight(config)


def test_preflight_requires_telegram_pairing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_preflight_config(tmp_path, telegram_bot_token="token-only", telegram_chat_id=None)
    monkeypatch.setattr(preflight, "_is_executable_file", lambda path: True)

    with pytest.raises(ValueError, match="must be set together"):
        validate_preflight(config)
