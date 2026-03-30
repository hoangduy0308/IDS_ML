from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ids.runtime.live_sensor_sinks import DEFAULT_SUMMARY_OUTPUT_PATH
from scripts.ids_model_bundle import (
    ActiveBundleResolutionError,
    ModelBundleContractError,
    build_bundle_status_payload,
)


DEFAULT_FRESHNESS_WINDOW_SECONDS = 300.0


@dataclass(frozen=True)
class LiveSensorHealthConfig:
    activation_path: Path
    summary_output_path: Path = DEFAULT_SUMMARY_OUTPUT_PATH
    freshness_window_seconds: float = DEFAULT_FRESHNESS_WINDOW_SECONDS

    def __post_init__(self) -> None:
        object.__setattr__(self, "activation_path", Path(self.activation_path).resolve())
        object.__setattr__(self, "summary_output_path", Path(self.summary_output_path).resolve())
        if self.freshness_window_seconds <= 0:
            raise ValueError("freshness_window_seconds must be positive")


def _load_latest_summary_event(summary_output_path: Path) -> dict[str, Any] | None:
    if not summary_output_path.is_file():
        return None
    latest_line = ""
    with summary_output_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                latest_line = stripped
    if not latest_line:
        return None
    payload = json.loads(latest_line)
    if not isinstance(payload, dict):
        raise ValueError("latest summary payload must be a JSON object")
    return payload


def _parse_event_timestamp(raw_timestamp: Any) -> datetime | None:
    if not isinstance(raw_timestamp, str):
        return None
    normalized = raw_timestamp.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_activation_component(config: LiveSensorHealthConfig) -> dict[str, Any]:
    try:
        payload = build_bundle_status_payload(config.activation_path)
    except (ActiveBundleResolutionError, ModelBundleContractError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "state": "invalid",
            "detail": str(exc),
            "payload": {"activation_path": str(config.activation_path)},
        }
    return {
        "ok": bool(payload.get("runtime_ready")),
        "state": "ready" if payload.get("runtime_ready") else "degraded",
        "detail": None if payload.get("runtime_ready") else str(payload.get("detail", "")),
        "payload": payload,
    }


def _bundle_mismatch_detail(
    activation_payload: dict[str, Any],
    summary_event: dict[str, Any],
) -> str | None:
    active_bundle = summary_event.get("active_bundle")
    if not isinstance(active_bundle, dict):
        return "summary event missing active_bundle state"
    for field in ("activation_path", "active_bundle_root", "active_bundle_name"):
        expected = activation_payload.get(field)
        observed = active_bundle.get(field)
        if expected is None or observed is None:
            return f"summary event missing {field}"
        if str(expected) != str(observed):
            return (
                f"summary {field} does not match activation contract "
                f"(expected {expected}, observed {observed})"
            )
    return None


def _build_runtime_evidence_component(
    config: LiveSensorHealthConfig,
    *,
    activation_component: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    summary_exists = config.summary_output_path.is_file()
    component: dict[str, Any] = {
        "ok": False,
        "state": "missing",
        "detail": "summary output not found",
        "summary_output_path": str(config.summary_output_path),
        "summary_output_exists": summary_exists,
        "freshness_window_seconds": config.freshness_window_seconds,
        "latest_summary": None,
        "timestamp": None,
        "age_seconds": None,
    }
    try:
        latest_summary = _load_latest_summary_event(config.summary_output_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        component["state"] = "malformed"
        component["detail"] = str(exc)
        return component
    if latest_summary is None:
        if summary_exists:
            component["detail"] = "summary output exists but contains no events"
        return component

    component["latest_summary"] = latest_summary
    if latest_summary.get("event_type") != "live_sensor_summary":
        component["state"] = "unexpected_event"
        component["detail"] = "latest summary event is not a live_sensor_summary payload"
        return component

    event_timestamp = _parse_event_timestamp(latest_summary.get("timestamp"))
    if event_timestamp is None:
        component["state"] = "malformed"
        component["detail"] = "latest summary event timestamp is missing or invalid"
        return component

    age_seconds = max(0.0, (now - event_timestamp).total_seconds())
    component["timestamp"] = event_timestamp.isoformat()
    component["age_seconds"] = age_seconds

    if age_seconds > config.freshness_window_seconds:
        component["state"] = "stale"
        component["detail"] = (
            f"latest summary event is stale ({age_seconds:.1f}s > "
            f"{config.freshness_window_seconds:.1f}s)"
        )
        return component

    if latest_summary.get("reason") == "capture-failure":
        component["state"] = "capture_failure"
        component["detail"] = "latest summary event reports capture-failure"
        return component

    if activation_component.get("ok"):
        activation_payload = activation_component["payload"]
        mismatch_detail = _bundle_mismatch_detail(activation_payload, latest_summary)
        if mismatch_detail is not None:
            component["state"] = "mismatch"
            component["detail"] = mismatch_detail
            return component

    component["ok"] = True
    component["state"] = "current"
    component["detail"] = None
    return component


def build_live_sensor_health_payload(
    config: LiveSensorHealthConfig,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    activation_component = _build_activation_component(config)
    runtime_evidence = _build_runtime_evidence_component(
        config,
        activation_component=activation_component,
        now=observed_at,
    )
    ready = bool(activation_component["ok"] and runtime_evidence["ok"])
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "service": "ids-live-sensor",
        "checked_at": observed_at.isoformat(),
        "activation_path": str(config.activation_path),
        "summary_output_path": str(config.summary_output_path),
        "freshness_window_seconds": config.freshness_window_seconds,
        "components": {
            "activation_contract": activation_component,
            "runtime_evidence": runtime_evidence,
        },
    }


def _print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect live sensor runtime health from activation state and durable summary evidence."
    )
    parser.add_argument("--activation-path", type=Path, required=True)
    parser.add_argument("--summary-output-path", type=Path, default=DEFAULT_SUMMARY_OUTPUT_PATH)
    parser.add_argument(
        "--freshness-window-seconds",
        type=float,
        default=DEFAULT_FRESHNESS_WINDOW_SECONDS,
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = LiveSensorHealthConfig(
        activation_path=args.activation_path,
        summary_output_path=args.summary_output_path,
        freshness_window_seconds=args.freshness_window_seconds,
    )
    payload = build_live_sensor_health_payload(config)
    _print_payload(payload, as_json=args.json_output)
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
