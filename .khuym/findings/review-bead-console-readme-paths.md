## Problem Statement

Source epic: `ids_ml_new-urzq`.

The canonical console README now links to additional docs using absolute workstation paths under `F:/Work/IDS_ML_New/...`. That makes the canonical documentation spine machine-specific and breaks the links for every other checkout path. It also conflicts with the packaging decisions that require one portable operator-facing documentation path.

## Evidence

**File:** `docs/current/console/README.md`
**Line(s):** 5-8

```markdown
- [ids_operator_console_architecture.md](F:/Work/IDS_ML_New/docs/current/console/ids_operator_console_architecture.md)
- [ids_operator_console_ui_prd.md](F:/Work/IDS_ML_New/docs/current/console/ids_operator_console_ui_prd.md)
- [ids_operator_console_ui_surface_spec.md](F:/Work/IDS_ML_New/docs/current/console/ids_operator_console_ui_surface_spec.md)
- [ids_operator_console_operations.md](F:/Work/IDS_ML_New/docs/current/console/ids_operator_console_operations.md)
```

**Why this is a problem:** canonical docs should be portable across checkouts and hosts, not bound to one maintainer filesystem.

## Proposed Solutions

### Option A - Recommended: switch to repo-relative links
**Pros:** portable and consistent with the canonical docs spine.
**Cons:** none.
**Effort:** Small

### Option B - remove the index links entirely
**Pros:** avoids broken absolute links.
**Cons:** degrades discoverability.
**Effort:** Small

## Acceptance Criteria

- [ ] Canonical console README links are repo-relative or otherwise portable across checkout roots.
- [ ] No `F:/Work/IDS_ML_New` absolute path remains in the canonical console README.
