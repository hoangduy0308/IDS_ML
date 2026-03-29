# Spike Findings: `ids_ml_new-n1m`

## Question

Can startup fail closed while an explicit migration CLI upgrades a v1 operator-console database?

## Result

**YES**

## Why

- The current schema seam is centralized enough to evolve:
  - [`scripts/ids_operator_console/db.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\db.py) contains one large bootstrap script and a single `OperatorStore.open()` path
  - local inspection of a bootstrapped database showed there is currently **no** schema-version table
- The current runtime side effect is real and therefore visible:
  - a local experiment confirmed that merely building the web app currently creates the SQLite file because `create_operator_console_web_app()` bootstraps through `OperatorStore.open()`
- That means the repo does need a refactor, but the refactor is straightforward and bounded:
  - separate `connect` from `bootstrap/migrate`
  - add non-mutating schema inspection
  - make startup call verification instead of implicit bootstrap
  - route shape-changing work through an explicit management CLI

## Current Gaps In Repo

- [`scripts/ids_operator_console/db.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\db.py) bootstraps with `CREATE TABLE IF NOT EXISTS` and no schema metadata.
- [`scripts/ids_operator_console/web.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\web.py) currently causes bootstrap side effects during app construction.
- There is no admin bootstrap or migrate command surface yet.

## Validated Constraints

1. Introduce schema metadata as an explicit version contract, not as hidden table drift.
2. Split store opening into at least two modes:
   - inspect/verify without mutating schema
   - explicit bootstrap/migrate path for operator tooling
3. Normal startup must:
   - fail closed on missing/incompatible schema
   - fail closed on uninitialized admin/bootstrap state
   - never auto-apply shape-changing migrations
4. `bootstrap-admin` and `migrate` belong in the operator CLI, not in request-time auth/session helpers.
5. Upgrade from v1 should be treated as:
   - detect current schema state
   - apply ordered migration(s)
   - then allow runtime startup

## Impacted Beads

- `ids_ml_new-z2i.2`
- `ids_ml_new-z2i.3`
- `ids_ml_new-z2i.4`
- `ids_ml_new-z2i.5`

## Evidence

- Local experiment: current bootstrapped DB has no `schema_version`/equivalent metadata table
- Local experiment: building the app creates the DB file today, proving startup is not yet fail-closed
- Repo evidence:
  - [`scripts/ids_operator_console/db.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\db.py)
  - [`scripts/ids_operator_console/web.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\web.py)
