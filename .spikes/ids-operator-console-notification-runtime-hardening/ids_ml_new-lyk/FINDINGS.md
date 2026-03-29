# Spike Findings: ids_ml_new-lyk

**Question**: Can deploy and preflight share one explicit notification worker contract on the same host?

**Decision**: `YES`

## Evidence

- `deploy/systemd/ids-operator-console.service` already demonstrates the repo pattern of one env contract plus one exact-path preflight plus one explicit runtime entrypoint.
- `scripts/ids_operator_console_preflight.py` already validates path existence, runtime prerequisites, secret loading, and Telegram token/chat pairing.
- `tests/test_ids_operator_console_preflight.py` already proves the preflight contract is testable in isolation and can reject invalid bootstrap or secret/config states.
- `scripts/ids_operator_console_manage.py` already acts as the explicit operator command surface for runtime lifecycle tasks, which is the correct place to surface notification worker commands.

## Constraints Locked By This Spike

- The notification worker must get its own explicit runtime entrypoint or finalized manage subcommand contract; systemd must point at that exact contract rather than inventing an unrelated unit-only interface.
- Web startup remains verify-only. Notification dispatch cannot become an `ExecStart` side effect of `ids_operator_console_server.py`.
- Preflight must become worker-aware only when notifications are enabled; disabled mode stays valid and must not fail host startup merely because the worker is intentionally unused.
- The worker service must reuse the same config source and secret semantics as the existing console service.

## Result

The planned deploy/preflight bead remains valid. The work required is contract extension and alignment, not a topology change.
