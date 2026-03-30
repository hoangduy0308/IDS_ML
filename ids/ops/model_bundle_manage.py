from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from scripts.ids_model_bundle import (
    ActiveBundleResolutionError,
    ModelBundleContractError,
    build_bundle_status_payload,
    promote_candidate_bundle,
    rollback_active_bundle,
    verify_candidate_bundle,
)


def _print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage IDS model bundle verification and activation state.")
    parser.add_argument("--activation-path", type=Path, required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Inspect the current active bundle state.")
    subparsers.add_parser("inspect", help="Alias for status.")

    verify_parser = subparsers.add_parser(
        "verify",
        help="Validate a candidate bundle before activation.",
    )
    verify_parser.add_argument("--bundle-root", type=Path, required=True)

    promote_parser = subparsers.add_parser(
        "promote",
        help="Verify and atomically activate a candidate bundle.",
    )
    promote_parser.add_argument("--bundle-root", type=Path, required=True)

    activate_parser = subparsers.add_parser(
        "activate",
        help="Alias for promote.",
    )
    activate_parser.add_argument("--bundle-root", type=Path, required=True)

    subparsers.add_parser(
        "rollback",
        help="Restore the previous known-good bundle recorded at promotion time.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    activation_path = Path(args.activation_path).resolve()

    try:
        if args.command in {"status", "inspect"}:
            payload = build_bundle_status_payload(activation_path)
            _print_payload(payload, as_json=args.json_output)
            return 0 if payload.get("runtime_ready") else 2

        if args.command == "verify":
            payload = verify_candidate_bundle(Path(args.bundle_root).resolve())
            payload["activation_path"] = str(activation_path)
            _print_payload(payload, as_json=args.json_output)
            return 0

        if args.command in {"promote", "activate"}:
            payload = promote_candidate_bundle(
                candidate_bundle_root=Path(args.bundle_root).resolve(),
                activation_path=activation_path,
            )
            payload["action"] = "promote"
            _print_payload(payload, as_json=args.json_output)
            return 0

        if args.command == "rollback":
            payload = rollback_active_bundle(activation_path=activation_path)
            payload["action"] = "rollback"
            _print_payload(payload, as_json=args.json_output)
            return 0
    except (ModelBundleContractError, ActiveBundleResolutionError) as exc:
        raise SystemExit(str(exc)) from exc

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
