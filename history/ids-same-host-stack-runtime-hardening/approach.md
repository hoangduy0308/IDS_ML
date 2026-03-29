# Approach: IDS Same-Host Stack Runtime Hardening

**Date**: 2026-03-29
**Feature**: `ids-same-host-stack-runtime-hardening`
**Based on**:
- `history/ids-same-host-stack-runtime-hardening/discovery.md`
- `history/ids-same-host-stack-runtime-hardening/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Model activation lifecycle | `scripts/ids_model_bundle_manage.py` with `status|verify|promote|rollback` and tests | Stack-level reuse of activation status/preflight without reintroducing split model selection | Small — compose existing surface |
| Live sensor deploy gate | `scripts/ids_live_sensor_preflight.py`, `deploy/systemd/ids-live-sensor.service`, daemon tests | Canonical stack-visible sensor health/status seam beyond one-shot preflight | Medium — add read-only health evidence seam |
| Operator console runtime/ops | `scripts/ids_operator_console_manage.py`, `scripts/ids_operator_console_preflight.py`, smoke/readiness/backup/restore tests | Stack-level composition of existing status/smoke/restore verification | Small — compose existing surface |
| Notification worker runtime | `notify-status`, `notify-worker`, `notify-redrive`, tested readiness semantics | Stack-level gating when enabled and explicit `disabled` semantics when not enabled | Small — compose existing surface |
| Reverse proxy seam | `deploy/nginx/ids-operator-console.conf.example`, proxy-aware runtime config | Optional production-facing proxy seam check that remains non-gating | Medium — add bounded verification hook |
| Whole-stack orchestration | No stack-level bootstrap/preflight/smoke/recovery artifact exists today | One canonical thin orchestrator + tests + runbooks matching shipped commands | New — architectural integration layer |
| Stack runbooks | Component-level docs exist for sensor, bundle, console, notifications | Stack-level fresh bootstrap, recovery, backup/restore, degraded-diagnosis runbooks | New — documentation integration layer |

---

## 2. Recommended Approach

Implement the feature as a thin Python orchestration layer centered on a new stack management CLI plus one narrow read-only sensor health seam, while keeping all mutation and runtime ownership inside the existing component-specific commands and systemd units. The stack layer should expose canonical `preflight`, `status`, `smoke`, and `post-restore-check` commands that aggregate machine-readable results for model activation, live sensor, operator console, notification worker, and optional reverse proxy. Where a component already has a tested contract, the stack layer should call it directly; where the repo lacks a testable runtime health surface today, add the smallest read-only helper necessary in that component domain instead of teaching the stack manager to infer state from ad hoc heuristics. The same feature should ship stack runbooks and deploy references that point to the new canonical commands, so review can verify `EXISTS / SUBSTANTIVE / WIRED` at the whole-system level rather than only at individual services.

### Why This Approach

- It matches the existing repo pattern of thin management CLIs over explicit domain helpers, as seen in `scripts/ids_model_bundle_manage.py` and `scripts/ids_operator_console_manage.py`.
- It honors locked decisions D1-D3 from `CONTEXT.md` by making the stack layer a coordinator rather than a new owner of model, sensor, console, or notification mutation logic.
- It preserves verify-only startup and explicit operator mutation flows, which is the core production-hardening lesson from `history/learnings/20260329-operator-console-production-hardening.md`.
- It gives reviewing one canonical host-level artifact surface to inspect, without undoing the component-level contracts already hardened in prior features.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Stack orchestration surface | Add `scripts/ids_same_host_stack_manage.py` backed by a small helper module | Matches existing CLI pattern and keeps stack semantics in one testable place |
| Sensor runtime evidence | Add a read-only sensor status helper that reports activation state plus latest durable summary evidence without mutating runtime state | Current repo has preflight but no canonical runtime status seam; stack manager should not guess from raw files alone |
| Bundle integration | Reuse `build_bundle_status_payload()` and existing activation-record semantics directly | Honors D5 and the one-activation-contract rule from prior learnings |
| Console integration | Reuse `ids_operator_console_manage.py smoke|notify-status|notify-redrive` and `ids_operator_console_preflight.py` | Existing machine-readable surfaces are already tested and aligned with deploy docs |
| Proxy integration | Add optional, non-gating seam verification driven by explicit config/input, not implicit probing | Honors D6 and avoids making proxy health indistinguishable from internal runtime health |
| Restore posture | Keep restore mutations owned by existing bundle/console flows; let the stack layer orchestrate verification and ordering around them | Preserves D12-D15 and avoids a broad new mutation owner at stack level |

---

## 3. Alternatives Considered

### Option A: Documentation-only stack contract

- Description: keep per-service commands as-is and only add a stack-level runbook describing order.
- Why considered: lowest implementation cost and no new code surfaces.
- Why rejected: fails the feature’s core gap. It leaves bootstrap/preflight/smoke/recovery fragmented across docs only and makes `WIRED` verification at stack level weak.

### Option B: Heavy stack manager that owns bootstrap, restore, and service control end to end

- Description: build one broad stack controller that performs mutations, service control, and all checks itself.
- Why considered: seemingly gives one-stop operator UX.
- Why rejected: violates locked decisions D1-D3, blurs failure domains, and risks turning the feature into a mini control-plane.

### Option C: Stack manager with no new sensor health seam

- Description: compose existing bundle/console/notification contracts and approximate sensor runtime health from activation status plus static paths only.
- Why considered: minimizes new component code.
- Why rejected: too weak for real stack smoke/status. Preflight plus activation status does not prove the live sensor runtime is actually healthy enough for the stack contract the user asked for.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Stack manager CLI and aggregator module | **MEDIUM** | New artifact, but follows strong existing `*_manage.py` CLI pattern | Unit tests for command payloads and composition flow |
| Live sensor read-only runtime status seam | **HIGH** | No existing canonical runtime status surface; wrong choice could invent a fake health source or blur runtime ownership | Spike in validating to prove the chosen seam is durable, testable, and non-misleading |
| Stack preflight composition | **LOW** | Existing exact-path preflight contracts already exist for sensor and console | Reuse tests plus stack-level composition tests |
| Stack smoke/status composition | **MEDIUM** | New aggregation logic across multiple domains and gating semantics | Unit tests for enabled/disabled/degraded combinations |
| Reverse proxy seam check | **MEDIUM** | Optional edge verification with no current canonical implementation | Validate optional/non-gating behavior and config-driven invocation |
| Stack recovery/post-restore verification | **HIGH** | Crosses activation record, console restore, notification redrive, and summary-backed visibility; easy place for partial integration drift | Spike in validating to prove post-restore story and ownership boundaries are coherent |
| Stack runbooks/docs | **LOW** | Built from existing operations docs and locked decisions | Review for doc/artifact wiring consistency |
| Bead decomposition / file scope | **HIGH** | This feature spans scripts, deploy, docs, and tests; poor slicing could create conflicting write scopes | Validating must check reservations/write-scope overlap before swarming |

### HIGH-Risk Summary (for khuym:validating skill)

- `live sensor runtime status seam`: What is the narrowest read-only source that proves real sensor runtime health for stack `status/smoke` without inventing a second source of truth or requiring systemd-only assumptions in unit tests?
- `stack recovery/post-restore verification`: Should stack-level restore support stay verification-first over existing commands, or is a thin wrapper justified without violating ownership boundaries?
- `bead decomposition / file scopes`: Do the proposed task slices keep write scopes disjoint enough for swarming, especially around shared stack-manager files and docs?

---

## 5. Decision Rationale

This approach buys correctness in the cheapest place: reuse every hardened component contract that already exists, and only add code where the stack contract has a genuine missing seam. It avoids the two main failure modes visible from prior work: integration drift caused by having no canonical runtime wiring, and ownership drift caused by teaching a new top-level tool to mutate or “own” component state that already has a tested contract elsewhere. The recommended plan therefore introduces one stack orchestration surface and one focused sensor health seam, then spends the rest of the effort wiring deploy artifacts, verification paths, and runbooks so the system can be bootstrapped, smoked, recovered, and reviewed as one same-host stack.

---

## 6. Proposed File Structure

```text
scripts/
  ids_same_host_stack.py              # New stack orchestration helpers / result dataclasses
  ids_same_host_stack_manage.py       # New canonical stack CLI
  ids_live_sensor_health.py           # New read-only live sensor status helper (or equivalent narrow helper)

deploy/
  systemd/
    ids-same-host-stack.env.example   # Optional sample stack env / contract reference if justified
  nginx/
    ids-operator-console.conf.example # Updated only if stack seam verification needs documented config inputs

docs/
  ids_same_host_stack_operations.md   # New stack bootstrap/smoke/recovery/restore runbook

tests/
  test_ids_same_host_stack_manage.py  # New stack CLI composition tests
  test_ids_live_sensor_health.py      # New sensor status seam tests
```

If validating disproves the need for a dedicated `ids_live_sensor_health.py`, collapse that file into a narrower helper while keeping the same read-only contract goals.

---

## 7. Dependency Order

```text
Layer 1: Sensor health seam + tests
Layer 2: Stack orchestration module/CLI + composition tests
Layer 3: Stack recovery/post-restore verification flow
Layer 4: Stack runbooks and deploy artifact updates
```

### Parallelizable Groups

- Group A: `Sensor health seam`, `Stack runbooks/deploy docs`
  - These can proceed in parallel if docs stay anchored to locked decisions and not to unfinished command names.
- Group B: `Stack orchestration module/CLI`
  - Depends on Group A’s sensor seam decision if a new helper is introduced.
- Group C: `Stack recovery/post-restore verification`
  - Depends on Group B because it shares the stack management surface and status/smoke payload model.

---

## 8. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Preflight must use exact absolute paths and runtime evidence must be durable | Stack preflight reuses exact-path contracts; sensor status seam must rely on durable evidence, not transient guesses |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | `EXISTS / SUBSTANTIVE / WIRED` must include deploy/runtime entrypoints | Plan includes one canonical stack CLI and runbooks so stack wiring becomes reviewable |
| `history/learnings/20260329-operator-console-production-hardening.md` | Keep runtime verification separate from mutation | Stack layer will orchestrate verification and ordering, not absorb migrate/bootstrap/restore mutations |
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | Production model selection must stay on one activation contract | Stack health and preflight reuse activation-record status directly rather than adding new model selection knobs |
| `history/learnings/20260329-notification-runtime-contracts.md` | Notification worker stays separate and restore verification must include redrive/status | Stack top-level health gates notification only when enabled, and post-restore verification includes notification status/redrive |

---

## 9. Open Questions for Validating

- [ ] Does the proposed live sensor status seam prove enough real runtime health for stack `status/smoke`, or does it still risk over-reporting health under no-traffic or stale-summary conditions?
- [ ] Is a dedicated stack wrapper for post-restore verification enough, or should validating force restore mutation steps to remain fully component-owned with the stack layer only checking outcomes?
- [ ] Are the proposed bead write scopes sufficiently disjoint to support safe swarming without shared edits to the same stack-manager files?
