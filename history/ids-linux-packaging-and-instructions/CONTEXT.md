# Linux Packaging & Instructions Readiness — Context

**Feature slug:** ids-linux-packaging-and-instructions
**Date:** 2026-04-04
**Exploring session:** complete
**Scope:** Standard

---

## Feature Boundary

Review all existing documentation and packaging infrastructure, verify Linux deployment readiness, fill gaps in packaging tooling and operator instructions so the system can be built, shipped, and run on a fresh Linux host from a single set of docs.

**Domain type(s):** RUN, READ, ORGANIZE

---

## Locked Decisions

### Release Artifact Structure
- **D1** The decision on whether to trim the release tarball (via `.gitattributes` `export-ignore`) or ship the full repo checkout is delegated to planning. Planning should analyze actual tarball size, identify dev-only content, and recommend based on operational trade-offs.
  *Rationale: User deferred — planning has better context after codebase analysis.*

### Documentation
- **D2** The target audience and depth of Linux prerequisites documentation is delegated to planning. Planning should assess what system packages are needed and propose appropriate detail level.
  *Rationale: User deferred — planning can inspect actual installer dependencies.*

- **D3** The choice of shell syntax (bash-only, PowerShell-only, or dual examples) across all documentation is delegated to planning. Planning should evaluate per-document purpose and recommend consistency.
  *Rationale: User deferred — the right answer depends on each document's audience.*

### Model Bundle Delivery
- **D4** Whether the trained model bundle ships inside the release tarball or is delivered separately is delegated to planning. Planning should evaluate bundle size, git-tracked status, and operator workflow impact.
  *Rationale: User deferred — requires size analysis and workflow assessment.*

### Agent's Discretion
All four gray areas (D1–D4) were delegated to planning. Planning has full discretion to make concrete recommendations on each, subject to these constraints:
- Recommendations must respect the critical patterns from `history/learnings/critical-patterns.md`, especially "Build Release Bundles From A Safe Export Surface" (git archive safety) and "Prove Editable Installs In A Scrubbed Environment".
- Any recommendation that changes the existing `ops/build_release.sh` or `ops/install.sh` contract must justify why and prove backward compatibility or document the migration path.

---

## Existing Code Context

From the codebase review during exploring. Downstream agents: read these files before planning.

### Reusable Assets
- `pyproject.toml` — 10 CLI entrypoints, package-data for templates/CSS/JS, setuptools backend
- `requirements.txt` — pinned deps (numpy, pandas, scikit-learn, catboost, fastapi, uvicorn, jinja2, etc.), tested on Python 3.11.9
- `ops/build_release.sh` — git archive-based release bundler with wheelhouse support
- `ops/install.sh` — full Linux installer (system users, venv, systemd, secrets, permissions hardening)
- `ops/ids-operator-console.env.example` — environment template for target host
- `deploy/systemd/ids-live-sensor.service` — live sensor systemd unit
- `deploy/systemd/ids-operator-console.service` — operator console systemd unit
- `deploy/systemd/ids-operator-console-notify.service` — notification worker systemd unit
- `deploy/nginx/ids-operator-console.conf.example` — reverse proxy config template

### Established Patterns
- **Safe export surface:** `build_release.sh` uses `git archive HEAD` — only tracked files ship. Critical pattern from `20260404-telegram-settings-deploy-hardening.md`.
- **Hardened secret seeding:** `install.sh` re-applies `0640 root:ids-operator` on pre-seeded env files. Critical pattern from same learning.
- **Editable install proof:** packaging learnings require fresh `__pycache__`-free install proofs. Critical pattern from `20260403-packaging-contract-proof.md`.
- **Interpreter trust boundary:** `install.sh` creates a dedicated `.venv` and the systemd units use that venv's Python. Critical pattern from same learning.
- **Canonical checkout root:** `/opt/ids_ml_new` is enforced by the installer and all systemd units.

### Integration Points
- `ids/ops/same_host_stack_manage.py` — `ids-stack` CLI, the canonical lifecycle surface for preflight/bootstrap/status/smoke/recover
- `ids/ops/live_sensor_preflight.py` — preflight gate for live sensor, called by systemd ExecStartPre
- `ids/ops/operator_console_preflight.py` — preflight gate for console, called by systemd ExecStartPre
- `ids/console/server.py` — console app factory, the FastAPI application entrypoint

### Known Gaps Found During Review
- No `.gitattributes` file exists — `git archive` exports everything tracked
- No Linux prerequisites/system-packages documentation
- `docs/current/operations/e2e_demo_runbook.md` uses PowerShell syntax exclusively
- Root `README.md` quick-test uses PowerShell syntax
- No `MANIFEST.in` (relevant for `sdist` but not for the current editable-install deployment path)
- Installer does not verify Python version before creating venv

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `ops/README-deploy.md` — Golden path deployment guide
- `docs/current/operations/deployment_quickstart.md` — Quickstart deployment reference
- `docs/current/operations/ids_same_host_stack_operations.md` — Full stack operations guide
- `docs/current/operations/e2e_demo_runbook.md` — Demo walkthrough (currently Windows-only)
- `history/learnings/critical-patterns.md` — All promoted critical learnings (mandatory context)

---

## Outstanding Questions

### Resolve Before Planning
None — all four gray areas were delegated to planning with discretion.

### Deferred to Planning
- [ ] What is the actual size of the release tarball with and without dev artifacts? — Measure before deciding D1.
- [ ] Is `artifacts/final_model/catboost_full_data_v1` git-tracked or gitignored? — Determines D4 feasibility.
- [ ] Which system packages (apt/yum) are needed for `dumpcap`, `python3.11`, `cicflowmeter`? — Needed for D2.
- [ ] Should `install.sh` add a Python version check before `python3.11 -m venv`? — Technical question for planning.
- [ ] Are there any missing files in `pyproject.toml` `package-data` that would break a fresh editable install? — Verify with install proof.

---

## Deferred Ideas

- **Container/Docker packaging** — not requested, Linux bare-metal is the deployment target. Could be a future feature.
- **CI/CD pipeline** — no CI exists; could automate `build_release.sh` and run install proofs. Separate work item.
- **Cloud deployment docs** (AWS, Azure, etc.) — not in scope for same-host deployment.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions (all delegated — planning has discretion), code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1–D4) are stable. Reference them by ID in all downstream artifacts.
