from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_same_host_stack import (  # noqa: E402
    SameHostStackConfig,
    run_stack_bootstrap,
    validate_stack_preflight,
)


def _print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage canonical same-host IDS stack bootstrap and preflight contracts."
    )
    parser.add_argument("--repo-root", type=Path, default=Path("/opt/ids_ml_new"))
    parser.add_argument("--python-binary", type=Path, default=Path("/usr/bin/python3"))
    parser.add_argument(
        "--operator-env-file",
        type=Path,
        default=Path("/etc/ids-operator-console/ids-operator-console.env"),
    )
    parser.add_argument(
        "--activation-path",
        type=Path,
        default=Path("/var/lib/ids-live-sensor/active_bundle.json"),
    )
    parser.add_argument("--interface", default="eth0")
    parser.add_argument("--dumpcap-binary", type=Path, default=Path("/usr/bin/dumpcap"))
    parser.add_argument("--java-binary", type=Path, default=Path("/usr/bin/java"))
    parser.add_argument(
        "--extractor-binary",
        type=Path,
        default=Path("/opt/cicflowmeter/Cmd"),
    )
    parser.add_argument(
        "--jnetpcap-path",
        type=Path,
        default=Path("/opt/cicflowmeter/lib/jnetpcap.jar"),
    )
    parser.add_argument("--spool-dir", type=Path, default=Path("/var/lib/ids-live-sensor"))
    parser.add_argument(
        "--alerts-output-path",
        type=Path,
        default=Path("/var/log/ids-live-sensor/ids_live_alerts.jsonl"),
    )
    parser.add_argument(
        "--quarantine-output-path",
        type=Path,
        default=Path("/var/log/ids-live-sensor/ids_live_quarantine.jsonl"),
    )
    parser.add_argument(
        "--summary-output-path",
        type=Path,
        default=Path("/var/log/ids-live-sensor/ids_live_sensor_summary.jsonl"),
    )
    parser.add_argument("--model-manage-entrypoint", type=Path, default=None)
    parser.add_argument("--operator-manage-entrypoint", type=Path, default=None)
    parser.add_argument("--operator-server-entrypoint", type=Path, default=None)
    parser.add_argument("--console-service-name", default="ids-operator-console.service")
    parser.add_argument("--live-sensor-service-name", default="ids-live-sensor.service")
    parser.add_argument(
        "--notification-service-name",
        default="ids-operator-console-notify.service",
    )
    parser.add_argument("--json", action="store_true", dest="json_output")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="Validate the canonical same-host stack preflight.")

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Run the canonical same-host bootstrap ordering through existing component owners.",
    )
    bootstrap_parser.add_argument("--candidate-bundle-root", type=Path, required=True)
    bootstrap_parser.add_argument("--admin-username", required=True)
    bootstrap_parser.add_argument("--admin-password", default=None)
    bootstrap_parser.add_argument("--admin-password-file", type=Path, default=None)
    return parser


def build_config_from_args(args: argparse.Namespace) -> SameHostStackConfig:
    repo_root = Path(args.repo_root).resolve()
    return SameHostStackConfig(
        repo_root=repo_root,
        python_binary=Path(args.python_binary).resolve(),
        operator_env_file=Path(args.operator_env_file).resolve(),
        model_manage_entrypoint=(
            Path(args.model_manage_entrypoint).resolve()
            if args.model_manage_entrypoint
            else (repo_root / "scripts" / "ids_model_bundle_manage.py").resolve()
        ),
        operator_manage_entrypoint=(
            Path(args.operator_manage_entrypoint).resolve()
            if args.operator_manage_entrypoint
            else (repo_root / "scripts" / "ids_operator_console_manage.py").resolve()
        ),
        operator_server_entrypoint=(
            Path(args.operator_server_entrypoint).resolve()
            if args.operator_server_entrypoint
            else (repo_root / "scripts" / "ids_operator_console_server.py").resolve()
        ),
        activation_path=Path(args.activation_path).resolve(),
        live_sensor_interface=str(args.interface).strip(),
        dumpcap_binary=Path(args.dumpcap_binary).resolve(),
        java_binary=Path(args.java_binary).resolve(),
        extractor_binary=Path(args.extractor_binary).resolve(),
        jnetpcap_path=Path(args.jnetpcap_path).resolve(),
        spool_dir=Path(args.spool_dir).resolve(),
        alerts_output_path=Path(args.alerts_output_path).resolve(),
        quarantine_output_path=Path(args.quarantine_output_path).resolve(),
        summary_output_path=Path(args.summary_output_path).resolve(),
        console_service_name=str(args.console_service_name),
        live_sensor_service_name=str(args.live_sensor_service_name),
        notification_service_name=str(args.notification_service_name),
        candidate_bundle_root=(
            Path(args.candidate_bundle_root).resolve()
            if getattr(args, "candidate_bundle_root", None)
            else None
        ),
        admin_username=getattr(args, "admin_username", None),
        admin_password=getattr(args, "admin_password", None),
        admin_password_file=(
            Path(args.admin_password_file).resolve()
            if getattr(args, "admin_password_file", None)
            else None
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = build_config_from_args(args)

    if args.command == "preflight":
        payload = validate_stack_preflight(config)
        _print_payload(payload, as_json=args.json_output)
        return 0 if payload.get("ready") else 2

    if args.command == "bootstrap":
        payload = run_stack_bootstrap(config)
        _print_payload(payload, as_json=args.json_output)
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
