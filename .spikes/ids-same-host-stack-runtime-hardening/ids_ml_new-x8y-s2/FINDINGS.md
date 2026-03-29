# Spike Findings: Stack Restore Ownership Boundary

## Question

Should stack restore support remain verification-first over existing component-specific restore commands, or is any thin wrapper justified without violating ownership boundaries?

## Decision

YES: stack restore support should remain verification-first. No stack-owned restore mutation wrapper is justified in the current repo state.

## Evidence

- `scripts/ids_operator_console_manage.py` already owns `backup`, `restore`, `notify-status`, and `notify-redrive`.
- `scripts/ids_operator_console/ops.py` implements the actual database backup/restore logic and enforces offline restore with `--service-stopped`.
- `tests/test_ids_operator_console_ops.py` already proves restore, post-restore smoke, and notification redrive semantics on the component-owned path.
- `scripts/ids_model_bundle_manage.py` already owns model activation lifecycle through `verify`, `promote`, and `rollback`.
- `docs/ids_live_sensor_operations.md` defines live sensor restore as preserving `/var/lib/ids-live-sensor/active_bundle.json` plus referenced bundle roots, then re-running preflight or restarting the supervised service.
- `docs/ids_operator_console_operations.md` explicitly separates console restore health from live sensor readiness after restore.
- `history/learnings/20260329-model-bundle-promotion-hardening.md` and `history/learnings/20260329-notification-runtime-contracts.md` both push toward preserving component-owned mutation and validating post-restore visibility/redrive rather than introducing a new top-level mutation owner.

## Constraints For The Future Implementation

- The stack layer may orchestrate inventory checks, ordering, and post-restore verification.
- The stack layer may call existing component commands in the canonical runbook.
- The stack layer must not replace:
  - `ids_model_bundle_manage.py rollback|status|verify`
  - `ids_operator_console_manage.py restore|smoke|notify-status|notify-redrive`
  - `ids-live-sensor.service` plus `ids_live_sensor_preflight.py` for runtime re-validation
- Recovery/post-restore health must stay split by failure domain: sensor data path, operator visibility path, outbound notification path.

## Conclusion

The restore boundary is already strong at component level. The stack feature should ship verification and coordination around that boundary, not a new restore wrapper that blurs ownership.
