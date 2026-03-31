# Question
What phased test-move sequence keeps `pytest` discovery and imports stable while moving from flat `tests/*.py` into domain directories?

# Evidence
- The current test tree is still flat: `tests/test_*.py` files at the top level, with no domain subdirectories yet.
- There is no `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`, or `conftest.py` in the repo root or under `tests/`.
- Current tests rely on the same bootstrap pattern everywhere: `Path(__file__).resolve().parents[1]` plus `sys.path.insert(0, str(REPO_ROOT))`.
- That bootstrap works for files directly under `tests/`, but it breaks as soon as a file moves deeper, because `parents[1]` will resolve to `tests/` instead of the repo root.
- Current imports are mostly `scripts.*`, not `ids.*`, so the bootstrap must remain stable until moved tests are switched to canonical package imports.

# Decision (YES/NO)
YES. A phased migration is safe, but only if repo-root import bootstrapping is centralized before the first deeper test move and each domain is moved as a single ownership slice.

# Safe migration sequence
1. Add one shared test bootstrap at `tests/conftest.py` that inserts the repo root into `sys.path` once for the whole suite.
2. Keep all existing flat `tests/test_*.py` files working during that bootstrap change; do not rename or relocate them yet.
3. Migrate tests one domain at a time, starting with the domain whose code move is already stable and whose imports can switch cleanly to canonical packages.
4. For each domain move, relocate the test file and its imports in the same change, and update the test to import `ids.*` or `ml_pipeline.*` instead of `scripts.*`.
5. Use `tests/<domain>/unit`, `tests/<domain>/integration`, and `tests/<domain>/e2e` only after the bootstrap is centralized; keep the directory depth consistent within each domain.
6. Remove the flat original for a test only after the moved copy is green, so there is never a long-lived dual-path pair for the same behavior.
7. Leave wrapper smoke tests only for phase-1 compatibility surfaces; do not keep duplicate logic tests in both flat and domain locations.

# Pytest/discovery constraints
- Default `pytest` discovery is enough for this repo as long as moved files still match `test_*.py` under `tests/`.
- No pytest config file currently overrides discovery, so adding one is optional and should be avoided unless the migration later proves it necessary.
- The current per-file `parents[1]` bootstrap is the main migration hazard, not discovery itself.
- Domain directories are safe only after the path bootstrap is centralized; otherwise moved tests will import from the wrong directory.
- Keep one canonical test location per behavior after each move to avoid a dual-import or dual-collection mess.

# Recommended rules to embed into affected beads
- Add a repo-root `tests/conftest.py` bootstrap before any deeper test move.
- Do not copy the current `parents[1]` path hack into relocated tests.
- Move tests in domain-sized slices that match the code-move beads, not file-by-file across unrelated domains.
- Update moved tests to canonical `ids.*` and `ml_pipeline.*` imports in the same change that relocates them.
- Keep wrapper compatibility checks narrow and explicit; do not preserve both wrapper and implementation tests indefinitely.
