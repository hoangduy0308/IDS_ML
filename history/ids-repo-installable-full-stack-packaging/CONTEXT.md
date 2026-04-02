# IDS Repo-Installable Full Stack Packaging — Context

**Feature slug:** ids-repo-installable-full-stack-packaging
**Date:** 2026-04-01
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature delivers one canonical, repo-installable packaging path for the full ML-backed IDS stack on a same-host Linux machine, ending at a verified bootstrap that brings up the packaged stack and passes the documented stack readiness checks.

**Domain type(s):** RUN | CALL | READ | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Product Target
- **D1** The packaging effort targets same-host Linux production first, with developer/local ergonomics treated as a secondary layer after the production contract is made coherent.
  *Rationale: The repository's strongest existing contract is the same-host Linux stack, including stack commands, host paths, systemd assets, and production-oriented runbooks.*

- **D2** The packaged product scope is the full stack: model bundle lifecycle, live sensor/runtime, operator console, and same-host stack commands.
  *Rationale: The current canonical docs and runtime contract already define the product boundary as a coordinated full stack rather than an inference-only tool.*

- **D3** The primary distribution target is a repo-installable stack, not a `.deb` package and not a container-first deployment.
  *Rationale: The codebase already has canonical Python package roots and compatibility wrappers, but it does not yet have a normalized install/distribution layer.*

### Readiness Contract
- **D4** "Done" for this packaging work means a fresh Linux host can install from the repo, invoke the canonical packaged entrypoints, and complete the documented bootstrap path through `preflight`, `status`, and `smoke`.
  *Rationale: This proves the packaging is operationally real, not just importable or documented.*

- **D5** The packaged production system must preserve one canonical runtime contract centered on the active bundle activation record and the same-host stack orchestration path.
  *Rationale: Planning must not create a second production model-selection or runtime path that bypasses the activation contract or stack contract.*

### Surface Stability
- **D6** Canonical installed entrypoints must map directly onto the `ids/*` canonical modules, while existing `scripts/*` wrappers remain supported compatibility surfaces during the packaging transition.
  *Rationale: The repo's current architecture intentionally keeps domain logic in `ids/*` and wrappers in `scripts/*`; packaging must strengthen that boundary instead of collapsing it.*

- **D7** Machine-specific paths, host secrets, and deployment-local values must remain externalized in host config or operator inputs; the packaging work must remove dependence on current hardcoded workstation paths as a required runtime assumption.
  *Rationale: A repo-installable product cannot require `F:\\Work\\IDS_ML_New`-style defaults to function on its target Linux host.*

- **D8** The model bundle remains part of the product surface, but production activation must still happen through explicit verify/promote flows and the active-bundle record rather than implicit file-path overrides.
  *Rationale: The model lifecycle is already hardened around verify/promote/rollback and should stay explicit in the packaged system.*

### Documentation Shape
- **D9** Packaging deliverables must include one canonical operator-facing installation path and one canonical documentation spine for install, bootstrap, and verification, rather than multiple "equivalent" setup recipes.
  *Rationale: Planning should reduce ambiguity and operator guesswork instead of documenting several competing deployment styles.*

### Agent's Discretion
- Exact `pyproject`/build-backend choice, dependency grouping, and optional extras layout.
- Final names of installed CLI entrypoints, as long as they map cleanly to canonical modules and preserve documented compatibility surfaces.
- Whether wrapper-smoke, module-smoke, and install-smoke checks are split into separate tests or composed into a shared packaging verification suite.

---

## Specific Ideas & References

- The production packaging path should align with the existing same-host Linux contract, not redefine the product around containers or a notebook-oriented workflow.
- The current full-stack deploy/runbook surface already centers on:
  - active bundle verification/promotion
  - same-host stack bootstrap and health commands
  - operator console plus notification worker
  - live sensor preflight and runtime assets
- The desired result is not merely "a Python package"; it is an installable full system with a single operational path an operator can follow.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `ids/__init__.py` — defines `ids` as the canonical product package root and explicitly frames `scripts/*` as compatibility-only entrypoints.
- `ids/runtime/inference.py` — canonical inference CLI/module surface, already enforces bundle/config/activation exclusivity and demonstrates the desired module-to-entrypoint mapping.
- `ids/ops/same_host_stack_manage.py` — canonical full-stack orchestration entrypoint and argument contract for `preflight`, `bootstrap`, `status`, `smoke`, `recover`, `restore-inventory`, and `post-restore-check`.
- `scripts/ids_inference.py` — compatibility wrapper that bootstraps repo-root import resolution before delegating to the canonical module.
- `scripts/ids_same_host_stack_manage.py` — compatibility wrapper for stack orchestration, preserving file-execution behavior from the repo checkout.
- `requirements.txt` — current dependency pin set and the current lightweight install surface the packaging work will supersede or formalize.

### Established Patterns
- Canonical-module boundary: implementation lives under `ids/*`; `scripts/*` forwards into canonical modules.
- Activation-contract model selection: production runtime resolves one active bundle through the activation record instead of mixing independent model/schema/threshold paths.
- Same-host orchestration: stack-level commands coordinate component owners but do not absorb their domain-specific mutation logic.
- Compatibility preservation: wrappers are treated as executable contracts and must be tested if they remain part of the user-facing surface.

### Integration Points
- `ml_pipeline/packaging/package_final_model.py` — current bundle assembly path and a likely packaging-adjacent integration point for how the shipped candidate bundle is structured.
- `docs/current/runtime/final_model_bundle.md` — defines the bundle contract and verify/promote/rollback expectations that packaging must preserve.
- `docs/current/operations/ids_same_host_stack_operations.md` — defines the same-host install/bootstrap/health lifecycle that packaging must satisfy.
- `deploy/systemd/ids-live-sensor.service` — shipped host integration asset for the live sensor service.
- `deploy/systemd/ids-operator-console.service` — shipped host integration asset for the operator console service.
- `deploy/systemd/ids-operator-console-notify.service` — shipped host integration asset for the notification worker.
- `deploy/nginx/ids-operator-console.conf.example` — reverse-proxy edge asset already expected by the stack docs.
- `tests/runtime/test_ids_inference.py` — regression coverage for canonical bundle/config resolution behavior.
- `tests/ops/test_ids_same_host_stack_manage.py` — regression coverage for stack command wiring and contract behavior.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `docs/current/operations/ids_same_host_stack_operations.md` — canonical same-host install/bootstrap/status/smoke/recover contract.
- `docs/current/runtime/final_model_bundle.md` — canonical bundle packaging, verification, activation, and rollback contract.
- `history/learnings/critical-patterns.md` — promoted critical constraints around wrappers, activation contracts, path containment, explicit preflight, and fail-closed runtime behavior.
- `ids/__init__.py` — states the intended canonical package boundary between `ids/*` and `scripts/*`.

---

## Outstanding Questions

### Deferred to Planning
- [ ] What exact installation shape should the repo-installable product use: editable install, wheel/sdist install, or both? — Planning needs to choose the lowest-risk install contract that still satisfies D4.
- [ ] How should dependencies be grouped between runtime-critical, console/web, ML tooling, and dev/test extras? — Planning should normalize dependency boundaries without breaking the documented stack.
- [ ] Which existing hardcoded path defaults must be removed immediately versus retained only as compatibility fallbacks? — Planning needs a codebase-wide audit and prioritization.
- [ ] Should the packaged install expose new canonical CLI names while retaining `scripts/*`, or should the first packaging pass keep names functionally identical? — Planning needs to balance product clarity against migration risk.
- [ ] How should the shipped candidate bundle be handled for installation size and operator flow: included in the install path, staged as a documented prerequisite, or split into an explicit optional artifact? — Planning must resolve this without violating D8.

---

## Deferred Ideas

- `.deb` or other OS-native package output — deferred because the repo-installable contract should be stabilized first.
- Container-first deployment flow — deferred because it would define a second primary operational path instead of hardening the existing same-host contract.
- Full upgrade-story productization beyond the existing bundle rollback/recover surfaces — deferred until the initial packaging contract is installable and bootstrap-clean.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
