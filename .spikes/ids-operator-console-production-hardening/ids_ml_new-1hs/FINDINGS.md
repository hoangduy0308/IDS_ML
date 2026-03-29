# Spike Findings: `ids_ml_new-1hs`

## Question

Is SQLite backup plus manifest restore safe enough if restore is forced offline and secret references are revalidated?

## Result

**YES**

## Why

- The backup primitive is real in this runtime:
  - local Python runtime exposes `sqlite3.Connection.backup()`
  - a local WAL-mode experiment successfully backed up a live database and preserved committed rows in the backup snapshot
- The current operator console already runs SQLite in WAL mode:
  - [`scripts/ids_operator_console/db.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\db.py) sets `PRAGMA journal_mode = WAL`
- That means the plan is sound **only** if it is disciplined:
  - online backup uses SQLite's backup API
  - restore does **not** pretend file-copy replacement is safe while the service is live
  - secret references are restored as metadata, but secret material remains external and must be revalidated before success

## Current Gaps In Repo

- No backup or restore command surface exists yet.
- No manifest format exists yet for config values and secret references.
- No restore preflight exists yet to refuse operation while the service is still running.

## Validated Constraints

1. Online backup may use `sqlite3.Connection.backup()` against the live operator DB.
2. Restore must be offline-only:
   - service stopped
   - destination not actively in use
   - restore target verified before replacement
3. Manifest scope should include operator-owned deployment metadata such as:
   - backup timestamp
   - schema version / migration state
   - non-secret config values needed to recreate runtime contract
   - secret file references / credential references
4. Manifest must **not** store secret material.
5. Restore success criteria must include:
   - DB restored
   - config/reference manifest restored
   - secret references revalidated and readable
   - refusal/fail-closed if any referenced secret is missing or unreadable

## Impacted Beads

- `ids_ml_new-z2i.3`
- `ids_ml_new-z2i.4`
- `ids_ml_new-z2i.5`

## Evidence

- Local experiment: WAL-mode SQLite backup snapshot succeeded and contained committed rows
- Current runtime code sets WAL mode in [`scripts/ids_operator_console/db.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\db.py)
- Official docs / references:
  - [Python sqlite3 docs](https://docs.python.org/3/library/sqlite3.html)
  - local runtime docstring for `sqlite3.Connection.backup`: `Makes a backup of the database.`
