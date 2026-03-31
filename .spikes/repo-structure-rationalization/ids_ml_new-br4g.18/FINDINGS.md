# Question
Can this repo introduce a canonical `ids` package and preserve current `scripts.*` entrypoints in phase 1 without adding packaging metadata or breaking import resolution?

## Evidence
- `history/repo-structure-rationalization/CONTEXT.md` explicitly requires a two-phase rollout and says phase 1 should preserve current behavior and compatibility entrypoints.
- `history/repo-structure-rationalization/approach.md` already recommends a canonical `ids/` product package with thin `scripts/*.py` wrappers.
- `scripts/ids_operator_console_server.py:12-17` and `scripts/ids_same_host_stack_manage.py:9-14` already use the repo-root `sys.path` bootstrap before importing package-owned logic.
- `scripts/ids_live_sensor.py:13-42` shows the same wrapper pattern on a heavier runtime entrypoint with many intra-repo imports.
- `scripts/ids_operator_console/__init__.py:3-9` proves the repo already tolerates real package-owned implementation under `scripts/`.
- The repo root has no `pyproject.toml`, `setup.py`, `setup.cfg`, or similar packaging metadata, so this phase would remain source-tree execution.
- Isolated prototype: a temp repo with an `ids` package and a `scripts/entry.py` wrapper successfully resolved `import ids`, `python -m scripts.entry`, and direct file execution when the wrapper kept the repo-root bootstrap shim.

## Decision
YES

## Constraints
- Put the canonical implementation in `ids/*` at the repository root.
- Keep `scripts/*` as compatibility wrappers only; do not leave business logic in the wrappers.
- Preserve the `if __package__ in (None, "")` bootstrap in any wrapper that must still run as a file.
- Keep imports one-way: `scripts -> ids`, not `ids -> scripts`.
- Any file that still needs direct execution must keep the repo-root path shim; `python -m scripts.*` alone is not enough for those files.

## Recommended rules to embed into affected beads
- `ids` owns implementation; `scripts` owns compatibility entrypoints.
- Phase 1 wrappers may delegate only, never reimplement.
- Wrapper acceptance criteria must include `import ids`, `python -m scripts.<entry>`, and direct file execution for any file that is currently invoked that way.
- Do not add packaging metadata as a prerequisite for phase 1; treat install-time packaging as a separate phase-2 concern.
- Keep wrapper imports one-way only, and reject any bead that introduces a reverse dependency from `ids` back into `scripts`.
