# Install-Ready Linux Productization — Context

**Feature slug:** ids-install-ready-linux-productization
**Date:** 2026-04-05
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature turns the current repo-and-runbook Linux deployment into one canonical install path that can land in either `console-only` mode or `full-stack same-host` mode without manual systemd overrides, ad-hoc bootstrap sequencing, or hidden host-specific assumptions.

**Domain type(s):** RUN | CALL | READ | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Product Modes
- **D1** The installer must support two explicit modes: `console-only` and `full-stack same-host`.
  *Rationale: This keeps the operator path realistic for both demo/admin hosts and real sensor hosts instead of forcing one host shape on every install.*

- **D2** `console-only` is a first-class product mode, not a degraded accident. A successful `console-only` install ends with operator console plus notification services working through the canonical packaged surfaces without requiring live sensor activation.
  *Rationale: The operator/admin host use case is real and should not inherit full capture/runtime requirements.*

- **D3** `full-stack same-host` remains the canonical production mode for a host that should actually run capture, bundle activation, and same-host stack checks.
  *Rationale: The existing stack/runbook contract is still the main production contract and must stay coherent.*

### Bundle & Bootstrap Behavior
- **D4** The installer must support both shipped-bundle bootstrap and explicit operator override, but if the release contains a valid packaged production bundle then install defaults to auto `verify + promote` of that bundle.
  *Rationale: This is the shortest path to “install and use immediately” while still preserving an escape hatch for operator-selected bundles.*

- **D5** In `full-stack same-host`, install must fail closed if the default bundled artifact cannot be verified/promoted and no explicit replacement bundle was supplied.
  *Rationale: A product that claims full-stack readiness must not silently leave the host half-activated.*

- **D6** `console-only` must not require a candidate bundle root or activation record to succeed.
  *Rationale: That mode exists specifically to avoid unnecessary runtime capture/model prerequisites.*

### Host Configuration Contract
- **D7** The canonical install path must eliminate manual service edits and ad-hoc drop-ins as required operator steps. Host-specific values belong in seeded env/config files, not in post-install unit surgery.
  *Rationale: The current manual override flow is exactly the operator pain this feature is meant to remove.*

- **D8** Live sensor configuration must move to a host-owned env/config contract analogous to the operator console env file; packaged systemd units should consume that contract instead of hardcoded `Environment=` defaults for critical runtime behavior.
  *Rationale: The live sensor currently needs manual intervention for interface/extractor changes, which blocks zero-surprise packaging.*

- **D9** The replacement offline extractor becomes the default packaged extractor path; CICFlowMeter remains compatibility-only and must not remain the canonical default for new installs.
  *Rationale: The repo already contains the replacement path, and the goal is to remove avoidable external setup friction on Linux hosts.*

- **D10** Machine-specific paths, secrets, interfaces, public URLs, and similar deployment-local values remain externalized, but the installer may seed safe defaults and generated secrets so the canonical path does not depend on manual file creation before first boot.
  *Rationale: Externalized config is still correct; the friction comes from lack of seeded contracts, not from config existing at all.*

### Lifecycle & Verification
- **D11** The canonical install path must absorb the current manual sequence of env seeding, secret generation, DB migration, admin bootstrap, bundle activation, and base service enablement into one documented lifecycle instead of leaving these as separate operator-discovered chores.
  *Rationale: “Install-ready” means the product owns this sequencing rather than requiring the operator to reconstruct it from memory.*

- **D12** Release creation must verify the shipped production artifact before packaging and fail the build if the default product artifact is internally inconsistent.
  *Rationale: The Kali `feature schema digest mismatch` failure shows that bundle integrity drift must be caught before shipping, not after host install.*

### Surface Stability
- **D13** Canonical installed entrypoints must map onto the `ids/*` package modules; `scripts/*` wrappers remain compatibility surfaces only and are not the primary operator story.
  *Rationale: The repo architecture already intends `ids/*` to be canonical and wrappers to be transitional.*

### Agent's Discretion
- Exact CLI UX for mode selection, bundle override flags, and admin credential output.
- Exact env file names/locations for live sensor config, as long as they become the canonical host contract.
- Whether service enable/start behavior is split between install-time flags or inferred from mode.
- Whether release packaging uses a single tarball or a tarball plus optional side artifact, as long as D4-D12 remain true.

---

## Specific Ideas & References

- The desired operator story is: copy one release to Linux, run one installer command, and land in a believable ready state for the selected mode.
- `console-only` should prove the admin/control plane is operational without asking the host to solve capture/extractor/model activation.
- `full-stack same-host` should prove the host can actually score with the packaged default bundle and packaged extractor path.
- Manual `systemctl edit`, manual `source ...env`, and manual bundle repair are specifically anti-goals for the canonical path.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `ops/install.sh` — current Linux host installer; already seeds console env/secrets, installs the venv, installs systemd units, and can optionally invoke stack bootstrap.
- `ops/build_release.sh` — current release builder; exports the tracked repo and wheelhouse, but does not yet enforce shipped-bundle validity before packaging.
- `deploy/systemd/ids-live-sensor.service` — current live sensor service contract; hardcodes critical runtime values with `Environment=` and still defaults extractor behavior to CICFlowMeter.
- `ids/console/config.py` — current operator console config loader; demonstrates the host-env + secret-file contract the live sensor path should converge toward.
- `ids/ops/operator_console_manage.py` — current operator console lifecycle CLI; shows the existing migration/bootstrap/admin/notification lifecycle that install-ready packaging must absorb cleanly.
- `ml_pipeline/packaging/package_final_model.py` — current bundle packager; this is the packaging seam for default shipped product artifacts.
- `ids/core/model_bundle.py` — current bundle manifest validation and feature-schema hashing; this is where shipped artifact integrity is enforced.

### Established Patterns
- Canonical module boundary: real behavior lives under `ids/*`, while `scripts/*` are compatibility wrappers.
- Single activation contract: production runtime is supposed to resolve one active bundle via the activation record instead of loose file-path overrides.
- Fail-closed validation: bundle integrity problems already have a canonical enforcement point and should not be papered over in install logic.
- Same-host orchestration: `ids-stack` is the lifecycle surface that coordinates the host, not a pile of independent shell instructions.

### Integration Points
- `ops/install.sh` — extend mode selection, seeded host contracts, automatic lifecycle sequencing, and default-bundle behavior.
- `deploy/systemd/ids-live-sensor.service` — replace hardcoded runtime defaults with a host env contract and default packaged extractor.
- `ops/build_release.sh` — add pre-ship bundle validation so release artifacts fail before distribution if the default product artifact is broken.
- `ml_pipeline/packaging/package_final_model.py` and `ids/core/model_bundle.py` — define the release-time validity contract for shipped bundle artifacts.
- `ids/console/config.py` and `ids/ops/operator_console_manage.py` — converge CLI/runtime behavior so host tools can use the packaged env contract consistently.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `history/learnings/critical-patterns.md` — promoted constraints around activation contracts, wrapper seams, fail-closed runtime behavior, and explicit Linux path checks.
- `history/ids-repo-installable-full-stack-packaging/CONTEXT.md` — prior packaging lane that hardened the same-host Linux direction and canonical packaging surface.
- `docs/current/operations/ids_same_host_stack_operations.md` — current same-host lifecycle the packaged installer must preserve while simplifying operator effort.
- `docs/current/runtime/final_model_bundle.md` — canonical bundle verification/promotion/rollback contract that install-ready packaging must preserve.

---

## Outstanding Questions

### Deferred to Planning
- [ ] What exact CLI surface should the installer expose for `console-only` vs `full-stack same-host`? — Planning needs to pick a mode-selection UX that is operator-obvious and testable.
- [ ] What is the exact live-sensor env file contract and how should unit files consume it? — Planning needs to settle the host config shape and service wiring.
- [ ] How should admin bootstrap credentials be created and surfaced safely in the zero-manual canonical path? — Planning needs a concrete operator-safe credential story.
- [ ] What exact success checks define `console-only` readiness versus `full-stack same-host` readiness? — Planning needs mode-specific exit criteria and smoke semantics.
- [ ] How should the release artifact include the default product bundle while keeping release size and override paths manageable? — Planning needs to reconcile D4 and D12 with distribution ergonomics.

---

## Deferred Ideas

- `.deb`/OS-native packaging — deferred until the repo-installable contract is actually install-ready.
- Container-first deployment — deferred because it would create a second primary operator story instead of fixing the current same-host one.
- Full upgrade/orchestration productization beyond install/bootstrap/readiness — deferred until the install path itself is clean.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
