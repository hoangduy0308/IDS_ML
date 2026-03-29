# Spike Findings: ids_ml_new-uj1

**Question**: Can notification health stay operator-visible while remaining non-gating for core readiness?

**Decision**: `YES`

## Evidence

- `scripts/ids_operator_console/health.py` already builds a componentized readiness payload and computes the top-level `ready` boolean separately.
- `scripts/ids_operator_console/web.py` returns `/readyz` HTTP 200 or 503 based only on `payload["ready"]`, so a new notification component can be added without forcing readiness failure if the core `ready` formula stays unchanged.
- `scripts/ids_operator_console/ops.py` already reuses `build_readiness_payload()` for smoke checks, which means one notification-health component can flow naturally to both `/readyz` and operator smoke output.
- `tests/test_ids_operator_console_web.py` already proves readiness is part of the shipped dashboard/runtime contract rather than a dead helper.

## Constraints Locked By This Spike

- The core `ready` boolean must remain based on core runtime essentials only. Notification degradation may be visible in `components.notification`, but must not make the console unready by itself.
- The notification component must expose actionable operator data such as `enabled`, `configured`, `backlog`, `retrying`, `failed`, `oldest_due`, and a sample `last_error`.
- The manage `status` command, `/readyz`, and smoke output must present the same notification-health story so operators do not have to infer state across surfaces.

## Result

The planned health/readiness bead remains valid. The key is to add a non-gating component, not to invent a second readiness model.
