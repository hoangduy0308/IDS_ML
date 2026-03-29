from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .config import OperatorConsoleConfig
from .db import open_existing_operator_store
from .migrations import inspect_operator_store
from .notification_runtime import NotificationRuntimeConfig, build_notification_runtime_status


def _path_health(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "exists": resolved.exists(),
        "readable": resolved.exists() and resolved.is_file(),
        "parent_exists": resolved.parent.exists(),
        "parent_readable": resolved.parent.exists(),
    }


def build_liveness_payload(config: OperatorConsoleConfig) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "ids-operator-console",
        "environment": config.environment,
        "database_path": str(config.database_path),
    }


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


def _load_latest_active_bundle_state(config: OperatorConsoleConfig) -> dict[str, Any] | None:
    try:
        store = open_existing_operator_store(config.database_path)
    except Exception:
        return None
    try:
        summaries = store.list_recent_summaries(limit=1)
    finally:
        store.close()
    if not summaries:
        return None
    payload = _decode_payload(summaries[0].get("payload_json"))
    active_bundle = payload.get("active_bundle")
    return dict(active_bundle) if isinstance(active_bundle, dict) else None


def _build_notification_component(config: OperatorConsoleConfig) -> dict[str, Any]:
    token_present = config.telegram_bot_token is not None
    chat_present = config.telegram_chat_id is not None
    enabled = token_present and chat_present
    configured = enabled
    if token_present != chat_present:
        return {
            "ok": False,
            "state": "misconfigured",
            "enabled": False,
            "configured": False,
            "channel": "telegram",
            "target": config.telegram_chat_id,
            "backlog": 0,
            "pending_count": 0,
            "retry_count": 0,
            "failed_count": 0,
            "sent_count": 0,
            "due_count": 0,
            "oldest_due_at": None,
            "last_error": {
                "message": "telegram_bot_token and telegram_chat_id must be set together",
            },
        }
    if not enabled:
        return {
            "ok": True,
            "state": "disabled",
            "enabled": False,
            "configured": False,
            "channel": "telegram",
            "target": None,
            "backlog": 0,
            "pending_count": 0,
            "retry_count": 0,
            "failed_count": 0,
            "sent_count": 0,
            "due_count": 0,
            "oldest_due_at": None,
            "last_error": None,
        }

    try:
        store = open_existing_operator_store(config.database_path)
    except Exception as exc:
        return {
            "ok": False,
            "state": "degraded",
            "enabled": enabled,
            "configured": configured,
            "channel": "telegram",
            "target": config.telegram_chat_id,
            "backlog": 0,
            "pending_count": 0,
            "retry_count": 0,
            "failed_count": 0,
            "sent_count": 0,
            "due_count": 0,
            "oldest_due_at": None,
            "last_error": {"message": str(exc)},
        }
    try:
        runtime_status = build_notification_runtime_status(
            store,
            runtime_config=NotificationRuntimeConfig.from_operator_console_config(config),
        )
    finally:
        store.close()

    backlog = runtime_status.pending_count + runtime_status.retry_count
    component_ok = runtime_status.failed_count == 0
    state = "ok" if component_ok else "degraded"
    return {
        "ok": component_ok,
        "state": state,
        "enabled": runtime_status.enabled,
        "configured": runtime_status.configured,
        "channel": runtime_status.channel,
        "target": runtime_status.target,
        "backlog": backlog,
        "pending_count": runtime_status.pending_count,
        "retry_count": runtime_status.retry_count,
        "failed_count": runtime_status.failed_count,
        "sent_count": runtime_status.sent_count,
        "due_count": runtime_status.due_count,
        "oldest_due_at": runtime_status.oldest_due_at,
        "last_error": runtime_status.last_error,
    }


def build_readiness_payload(config: OperatorConsoleConfig) -> dict[str, Any]:
    inspection = inspect_operator_store(config.database_path)
    data_paths = {
        "alerts": _path_health(config.alerts_input_path),
        "quarantine": _path_health(config.quarantine_input_path),
        "summary": _path_health(config.summary_input_path),
    }
    data_path_ok = all(item["parent_exists"] for item in data_paths.values())
    config_ok = True
    try:
        config.__post_init__()
    except ValueError:
        config_ok = False

    active_bundle_state = _load_latest_active_bundle_state(config)
    notification = _build_notification_component(config)
    ready = config_ok and inspection.runtime_ready and data_path_ok
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "service": "ids-operator-console",
        "environment": config.environment,
        "proxy": {
            "public_base_url": config.public_base_url,
            "root_path": config.root_path,
            "forwarded_allow_ips": config.forwarded_allow_ips,
        },
        "components": {
            "config": {
                "ok": config_ok,
                "session_cookie_https_only": config.session_cookie_https_only,
                "session_cookie_same_site": config.session_cookie_same_site,
                "secret_source": str(config.secret_key_source) if config.secret_key_source else "env",
            },
            "schema": {
                "ok": inspection.schema_state == "current",
                "state": inspection.schema_state,
                "version": inspection.schema_version,
                "detail": inspection.detail,
            },
            "admin_bootstrap": {
                "ok": inspection.admin_count > 0,
                "admin_count": inspection.admin_count,
            },
            "data_paths": {
                "ok": data_path_ok,
                "streams": data_paths,
            },
            "active_bundle": {
                "ok": active_bundle_state is not None,
                "state": active_bundle_state,
            },
            "notification": notification,
        },
    }
