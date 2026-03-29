from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console.auth import ensure_admin_user
from scripts.ids_operator_console.db import open_existing_operator_store
from scripts.ids_operator_console.config import load_operator_console_config
from scripts.ids_operator_console.migrations import inspect_operator_store, migrate_operator_store
from scripts.ids_operator_console.ops import (
    create_backup,
    prune_backup_retention,
    restore_backup,
    run_smoke_checks,
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
            },
            as_json=args.json_output,
        )
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
