# Story Map: Phase 1 - Make Install Modes And Host Config Real

**Date**: 2026-04-05
**Phase Plan**: `history/ids-install-ready-linux-productization/phase-plan.md`
**Phase Contract**: `history/ids-install-ready-linux-productization/phase-1-contract.md`
**Approach Reference**: `history/ids-install-ready-linux-productization/approach.md`

---

## 1. Story Dependency Diagram

```mermaid
flowchart LR
    E[Entry State] --> S1[Story 1: Explicit install modes]
    S1 --> S2[Story 2: Exact live-sensor startup contract]
    S2 --> S3[Story 3: Exact packaged replacement extractor default]
    S3 --> X[Exit State]
```

---

## 2. Story Table

| Story | What Happens In This Story | Why Now | Contributes To | Creates | Unlocks | Done Looks Like |
|-------|-----------------------------|---------|----------------|---------|---------|-----------------|
| Story 1: Explicit install modes | Installer behavior becomes explicitly split into `console-only` and `full-stack same-host`. | This is first because later service/config behavior must know which host shape is being installed. | Exit state 1 | Mode-aware installer contract | Story 2 | Installer help, flags, and install behavior make the two modes unambiguous. |
| Story 2: Exact live-sensor startup contract | Live sensor stops depending on hardcoded unit `Environment=` values and shell-wrapped startup, and instead reads seeded host config through one direct packaged startup contract. | Once modes exist, the service contract can be normalized around them. | Exit state 2 | New live-sensor env template, unit wiring, and direct startup contract | Story 3 | A normal live-sensor configuration change no longer requires `systemctl edit` or `bash -lc` startup hacks. |
| Story 3: Exact packaged replacement extractor default | The packaged replacement extractor becomes one exact helper path and its startup contract is pinned. | This closes the most painful Linux prerequisite before Phase 2 automates shipped-bundle activation. | Exit state 3 | Default exact-path extractor contract + verification coverage | Phase 2 | Preflight/startup use the packaged replacement-extractor helper path by default and tests pin that behavior. |

---

## 3. Story Details

### Story 1: Explicit install modes

- **What Happens In This Story**: `ops/install.sh` grows an explicit product-level mode choice and mode-specific behavior for what it seeds, enables, and treats as required.
- **Why Now**: The installer must know whether it is making a control-plane-only host or a real sensor host before any later contract can be normalized.
- **Contributes To**: Exit state 1 — the installer exposes an explicit choice between `console-only` and `full-stack same-host`.
- **Creates**: a mode-aware install contract, mode-specific validation rules, and a stable place for later bundle automation to hook in.
- **Unlocks**: Story 2 can define the live-sensor host contract against a known `full-stack` mode instead of an ambiguous generic install.
- **Done Looks Like**: installer help, docs stub, and install-path behavior all tell the same story about the two modes.
- **Candidate Bead Themes**:
  - installer mode flag/behavior ownership
  - mode-specific verification and docs-command proof

### Story 2: Exact live-sensor startup contract

- **What Happens In This Story**: the live-sensor systemd unit stops carrying critical runtime configuration as hardcoded `Environment=` values, reads a seeded host env file, and starts through a direct packaged path instead of a shell-sensitive wrapper.
- **Why Now**: This only makes sense after Story 1 has clarified which installs should even own live-sensor behavior.
- **Contributes To**: Exit state 2 — live sensor has a seeded host-owned env/config contract consumed by the packaged unit and a direct startup path that does not depend on `bash -lc`.
- **Creates**: a live-sensor env template, updated unit wiring, and a normal path for setting interface/dumpcap/extractor/runtime outputs without manual service edits or shell-tokenization drift.
- **Unlocks**: Story 3 can make the replacement extractor default against a stable exact-path startup seam.
- **Done Looks Like**: ordinary host-specific live-sensor changes happen through the seeded env contract instead of drop-ins, unit edits, or shell wrapper surgery.
- **Candidate Bead Themes**:
  - env template + `EnvironmentFile` wiring
  - direct startup contract and shell-wrapper removal/containment

### Story 3: Exact packaged replacement extractor default

- **What Happens In This Story**: the packaged replacement extractor becomes one exact helper path for the default live-sensor startup path and its startup/argument contract is pinned end-to-end.
- **Why Now**: This closes the biggest setup pain only after the service has a proper direct startup contract to carry it.
- **Contributes To**: Exit state 3 — the packaged default extractor path is the replacement extractor exact helper path and startup semantics are pinned by verification.
- **Creates**: the packaged default extractor contract and contract-level verification of exact-path startup parity.
- **Unlocks**: Phase 2 can automate shipped-bundle activation on top of a stable preflight/runtime path.
- **Done Looks Like**: a fresh `full-stack` install no longer assumes CICFlowMeter as the normal path, and the packaged replacement extractor helper path is a tested contract.
- **Candidate Bead Themes**:
  - packaged default extractor helper path / wrapper ownership
  - env-file to preflight to daemon regression proof

---

## 4. Story Order Check

- [x] Story 1 is obviously first
- [x] Every later story builds on or de-risks an earlier story
- [x] If every story reaches "Done Looks Like", the phase exit state should be true

---

## 5. Story-To-Bead Mapping

> Fill this in after bead creation so validating and swarming can see how the narrative maps to executable work.

| Story | Beads | Notes |
|-------|-------|-------|
| Story 1: Explicit install modes | `ids_ml_new-1u8h.1`, `ids_ml_new-1u8h.2` | `.1` owns the installer mode contract; `.2` pins proof so the mode story cannot drift silently. |
| Story 2: Exact live-sensor startup contract | `ids_ml_new-1u8h.3`, `ids_ml_new-1u8h.4` | `.3` creates the env-file/unit seam; `.4` removes shell-sensitive startup drift so that seam becomes the real deploy contract. |
| Story 3: Exact packaged replacement extractor default | `ids_ml_new-1u8h.5` | Depends on the direct startup seam so the default extractor is pinned on top of the real deploy contract. |
