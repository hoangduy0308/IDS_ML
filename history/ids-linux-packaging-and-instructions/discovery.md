# Discovery Report: Linux Packaging & Instructions Readiness

**Date**: 2026-04-04
**Feature**: ids-linux-packaging-and-instructions
**CONTEXT.md reference**: `history/ids-linux-packaging-and-instructions/CONTEXT.md`

---

## Institutional Learnings

### Critical Patterns (Always Applied)

- **Build Release Bundles From A Safe Export Surface** — `git archive HEAD` is already the export method in `ops/build_release.sh`. Any tarball trimming must keep this approach, not regress to manual tar exclusions.
- **Harden Pre-Seeded Secret Files During Install** — `ops/install.sh` already re-applies `0640 root:ids-operator` on pre-seeded env files. Any install changes must preserve this.
- **Prove Editable Installs In A Scrubbed Environment** — packaging work must include a fresh install proof that removes `__pycache__` dependence.
- **Bind Privileged Bootstrap To Validated Interpreter Contract** — the `.venv/bin/python` path is the canonical interpreter. Documentation must not suggest using host-global Python.

### Domain-Specific Learnings

| File | Key Insight | Severity |
|------|-------------|----------|
| `20260403-packaging-contract-proof.md` | Warmed `__pycache__` can mask missing source files; fresh install proofs are mandatory | critical |
| `20260404-telegram-settings-deploy-hardening.md` | `git archive` is the safe export surface; never archive the raw working tree | critical |
| `20260404-telegram-settings-deploy-hardening.md` | Config contracts must be shared, not reimplemented per surface | critical |
| `20260403-packaging-contract-proof.md` | Wrapper seams need explicit test coverage or intentional narrowing | standard |

---

## Architecture Snapshot

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `ids/` | Main Python package (runtime, console, ops, core) | `ids/__init__.py`, subpackages |
| `ml_pipeline/` | ML training and model packaging | `ml_pipeline/packaging/package_final_model.py` |
| `ops/` | Release and install scripts | `build_release.sh`, `install.sh`, `ids-operator-console.env.example` |
| `deploy/` | Deployment artifacts | `systemd/*.service`, `nginx/*.conf.example` |
| `docs/current/` | Active documentation | `operations/`, `runtime/`, `console/`, `ml/` |

### Entry Points (10 CLI commands from pyproject.toml)

- `ids-inference`, `ids-realtime-pipeline`, `ids-live-sensor`, `ids-live-sensor-health`
- `ids-live-sensor-preflight`, `ids-model-bundle-manage`
- `ids-operator-console-server`, `ids-operator-console-preflight`, `ids-operator-console-manage`
- `ids-stack`, `ids-package-final-model`

---

## Tarball Size Analysis

- **Uncompressed git archive**: ~36.5 MB (771 files)
- **Model bundle** (`artifacts/final_model/catboost_full_data_v1`): git-tracked, explicitly whitelisted in `.gitignore`
- **Dev-only directories in archive**: `.beads/`, `.claude/`, `.khuym/`, `.spikes/`, `history/`, `kaggle/`, `tests/`, `design/`, `AGENTS.md`, `wrapper_smoke_support.py`, `tests_editable_install_cache.py`
- **Production-needed**: `ids/`, `ml_pipeline/`, `artifacts/final_model/`, `deploy/`, `ops/`, `docs/`, `scripts/`, `pyproject.toml`, `requirements.txt`, `README.md`
- **No `.gitattributes` file exists** — no `export-ignore` rules
- **No `MANIFEST.in` file exists** — not needed for current editable-install path

---

## Linux Prerequisites Catalog

### Required

| System Package | Why Needed | Default Path |
|----------------|-----------|--------------|
| Python 3.11+ | Application runtime | `python3.11` (configurable) |
| bash | Systemd ExecStart shells | `/usr/bin/bash` |
| systemd + systemctl | Service lifecycle management | system |
| dumpcap (wireshark-common) | Live packet capture | `/usr/bin/dumpcap` (configurable) |
| CICFlowMeter | Flow feature extraction from PCAPs | `/opt/cicflowmeter/Cmd` (configurable) |
| GNU coreutils | install, chmod, chown for hardening | system |

### Optional

| System Package | Why Needed | Default Path |
|----------------|-----------|--------------|
| nginx | Reverse proxy with HTTPS termination | config example provided |
| certbot | SSL certificate provisioning | referenced in nginx example |
| git | Building release archives (build-time only) | system |

### Host Directory Layout

| Path | Owner | Mode | Purpose |
|------|-------|------|---------|
| `/opt/ids_ml_new` | root | 0755 | Canonical checkout root |
| `/opt/ids_ml_new/.venv` | root | 0755 | Python virtual environment |
| `/etc/ids-operator-console/` | root:ids-operator | 0750 | Configuration |
| `/var/lib/ids-live-sensor/` | ids-sensor:ids-sensor | 0750 | Sensor runtime state |
| `/var/log/ids-live-sensor/` | ids-sensor:ids-sensor | 0750 | Sensor output logs |
| `/var/lib/ids-operator-console/` | ids-operator:ids-operator | 0750 | Console database |
| `/var/backups/ids-operator-console/` | ids-operator:ids-operator | 0750 | Console backups |

---

## Documentation Shell Syntax Audit

### Bash/Linux only (7 files — correct for deployment audience)
- `ops/README-deploy.md`
- `docs/current/operations/deployment_quickstart.md`
- `docs/current/operations/ids_same_host_stack_operations.md`
- `docs/current/runtime/final_model_bundle.md`
- `docs/current/runtime/ids_live_sensor_operations.md`
- `docs/current/console/ids_operator_console_operations.md`

### PowerShell only (3 files — development audience)
- `README.md` (root)
- `docs/current/ml/kaggle_parallel_benchmark.md`
- `docs/current/ml/dataset_preprocessing_protocol.md`

### Mixed/PowerShell with Windows paths (5 files — need attention)
- `docs/current/operations/e2e_demo_runbook.md`
- `docs/current/runtime/ids_inference_architecture.md`
- `docs/current/runtime/ids_realtime_pipeline_architecture.md`
- `docs/current/ml/system_evaluation.md`
- `docs/current/ml/hyperparameter_tuning_setup.md`

---

## Open Questions

- [x] Tarball size measured: ~36.5 MB uncompressed — reasonable but could be trimmed
- [x] Model bundle is git-tracked — intentionally whitelisted
- [ ] Exact compressed tarball size (gzip) — estimate ~10-15 MB
- [ ] Whether `scripts/` directory is needed on target host for backward compatibility

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: A mature same-host deployment stack with `build_release.sh` (git archive), `install.sh` (full Linux installer), 3 systemd units, nginx example, env template, and comprehensive ops docs already written in bash.

**What we need**: `.gitattributes` for tarball trimming, Linux prerequisites documentation, cross-platform doc consistency fixes, and a decision on model bundle packaging.

**Key constraints from research**:
- Git archive safety must be preserved (critical pattern)
- 36.5 MB tarball includes ~40% dev-only content that could be stripped
- 5 documentation files use Windows-only syntax and need platform attention

**Institutional warnings to honor**:
- Never regress `build_release.sh` to manual tar exclusions
- Fresh install proofs must be run after any packaging changes
- All documentation must reference `.venv/bin/python`, not host-global Python
