# Findings: ids_ml_new-br4g.21

## Question

Can the operator console web app, templates, and static assets move under `ids.console` while preserving app-factory wiring and package-relative asset loading?

## Evidence

- The runnable server entrypoint is already a thin wrapper. `scripts/ids_operator_console_server.py` only parses CLI overrides, loads config, and delegates to `build_operator_console_app()` / `create_operator_console_web_app()`.
- The app factory is the single canonical web assembly point. In `scripts/ids_operator_console/web.py`, `create_operator_console_web_app()` creates `Jinja2Templates(directory=str(config.templates_dir))`, stores the templates on `app.state`, and mounts static files with `StaticFiles(directory=str(config.static_dir))` at `/static`.
- The asset URLs in the templates are mount-based, not filesystem-path-based. `scripts/ids_operator_console/templates/base.html` refers to `/static/console.css` and `/static/console.js`, so the browser-facing contract depends on the mount point, not on the package name on disk.
- The path selection is config-driven. `scripts/ids_operator_console/config.py` resolves `templates_dir` and `static_dir` from explicit config values, and the current defaults are only repository-relative strings pointing at `scripts/ids_operator_console/templates` and `scripts/ids_operator_console/static`.
- The tests already exercise the app through the factory and override the paths explicitly. `tests/test_ids_operator_console_config.py` and `tests/test_ids_operator_console_web.py` build the app from config and inject template/static directories, which means the test contract is on behavior, not on the old package name itself.

## Decision

YES.

This console surface can move under `ids.console` without breaking the app factory or asset loading, because the runtime is already assembled through explicit config and a single web factory, and the browser contract is anchored to `/static`, not to `scripts/ids_operator_console` paths.

## Asset/app-factory constraints

- Keep one canonical app-factory path. `create_operator_console_web_app()` must remain the only place that mounts `/static` and binds the template directory.
- Keep static and template roots configurable. The move is safe only if the default paths are updated to the new package location and the config still accepts overrides for tests and deployments.
- Keep the server entrypoint thin. `scripts/ids_operator_console_server.py` should remain a wrapper or become a wrapper to the new package location, not a second web bootstrap path.
- Keep URL contracts stable. `/static/*` and the existing web routes should continue to work unchanged after the package move.
- Keep tests package-agnostic. Tests should assert the app behavior and configurable filesystem roots, not the old `scripts/` directory name.

## Recommended rules to embed into affected beads

- Treat `ids.console` as the canonical home for the operator UI, but preserve the single FastAPI app factory and mount behavior.
- Move filesystem defaults with the package, not by hardcoding `scripts/ids_operator_console` anywhere new.
- Preserve `/static` as the public asset mount and keep template references URL-based.
- Keep `scripts/ids_operator_console_server.py` as a compatibility wrapper until the phase-1 migration is fully proven.
- Add or update tests so they verify app creation, route wiring, and configurable asset roots after the package move.
