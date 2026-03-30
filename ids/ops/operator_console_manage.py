from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Sequence

from ids.console.auth import ensure_admin_user
from ids.console.config import load_operator_console_config
from ids.console.db import open_existing_operator_store
from ids.console.migrations import inspect_operator_store, migrate_operator_store
from ids.console.ops import (
    create_backup,
    notification_status,
    prune_backup_retention,
    redrive_notification_failures,
    restore_backup,
    run_notification_maintenance_once,
    run_notification_worker_iterations,
    run_smoke_checks,
    send_test_notification,
)


def _inspection_to_payload(inspection: Any) -> dict[str, Any]:
    return {
        "database_path": str(inspection.database_path),
        "database_exists": inspection.database_exists,
        "schema_state": inspection.schema_state,
        "schema_version": inspection.schema_version,
        "admin_count": inspection.admin_count,
        "runtime_ready": inspection.runtime_ready,
        "detail": inspection.detail,
    }


def _read_password(args: argparse.Namespace) -> str:
    if bool(args.password) == bool(args.password_file):
        raise ValueError("exactly one of --password or --password-file must be provided")
    if args.password:
        password = str(args.password).strip()
    else:
        password = Path(args.password_file).read_text(encoding="utf-8").strip()
    if not password:
        raise ValueError("password must not be blank")
    return password


def _print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _load_runtime_config(*, database_path: Path) -> Any:
    config = load_operator_console_config()
    return replace(config, database_path=database_path)


def _optional_positive_int(value: str) -> int:
    normalized = int(value)
    if normalized < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return normalized


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage IDS operator console bootstrap and schema state.")
    parser.add_argument("--database-path", type=Path, required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Inspect schema/admin bootstrap state.")

    migrate_parser = subparsers.add_parser("migrate", help="Apply explicit schema migration or bootstrap.")
    migrate_parser.add_argument("--allow-bootstrap", action="store_true")

    bootstrap_parser = subparsers.add_parser("bootstrap-admin", help="Create or update the admin credential.")
    bootstrap_parser.add_argument("--username", required=True)
    bootstrap_parser.add_argument("--password")
    bootstrap_parser.add_argument("--password-file", type=Path)

    backup_parser = subparsers.add_parser("backup", help="Create a transactional operator backup.")
    backup_parser.add_argument("--output-dir", type=Path, required=True)

    restore_parser = subparsers.add_parser("restore", help="Restore an operator backup.")
    restore_parser.add_argument("--backup-dir", type=Path, required=True)
    restore_parser.add_argument("--service-stopped", action="store_true")

    retention_parser = subparsers.add_parser("prune-retention", help="Prune old backup artifacts.")
    retention_parser.add_argument("--backup-root", type=Path, required=True)
    retention_parser.add_argument("--keep-last", type=int, default=3)

    subparsers.add_parser("smoke", help="Run smoke checks against the wired runtime contract.")

    subparsers.add_parser("notify-status", help="Show non-gating notification runtime health.")

    notify_test_send_parser = subparsers.add_parser(
        "notify-test-send",
        help="Send a test Telegram notification through the configured runtime contract.",
    )
    notify_test_send_parser.add_argument("--text", required=True)

    subparsers.add_parser(
        "notify-run-once",
        help="Run one explicit notification maintenance cycle (ingest -> queue -> dispatch).",
    )

    notify_worker_parser = subparsers.add_parser(
        "notify-worker",
        help="Run the notification worker loop; omit --iterations for long-running supervised mode.",
    )
    notify_worker_parser.add_argument("--iterations", type=_optional_positive_int, default=None)
    notify_worker_parser.add_argument("--poll-interval-seconds", type=float, default=30.0)

    notify_redrive_parser = subparsers.add_parser(
        "notify-redrive",
        help="Redrive failed notification deliveries back to pending.",
    )
    notify_redrive_parser.add_argument("--limit", type=int, default=100)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    database_path = Path(args.database_path).resolve()

    if args.command == "status":
        inspection = inspect_operator_store(database_path)
        _print_payload(_inspection_to_payload(inspection), as_json=args.json_output)
        return 0 if inspection.runtime_ready else 2

    if args.command == "migrate":
        inspection = migrate_operator_store(database_path, allow_bootstrap=bool(args.allow_bootstrap))
        _print_payload(_inspection_to_payload(inspection), as_json=args.json_output)
        return 0

    if args.command == "bootstrap-admin":
        inspection = inspect_operator_store(database_path)
        if inspection.schema_state != "current":
            raise SystemExit(
                "database schema is not current; run migrate before bootstrap-admin"
            )
        password = _read_password(args)
        store = open_existing_operator_store(database_path)
        try:
            ensure_admin_user(store, username=str(args.username), password=password)
        finally:
            store.close()
        refreshed = inspect_operator_store(database_path)
        _print_payload(_inspection_to_payload(refreshed), as_json=args.json_output)
        return 0

    if args.command == "backup":
        config = _load_runtime_config(database_path=database_path)
        result = create_backup(config, backup_root=Path(args.output_dir))
        _print_payload(
            {
                "backup_dir": str(result.backup_dir),
                "database_backup_path": str(result.database_backup_path),
                "manifest_path": str(result.manifest_path),
            },
            as_json=args.json_output,
        )
        return 0

    if args.command == "restore":
        config = _load_runtime_config(database_path=database_path)
        result = restore_backup(
            config,
            backup_dir=Path(args.backup_dir),
            service_stopped=bool(args.service_stopped),
        )
        _print_payload(
            {
                "database_path": str(result.database_path),
                "manifest_path": str(result.manifest_path),
                "schema_state": result.inspection.schema_state,
                "admin_count": result.inspection.admin_count,
            },
            as_json=args.json_output,
        )
        return 0

    if args.command == "prune-retention":
        result = prune_backup_retention(
            backup_root=Path(args.backup_root),
            keep_last=int(args.keep_last),
        )
        _print_payload(
            {
                "backup_root": str(result.backup_root),
                "kept": result.kept,
                "removed": result.removed,
            },
            as_json=args.json_output,
        )
        return 0

    if args.command == "smoke":
        config = _load_runtime_config(database_path=database_path)
        result = run_smoke_checks(config)
        _print_payload(
            {
                "health_status": result.health_status,
                "readiness_status": result.readiness_status,
                "redirect_status": result.redirect_status,
                "ready": result.readiness_payload["ready"],
                "notification": result.readiness_payload["components"]["notification"],
            },
            as_json=args.json_output,
        )
        return 0

    if args.command == "notify-status":
        config = _load_runtime_config(database_path=database_path)
        _print_payload(notification_status(config), as_json=args.json_output)
        return 0

    if args.command == "notify-test-send":
        config = _load_runtime_config(database_path=database_path)
        result = send_test_notification(config, text=str(args.text))
        _print_payload(
            {
                "target": result.target,
                "provider_message_id": result.provider_message_id,
            },
            as_json=args.json_output,
        )
        return 0

    if args.command == "notify-run-once":
        config = _load_runtime_config(database_path=database_path)
        _print_payload(run_notification_maintenance_once(config), as_json=args.json_output)
        return 0

    if args.command == "notify-worker":
        config = _load_runtime_config(database_path=database_path)
        result = run_notification_worker_iterations(
            config,
            iterations=args.iterations,
            poll_interval_seconds=float(args.poll_interval_seconds),
        )
        _print_payload(result, as_json=args.json_output)
        return 0

    if args.command == "notify-redrive":
        config = _load_runtime_config(database_path=database_path)
        result = redrive_notification_failures(config, limit=int(args.limit))
        _print_payload(
            {
                "redriven": result.redriven,
                "status": result.status,
            },
            as_json=args.json_output,
        )
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
