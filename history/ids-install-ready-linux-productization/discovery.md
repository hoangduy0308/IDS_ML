# Discovery Report: Install-Ready Linux Productization

**Date**: 2026-04-05
**Feature**: ids-install-ready-linux-productization
**CONTEXT.md reference**: `history/ids-install-ready-linux-productization/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- Keep production model selection on one activation contract. Packaging must not reopen raw model/schema/threshold override seams.
- Use exact-path preflight contracts for Linux services. Host-sensitive services should read from one explicit config source and validate exact helper paths before runtime starts.
- Execute the full stack lifecycle before returning success. Install/bootstrap work is only real if `preflight`, readiness, and smoke-like checks actually run.
- Treat compatibility wrappers as executable contracts. If `scripts/*` remain supported, tests and docs must pin that support intentionally.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260403-packaging-contract-proof.md` | packaging / bootstrap | Preflight approval and privileged bootstrap must run under the same validated interpreter/env contract; install proof must use a scrubbed environment instead of a warmed dev tree. | high |
| `history/learnings/20260404-telegram-settings-deploy-hardening.md` | release / install / config | Release artifacts must come from a safe tracked export surface, and installers must always reharden pre-seeded env/secret files. | high |
| `history/learnings/20260330-extractor-contract-hardening.md` | live sensor / systemd / extractor | Multi-token extractor startup contracts drift across systemd, shell, and argparse unless they are pinned end-to-end in tests. | high |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | bundle activation | Production activation must stay on one verify/promote + activation-record contract even when packaging becomes more automated. | high |
| `history/learnings/20260329-operator-console-production-hardening.md` | operator console lifecycle | Runtime should stay verify-only; migration/bootstrap remain explicit lifecycle steps that install can orchestrate, not implicit side effects of service start. | medium |

---

## Agent A: Architecture Snapshot

> Source: targeted file reads and contract surfaces in `ops/`, `ids/ops/`, `deploy/systemd/`, and `ids/console/`

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `ops` | release building and target-host install orchestration | `ops/build_release.sh`, `ops/install.sh` |
| `ids.ops` | canonical same-host stack lifecycle, operator maintenance, model activation | `ids/ops/same_host_stack_manage.py`, `ids/ops/same_host_stack.py`, `ids/ops/operator_console_manage.py`, `ids/ops/model_bundle_manage.py` |
| `ids.console` | operator console config/runtime contract | `ids/console/config.py`, `ids/console/server.py`, `ids/console/web.py` |
| `ids.core` | path defaults and bundle integrity/activation primitives | `ids/core/path_defaults.py`, `ids/core/model_bundle.py`, `ids/core/model_bundle_activation.py` |
| `deploy/systemd` | shipped service contracts | `deploy/systemd/ids-live-sensor.service`, `deploy/systemd/ids-operator-console.service`, `deploy/systemd/ids-operator-console-notify.service` |
| `ml_pipeline.packaging` | canonical bundle artifact generation | `ml_pipeline/packaging/package_final_model.py` |

### Entry Points

- **Release build**: `ops/build_release.sh`
- **Target-host install**: `ops/install.sh`
- **Canonical stack lifecycle CLI**: `ids-stack` -> `ids.ops.same_host_stack_manage:main`
- **Canonical bundle lifecycle CLI**: `ids-model-bundle-manage` -> `ids.ops.model_bundle_manage:main`
- **Canonical console lifecycle CLI**: `ids-operator-console-manage` -> `ids.ops.operator_console_manage:main`
- **Canonical console service**: `ids-operator-console-server` -> `ids.console.server:main`

### Key Files to Model After

- `deploy/systemd/ids-operator-console.service` — already uses `EnvironmentFile` and a preflight contract; this is the deployment shape the live sensor should converge toward.
- `ids/ops/same_host_stack.py:191` — parses the operator env file and builds one validated config snapshot, which is the right pattern for host-owned config contracts.
- `ids/core/path_defaults.py` — already centralizes canonical Linux paths such as `/opt/ids_ml_new` and the activation record location.
- `ml_pipeline/packaging/package_final_model.py` — already owns the canonical bundle payload shape and is the correct seam for release-shipped artifacts.

---

## Agent B: Pattern Search

> Source: targeted file reads and existing packaging/deploy artifacts

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Host env contract for a supervised service | `deploy/systemd/ids-operator-console.service` | `EnvironmentFile` + preflight + canonical module entrypoint | Yes |
| Config snapshot from env file | `ids/ops/same_host_stack.py:191-240` | parse env file -> merge defaults -> call canonical config loader | Yes |
| Installer hardening for pre-seeded secrets | `ops/install.sh` | reharden existing env/secret files even if the operator created them first | Yes |
| Release export safety | `ops/build_release.sh` | `git archive HEAD` + post-export wheelhouse staging | Yes |
| Canonical installed CLI map | `pyproject.toml` | `project.scripts` bound directly to `ids.*` and `ml_pipeline.*` module `main()` functions | Yes |
| Fail-closed bundle lifecycle | `ids/ops/model_bundle_manage.py` + `ids/core/model_bundle.py` | `verify/promote/rollback` against one activation path | Yes |

### Reusable Utilities

- **Host path defaults**: `ids/core/path_defaults.py` — already centralizes `/opt`, `/var`, and activation-path defaults.
- **Config loading**: `ids.console.config.load_operator_console_config()` — canonical env + secret-file interpretation for the operator control plane.
- **Stack orchestration**: `ids/ops/same_host_stack.py` — already coordinates preflight/bootstrap/status/smoke and threads validated config snapshots forward.
- **Bundle lifecycle**: `ids/ops/model_bundle_manage.py` — canonical verify/promote CLI that install should call instead of inventing its own manifest logic.

### Naming Conventions

- Canonical user-facing CLIs are package-backed and imperative: `ids-stack`, `ids-model-bundle-manage`, `ids-operator-console-manage`.
- Host config lives under `/etc/<product>` and state under `/var/lib/<product>`, with log roots under `/var/log/<product>`.
- Compatibility wrappers remain under `scripts/*`, but package-backed CLIs are the intended canonical story.

---

## Agent C: Constraints Analysis

> Source: `ops/install.sh`, `ops/build_release.sh`, service units, package metadata, and host-contract code

### Runtime & Framework

- **Python requirement**: `>=3.11` in `pyproject.toml`
- **Current installer default**: `python3.11` in `ops/install.sh`
- **Packaging shape**: repo-installable Python product with editable install into `/opt/ids_ml_new/.venv`
- **Supervision model**: `systemd` units under `/etc/systemd/system`
- **Same-host roots**: `/opt/ids_ml_new`, `/etc/ids-operator-console`, `/var/lib/ids-live-sensor`, `/var/lib/ids-operator-console`, `/var/log/ids-live-sensor`

### Existing Dependencies (Relevant to This Feature)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | `0.115.12` | operator console runtime |
| `uvicorn` | `0.34.0` | supervised web service |
| `catboost` | `1.2.10` | production model loading |
| `pandas` | `3.0.1` | runtime feature frame handling |
| `pytest` | `8.3.5` | regression and contract verification |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None required by the locked decisions | The main gaps are contract wiring, release validation, and service/env normalization. | LOW |

### Build / Quality Requirements

```bash
# Existing contract surfaces planning should preserve and extend:
python -m pytest tests/ops -q
python -m pytest tests/runtime -q
python -m pytest tests/docs -q
bash ./ops/build_release.sh --python-bin <python>
sudo bash /opt/ids_ml_new/ops/install.sh ...
```

### Packaging / Install Constraints

- `ops/install.sh` still defaults the extractor to `/opt/cicflowmeter/Cmd`, even though the repo now contains a replacement extractor path.
- `deploy/systemd/ids-live-sensor.service` still hardcodes critical runtime values with `Environment=` rather than a host-owned env file.
- `ops/install.sh` can optionally call `ids-stack bootstrap`, but it still requires the operator to supply `--candidate-bundle-root` when bootstrapping.
- `ids/ops/operator_console_manage.py` loads runtime config from ambient `os.environ`, not from a host env file path, which creates CLI/runtime drift relative to the systemd service contract.
- `ops/build_release.sh` builds wheelhouse and exports tracked files safely, but it does not validate the shipped default bundle before release creation.
- The current packaged final-model surface under `artifacts/final_model/` only contains `catboost_full_data_v1`; there is no shipped composite/two-stage default artifact yet.

### Storage / Host-State Boundaries

- **Activation record**: `/var/lib/ids-live-sensor/active_bundle.json`
- **Live-sensor outputs**: `/var/log/ids-live-sensor/*.jsonl`
- **Console DB**: `/var/lib/ids-operator-console/operator_console.db`
- **Console env and secrets**: `/etc/ids-operator-console/*`
- **Missing host contract**: there is no equivalent `/etc/ids-live-sensor/*.env` file yet

---

## Agent D: External Research

> Source: skipped by design

External research is not required. The gaps are internal productization and contract alignment problems inside the existing repo and deploy assets.

---

## Open Questions

> Items that were not resolvable through research alone.
> These will be raised to the synthesis subagent in Phase 2.

- [ ] Should the installer expose mode selection through one `--mode` flag or explicit mutually-exclusive lifecycle flags? This affects operator clarity and docs simplicity.
- [ ] Should `console-only` releases still carry the default bundle artifact for convenience, or should bundle payload be considered a `full-stack` concern only? This affects release size and distribution shape.
- [ ] How should the live-sensor host env file be named and seeded so it feels parallel to, but not confused with, the operator console env file? This affects operator ergonomics and docs clarity.
- [ ] Should the first install-ready pass auto-start services immediately after success, or only enable them and rely on explicit stack/status commands for the first readiness proof? This affects perceived simplicity versus failure diagnosis clarity.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a package-backed repo with canonical CLI entrypoints, a same-host stack lifecycle surface, safe tracked-file release export, fail-closed bundle activation logic, and a good operator-console env/preflight pattern.

**What we need**: one operator-ready install contract that turns those parts into a believable `console-only` or `full-stack same-host` product without manual systemd surgery, manual env sourcing, or post-install bundle debugging.

**Key constraints from research**:
- The live-sensor service is the biggest remaining outlier: hardcoded `Environment=` values, CICFlowMeter default, and no host env file.
- Install and release still stop short of owning the full operator path: no default-bundle validation in release build, and no automatic shipped-bundle activation path in install.
- The stack layer already knows how to parse an env file and hold a validated config snapshot, so planning should reuse that pattern instead of inventing a second config interpretation path.
- The operator console already proves that `EnvironmentFile` + exact-path preflight + canonical package entrypoint is a workable deploy pattern.

**Institutional warnings to honor**:
- Keep one activation contract for production model selection.
- Bind privileged bootstrap execution to the exact interpreter/env contract that preflight approved.
- Prove install/readiness in a scrubbed environment, not only inside a warmed repo.
- Treat extractor tokenization and compatibility wrappers as explicit executable contracts.
