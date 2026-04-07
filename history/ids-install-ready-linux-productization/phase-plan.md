# Phase Plan: Install-Ready Linux Productization

**Date**: 2026-04-05
**Feature**: ids-install-ready-linux-productization
**Based on**:
- `history/ids-install-ready-linux-productization/CONTEXT.md`
- `history/ids-install-ready-linux-productization/discovery.md`
- `history/ids-install-ready-linux-productization/approach.md`

---

## 1. Feature Summary

This feature makes Linux deployment feel like a product instead of a repo ritual. After it lands, an operator should be able to pick `console-only` or `full-stack same-host`, run one installer path, and end up with a believable ready state for that mode without manual unit edits, ad-hoc env sourcing, or hand-repaired bundle activation. The work is split because the host contract has to be made stable first, then the shipped-bundle lifecycle can safely become automatic, and only then do end-to-end proofs and docs become trustworthy.

---

## 2. Why This Breakdown

- Phase 1 must happen first because nothing about “install-ready” is believable until the host contract itself is coherent: mode selection, seeded config files, service wiring, and the default extractor path.
- Bundle automation is a separate phase because it mutates production activation state and should only be layered on after the install/runtime contract stops drifting.
- End-to-end operator proof belongs last because docs and smoke paths are only worth freezing after the real install and activation behavior is stable.

---

## 3. Phase Overview Table

| Phase | What Changes In Real Life | Why This Phase Exists Now | Demo Walkthrough | Unlocks Next |
|-------|----------------------------|---------------------------|------------------|--------------|
| Phase 1: Make Install Modes And Host Config Real | A Linux host can be installed as `console-only` or `full-stack same-host` without manual `systemctl edit`, shell-wrapped startup hacks, or ad-hoc config surgery. | This is the minimum believable product loop; nothing else matters until the host contract is clean. | Install in `console-only`, see console + notification services come up from seeded config. Install in `full-stack`, inspect the live-sensor unit/env contract, and see preflight/startup use one exact packaged extractor helper path without override hacks. | Safe bundle automation |
| Phase 2: Make The Shipped Full-Stack Path Self-Bootstrapping | A `full-stack same-host` install can use the shipped default production artifact automatically through canonical `verify + promote`, or fail closed if that artifact is bad. | Once the host contract is stable, the next operator pain is bundle activation drift and post-install manual repair. | Build a release, prove it refuses to ship a broken default artifact, then install `full-stack` and watch activation happen without hand-supplied bundle surgery. | Trustworthy operator docs and proofs |
| Phase 3: Prove The Product Path End To End | Operators have one canonical install/runbook path per mode, and the repo has clean proofs that the documented path is real. | Docs and smoke proofs should freeze the final operator contract, not chase moving internals. | Follow the documented `console-only` and `full-stack` procedures on a clean host or clean proof harness and see them pass the promised checks. | Ship / review / next packaging features |

---

## 4. Phase Details

### Phase 1: Make Install Modes And Host Config Real

- **What Changes In Real Life**: an operator can choose the installation shape intentionally, and the host no longer requires manual unit overrides or hand-written runtime config just to start the right services.
- **Why This Phase Exists Now**: it is obviously first because every later promise depends on one stable host contract.
- **Stories Inside This Phase**:
  - Story 1: Add explicit install modes — the installer stops behaving like one ambiguous path and becomes two clear product choices.
  - Story 2: Make the live-sensor startup contract exact — the live-sensor service moves from hardcoded `Environment=` values and shell-wrapped startup to a seeded host-owned env file plus a direct packaged start path.
  - Story 3: Make the packaged default extractor path exact — the replacement extractor becomes one exact helper path and the preflight/startup contract is pinned around that path.
- **Demo Walkthrough**: On a fresh Linux host, run the installer in `console-only` mode and see it seed config, create/harden secrets, migrate/bootstrap the console path, and enable only the relevant services. Then run the installer in `full-stack same-host` mode and inspect the live-sensor unit/config to see that it uses the packaged env contract, a direct startup path, and one exact packaged extractor helper path without any `systemctl edit`.
- **Unlocks Next**: a safe place to automate bundle activation without layering that logic on top of a drifting host/service contract.

### Phase 2: Make The Shipped Full-Stack Path Self-Bootstrapping

- **What Changes In Real Life**: a full-stack install can use the shipped default production bundle immediately instead of forcing the operator to discover and repair activation by hand.
- **Why This Phase Exists Now**: once the host contract is stable, the next fragile seam is artifact validity and activation ownership.
- **Stories Inside This Phase**:
  - Story 1: Refuse to ship broken defaults — release build validates the default product artifact before emitting a tarball.
  - Story 2: Auto-activate the shipped artifact in full-stack mode — installer drives canonical `verify/promote` when the bundled artifact is valid.
  - Story 3: Keep override and failure semantics explicit — operators can still point at a replacement bundle, and invalid defaults fail closed instead of degrading silently.
- **Demo Walkthrough**: Build a release with a good default artifact and see the build succeed; simulate an invalid default artifact and see the build fail before shipping. Then install `full-stack same-host`, watch the installer promote the shipped bundle automatically, and confirm `active_bundle.json` appears without manual bundle CLI intervention.
- **Unlocks Next**: truthful documentation and mode-specific readiness proofs that reflect the actual product path.

### Phase 3: Prove The Product Path End To End

- **What Changes In Real Life**: the operator-facing docs finally match what the product really does, and the repo has machine-checked proof for both install modes.
- **Why This Phase Exists Now**: only after mode behavior and full-stack activation are stable does it make sense to freeze the operator story.
- **Stories Inside This Phase**:
  - Story 1: Collapse the docs to one canonical path per mode — remove competing recipes and describe the install/bootstrap flow the product now owns.
  - Story 2: Add clean install proofs — prove `console-only` and `full-stack same-host` from a scrubbed environment or equivalent proof harness.
  - Story 3: Pin compatibility seams intentionally — confirm wrapper/doc/service seams that still survive are explicitly tested and documented as compatibility-only.
- **Demo Walkthrough**: Hand an operator the docs for each mode, follow them literally on a clean host, and see the promised checks pass without improvisation. The same repo should also fail loudly if a documented command or packaged seam drifts.
- **Unlocks Next**: review, ship, and follow-on features such as making the two-stage composite bundle the default shipped artifact.

---

## 5. Phase Order Check

- [x] Phase 1 is obviously first
- [x] Each later phase depends on or benefits from the one before it
- [x] No phase is just a technical bucket with no user/system meaning

---

## 6. Approval Summary

- **Current phase to prepare next**: `Phase 1 - Make Install Modes And Host Config Real`
- **What the user should picture after that phase**: a Linux host can be installed in either mode and use seeded config plus one exact packaged extractor helper path without manual service edits or shell-wrapper startup hacks.
- **What will not happen until later phases**: the shipped default bundle will not auto-activate until Phase 2, and final docs/proof cleanup waits until Phase 3.
