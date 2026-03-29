# Validation: IDS Model Bundle Promotion Hardening

**Date:** 2026-03-29
**Feature:** ids-model-bundle-promotion-hardening
**Phase:** validating

---

## Phase 1: Plan Verification

### Iteration 1

`DIMENSION 1 — Requirement Coverage: PASS`
- Locked decisions D1-D16 map to the bead set. The coverage is distributed across foundational contract work (`ids_ml_new-hup.1`), operator mutation (`ids_ml_new-hup.2`), runtime/preflight wiring (`ids_ml_new-hup.3`), visibility (`ids_ml_new-hup.4`), and docs/regression (`ids_ml_new-hup.5`).

`DIMENSION 2 — Dependency Correctness: PASS`
- `br show` and `bv --robot-insights` confirm a DAG with no cycles. The critical path is `ids_ml_new-hup.1 -> ids_ml_new-hup.3 -> ids_ml_new-hup.4 -> ids_ml_new-hup.5 -> ids_ml_new-hup`.

`DIMENSION 3 — File Scope Isolation: PASS`
- The only overlapping file scopes are intentionally sequenced by dependencies: `ids_ml_new-hup.2` depends on `.1` for shared lifecycle files, and `ids_ml_new-hup.5` depends on `.2/.3/.4` for shared test/docs surfaces.

`DIMENSION 4 — Context Budget: PASS`
- Each bead remains bounded to one concern layer and a manageable file set. None requires cross-cutting implementation over too many subsystems at once.

`DIMENSION 5 — Test Coverage: PASS`
- Every implementation bead carries explicit verification criteria covering compatibility, promote/rollback, runtime/preflight failure modes, visibility wiring, or docs/regression checks.

`DIMENSION 6 — Gap Detection: PASS`
- Completing the five implementation beads would deliver the requested single-host lifecycle hardening without drifting into retraining or multi-host rollout.

`DIMENSION 7 — Risk Alignment: FAIL`
- `approach.md` identified three HIGH-risk items, but no spike beads existed yet for manifest evolution, atomic activation/rollback semantics, or runtime/preflight/systemd contract parity.

`DIMENSION 8 — Completeness: PASS`
- Aside from missing spike proof for HIGH-risk assumptions, the bead set is structurally complete for the feature boundary locked in `CONTEXT.md`.

### Iteration 2

Result after adding and closing spike beads `ids_ml_new-tz9`, `ids_ml_new-a8t`, and `ids_ml_new-d85`: all 8 dimensions PASS.

---

## Phase 2: Spike Execution

HIGH-risk items from `approach.md` were validated with definitive YES/NO spikes:

- `ids_ml_new-tz9`: YES — evolve `model_bundle.json` in place into a versioned compatibility contract.
- `ids_ml_new-a8t`: YES — use atomic activation record + previous-known-good tracking; no copy-based restore fallback.
- `ids_ml_new-d85`: YES — runtime, preflight, and systemd can converge on one active-bundle contract and fail closed consistently.

Spike findings were written under:

- `.spikes/ids-model-bundle-promotion-hardening/ids_ml_new-tz9/FINDINGS.md`
- `.spikes/ids-model-bundle-promotion-hardening/ids_ml_new-a8t/FINDINGS.md`
- `.spikes/ids-model-bundle-promotion-hardening/ids_ml_new-d85/FINDINGS.md`

The validated constraints were then embedded into the affected implementation beads as execution notes.

---

## Phase 3: Bead Polishing

### Round 1: Dependency Completeness

- Reviewed `bv --robot-suggest`.
- Rejected the suggested dependency `ids_ml_new-hup.3 -> ids_ml_new-hup.2` because runtime wiring and CLI work are intentionally parallel after `.1`.
- Rejected the extra `.4 -> .1` and `.5 -> .1` suggestions as already satisfied transitively through the planned chain.
- Ignored duplicate noise from unrelated closed features outside this epic.

### Round 2: Graph Health

- `bv --robot-insights` reports no cycles.
- `ids_ml_new-hup.1` remains the keystone bead and the only actionable start point, which matches the intended execution order.
- No critical graph-health defects remain for this epic.

### Round 3: Priority Sanity

- Reviewed `bv --robot-priority`.
- Kept current priorities because `.1/.2/.3` are intentionally high-priority critical-path work and `.4/.5` remain downstream medium-priority execution.

### Fresh-Eyes Review

- No blocking bead-readability defects remain after spike constraints were embedded into notes.
- The main ambiguity from planning — manifest migration shape, activation-state semantics, and single-source runtime/preflight contract — is now explicitly resolved for executors.

---

## Validation Outcome

Validation passes.

- Plan verification: PASS after 2 iterations
- HIGH-risk spikes: 3/3 PASS
- Bead graph: clean for execution
- Execution is still blocked on Gate 2 user approval per workflow
