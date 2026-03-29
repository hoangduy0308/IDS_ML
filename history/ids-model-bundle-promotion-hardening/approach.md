# Approach: IDS Model Bundle Promotion Hardening

**Date**: 2026-03-29
**Feature**: ids-model-bundle-promotion-hardening
**Based on**:
- `history/ids-model-bundle-promotion-hardening/discovery.md`
- `history/ids-model-bundle-promotion-hardening/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Bundle manifest | `artifacts/final_model/catboost_full_data_v1/model_bundle.json` with model/schema/threshold metadata | Versioned production contract with compatibility metadata and lifecycle-aware provenance | Medium |
| Active bundle resolution | Optional `bundle_root` plus separate raw `model_path`, `feature_columns_path`, and `threshold` overrides in runtime CLIs | One canonical activation contract and one resolver used by runtime, preflight, and operator workflows | High |
| Promotion / rollback workflow | None for model bundles | Explicit same-host operator commands for verify, promote, activate, and rollback | High |
| Runtime + preflight wiring | `ids_live_sensor.py`, `ids_live_sensor_preflight.py`, and systemd unit use separate model/schema env vars | Fail-closed activation-aware startup, compatibility gating, and exact-path deploy parity | High |
| Operator visibility | Dashboard and readiness expose generic sensor health only | Active bundle identity, promoted/activated timestamp, compatibility state, rollback target, and blocked/healthy status | Medium |
| Runbooks / restore contract | Existing sensor/console operations docs and console backup/restore patterns | Same-host promote/rollback and restore guidance aligned to the active-bundle contract | Medium |

---

## 2. Recommended Approach

Introduce a dedicated model-bundle lifecycle layer that sits between bundle packaging and runtime consumption. This layer should define a versioned manifest schema plus a host-local activation state contract, then expose explicit operator commands to verify a candidate bundle, atomically activate it, and roll back to the last known-good bundle without relying on startup-side mutation. Runtime, preflight, and systemd wiring should stop accepting independent model/schema/threshold paths in production mode and instead resolve the active bundle through that lifecycle layer. Finally, the live sensor summary path and operator console should surface the resolved active bundle metadata so operators can see exactly what is live, what changed, and whether the runtime is blocked on compatibility.

### Why This Approach

- It follows the repo’s explicit mutation pattern from `scripts/ids_operator_console_manage.py` and honors locked decision `D3`.
- It removes the known drift seam in `scripts/ids_live_sensor.py` and `deploy/systemd/ids-live-sensor.service`, honoring `D5`, `D7`, and the exact-path preflight learnings.
- It reuses repo-native transactional filesystem promotion patterns rather than introducing a new storage service or dependency, honoring `D6` and the rollback safety learning.
- It uses the existing summary ingest/dashboard path for visibility, which keeps the feature within the same-host topology locked by `D1`, `D12`, and `D13`.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Bundle lifecycle module | Add a dedicated Python module for manifest validation, compatibility checks, active-bundle resolution, and activation state I/O | Keeps lifecycle rules centralized instead of re-encoding them across runtime, preflight, and CLI entrypoints |
| Activation state | Use a small host-local activation record/current pointer updated via atomic replace, plus previous-known-good metadata for rollback | Preserves provenance and rollback target while staying within safe rename/replace semantics |
| Operator mutation surface | Add explicit bundle-management CLI commands rather than hiding mutation inside runtime startup or the web UI | Matches the repo’s verify-vs-mutate split and keeps operator behavior auditable |
| Runtime contract | Production runtime/preflight resolve only the active bundle contract; ad hoc path mixing is removed or quarantined to non-production/dev-only code paths | Closes the exact drift seam identified during discovery |
| Visibility path | Publish active bundle metadata in live sensor summaries, reflect compatibility in readiness, and render the same data in the operator console dashboard | Reuses the existing JSONL -> ingest -> SQLite -> dashboard path instead of creating a separate control plane |

---

## 3. Alternatives Considered

### Option A: Keep path-based runtime wiring and document manual promotion

- Description: Continue using `MODEL_PATH`, `FEATURE_COLUMNS_PATH`, and threshold/path flags; rely on docs and operator discipline to keep them aligned.
- Why considered: Minimal code churn and matches the current deployed shape.
- Why rejected: It leaves the main production gap untouched because the runtime can still mix incompatible model/schema/config inputs, and there is no safe rollback contract.

### Option B: Put active bundle state in the operator console database

- Description: Store active bundle selection and rollback metadata in SQLite and have the sensor/runtime query that state.
- Why considered: The console already has persistent state, health, and operator workflows.
- Why rejected: It would make the sensor runtime depend on the console’s DB/service boundary for core scoring behavior, which violates the current same-host topology and couples runtime activation to an adjacent subsystem it does not need.

### Option C: Symlink-only switching with no activation journal

- Description: Maintain only a `current` symlink/directory pointer and infer rollback from filesystem layout.
- Why considered: Simple operator mental model and a common local deployment pattern.
- Why rejected: A pointer alone does not capture promoted-at time, compatibility verification result, previous-known-good target, or restore semantics cleanly enough for `D10`, `D12`, `D14`, and review-grade observability.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Versioned manifest + compatibility validator | **HIGH** | Core contract change with blast radius across packaging, runtime loading, and tests | Validating spike on manifest shape and compatibility failure matrix |
| Active bundle activation state + rollback primitives | **HIGH** | Filesystem safety-critical, rollback-sensitive, and must honor no-copy-fallback behavior | Validating spike on atomic activation/rollback semantics |
| Bundle management CLI | **MEDIUM** | New command surface but follows existing manage-script pattern | Command-level tests and dry-run/promote/rollback verification |
| Live sensor runtime + preflight + systemd wiring | **HIGH** | Blast radius > 5 files and a production entrypoint seam that must fail closed | Validation of runtime/preflight parity and readiness failure modes |
| Summary telemetry + operator readiness/dashboard visibility | **MEDIUM** | Reuses existing paths but spans sink, ingest, health, web, and templates | EXISTS / SUBSTANTIVE / WIRED review plus targeted web/ingest tests |
| Ops docs + restore contract updates | **MEDIUM** | Must stay aligned with the real implementation across promotion, rollback, and restore | Docs/runbook review against implemented command and readiness contract |

### Risk Classification Reference

```
Pattern in codebase?        → YES = LOW base
External dependency?        → YES = HIGH
Blast radius > 5 files?     → YES = HIGH
Otherwise                   → MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `Versioned manifest + compatibility validator`: validate the exact manifest shape and confirm mismatch cases fail closed without breaking current bundle packaging.
- `Active bundle activation state + rollback primitives`: validate that activation/rollback can be done atomically with no copy-based restore fallback and with correct previous-known-good tracking.
- `Live sensor runtime + preflight + systemd wiring`: validate that production runtime, preflight, and deploy artifacts all consume the same active-bundle contract and surface compatibility failures consistently.

---

## 5. Proposed File Structure

```text
scripts/
  ids_model_bundle.py                 # New canonical manifest + compatibility + active-state resolver
  ids_model_bundle_manage.py          # New explicit operator CLI for verify/promote/rollback/status
  ids_inference.py                    # Tightened around canonical bundle contract
  package_final_model.py              # Emits versioned manifest metadata
  ids_live_sensor.py                  # Resolves active bundle instead of mixed raw paths
  ids_live_sensor_preflight.py        # Activation-aware compatibility preflight
  ids_live_sensor_sinks.py            # Publishes active-bundle summary metadata
  ids_operator_console_manage.py      # Optional integration point if shared smoke helpers are reused
  ids_operator_console/
    health.py                         # Readiness includes active-bundle compatibility state
    web.py                            # Dashboard surfaces active bundle metadata
    templates/dashboard.html          # Visibility UI for active bundle / rollback target
tests/
  test_ids_model_bundle.py            # New manifest/activation/rollback tests
  test_ids_model_bundle_manage.py     # New CLI workflow tests
  test_ids_inference.py               # Updated config-resolution tests
  test_ids_live_sensor_preflight.py   # Updated preflight contract tests
  test_ids_live_sensor.py             # Updated runtime wiring tests
  test_ids_live_sensor_sinks.py       # Summary payload visibility tests
  test_ids_operator_console_ingest.py # Summary ingest visibility tests
  test_ids_operator_console_web.py    # Dashboard/readiness visibility tests
deploy/systemd/
  ids-live-sensor.service             # Active bundle contract wiring
docs/
  final_model_bundle.md               # Versioned manifest / active bundle contract
  ids_live_sensor_operations.md       # Promote/rollback runbook
  ids_operator_console_operations.md  # Visibility + restore implications
```

---

## 6. Dependency Order

```text
Layer 1: Bundle contract + activation primitives
Layer 2: Explicit manage CLI on top of Layer 1
Layer 3: Runtime/preflight/systemd wiring on top of Layer 1
Layer 4: Summary/readiness/dashboard visibility on top of Layer 3
Layer 5: Ops docs and full verification on top of Layers 2-4
```

### Parallelizable Groups

- Group A: `Implement versioned bundle contract and active-state resolver` — foundational, no dependency on other new beads.
- Group B: `Add explicit promote/rollback manage CLI` and `Wire live sensor runtime/preflight to active bundle contract` — both depend on Group A, but can proceed in parallel after the contract exists.
- Group C: `Surface active bundle visibility in summaries and operator console` — depends on runtime wiring from Group B.
- Group D: `Update docs and regression coverage for promotion/rollback lifecycle` — depends on Groups B and C so docs match the implemented contract.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260328-adapter-rollback-contract.md` | Rollback must stay on atomic replace semantics; no copy fallback | Activation state and rollback are planned around staged state + atomic replace only |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | One exact-path config source and one preflight contract reduce deployment drift | Runtime, preflight, and systemd will resolve the same active bundle contract rather than separate env vars |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | EXISTS / SUBSTANTIVE / WIRED catches integration drift | Visibility work is planned as sink + ingest + readiness + dashboard wiring, not just UI text |
| `history/learnings/20260329-operator-console-production-hardening.md` | Runtime verify-only and explicit operator mutation paths are safer | Promote/activate/rollback are placed in explicit management commands, not runtime startup |

---

## 8. Open Questions for Validating

- [ ] Does the chosen activation-state design preserve safe rollback semantics under interrupted or failed activation without introducing stale-pointer edge cases? — If wrong, production rollback may be unsafe or ambiguous.
- [ ] Is evolving `model_bundle.json` in place enough, or does backward-compatible dual-manifest reading reduce migration risk materially? — If wrong, upgrade compatibility may break current bundle consumers.
- [ ] What candidate input source gives the highest-confidence same-host smoke or dry-run verification without expanding into a new replay/fleet system? — If wrong, promotion may look safe without exercising the real contract.
