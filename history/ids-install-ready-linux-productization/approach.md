# Approach: Install-Ready Linux Productization

**Date**: 2026-04-05
**Feature**: ids-install-ready-linux-productization
**Based on**:
- `history/ids-install-ready-linux-productization/discovery.md`
- `history/ids-install-ready-linux-productization/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Installer modes | `ops/install.sh` installs one shape and optionally bootstraps | one explicit `console-only` vs `full-stack same-host` operator contract | Medium |
| Host config contract | operator console already has `/etc/ids-operator-console/*.env` + `EnvironmentFile` | equivalent live-sensor host env contract and no required manual unit edits | Large |
| Default extractor | repo contains replacement extractor path, but deploy defaults still point at CICFlowMeter | replacement extractor as packaged default for new installs | Medium |
| Bundle bootstrap | bundle lifecycle CLI exists and stack bootstrap can use it | shipped-bundle auto `verify + promote` when a valid default artifact is present | Large |
| Release validation | `ops/build_release.sh` exports a safe tracked tree and builds wheelhouse | fail-fast validation of the default product artifact before packaging | Medium |
| Host-tool config consistency | `ids-stack` can parse env files and carry a validated config snapshot | operator-side lifecycle tools should align with the host env contract instead of ambient process env | Medium |
| Readiness proof | `ids-stack preflight/status/smoke` already exist | mode-specific install success criteria and clean end-to-end proof for both modes | Medium |

---

## 2. Recommended Approach

Keep the current same-host architecture, but move the product boundary from “repo plus runbook” to “mode-aware installer plus validated shipped artifact.” The installer should become the one place that chooses between `console-only` and `full-stack same-host`, seeds the right host config files, generates or hardens secrets, and then invokes the existing canonical lifecycle surfaces rather than bypassing them. The live sensor should be brought into parity with the operator console by giving it a host-owned env file and making the replacement extractor the packaged default. Release build should fail before shipping if the default bundled production artifact is invalid, and `full-stack same-host` install should auto `verify + promote` that shipped artifact unless the operator explicitly overrides it. This keeps the architecture familiar, preserves the activation contract, and removes the manual steps that currently make Linux deployment feel fragile.

### Why This Approach

- It reuses the strongest pattern already present in the repo: package-backed CLIs, exact-path preflight, and same-host orchestration through `ids-stack`.
- It honors locked decisions `D1-D13` without inventing a second deployment topology or reopening raw file-path runtime seams.
- It uses the operator console deploy contract as the model for live sensor normalization, which reduces novelty and review risk.
- It catches broken default artifacts at release time instead of letting operators discover them after host install.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Install UX | One explicit mode selector for `console-only` vs `full-stack same-host` | Makes the product story operator-obvious and directly implements `D1-D3` |
| Live-sensor deploy contract | Introduce a live-sensor env file consumed by `EnvironmentFile` in the systemd unit | Matches the already-working operator-console deploy pattern and implements `D7-D9` |
| Default extractor | Package and call the replacement extractor by default; keep CICFlowMeter as override-only compatibility path | Removes avoidable Linux setup friction and matches `D9` |
| Bundle activation | In `full-stack same-host`, install invokes canonical `verify/promote` on the shipped default artifact unless the operator explicitly overrides the bundle root | Preserves the activation contract while implementing `D4-D6` |
| Release gate | `ops/build_release.sh` verifies the shipped default product artifact before emitting the tarball | Moves bundle-integrity failure to build time and implements `D12` |
| Host-tool config | Reuse env-file parsing / validated snapshot patterns so install-time and host-side CLI/runtime interpret the same contract | Avoids CLI/runtime drift and applies the config-contract learnings |

---

## 3. Alternatives Considered

### Option A: Keep the current packaging and just improve the docs

- Description: leave service units, installer, and bundle flow mostly as-is; document the manual overrides better.
- Why considered: lowest code churn and the repo already has detailed runbooks.
- Why rejected: it fails the product goal. The problem is operator friction in the contract itself, not lack of written instructions.

### Option B: Force every install through one `full-stack` path

- Description: simplify the CLI by dropping `console-only` and making every host satisfy live-sensor prerequisites.
- Why considered: smaller lifecycle surface on paper.
- Why rejected: it turns admin/demo hosts into second-class citizens and keeps unnecessary capture/runtime setup on machines that do not need it.

### Option C: Solve it with `.deb` packaging or container-first deployment now

- Description: move directly to an OS-native package or container image so host lifecycle complexity is hidden elsewhere.
- Why considered: it sounds like a more “productized” packaging story.
- Why rejected: it creates a second primary operational path before the current same-host contract is coherent. Locked decisions explicitly defer this.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Installer mode split in `ops/install.sh` | **MEDIUM** | Extends an existing script but changes operator-facing lifecycle semantics | Install-path tests + docs/runbook proof |
| Live-sensor env contract + service rewrite | **HIGH** | Changes supervised service startup contract and touches tokenization-sensitive extractor startup | Validating spike on service/env/tokenization design |
| Default replacement extractor path | **MEDIUM** | Variation of an existing repo pattern but affects real host runtime startup | End-to-end preflight/startup tests |
| Release-time default bundle verification | **MEDIUM** | Extends existing release builder with new failure gate | Build-path tests with valid and invalid bundle cases |
| Full-stack auto verify/promote during install | **HIGH** | Mutates activation state and changes what “install success” means on a production path | Validating spike on installer/bootstrap/error semantics |
| Host-tool config unification | **MEDIUM** | Shared config behavior across install, stack, and console tools can drift if underspecified | Regression tests for env-file-driven host CLIs |
| Mode-specific readiness proof | **LOW** | Existing `ids-stack` and console smoke contracts already exist; this is mostly composition and docs | Mode-specific smoke tests |

### HIGH-Risk Summary (for khuym:validating skill)

- **Live-sensor env contract + service rewrite**: prove the exact `EnvironmentFile` shape, extractor tokenization semantics, and no-regression startup path before execution.
- **Full-stack auto verify/promote during install**: prove fail-closed behavior, override semantics, and the trust boundary between preflight approval and privileged bootstrap execution.

### Validation Blocker (2026-04-05)

- **Spike `ids_ml_new-3tcz` returned NO**: one live-sensor host env contract cannot yet carry extractor tokenization cleanly through the deployed startup path because the shipped unit still hardcodes runtime values and shells through `bash -lc`, while `ops/install.sh` does not seed a live-sensor env file.
- **Why this blocks the current phase shape**: Phase 1 currently assumes Story 2 can normalize the env contract and Story 3 can pin extractor startup on top of it, but the spike shows the shell-wrapper/startup contract itself must be made explicit as part of that design before execution starts.
- **Required replanning direction**: re-shape Phase 1 so the live-sensor host-contract story owns both `EnvironmentFile=` wiring and removal of shell-sensitive startup drift, then narrow the packaged default extractor story to one exact helper path instead of an arbitrary multi-token env contract, then rerun validating before any implementation begins.

### Validation Resolution (2026-04-05)

- **Spike `ids_ml_new-tht7` returned YES**: after replanning, the blocker is now contained cleanly inside Phase 1 because Story 2 owns the exact `EnvironmentFile` + direct startup seam and Story 3 owns one exact packaged replacement-extractor helper path on top of that seam.
- **Execution consequence**: Phase 1 can execute without pulling hidden Phase 2 work, provided Story 2 removes `bash -lc` as the normal packaged live-sensor start path and Story 3 keeps arbitrary multi-token prefixes as compatibility overrides rather than the default product contract.

---

## 5. Proposed File Structure

```text
ops/
  install.sh                                  # Mode-aware installer and lifecycle owner
  build_release.sh                            # Release builder with pre-ship bundle validation
  ids-live-sensor.env.example                 # New host-owned env template for live sensor

deploy/
  systemd/
    ids-live-sensor.service                   # Switch to EnvironmentFile + packaged default extractor
    ids-operator-console.service              # Keep as canonical model
    ids-operator-console-notify.service

ids/
  core/
    path_defaults.py                          # Shared Linux defaults remain centralized
  ops/
    same_host_stack.py                        # Host config loading, bootstrap semantics, mode-aware readiness
    same_host_stack_manage.py                 # CLI surface remains canonical
    operator_console_manage.py                # Align host CLI config loading with packaged env contract
    model_bundle_manage.py                    # Canonical bundle lifecycle; reused, not replaced

artifacts/
  final_model/
    <default-bundled-artifact>/               # Release-shipped production bundle, verified at build time

tests/
  ops/
    ...                                       # Installer/release/service contract coverage
  docs/
    ...                                       # Canonical install/bootstrap command smoke

docs/current/
  operations/
    ...                                       # One canonical operator install path, not multiple recipes
```

---

## 6. Dependency Order

```text
Layer 1 (sequential): canonical install contract
  - choose explicit install modes
  - define mode-specific success semantics
  - define live-sensor host config shape

Layer 2 (parallel after Layer 1): host contract convergence
  - update live-sensor service/unit wiring
  - align installer with seeded host env/secrets/default extractor
  - align host-side CLI/config interpretation with the env contract

Layer 3 (parallel after Layer 2): shipped-artifact path
  - release-time default-bundle verification
  - installer auto verify/promote and override semantics

Layer 4 (sequential): operator proof
  - canonical docs/runbook update
  - clean proofs for console-only and full-stack same-host
```

### Parallelizable Groups

- Group A: live-sensor env/unit convergence and installer mode/seeding changes — coupled by contract, but can split after the env shape is pinned.
- Group B: release validation and installer bundle activation semantics — can proceed once the mode behavior is fixed.
- Group C: final docs and end-to-end proofs — depends on Groups A and B.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260403-packaging-contract-proof.md` | validated preflight and privileged bootstrap must share the same interpreter/env contract | install continues to route through canonical stack/bundle CLIs instead of inventing shell-local shortcuts |
| `history/learnings/20260404-telegram-settings-deploy-hardening.md` | release must ship only a safe tracked export and installers must reharden pre-seeded secrets | build stays on `git archive`; install remains the owner of file-hardening and secret seeding |
| `history/learnings/20260330-extractor-contract-hardening.md` | tokenization-sensitive extractor startup must be pinned end-to-end | live-sensor env/service work is treated as a contract surface and flagged HIGH risk |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | production model selection must stay on one activation record | shipped default bundle is still activated only via `verify/promote`, never via raw path overrides |
| `history/learnings/20260329-operator-console-production-hardening.md` | runtime verify-only, mutation explicit | install orchestrates migration/bootstrap/activation explicitly instead of hiding them inside service start |

---

## 8. Open Questions for Validating

- [ ] Should the install command auto-start services immediately in both modes, or should `console-only` and `full-stack` differ here for safer first-run diagnosis?
- [ ] Should the packaged default extractor become one exact helper path while multi-token prefixes remain override-only compatibility paths?
- [ ] What is the cleanest direct systemd start contract for the live sensor once `bash -lc` is removed or contained?
- [ ] How should `console-only` release payload shape interact with the default shipped bundle artifact if release size becomes material?
