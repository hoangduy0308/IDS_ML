# IDS Model Bundle Promotion Hardening — Context

**Feature slug:** ids-model-bundle-promotion-hardening
**Date:** 2026-03-29
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature hardens the single-host lifecycle of the existing IDS model bundle so operators can safely verify, promote, activate, observe, and roll back bundle changes without expanding into retraining or fleet orchestration.

**Domain type(s):** SEE | CALL | RUN | READ | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Scope Boundary
- **D1** The deployment target remains one Linux host with same-host artifacts and services only; this feature must not introduce fleet rollout, remote control-plane coordination, or multi-host state management.
  *Rationale: The user explicitly limited this feature to the current single-host production topology.*

- **D2** The feature hardens the lifecycle of the already-selected `CatBoost full-data` bundle only. It does not add retraining orchestration, online learning, model selection workflows, or new training artifacts.
  *Rationale: The production gap is lifecycle safety around the finalized bundle, not model creation.*

- **D3** Normal runtime startup stays verify-only. Any promotion, activation, rollback, bootstrap, or recovery that mutates active-model state must happen through explicit operator commands/workflows rather than implicit startup behavior.
  *Rationale: This follows the production-hardening pattern already established for the operator console.*

### Bundle Contract And Compatibility
- **D4** The active model bundle contract becomes versioned and self-describing. The manifest must declare the model artifact, feature schema, threshold/inference settings, provenance, and compatibility metadata needed to prove the bundle matches the runtime’s current feature schema and inference contract.

- **D5** Feature schema, threshold, and any runtime values that change inference semantics travel with the bundle and activate as one unit. Production execution must not mix a candidate `bundle_root` with an external `feature_columns_path`, raw `model_path`, or ad hoc threshold override.
  *Rationale: The current runtime wiring can mix bundle A with schema/config B, which is exactly the class of drift this feature must close.*

- **D6** Active bundle selection uses one host-local activation record/pointer that can be updated atomically with `replace`-style filesystem operations. The design must not depend on copy-based directory rewrites or rollback-by-copy fallbacks.
  *Rationale: Critical learnings already established that copy-based rollback is unsafe; activation must preserve that lesson.*

- **D7** The production runtime and preflight path resolve the active bundle only through the canonical activation contract. If the resolved bundle is missing or incompatible, startup/readiness must fail closed instead of silently falling back to static default paths.

### Promotion, Activation, And Rollback
- **D8** Promotion is an explicit operator flow with at least these stages: candidate selection, compatibility/preflight verification, dry-run or smoke verification on the same host, then activation.

- **D9** Activation is safe-first. A failed compatibility check or failed cutover must leave the previously active known-good bundle in place, or restore it via the same atomic activation mechanism before the system is considered ready again.

- **D10** Rollback targets the immediately previous known-good bundle recorded at promotion time. Rollback is an explicit, supported operator path, not an ad hoc manual repair procedure.

- **D11** The verification mode for a candidate bundle is same-host only. This feature may use smoke, dry-run, or shadow-style checks locally, but it must not expand into multi-host canary rollout or external control-plane orchestration.

### Visibility, Operations, And Acceptance
- **D12** The operator console surface added by this feature is visibility-first, not mutation-first. It must show the active bundle identity/version, activation or promotion timestamp, compatibility/health state, and the rollback target, while promote/rollback actions remain explicit CLI/runbook operations.

- **D13** Runtime telemetry/readiness outputs must publish active-bundle identity and compatibility state so operators can see which bundle is live and why the runtime is ready or blocked.

- **D14** Backup/restore and same-host runbooks must include the active-bundle metadata/pointer contract. After restore, the system must re-validate the resolved active bundle before declaring readiness.

- **D15** The feature is not done unless automated verification proves: compatibility validation rejects mismatched bundle/runtime inputs, promote/activate succeeds for a valid bundle, rollback succeeds back to a known-good bundle, and the chosen smoke/dry-run verification is wired into the operator flow.

- **D16** The feature is not done unless operator-facing visibility is substantively wired: readiness/health and operator console surfaces expose the active bundle state, and documentation/runbooks describe the same promote/rollback contract actually implemented.

### Agent's Discretion
- The exact filename and on-disk layout of the versioned manifest may evolve from `model_bundle.json` or be introduced as a backward-compatible successor, as long as D4-D7 remain true.
- The exact host-local location of the activation record/pointer may be chosen during planning, as long as it is compatible with the same-host Linux deployment and backup/restore flow.
- The exact implementation surface for operator mutation may be an existing management CLI or a new dedicated helper, as long as runtime startup remains verify-only and console mutation stays out of scope.

---

## Specific Ideas & References

- The existing finalized bundle at `artifacts/final_model/catboost_full_data_v1` is the seed input, not a throwaway prototype.
- The user explicitly wants exploration and hardening around these missing capabilities:
  - versioned model bundle contract
  - compatibility checks between bundle, feature schema, runtime config, and inference contract
  - safe promote/activate/rollback
  - preflight before activation
  - smoke/dry-run/shadow verification for new bundles
  - active model visibility in the operator console
  - same-host runbook and observability for model changes
- Candidate implementation seams already named by the user and preserved for planning:
  - atomic active pointer/activation record instead of manual path edits
  - threshold/config versioning bundled with the model
  - startup behavior when the active bundle is incompatible
  - backup/restore interaction with active bundle metadata

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `scripts/ids_inference.py` — current bundle loading, feature alignment, scoring, and CLI summary path. It already has `IDSModelConfig.from_bundle(...)`, but it still supports mixing bundle, raw model path, raw feature path, and threshold overrides.
- `scripts/package_final_model.py` — current bundle packager that emits `model_bundle.json`, `feature_columns.json`, `metrics.json`, and `training_summary.json`. This is the natural starting point for a versioned manifest contract.
- `scripts/ids_feature_contract.py` — existing feature-schema validation boundary used by the realtime path. It reinforces the fail-closed rule on missing/non-numeric canonical features.
- `scripts/ids_realtime_pipeline.py` — current micro-batch runtime around `IDSInferencer`; it already distinguishes model predictions from `schema_anomaly` events.
- `scripts/ids_live_sensor.py` — current daemon wiring. Today it constructs `FlowFeatureContract.from_feature_file(config.feature_columns_path)` separately from `build_inferencer(bundle_root=..., model_path=..., feature_columns_path=..., threshold=...)`, which permits semantic drift.
- `scripts/ids_live_sensor_preflight.py` — current systemd preflight gate. It validates separate `model_path` and `feature_columns_path`, not a single active bundle compatibility contract.
- `scripts/ids_live_sensor_sinks.py` — durable summary/output channel. Its summary payload can carry more runtime metadata and already feeds journald + JSONL.
- `scripts/ids_operator_console/db.py` — summaries are stored as arbitrary JSON payloads keyed by timestamp, so active-bundle visibility can flow through existing ingest/storage patterns.
- `scripts/ids_operator_console/web.py` — dashboard and readiness surface already read latest summary payloads and expose runtime health.
- `scripts/ids_operator_console/templates/dashboard.html` — current dashboard shows health/alerts/anomalies only; there is no active-model visibility yet.
- `deploy/systemd/ids-live-sensor.service` — deployment artifact currently pins separate env vars for `MODEL_PATH` and `FEATURE_COLUMNS_PATH`; planning must close that seam.

### Established Patterns
- Fail closed on schema/contract mismatch: `docs/ids_inference_architecture.md`, `docs/ids_realtime_pipeline_architecture.md`, and `scripts/ids_feature_contract.py`.
- Runtime verify-only, operator mutation explicit: `docs/ids_operator_console_architecture.md`, `docs/ids_operator_console_operations.md`, and `history/learnings/20260329-operator-console-production-hardening.md`.
- No copy-based rollback fallback on filesystem state changes: `history/learnings/critical-patterns.md`.
- Operator visibility via durable summary payloads rather than a separate control plane: `scripts/ids_live_sensor_sinks.py`, `scripts/ids_operator_console/ingest.py`, and `scripts/ids_operator_console/web.py`.

### Integration Points
- `scripts/ids_inference.py` — tighten `IDSModelConfig` / `build_model_config` around a canonical production bundle contract.
- `scripts/ids_live_sensor.py` — switch runtime activation from independent model/schema inputs to active bundle resolution.
- `scripts/ids_live_sensor_preflight.py` — extend preflight from file existence checks to compatibility-aware activation gating.
- `deploy/systemd/ids-live-sensor.service` — align deployment env + `ExecStartPre` + `ExecStart` with the same active bundle contract.
- `scripts/ids_live_sensor_sinks.py` — publish active bundle metadata into summary telemetry.
- `scripts/ids_operator_console/web.py` and `scripts/ids_operator_console/templates/dashboard.html` — show active bundle visibility and blocked/healthy compatibility state.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `docs/final_model_decision.md` — locked final model and operating threshold.
- `docs/final_model_bundle.md` — current finalized bundle shape and intended role in inference/realtime paths.
- `docs/ids_inference_architecture.md` — inference boundary and fail-closed schema expectations.
- `docs/ids_realtime_pipeline_architecture.md` — realtime contract around bundle-backed scoring and schema anomalies.
- `docs/ids_live_sensor_architecture.md` — same-host live-sensor runtime shape and local-output contract.
- `docs/ids_live_sensor_operations.md` — same-host systemd/preflight operating model.
- `docs/ids_operator_console_architecture.md` — operator-console hardening boundary and verify-only startup pattern.
- `docs/ids_operator_console_operations.md` — same-host operator runbook patterns to mirror.
- `history/learnings/critical-patterns.md` — promoted critical patterns, especially filesystem rollback and verify-before-swarming lessons.
- `history/learnings/20260328-live-sensor-runtime-contracts.md` — exact-path preflight and durable runtime-output patterns.
- `history/learnings/20260328-operator-console-runtime-wiring.md` — EXISTS / SUBSTANTIVE / WIRED review standard for service wiring.
- `history/learnings/20260329-operator-console-production-hardening.md` — explicit runtime verification vs operator mutation split.
- `artifacts/final_model/catboost_full_data_v1/model_bundle.json` — current bundle manifest baseline that planning will harden/version.

---

## Outstanding Questions

### Resolve Before Planning

None. The feature brief and existing system docs are sufficient to begin planning without another product-level clarification round.

### Deferred to Planning

- [ ] Should the versioned compatibility metadata live inside an evolved `model_bundle.json`, or in a successor manifest file with a compatibility shim? — This is an implementation research question about migration shape, not product scope.
- [ ] What exact host-local path should own the active bundle pointer/activation journal for the Linux deployment? — Planning should evaluate the current systemd/state-directory conventions and backup/restore flow.
- [ ] Which explicit operator entrypoint should own promote/activate/rollback? — Planning should choose whether to extend an existing management script or introduce a dedicated helper while keeping runtime verify-only.
- [ ] What concrete smoke/dry-run/shadow input source is safest for candidate bundle verification on one host? — Planning should choose a verifiable source that exercises the real contract without inventing a new rollout system.
- [ ] Which readiness/summary fields best express compatibility failure to operators? — Planning should align preflight, runtime telemetry, and console wording so they expose one consistent active-bundle health model.

---

## Definition Of Done

- A versioned bundle manifest/contract exists and is the canonical production source for model, feature schema, threshold/config, and compatibility metadata.
- Production runtime/preflight can resolve exactly one active bundle contract and fail closed on incompatibility.
- Operators have an explicit promote/activate workflow with preflight plus smoke/dry-run verification before cutover.
- Operators have an explicit rollback path to the last known-good bundle using the same activation contract.
- Runtime telemetry and readiness surfaces expose the active bundle identity and compatibility state.
- Operator console visibly shows active bundle/version, activation timestamp, compatibility/health state, and rollback target.
- Same-host docs/runbooks describe the real operational contract for promote/rollback and backup/restore.
- Verification proves compatibility validation, promote/activate, rollback, chosen smoke/dry-run path, and console wiring.

---

## Deferred Ideas

- Multi-host rollout, canarying, or a central model control plane — explicitly out of scope for this feature.
- Retraining orchestration, model registry expansion for training workflows, or online learning — separate future work.
- Console-driven mutation UI for promote/rollback — deferred in favor of explicit operator commands plus read-only visibility.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
